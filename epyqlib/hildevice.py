import contextlib
import decimal
import functools
import json
import operator
import pathlib
import time
import uuid

import attr
import canmatrix
import epcsunspecdemo.demos
import epcsunspecdemo.utils
import sunspec.core.client
import twisted.internet.defer

import epyqlib.canneo
import epyqlib.device
import epyqlib.nv
import epyqlib.utils.qt
import epyqlib.utils.twisted
import epyqlib.utils.units
import epyqlib.updateepc


class FormatVersionError(Exception):
    pass


class AlreadyLoadedError(Exception):
    pass


class BusAlreadySetError(Exception):
    pass


supported_version = [2]


def format_version_validator(instance, attribute, value):
    if value != supported_version:
        raise FormatVersionError(
            'Only format_version {} is supported'.format(
                '.'.join(str(v) for v in supported_version),
            ),
        )


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
    def _get_raw(self, stale_after=0.1, timeout=1):
        # TODO: uh...  why not time.monotonic()?
        start = time.time()

        last_received = self.signal.last_received()

        if last_received is None or last_received <= start - stale_after:
            yield epyqlib.utils.qt.signal_as_deferred(
                self.signal.value_set,
                timeout=timeout,
            )

        return self.signal.value

    @twisted.internet.defer.inlineCallbacks
    def get(self, stale_after=0.1, timeout=1, enumeration_as_string=True):
        yield self._get_raw(stale_after=stale_after, timeout=timeout)

        return self._to_human(enumeration_as_string=enumeration_as_string)

    def _to_human(self, enumeration_as_string):
        value = self.signal.to_human(value=self.signal.value)

        if enumeration_as_string and value in self.signal.enumeration:
            return self.signal.enumeration[value]

        return value * self.units()

    def set(self, value):
        units = self.units()
        if units != epyqlib.utils.units.registry.dimensionless:
            value = value.to(units).magnitude

        self.signal.set_human_value(value)
        self.signal.frame._send(update=True)

    # TODO: get rid of this and update everything to have .set() itself
    #       be an async
    async def async_set(self, value):
        return self.set(value=value)

    def units(self):
        unit = self.signal.unit
        if unit is not None:
            unit = unit.replace('%', ' percent ')

        return epyqlib.utils.units.registry.parse_units(unit)

    def cyclic_send(self, period):
        self.device.cyclic_send_signal(self, period=period)

    @twisted.internet.defer.inlineCallbacks
    def wait_for(self, op, value, timeout):
        op = operator_map.get(op, op)
        operator_string = reverse_operator_map.get(op, str(op))

        @twisted.internet.defer.inlineCallbacks
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

    @contextlib.asynccontextmanager
    async def temporary_set(
            self,
            value=None,
            read_context=None,
            set_context=None,
            restoration_context=None,
    ):
        @contextlib.asynccontextmanager
        async def async_null_context(enter_result=None):
            with contextlib.nullcontext(enter_result=enter_result) as result:
                yield result

        if set_context is None:
            set_context = async_null_context
        if restoration_context is None:
            restoration_context = async_null_context

        original = self._to_human(enumeration_as_string=True)

        try:
            async with set_context():
                self.set(value=value)

            yield
        finally:
            if original is not None:
                async with restoration_context():
                    self.set(value=original)


