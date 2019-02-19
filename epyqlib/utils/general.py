import collections
import enum
import inspect
import itertools
import logging
import math
import os
import pathlib
import shutil
import stat
import traceback
import textwrap
import time
import zipfile

import attr

__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'

logger = logging.getLogger()


class ExpectedException(Exception):
    def expected_message(self):
        return 'This is expected: {}'.format(str(self))


class UnmatchedSerialNumberError(Exception):
    pass


class Container:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


def multiparagraph_wrap(s, *args, **kwargs):
    paragraphs = s.split('\n\n')
    return '\n\n'.join(
        '\n'.join(textwrap.wrap(p, *args, **kwargs))
        for p in paragraphs
    )


@attr.s
class AverageValueRate:
    _seconds = attr.ib(converter=float)
    _deque = attr.ib(default=attr.Factory(collections.deque))

    @attr.s
    class Event:
        time = attr.ib()
        value = attr.ib()
        delta = attr.ib()

    def add(self, value):
        now = time.monotonic()

        if len(self._deque) > 0:
            delta = now - self._deque[-1].time

            cutoff_time = now - self._seconds

            while self._deque[0].time < cutoff_time:
                self._deque.popleft()
        else:
            delta = 0

        event = self.Event(time=now, value=value, delta=delta)
        self._deque.append(event)

    def rate(self):
        if len(self._deque) > 0:
            dv = self._deque[-1].value - self._deque[0].value
            dt = self._deque[-1].time - self._deque[0].time
        else:
            dv = -1
            dt = 0

        if dv <= 0:
            return 0
        elif dt == 0:
            return math.inf

        return dv / dt

    def remaining_time(self, final_value):
        rate = self.rate()
        if rate <= 0:
            return math.inf
        else:
            return (final_value - self._deque[-1].value) / rate


def write_device_to_zip(zip_path, epc_dir, referenced_files, code=None,
                        sha=None, checkout_dir=None):
    # TODO: stdlib zipfile can't create an encrypted .zip
    #       make a good solution that will...
    with zipfile.ZipFile(file=zip_path, mode='w') as zip:
        for device_path in referenced_files:
            filename = os.path.join(epc_dir, device_path)
            zip.write(filename=filename,
                      arcname=os.path.relpath(filename, start=epc_dir))

        if sha is not None:
            sha_file_name = 'sha'
            sha_file_path = os.path.join(checkout_dir, sha_file_name)
            with open(sha_file_path, 'w') as sha_file:
                sha_file.write(sha + '\n')
            zip.write(
                filename=sha_file_path,
                arcname=sha_file_name
            )


# https://docs.python.org/3/library/itertools.html
def pairwise(iterable):
    's -> (s0,s1), (s1,s2), (s2, s3), ...'
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


# https://docs.python.org/3/library/itertools.html
def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return itertools.zip_longest(*args, fillvalue=fillvalue)


def chunker(iterable, n, factory=tuple):
    """Collect data into fixed-length chunks or blocks except last due to
    lack of fill.
    """
    # chunker('ABCDEFG', 3) --> ABC DEF G"

    i = iter(iterable)
    r = range(n)

    while True:
        # t = factory(next(i) for _ in r)
        t = factory(v for _, v in zip(r, i))

        if len(t) > 0:
            yield t
        else:
            break


def generate_ranges(ids):
    try:
        start = ids[0]
    except IndexError:
        return

    for previous, next in pairwise(itertools.chain(ids, (None,))):
        if previous + 1 != next:
            yield (start, previous)

            start = next


@attr.s
class append_to_method:
    callable = attr.ib()
    name = attr.ib(default=None)

    def __attrs_post_init__(self):
        if self.name is None:
            self.name = self.callable.__name__

    def __call__(self, cls):
        old = getattr(cls, self.name, None)
        to_call = self.callable

        def f(s, *args, **kwargs):
            if old is not None:
                old(s, *args, **kwargs)

            to_call(s)

        setattr(cls, self.name, f)
        print('assigned {} to {}.{}'.format(f, cls.__name__, self.name))

        return cls


# Based on https://docs.python.org/3.5/library/enum.html#autonumber
class AutoNumberIntEnum(enum.IntEnum):
    def __new__(cls, value=None):
        if value is None:
            if len(cls.__members__) == 0:
                base = 0
            else:
                base = tuple(cls.__members__.values())[-1]
            value = base + 1

        obj = int.__new__(cls, value)
        obj._value_ = value
        return obj


def enumerated_attrs(enumeration, **kwargs):
    def inner(cls):
        for enumerator in enumeration:
            setattr(cls, enumerator.name, attr.ib(**kwargs))

        cls.enumeration = enumeration

        return cls
    return inner


