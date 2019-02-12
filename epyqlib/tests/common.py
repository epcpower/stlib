import contextlib
import functools
import locale
import os
import pathlib
import sys

import attr


library_path = pathlib.Path(__file__).parents[2].resolve()

project_path = library_path.parents[1]

scripts_path = project_path/'venv'/'Scripts'

examples_path = library_path/'examples'/'develop'

device_path = examples_path/'devices'

default_parameters_path = examples_path/'defaults.pmvs'
small_parameters_path = examples_path/'small.pmvs'

devices = {
    'customer': pathlib.Path('customer')/'distributed_generation.epc',
    'factory': pathlib.Path('factory')/'distributed_generation_factory.epc',
}

devices = {
    k: device_path / v
    for k, v in devices.items()
}

symbol_files = {
    'customer': pathlib.Path('customer')/'EPC_DG_ID247.sym',
    'factory': pathlib.Path('factory')/'EPC_DG_ID247_FACTORY.sym',
}

symbol_files = {
    k: device_path / v
    for k, v in symbol_files.items()
}

hierarchy_files = {
    'customer': pathlib.Path('customer')/'EPC_DG_ID247.parameters.json',
    'factory': pathlib.Path('factory')/'EPC_DG_ID247_FACTORY.parameters.json',
}

hierarchy_files = {
    k: device_path / v
    for k, v in hierarchy_files.items()
}


def single(x):
    y, = x

    return y


@attr.s
class DeviceFiles:
    can = attr.ib()
    hierarchy = attr.ib()
    device = attr.ib()
    epp = attr.ib()
    pmvs = attr.ib()

    @classmethod
    def build(cls, base, version, level):
        version = pathlib.Path(base) / version
        path = version / 'devices' / level

        print(path, list(path.glob('*')))

        return cls(
            can=single(path.glob('*.sym')),
            hierarchy=single(path.glob('*.json')),
            device=single(path.glob('*.epc')),
            epp=version/'small.epp',
            pmvs=version/'small.pmvs',
        )


new_examples_path = library_path/'examples'


@functools.lru_cache()
def new_devices():
    return {
        (version, level): DeviceFiles.build(
            base=new_examples_path,
            version=version,
            level=level,
        )
        for version in (
            'develop',
            'v1.2.5',
        )
        for level in (
            'customer',
            'factory',
        )
        if (version, level) not in (
            ('v1.2.5', 'customer'),
        )
    }


@attr.s
class Values:
    initial = attr.ib()
    input = attr.ib()
    expected = attr.ib()
    collected = attr.ib(default=attr.Factory(list))

    def collect(self, value):
        self.collected.append(value)

    def check(self):
        return all(x == y for x, y in zip(self.expected, self.collected))


@contextlib.contextmanager
def use_locale(*s):
    if len(s) == 0:
        s = ('',)

    #use setlocale() to get present settings because reasons:
    #https://docs.python.org/3/library/locale.html#locale.getlocale
    #https://docs.python.org/3/library/locale.html#locale.setlocale
    old = locale.setlocale(locale.LC_ALL)

    for name in s:
        try:
            locale.setlocale(locale.LC_ALL, name)
        except locale.Error:
            continue

        break
    else:
        assert False, 'Unable to set locale to any of {}'.format(s)

    yield

    locale.setlocale(locale.LC_ALL, old)