@attr.s
class Nv:
    nv = attr.ib()
    device = attr.ib()

    async def set(
            self,
            value=None,
            user_default=None,
            factory_default=None,
            minimum=None,
            maximum=None,
    ):
        values = {
            epyqlib.nv.MetaEnum.maximum: maximum,
            epyqlib.nv.MetaEnum.minimum: minimum,
            epyqlib.nv.MetaEnum.factory_default: factory_default,
            epyqlib.nv.MetaEnum.user_default: user_default,
            epyqlib.nv.MetaEnum.value: value,
        }

        values = {
            meta: value
            for meta, value in values.items()
            if value is not None
        }

        for meta, value in values.items():
            await self.set_meta(value=value, meta=meta)

    async def set_meta(self, value, meta):
        units = self.units()
        if units != epyqlib.utils.units.registry.dimensionless:
            value = value.to(units).magnitude

        if meta == epyqlib.nv.MetaEnum.value:
            self.nv.set_human_value(value)
        else:
            getattr(self.nv.meta, meta.name).set_human_value(value)

        # TODO: verify value was accepted
        await self.device.nvs.protocol.write(
            nv_signal=self.nv,
            meta=meta,
        )

    @contextlib.asynccontextmanager
    async def temporary_set(
            self,
            value=None,
            user_default=None,
            factory_default=None,
            minimum=None,
            maximum=None,
            read_context=None,
            set_context=None,
            restoration_context=None,
    ):
        @contextlib.asynccontextmanager
        async def async_null_context(enter_result=None):
            with contextlib.nullcontext(enter_result=enter_result) as result:
                yield result

        if read_context is None:
            read_context = async_null_context
        if set_context is None:
            set_context = async_null_context
        if restoration_context is None:
            restoration_context = async_null_context

        values = {
            epyqlib.nv.MetaEnum.maximum: maximum,
            epyqlib.nv.MetaEnum.minimum: minimum,
            epyqlib.nv.MetaEnum.factory_default: factory_default,
            epyqlib.nv.MetaEnum.user_default: user_default,
            epyqlib.nv.MetaEnum.value: value,
        }

        values = {
            meta: value
            for meta, value in values.items()
            if value is not None
        }

        original = {}

        try:
            async with read_context():
                for meta, value in values.items():
                    original[meta] = await self.get(meta=meta)

            async with set_context():
                for meta, value in values.items():
                    await self.set_meta(value=value, meta=meta)

            yield
        finally:
            async with restoration_context():
                for meta, value in original.items():
                    await self.set_meta(value=value, meta=meta)

    @twisted.internet.defer.inlineCallbacks
    def get(self, meta=epyqlib.nv.MetaEnum.value):
        value, _meta = yield self.device.nvs.protocol.read(
            nv_signal=self.nv,
            meta=meta,
        )

        return value * self.units()

    def units(self):
        unit = self.nv.unit
        if unit is not None:
            unit = unit.replace('%', ' percent ')

        return epyqlib.utils.units.registry.parse_units(unit)


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

    def parameter_uuid(self):
        return self.nv.parameter_uuid


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

        with epyqlib.updateepc.updated(self.definition_path) as updated:
            self.definition = Definition.loadp(updated)
            matrix = self.definition.load_can()

        node_id_adjust = functools.partial(
            epyqlib.device.node_id_types[self.definition.node_id_type],
            device_id=self.definition.node_id,
            controller_id=self.definition.controller_id,
        )

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
        # TODO: really think through what is proper...  won't this keep the
        #       nv objects from getting updated?
        # self.bus.notifier.add(self.nvs)

    # @functools.lru_cache(maxsize=512)
    def signal(self, *path):
        return Signal(
            signal=self.neo.signal_by_path(*path),
            device=self,
        )

    def signal_from_uuid(self, uuid_):
        return Signal(
            signal=self.neo.signal_from_uuid[uuid_],
            device=self,
        )

    # @functools.lru_cache(maxsize=512)
    def nv(self, *path):
        return Nv(
            nv=self.nvs.signal_from_names(*path),
            device=self,
        )

    def nv_from_uuid(self, uuid_):
        return Nv(
            nv=self.nvs.nv_from_uuid[uuid_],
            device=self,
        )

    def parameter_from_uuid(self, uuid_):
        try:
            return self.nv_from_uuid(uuid_=uuid_)
        except KeyError:
            return self.signal_from_uuid(uuid_=uuid_)

    @twisted.internet.defer.inlineCallbacks
    def active_to_nv(self, wait=False):
        # TODO: dedupe 8795477695t46542676781543768139
        yield twisted.internet.defer.ensureDeferred(
            self.save_nv.set(value=self.save_nv_value),
        )

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
    def get_access_level(self):
        nv = Nv(nv=self.nvs.access_level_node, device=self)
        access_level = yield nv.get()
        return access_level

    async def get_check_limits(self):
        nv = self.nv_from_uuid(
            uuid.UUID('bd7c3c96-bde9-4b4b-a646-e1d06a7cc24f'),
        )
        value = await nv.get()

        return value

    async def get_password(self):
        nv = self.nv_from_uuid(
            uuid.UUID('cc438574-bec0-4443-8a25-785e41240c1b'),
        )
        value = await nv.get()

        return value

    @twisted.internet.defer.inlineCallbacks
    def set_access_level(self, level=None, password=None, check_limits=True):
        if level is None:
            level = self.default_elevated_access_level

        if password is None:
            password = self.default_access_level_password

        self.nvs.password_node.set_value(password)
        self.nvs.access_level_node.set_value(level)
        check_limits_nv = self.nv_from_uuid(
            uuid.UUID('bd7c3c96-bde9-4b4b-a646-e1d06a7cc24f'),
        )
        check_limits_nv.nv.set_value(check_limits)

        selected_nodes = tuple(
            node
            for node in (
                self.nvs.password_node,
                self.nvs.access_level_node,
                check_limits_nv.nv,
            )
            if node is not None
        )

        yield self.nvs.write_all_to_device(
            only_these=selected_nodes,
            meta=[epyqlib.nv.MetaEnum.value],
        )

    @contextlib.asynccontextmanager
    async def temporary_access_level(
            self,
            level=None,
            password=None,
            check_limits=True,
    ):
        access_level_parameter = self.nv(*self.definition.access_level_path[1:])
        original_access_level = await access_level_parameter.get()

        check_limits_nv = self.nv_from_uuid(
            uuid.UUID('bd7c3c96-bde9-4b4b-a646-e1d06a7cc24f'),
        )
        original_check_limits = await check_limits_nv.get()

        try:
            await self.set_access_level(
                level=level,
                password=password,
                check_limits=check_limits,
            )
            yield
        finally:
            try:
                await self.set_access_level(
                    level=level,
                    password=password,
                    check_limits=original_check_limits,
                )
            finally:
                await self.set_access_level(
                    level=original_access_level,
                    password=password,
                )

    async def reset(self, timeout=None):
        # SoftwareReset:InitiateReset
        reset_nv = self.nv_from_uuid(
            uuid_=uuid.UUID('b582085d-7734-4260-ab97-47e50a41b06c'),
        )

        # StatusBits:State
        state_signal = self.signal_from_uuid(
            uuid_=uuid.UUID('6392782a-b886-45a0-9642-dd4f47cd2a59'),
        )

        # TODO: just accept the 1s or whatever default timeout?  A set without
        #       waiting for the response could be nice.  (or embedded sending
        #       a response)
        with contextlib.suppress(epyqlib.twisted.nvs.RequestTimeoutError):
            await reset_nv.set(value=1)

        await state_signal.get(stale_after=-1, timeout=10)

    async def wait_through_power_on_reset(self):
        status_signal = self.signal_from_uuid(
            uuid_=uuid.UUID('6392782a-b886-45a0-9642-dd4f47cd2a59'),
        )

        await status_signal.wait_for(
            op='!=',
            # TODO: stop comparing strings...
            value='Power On Reset',
            timeout=60,
        )

    async def to_nv(self):
        # TODO: dedupe 8795477695t46542676781543768139
        await self.nvs.module_to_nv()

    async def get_serial_number(self):
        nv = self.nv_from_uuid(
            uuid_=uuid.UUID('390f27ea-6f28-4313-b183-5f37d007ccd1'),
        )
        value = await nv.get()
        return value

    async def clear_faults(self):
        clear_faults_signal = self.signal_from_uuid(
            uuid_=uuid.UUID('62b6dc82-c93a-454a-a643-dd8a7b2a220e'),
        )
        clear_faults_status_signal = self.signal_from_uuid(
            uuid_=uuid.UUID('d84e5184-696d-487c-8850-cc904a7c018f'),
        )

        clear_faults_signal.set(value=False)
        await clear_faults_status_signal.wait_for(
            op='==',
            value='Normal',
            timeout=1,
        )

        clear_faults_signal.set(value=True)
        await clear_faults_status_signal.wait_for(
            op='==',
            value='Clear Faults',
            timeout=1,
        )

        clear_faults_signal.set(value=False)
        await clear_faults_status_signal.wait_for(
            op='==',
            value='Normal',
            timeout=1,
        )




