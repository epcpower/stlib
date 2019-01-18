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


class NoEventsError(epyqlib.utils.general.ExpectedException):
    def expected_message(self):
        return 'No script events found.'


class NoDevicesError(epyqlib.utils.general.ExpectedException):
    def expected_message(self):
        return 'No devices found.'


class MissingDevicesError(epyqlib.utils.general.ExpectedException):
    def expected_message(self):
        return 'Unable to find devices named: {}'.format(
            ', '.join(repr(name) for name in sorted(self.args[0]))
        )


@attr.s(frozen=True)
class Event:
    time = attr.ib()
    action = attr.ib()
    device = attr.ib()

    def resolve(self):
        if self.action is pause_sentinel:
            return self

        return attr.evolve(
            inst=self,
            action=self.action.resolve(device=self.device),
        )


@attr.s(frozen=True)
class Device:
    name = attr.ib()
    neo = attr.ib()
    nvs = attr.ib()


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
        if self is pause_sentinel:
            print('pausing')
            return

        if self.is_nv:
            return self.nv_handler(nvs)
        else:
            return self.standard_handler()

    def standard_handler(self):
        print('standard setting:', self.signal.name, self.value)
        self.signal.set_human_value(self.value)

    def set_nv_value(self):
        print('nv setting:', self.signal.name, self.value)
        self.signal.set_human_value(self.value)

    def nv_handler(self, nvs):
        self.set_nv_value()
        nvs.write_all_to_device(only_these=(self.signal,))

    def resolve(self, device):
        signal = device.neo.signal_by_path(*self.signal)

        # TODO: CAMPid 079320743340327834208
        is_nv = signal.frame.id == device.nvs.set_frames[0].id
        if is_nv:
            print('switching', self.signal)
            signal = device.nvs.neo.signal_by_path(*self.signal)

        return attr.evolve(
            inst=self,
            signal=signal,
            is_nv=is_nv,
        )


@attr.s(frozen=True)
class CompoundAction:
    actions = attr.ib()

    def __call__(self, nvs=None):
        nv_actions = []

        for action in self.actions:
            if action.is_nv:
                nv_actions.append(action)
                continue

            action(nvs=nvs)

        for action in nv_actions:
            action.set_nv_value()

        if len(nv_actions) > 0:
            nvs.write_all_to_device(
                only_these=tuple(action.signal for action in nv_actions),
            )

    def resolve(self, device):
        return attr.evolve(
            inst=self,
            actions=tuple(
                action.resolve(device=device)
                for action in self.actions
            )
        )


def compound_event_from_events(events):
    return attr.evolve(
        inst=events[0],
        action=CompoundAction(
            actions=tuple(event.action for event in events),
        ),
    )



pause_sentinel = Action(signal=[], value=0)


special_leading_characters = set('#')

def csv_load(f, devices):
    events = []

    lines = tuple(
        line.strip()
        for line in f.readlines()
    )

    device_names = None

    for line in lines:
        if line[0] == '@':
            s = line.split()
            command = s[0][1:]
            arguments = s[1:]

        # add commands here if needed


    device_map = {
        device.name: device
        for device in devices
    }

    reader = csv.reader(
        line
        for line in lines
        if line[0] not in special_leading_characters
    )

    last_event_time = 0

    missing_device_names = set()

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

        raw_actions = [x.strip() for x in row[1:] if len(x) > 0]

        try:
            events_group = tuple(events_from_raw_actions(
                device_map=device_map,
                event_time=event_time,
                events=events,
                raw_actions=raw_actions,
            ))
        except MissingDevicesError as e:
            missing_device_names |= e.args[0]
            continue

        events.extend(events_group)

        last_event_time = event_time

    events = [
        compound_event_from_events(tuple(events))
        for key, events in itertools.groupby(
            iterable=events,
            key=lambda e: (e.time, e.device),
        )
    ]

    if len(missing_device_names) > 0:
        raise MissingDevicesError(missing_device_names)

    return sorted(events, key=lambda event: event.time)


def events_from_raw_actions(device_map, event_time, events, raw_actions):
    missing_device_names = set()

    for path, value in epyqlib.utils.general.grouper(raw_actions, n=2):
        if path == 'pause':
            yield Event(
                time=event_time,
                action=pause_sentinel,
                device=None,
            )
            continue

        device_name, *signal = path.split(';')
        if device_name == '':
            device_name = None

        try:
            device = device_map[device_name]
        except KeyError:
            missing_device_names.add(device_name)
            continue

        yield Event(
            time=event_time,
            device=device,
            action=Action(
                signal=signal,
                value=decimal.Decimal(value),
            )
        )

    if len(missing_device_names) > 0:
        raise MissingDevicesError(missing_device_names)


def csv_loads(s, devices):
    f = io.StringIO(s)
    return csv_load(f, devices)


def csv_loadp(path, devices):
    with open(path) as f:
        return csv_load(f, devices)


def run(events, pause, loop):
    sequence = epyqlib.utils.twisted.Sequence()

    zero_padded = itertools.chain(
        (Event(time=0, action=None, device=None),),
        events,
    )

    for p, n in epyqlib.utils.general.pairwise(zero_padded):
        if n.action is pause_sentinel:
            def action(n=n):
                n.action()
                pause()
            kwargs = {}
        else:
            action = n.action
            kwargs = dict(nvs=n.device.nvs)

        sequence.add_delayed(
            delay=float(n.time - p.time),
            f=action,
            **kwargs,
        )

    sequence.run(loop=loop)

    return sequence


@attr.s
class Model:
    get_devices = attr.ib()

    def run_s(self, event_string, pause, loop=False):
        devices = tuple(
            Device(
                name=name,
                neo=device.neo_frames,
                nvs=device.widget_nvs,
            )
            for name, device in self.get_devices().items()
        )

        if len(devices) == 0:
            raise NoDevicesError()

        events = csv_loads(event_string, devices)

        if len(events) == 0:
            raise NoEventsError()

        events = [
            event.resolve()
            for event in events
        ]

        return run(events=events, pause=pause, loop=loop)
