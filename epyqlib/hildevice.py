import functools
import json
import pathlib
import uuid

import attr
import canmatrix
import twisted.internet.defer

import epyqlib.canneo
import epyqlib.nv


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


@attr.s
class Device:
    definition_path = attr.ib(converter=pathlib.Path)
    definition = attr.ib(default=None)
    canmatrix = attr.ib(default=None)
    neo = attr.ib(default=None)
    nvs = attr.ib(default=None)
    bus = attr.ib(default=None)
    cyclic_frames = attr.ib(default=attr.Factory(set))
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
    def find_signal(self, path):
        return self.neo.signal_by_path(*path)

    # @functools.lru_cache(maxsize=512)
    def find_nv(self, path):
        return self.nvs.signal_from_names(*path)

    def set_signal(self, path, value):
        signal = self.find_signal(path)
        signal.set_human_value(value)
        signal.frame._send(update=True)

    def get_signal(self, path):
        signal = self.find_signal(path)
        value = signal.to_human(signal.value)
        return signal.enumeration.get(value, value)

    def cyclic_send_signal(self, path, period):
        signal = self.find_signal(path)
        frame = signal.frame
        frame.cyclic_request(self.uuid, period)
        if period is not None:
            self.cyclic_frames.add(frame)
        else:
            self.cyclic_frames.discard(frame)

    def cancel_all_cyclic_sends(self):
        for frame in self.cyclic_frames:
            frame.cyclic_request(self.uuid, None)

    @twisted.internet.defer.inlineCallbacks
    def set_nv(
            self,
            path,
            value=None,
            user_default=None,
            factory_default=None,
            minimum=None,
            maximum=None,
    ):
        nv = self.find_nv(path)

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
                nv.set_value(value)
            else:
                getattr(nv.meta, meta.name).set_value(value)

            # TODO: verify value was accepted
            yield self.nvs.protocol.write(
                nv_signal=nv,
                meta=meta,
            )

    @twisted.internet.defer.inlineCallbacks
    def set_access_level(self, password, level=2):
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
