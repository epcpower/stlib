import csv
import decimal
import io
import itertools
import operator
import pathlib

import attr
import twisted.internet
import twisted.internet.defer
import twisted.internet.task

import epyqlib.utils.general
import epyqlib.utils.twisted


class TimeParseError(Exception):
    pass


@attr.s(frozen=True)
class Event:
    time = attr.ib()
    action = attr.ib()


operators = {
    '+': operator.add,
    '-': operator.sub,
}


@attr.s(frozen=True)
class Action:
    signal = attr.ib()
    value = attr.ib()
    is_nv = attr.ib(default=False)

    def __call__(self, nvs=None):
        if self.is_nv:
            return self.nv_handler(nvs)
        else:
            return self.standard_handler()

    def standard_handler(self):
        print('standard setting:', self.signal.name, self.value)
        self.signal.set_human_value(self.value)

    def nv_handler(self, nvs):
        print('nv setting:', self.signal.name, self.value)
        self.signal.set_human_value(self.value)
        nvs.write_all_to_device(only_these=(self.signal,))


def csv_load(f):
    events = []

    reader = csv.reader(f)

    last_event_time = 0

    for i, row in enumerate(reader):
        raw_event_time = row[0]

        selected_operator = operators.get(raw_event_time[0], None)
        if selected_operator is not None:
            raw_event_time = raw_event_time[1:]

        try:
            event_time = decimal.Decimal(raw_event_time)
        except decimal.InvalidOperation as e:
            raise TimeParseError(
                'Unable to parse as a time (line {number}): {string}'.format(
                    number=i,
                    string=raw_event_time,
                )
            ) from e

        if selected_operator is not None:
            event_time = selected_operator(last_event_time, event_time)

        actions = [x.strip() for x in row[1:] if len(x) > 0]
        actions = [
            Action(signal=path.split(';'), value=decimal.Decimal(value))
            for path, value in epyqlib.utils.general.pairwise(actions)
        ]

        events.extend([
            Event(time=event_time, action=action)
            for action in actions
        ])

        last_event_time = event_time

    return sorted(events)


def csv_loads(s):
    f = io.StringIO(s)
    return csv_load(f)


def csv_loadp(path):
    with open(path) as f:
        return csv_load(f)


def resolve(event, tx_neo, nvs):
    signal = tx_neo.signal_by_path(*event.action.signal)

    # TODO: CAMPid 079320743340327834208
    is_nv = signal.frame.id == nvs.set_frames[0].id
    if is_nv:
        print('switching', event.action.signal)
        signal = nvs.neo.signal_by_path(*event.action.signal)

    # TODO: remove this backwards compat and just use recent
    #       attrs everywhere
    evolve = getattr(attr, 'evolve', attr.assoc)

    return evolve(
        event,
        action=evolve(
            event.action,
            signal=signal,
            is_nv=is_nv,
        )
    )


def resolve_signals(events, tx_neo, nvs):
    return [
        resolve(event=event, tx_neo=tx_neo, nvs=nvs)
        for event in events
    ]


def run(events, nvs):
    d = twisted.internet.defer.Deferred()

    zero_padded = itertools.chain(
        (Event(time=0, action=None),),
        events,
    )

    for p, n in epyqlib.utils.general.pairwise(zero_padded):
        d.addCallback(lambda _, p=p, n=n: twisted.internet.task.deferLater(
            clock=twisted.internet.reactor,
            delay=float(n.time - p.time),
            callable=n.action,
            nvs=nvs,
        ))

    d.addCallback(lambda _: print('done'))
    d.addErrback(epyqlib.utils.twisted.errbackhook)
    d.callback(None)


@attr.s
class Model:
    tx_neo = attr.ib()
    nvs = attr.ib()

    def demo(self):
        events = epyqlib.scripting.csv_loadp(
            pathlib.Path(__file__).parents[0] / 'scripting.csv',
        )

        events = epyqlib.scripting.resolve_signals(
            events=events,
            tx_neo=self.tx_neo,
            nvs=self.nvs,
        )
        epyqlib.scripting.run(events=events, nvs=self.nvs)

    def runs(self, event_string):
        events = csv_loads(event_string)

        events = epyqlib.scripting.resolve_signals(
            events=events,
            tx_neo=self.tx_neo,
            nvs=self.nvs,
        )

        return run(events=events, nvs=self.nvs)