async def set_key_inplace(
        key_nvs,
        tag_nvs,
        existing_key,
        replacement_key,
        serial_number,
):
    new_level_key = attr.evolve(existing_key, level=replacement_key)
    new_low_key = attr.evolve(
        new_level_key,
        value=new_level_key.value.evolve_low(replacement_key.value.low_32()),
    )

    to_write = [
        (key_nvs.access_level, existing_key, replacement_key.level),
        (key_nvs.low, new_level_key, replacement_key.value.low_32()),
        (key_nvs.high, new_low_key, replacement_key.value.high_32()),
    ]

    for nv, present_key, value in to_write:
        tag = epyqlib.authorization.create_tag(
            key_value=present_key.value,
            serial_number=serial_number,
            parameter_uuid=nv.parameter_uuid(),
            meta_index=0,
            value=int(
                nv.nv.pack_bitstring(value=value),
                2,
            ),
        )

        async with temporary_set(
                nvs_and_values=(
                    (tag_nvs.low, tag.value.low_32()),
                    (tag_nvs.high, tag.value.high_32()),
                )
        ):
            await nv.set(value)
            print()


@contextlib.asynccontextmanager
async def temporary_key(
        key_nvs,
        tag_nvs,
        existing_key,
        replacement_key,
        serial_number,
):
    try:
        await set_key_inplace(
            key_nvs=key_nvs,
            tag_nvs=tag_nvs,
            existing_key=existing_key,
            replacement_key=replacement_key,
            serial_number=serial_number,
        )

        yield
    finally:
        await set_key_inplace(
            key_nvs=key_nvs,
            tag_nvs=tag_nvs,
            existing_key=replacement_key,
            replacement_key=existing_key,
            serial_number=serial_number,
        )


