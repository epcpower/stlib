import functools
import json
import operator
import pathlib
import time
import uuid

import attr
import canmatrix
import twisted.internet.defer

import epyqlib.canneo
import epyqlib.device
import epyqlib.nv
import epyqlib.utils.qt
import epyqlib.utils.twisted
import epyqlib.utils.units


class FormatVersionError(Exception):
    pass


class AlreadyLoadedError(Exception):
    pass


class BusAlreadySetError(Exception):
    pass


def format_version_validator(instance, attribute, value):
    if value != [1]:
        raise FormatVersionError('Only format_version 1 is supported')


@attr.s
class Definition:
    base_path = attr.ib()
    format_version = attr.ib(
        validator=format_version_validator,
    )
    can_path = attr.ib(converter=pathlib.Path)
    # can_configuration = attr.ib()
    nv_configuration = attr.ib()
    node_id_type = attr.ib()
    access_level_path = attr.ib()
    access_password_path = attr.ib()
    node_id = attr.ib(default=247)
    controller_id = attr.ib(default=65)
    # nv_range_check_overridable = attr.ib()
    # node_id_type = attr.ib()
    # name = attr.ib()
    # tabs = attr.ib()
    # ui_paths = attr.ib()
    # module = attr.ib()
    # parameter_hierarchy = attr.ib()
    # nv_meta_enum = attr.ib()

    def load_can(self):
        matrix, = canmatrix.formats.loadp(
            str(self.base_path / self.can_path)
        ).values()

        return matrix

    @classmethod
    def load(cls, file, base_path=None):
        if base_path is None:
            base_path = pathlib.Path(file.name).parents[0]

        return cls.loads(s=file.read(), base_path=base_path)

    @classmethod
    def loadp(cls, path):
        with open(path) as f:
            return cls.load(f)

    @classmethod
    def loads(cls, s, base_path):
        raw = json.loads(s)

        access_level_path = raw.get('access_level_path')
        if access_level_path is not None:
            access_level_path = access_level_path.split(';')

        access_password_path = raw.get('access_password_path')
        if access_password_path is not None:
            access_password_path = access_password_path.split(';')

        return Definition(
            base_path=base_path,
            format_version=raw['format_version'],
            can_path=base_path / raw['can_path'],
            nv_configuration=raw['nv_configuration'],
            node_id=raw.get('node_id'),
            node_id_type=raw.get(
                'node_id_type',
                next(iter(epyqlib.device.node_id_types)),
            ),
            controller_id=raw.get('controller_id'),
            access_level_path=access_level_path,
            access_password_path=access_password_path,
        )


operator_map = {
    '<': operator.lt,
    '<=': operator.le,
    '==': operator.eq,
    '!=': operator.ne,
    '>=': operator.ge,
    '>': operator.gt,
}

reverse_operator_map = {
    v: k
    for k, v in operator_map.items()
}


@attr.s
class Signal:
    signal = attr.ib()
    device = attr.ib()

    @twisted.internet.defer.inlineCallbacks
    def get(self, stale_after=0.1, timeout=1):
        start = time.time()

        last_received = self.signal.last_received()

        if last_received is None or last_received <= start - stale_after:
            yield epyqlib.utils.qt.signal_as_deferred(
                self.signal.value_set,
                timeout=timeout,
            )

        value = self.signal.to_human(self.signal.value)

        if value in self.signal.enumeration:
            return self.signal.enumeration[value]

        return value * self.units()

    def set(self, value):
        units = self.units()
        if units != epyqlib.utils.units.registry.dimensionless:
            value = value.to(units).magnitude

        self.signal.set_human_value(value)
        self.signal.frame._send(update=True)

    def units(self):
        return epyqlib.utils.units.registry.parse_expression(
            self.signal.unit,
        )

    def cyclic_send(self, period):
        self.device.cyclic_send_signal(self, period=period)

    @twisted.internet.defer.inlineCallbacks
    def wait_for(self, op, value, timeout):
        op = operator_map.get(op, op)
        operator_string = reverse_operator_map.get(op, str(op))

        def check():
            present_value = yield self.get()
            return op(present_value, value)

        yield epyqlib.utils.twisted.wait_for(
            check=check,
            timeout=timeout,
            message=(
                f'{self.signal.name} not {operator_string} {value} '
                f'within {timeout:.1f} seconds'
            ),
        )

    def scaling_factor(self):
        return self.signal.factor

    def decimal_places(self):
        return self.signal.get_decimal_places()

    def f_string(self):
        return f'.{self.decimal_places()}f'