class TextTable:
    def __init__(self, format_string=None):
        self.format = format_string
        self.rows = []
        self.widths = ()

    def append(self, *row):
        row = tuple(str(c) for c in row)
        self.rows.append(row)
        widths = tuple(len(c) for c in row)
        self.widths = tuple(
            max(a, b) for a, b
            in itertools.zip_longest(self.widths, widths, fillvalue=0)
        )

    def extend(self, rows):
        for row in rows:
            self.append(*row)

    def __str__(self):
        if len(self.rows) == 0:
            return ''

        f = self.format
        if f is None:
            f = ' '.join(('{{:{}}}',) * len(self.widths))

        f = f.format(*(max(w, 1) for w in self.widths))

        return '\n'.join((
            f.format(*(row + (('',) * (len(self.widths) - len(row)))))
            for row in self.rows
        ))


@attr.s
class Collector(list):
    cls = attr.ib()
    payload_attribute = attr.ib()

    def append(self, *args, **kwargs):
        s = super()

        def f(payload):
            payload_dict = {self.payload_attribute: payload}
            s.append(self.cls(
                *args,
                **kwargs,
                **{self.payload_attribute: payload},
            ))

            return payload

        return f


def exception_logger(excType, excValue, tracebackobj):
    logger.error('Uncaught exception hooked:\n{}'.format(
         ''.join(traceback.format_exception(excType, excValue, tracebackobj))
    ))


@attr.s
class TypeMap:
    types = attr.ib(default=attr.Factory(dict), init=False)

    def __call__(self, wrapped):
        def inner(cls):
            self.types[wrapped] = cls

            return cls

        return inner

    def __getitem__(self, item):
        return self.types[item]

    def wrap(self, wrapped, *args, **kwargs):
        return self.types[type(wrapped)](wrapped=wrapped, *args, **kwargs)


def spaced_to_camel(name, upper):
    segments = name.split(' ')

    if not upper:
        segments[0] = segments[0].lower()

    segments = itertools.chain(
        segments[:1],
        *(''.join(itertools.chain(
            c[:1].upper(), c[1:],
        )) for c in segments[1:]),
    )

    return ''.join(segments)


def spaced_to_lower_camel(name):
    return spaced_to_camel(name=name, upper=False)


def spaced_to_upper_camel(name):
    return spaced_to_camel(name=name, upper=True)


def underscored_to_upper_camel(name):
    return ''.join(w.title() for w in name.split('_'))


def underscored_camel_to_upper_camel(name):
    return ''.join(w[:1].upper() + w[1:] for w in name.split('_'))


def cameled_to_spaced(name):
    word_indexes = sorted(
        (0, len(name))
        + tuple(
            i
            for i, (c, next_c) in enumerate(pairwise(name))
            if c.isupper() and next_c.islower()
        )
        + tuple(
            i + 1
            for i, (prev_c, c) in enumerate(pairwise(name))
            if not prev_c.isupper() and c.isupper()
        )
    )

    words = (
        name[start:end]
        for start, end in pairwise(word_indexes)
        if end > start
    )

    return ' '.join(word.strip() for word in words).strip()


def underscored_camel_to_title_spaced(name):
    result = underscored_camel_to_upper_camel(name)
    result = cameled_to_spaced(result)

    return result


def identifier_path(it):
    return '__' + '_'.join(
        it.__module__.split('.') + [it.__qualname__]
    )


# TODO: CAMPid 0238493420143087667542054268097120437916848
# http://stackoverflow.com/a/21263493/228539
def del_rw(action, name, exc):
    os.chmod(name, stat.S_IWRITE)
    if os.path.isdir(name):
        os.rmdir(name)
    else:
        os.remove(name)


def rmtree(path, ignore_errors=False):
    try:
        shutil.rmtree(path, onerror=del_rw)
    except FileNotFoundError:
        if not ignore_errors:
            raise


def contiguous_groups(s):
    groups = []
    group = []

    for previous, current in pairwise(itertools.chain(s, (math.inf,))):
        group.append(previous)
        if current > previous + 1:
            groups.append(group)
            group = []

    return groups


def path_and_line(o):
    return '{}:{}'.format(
        inspect.getsourcefile(o),
        inspect.getsourcelines(o)[1],
    )


def intersect_dicts(a, b):
    common_keys = set(a).intersection(b)
    return {k: a[k] for k in common_keys}


# TODO: CAMPid 073407143081341008467657184603164130
def format_nested_lists(it, indent='    ', indentation=''):
    result = []

    for item in it:
        if isinstance(item, list):
            result.extend(format_nested_lists(
                it=item,
                indent=indent,
                indentation=indentation + indent),
            )
        elif item.strip() == '':
            result.append('')
        else:
            result.append(indentation + item)

    if indentation == '':
        result.append('')
        return '\n'.join(result)
    else:
        return result


def ordered_unique(iterable):
    seen = set()

    for item in iterable:
        if item not in seen:
            seen.add(item)
            yield item


@attr.s
class Orderer:
    ordered = attr.ib()
    indexes = attr.ib()
    key = attr.ib()

    @classmethod
    def build(cls, ordered, key=lambda item: item):
        indexes = {
            item: index
            for index, item in enumerate(ordered)
        }

        return cls(
            ordered=ordered,
            indexes=indexes,
            key=key,
        )

    def __call__(self, value):
        return self.indexes.get(self.key(value), math.inf)