@attr.s(frozen=True)
class KeyNvs:
    low = attr.ib()
    high = attr.ib()
    access_level = attr.ib()
    index = attr.ib()

    @classmethod
    def from_index(cls, index, device):
        # These UUIDs are for key 0

        return cls(
            low=device.nv_from_uuid(
                uuid_=uuid.UUID('f046a08b-9308-4da7-ae5e-b931d610b3f4'),
            ),
            high=device.nv_from_uuid(
                uuid_=uuid.UUID('3e021694-d565-4636-8a5d-3e0976d1112c'),
            ),
            access_level=device.nv_from_uuid(
                uuid_=uuid.UUID('07c45cff-0b95-413d-9aed-01a4f514e8da'),
            ),
            index=index,
        )


@attr.s(frozen=True)
class TagNvs:
    low = attr.ib()
    high = attr.ib()
    index = attr.ib()

    @classmethod
    def from_index(cls, index, device):
        return cls(
            low=device.nv(f'AuthTag{index}Low32', 'Low32'),
            high=device.nv(f'AuthTag{index}High32', 'High32'),
            index=index,
        )


@contextlib.asynccontextmanager
async def temporary_set(nvs_and_values):
    async with contextlib.AsyncExitStack() as exit_stack:
        for nv, value in nvs_and_values:
            await exit_stack.enter_async_context(nv.temporary_set(value=value))

        yield


@attr.s
class AccessLevel:
    name = attr.ib()
    level = attr.ib()
    password = attr.ib()


# TODO: shouldn't need to be duplicated here

highest_authenticatable_access_level = AccessLevel(
    name='EPC Factory',
    level=3,
    password=13250,
)


authenticatable_elevated_access_levels = [
    AccessLevel(
        name='Service Eng',
        level=1,
        password=42,
    ),
    AccessLevel(
        name='EPC Eng',
        level=2,
        password=13125,
    ),
    highest_authenticatable_access_level,
]


base_access_level = AccessLevel(
    name='Service Tech',
    level=0,
    password=0,
)


authenticatable_access_levels = [
    base_access_level,
    *authenticatable_elevated_access_levels,
]


unauthenticatable_access_levels = [
    AccessLevel(
        name='MAC Auth',
        level=4,
        password=31415,
    ),
]

access_levels = [
    *authenticatable_access_levels,
    *unauthenticatable_access_levels,
]