@attr.s
class Nv:
    nv = attr.ib()
    device = attr.ib()

    @twisted.internet.defer.inlineCallbacks
    def set(
            self,
            value=None,
            user_default=None,
            factory_default=None,
            minimum=None,
            maximum=None,
    ):
        values = (
            (epyqlib.nv.MetaEnum.maximum, maximum),
            (epyqlib.nv.MetaEnum.minimum, minimum),
            (epyqlib.nv.MetaEnum.factory_default, factory_default),
            (epyqlib.nv.MetaEnum.user_default, user_default),
            (epyqlib.nv.MetaEnum.value, value),
        )

        for meta, value in values:
            if value is None:
                continue

            if meta == epyqlib.nv.MetaEnum.value:
                self.nv.set_value(value)
            else:
                getattr(self.nv.meta, meta.name).set_value(value)

            # TODO: verify value was accepted
            yield self.device.nvs.protocol.write(
                nv_signal=self.nv,
                meta=meta,
            )

    @twisted.internet.defer.inlineCallbacks
    def get(self, meta=epyqlib.nv.MetaEnum.value):
        value, _meta = yield self.device.nvs.protocol.read(
            nv_signal=self.nv,
            meta=meta,
        )

        return value

    @twisted.internet.defer.inlineCallbacks
    def wait_for(self, op, value, timeout, ignore_read_failures=False):
        op = operator_map.get(op, op)
        operator_string = reverse_operator_map.get(op, str(op))

        @twisted.internet.defer.inlineCallbacks
        def check():
            try:
                own_value = yield self.get()
            except epyqlib.twisted.nvs.RequestTimeoutError:
                if ignore_read_failures:
                    return False

                raise

            return op(own_value, value)

        yield epyqlib.utils.twisted.wait_for(
            check=check,
            timeout=timeout,
            message=(
                f'{self.nv.name} not {operator_string} {value} '
                f'within {timeout:.1f} seconds'
            ),
        )


@attr.s
class Device:
    definition_path = attr.ib(converter=pathlib.Path)
    definition = attr.ib(default=None)
    canmatrix = attr.ib(default=None)
    neo = attr.ib(default=None)
    nvs = attr.ib(default=None)
    bus = attr.ib(default=None)
    cyclic_frames = attr.ib(default=attr.Factory(set))
    default_elevated_access_level = attr.ib(default=None)
    default_access_level_password = attr.ib(default=None)
    save_nv = attr.ib(default=None)
    save_nv_value = attr.ib(default=None)
    uuid = attr.ib(default=uuid.uuid4)

    def load(self):
        if self.definition is not None:
            raise AlreadyLoadedError('The definition has already been loaded')

        self.definition = Definition.loadp(self.definition_path)

        node_id_adjust = functools.partial(
            epyqlib.device.node_id_types[self.definition.node_id_type],
            device_id=self.definition.node_id,
            controller_id=self.definition.controller_id,
        )

        matrix = self.definition.load_can()

        self.neo = epyqlib.canneo.Neo(
            matrix=matrix,
            node_id_adjust=node_id_adjust,
        )

        nv_neo = epyqlib.canneo.Neo(
            matrix=matrix,
            frame_class=epyqlib.nv.Frame,
            signal_class=epyqlib.nv.Nv,
            strip_summary=False,
            node_id_adjust=node_id_adjust,
        )
        self.nvs = epyqlib.nv.Nvs(
            neo=nv_neo,
            configuration=self.definition.nv_configuration,
            access_level_path=self.definition.access_level_path,
            access_password_path=self.definition.access_password_path,
        )

        self.save_nv = self.nv(
            self.nvs.save_frame.mux_name,
            self.nvs.save_signal.name,
        )
        self.save_nv_value = self.nvs.save_value

    def set_bus(self, bus):
        if self.bus is not None:
            raise BusAlreadySetError()

        try:
            self.neo.set_bus(bus=bus)
            self.nvs.set_bus(bus=bus)
        except:
            # TODO: actually rollback a partial setting
            self.bus = object()
            raise

        self.bus = bus
        self.bus.notifier.add(self.neo)
        self.bus.notifier.add(self.nvs)

    # @functools.lru_cache(maxsize=512)
    def signal(self, *path):
        return Signal(
            signal=self.neo.signal_by_path(*path),
            device=self,
        )

    # @functools.lru_cache(maxsize=512)
    def nv(self, *path):
        return Nv(
            nv=self.nvs.signal_from_names(*path),
            device=self,
        )

    @twisted.internet.defer.inlineCallbacks
    def active_to_nv(self, wait=False):
        yield self.save_nv.set(value=self.save_nv_value)

        if wait:
            yield self.wait_for_nv_save_completion()

    @twisted.internet.defer.inlineCallbacks
    def wait_for_nv_save_completion(self):
        nv = self.nv('StatusWarnings', 'eeSaveInProgress')

        yield epyqlib.utils.twisted.sleep(2)

        yield nv.wait_for(
            op='==',
            value=0,
            timeout=120,
            ignore_read_failures=True,
        )

    def cyclic_send_signal(self, signal, period):
        frame = signal.signal.frame
        frame.cyclic_request(self.uuid, period)
        if period is not None:
            self.cyclic_frames.add(frame)
        else:
            self.cyclic_frames.discard(frame)

    def cancel_all_cyclic_sends(self):
        for frame in self.cyclic_frames:
            frame.cyclic_request(self.uuid, None)

    @twisted.internet.defer.inlineCallbacks
    def set_access_level(self, level=None, password=None):
        if level is None:
            level = self.default_elevated_access_level

        if password is None:
            password = self.default_access_level_password

        self.nvs.password_node.set_value(password)
        self.nvs.access_level_node.set_value(level)

        selected_nodes = tuple(
            node
            for node in (
                self.nvs.password_node,
                self.nvs.access_level_node,
            )
            if node is not None
        )

        yield self.nvs.write_all_to_device(only_these=selected_nodes)
