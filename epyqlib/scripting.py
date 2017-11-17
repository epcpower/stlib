import csv
import decimal
import io
import itertools
import pathlib

import attr
import twisted.internet
import twisted.internet.defer
import twisted.internet.task

import epyqlib.utils.general
import epyqlib.utils.twisted


@attr.s(frozen=True)
class Event:
    time = attr.ib()
    action = attr.ib()


@attr.s(frozen=True)
class Action:
    signal = attr.ib()
    value = attr.ib()

    def __call__(self):
        print('setting:', self.signal.name, self.value)
        self.signal.set_human_value(self.value)


def csv_load(f):
    events = []

    reader = csv.reader(f)

    for row in reader:
        event_time = decimal.Decimal(row[0])

        actions = [x.strip() for x in row[1:] if len(x) > 0]
        actions = [
            Action(signal=path.split(';'), value=decimal.Decimal(value))
            for path, value in epyqlib.utils.general.pairwise(actions)
        ]

        events.extend([
            Event(time=event_time, action=action)
            for action in actions
        ])

    return events


def csv_loads(s):
    f = io.StringIO(s)
    return csv_load(f)


def csv_loadp(path):
    with open(path) as f:
        return csv_load(f)


def resolve_signals(events, neo):
    # TODO: remove this backwards compat and just use recent
    #       attrs everywhere
    evolve = getattr(attr, 'evolve', attr.assoc)

    return [
        evolve(
            event,
            action=evolve(
                event.action,
                signal=neo.signal_by_path(*event.action.signal),
            )
        )
        for event in events
    ]


def run(events):
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
        ))

    d.addCallback(lambda _: print('done'))
    d.addErrback(epyqlib.utils.twisted.errbackhook)
    d.callback(None)


@attr.s
class Model:
    neo = attr.ib()

    def demo(self):
        events = epyqlib.scripting.csv_loadp(
            pathlib.Path(__file__).parents[0] / 'scripting.csv',
        )

        events = epyqlib.scripting.resolve_signals(events, self.neo)
        epyqlib.scripting.run(events)