@attr.s
class SunSpecNv:
    nv = attr.ib()
    model = attr.ib()
    # device = attr.ib()

    async def set(self, value):
        units = self.units()
        if units != epyqlib.utils.units.registry.dimensionless:
            value = value.to(units).magnitude

        self.nv.value = value
        self.nv.write()

    @contextlib.asynccontextmanager
    async def temporary_set(
            self,
            value,
            read_context=None,
            set_context=None,
            restoration_context=None,
    ):
        @contextlib.asynccontextmanager
        async def async_null_context(enter_result=None):
            with contextlib.nullcontext(enter_result=enter_result) as result:
                yield result

        if read_context is None:
            read_context = async_null_context
        if set_context is None:
            set_context = async_null_context
        if restoration_context is None:
            restoration_context = async_null_context

        original = None

        try:
            async with read_context():
                original = await self.get()

            async with set_context():
                await self.set(value=value)

            yield
        finally:
            if original is not None:
                async with restoration_context():
                    await self.set(value=original)

    async def get(self):
        self.model.read_points()

        value = decimal.Decimal(self.nv.value)
        scale_factor = self.nv.value_sf
        if scale_factor is None:
            scale_factor = 0
        value = round(value, -scale_factor)

        return value * self.units()

    def units(self):
        unit = self.nv.point_type.units
        if unit is not None:
            unit = unit.replace('%', ' percent ')

        return epyqlib.utils.units.registry.parse_units(unit)


@attr.s
class SunSpecDevice:
    model_path = attr.ib(converter=pathlib.Path)
    device = attr.ib(default=None)
    cyclic_frames = attr.ib(default=attr.Factory(set))
    default_elevated_access_level = attr.ib(default=None)
    default_access_level_password = attr.ib(default=None)
    save_nv = attr.ib(default=None)
    save_nv_value = attr.ib(default=None)
    uuid_to_point = attr.ib(default=None)
    uuid_to_model = attr.ib(default=None)
    uuid = attr.ib(default=uuid.uuid4)

    def load(self):
        with epcsunspecdemo.utils.fresh_smdx_path(self.model_path):
            self.device = sunspec.core.client.SunSpecClientDevice(
                slave_id=1,
                device_type=sunspec.core.client.RTU,
                name='/dev/ttyUSB0',
                baudrate=9600,
                timeout=1,
            )

    # def signal_from_uuid(self, uuid_) -> SunSpecNv:
    #     return self.nv_from_uuid(uuid_=uuid_)

    def nv_from_uuid(self, uuid_) -> SunSpecNv:
        return SunSpecNv(
            nv=self.uuid_to_point[uuid_],
            model=self.uuid_to_model[uuid_],
            # device=self,
        )

    # no 'signals' so just alias
    parameter_from_uuid = nv_from_uuid

    def map_uuids(self):
        def get_uuid(point):
            comment, uuid = epyqlib.canneo.strip_uuid_from_comment(
                point.point_type.notes,
            )

            return uuid

        self.uuid_to_point = {
            get_uuid(point): point
            for model in self.device.device.models_list
            for point in model.points_list
        }

        self.uuid_to_model = {
            get_uuid(point): model
            for model in self.device.device.models_list
            for point in model.points_list
        }

    async def get_access_level(self):
        access_level_point = self.device.epc_control.model.points['AccLvl']

        self.device.epc_control.read()

        return access_level_point.value

    async def get_check_limits(self):
        point = self.device.epc_control.model.points['ChkLmts']
        self.device.epc_control.read()

        return point.value

    async def get_password(self):
        point = self.device.epc_control.model.points['Passwd']
        self.device.epc_control.read()

        return point.value

    async def set_access_level(self, level=None, password=None, check_limits=True):
        if level is None:
            level = self.default_elevated_access_level

        if password is None:
            password = self.default_access_level_password

        access_level_point = self.device.epc_control.model.points['AccLvl']
        password_point = self.device.epc_control.model.points['Passwd']
        check_limits_point = self.device.epc_control.model.points['ChkLmts']
        submit_point = self.device.epc_control.model.points['SubAccLvl']

        epcsunspecdemo.demos.send_val(access_level_point, level)
        epcsunspecdemo.demos.send_val(password_point, password)
        epcsunspecdemo.demos.send_val(check_limits_point, check_limits)

        epcsunspecdemo.demos.send_val(submit_point, True)

    @contextlib.asynccontextmanager
    async def temporary_access_level(
            self,
            level=None,
            password=None,
            check_limits=True,
    ):
        check_limits_point = self.device.epc_control.model.points['ChkLmts']

        original_access_level = await self.get_access_level()
        self.device.epc_control.read()
        original_check_limits = check_limits_point.value

        try:
            await self.set_access_level(
                level=level,
                password=password,
                check_limits=check_limits,
            )
            yield
        finally:
            await self.set_access_level(
                level=original_access_level,
                password=password,
                check_limits=original_check_limits,
            )
