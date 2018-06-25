import collections
import json
import pathlib
import time
import zipfile

import attr
import can
import pytest
import pytest_twisted
import twisted

import epyqlib.autodevice.build
import epyqlib.device
import epyqlib.tests.common
import epyqlib.utils.general

example_archive_code = 'the archive code'
example_access_password = '1'
example_access_level = '2'


@attr.s
class AutoDevice:
    version = attr.ib()
    path = attr.ib()


def create_example_auto_device(
    version,
    target,
    archive_code=example_archive_code,
    access_password=example_access_password,
    access_level=example_access_level,
    serial_number=None,
    parameter_type='pmvs',
):
    builder = epyqlib.autodevice.build.Builder()
    builder.archive_code = archive_code

    if serial_number is not None:
        builder.required_serial_number = serial_number

    builder.set_access_level_names(
        password_name='AccessLevel:Password',
        access_level_name='AccessLevel:Level',
    )

    for access_input in builder.access_parameters:
        if 'Password' in access_input.node:
            access_input.value = access_password
        elif 'Level' in access_input.node:
            access_input.value = access_level

    template = pathlib.Path(epyqlib.autodevice.__file__).with_name('template')
    builder.set_template(path=template/'auto_parameters.epc')

    device_files = epyqlib.tests.common.new_devices[(version, 'factory')]

    with open(device_files.device) as f:
        original_raw_dict = json.load(
            f,
            object_pairs_hook=collections.OrderedDict,
        )

    builder.set_original_raw_dict(original_raw_dict)

    if parameter_type == 'pmvs':
        builder.load_pmvs(device_files.pmvs)
    elif parameter_type == 'epp':
        builder.load_epp_paths(
            parameter_path=device_files.epp,
            can_path=device_files.can,
        )

    builder.set_target(path=target)

    with open(device_files.can, 'rb') as f:
        can_contents = f.read()

    builder.create(can_contents=can_contents)

    return AutoDevice(version=version, path=target)


@pytest.fixture(params=['epp', 'pmvs'])
def parameter_type(request):
    return request.param


versions = ['develop', 'v1.2.5']
# version_to_test = 'v1.2.5'
version_to_test = 'develop'


@pytest.fixture(params=[version_to_test])
def version(request):
    return request.param


@pytest.fixture
def auto_device(version, parameter_type, tmpdir):
    temporary_directory = pathlib.Path(tmpdir)
    target = temporary_directory / 'auto_device.epz'

    yield create_example_auto_device(
        version=version,
        target=target,
        parameter_type=parameter_type,
    )


@pytest.fixture()
def bus():
    real_bus = can.interface.Bus(bustype='socketcan', channel='can0')
    bus = epyqlib.busproxy.BusProxy(bus=real_bus)

    yield bus

    bus.terminate()
    real_bus.shutdown()


@twisted.internet.defer.inlineCallbacks
def wait_until_present(device, period=1):
    start = time.monotonic()

    yield epyqlib.utils.twisted.sleep(2 * device.connection_monitor.timeout)

    while True:
        yield epyqlib.utils.twisted.sleep(period)

        if device.connection_monitor.present:
            break

    save_time = time.monotonic() - start
    print(f'Waited {save_time:0.2f} seconds for EE to save')


def test_contains_epc(auto_device):
    with zipfile.ZipFile(auto_device.path) as z:
        assert any(name.endswith('.epc') for name in z.namelist())


@pytest.mark.require_device
@pytest_twisted.inlineCallbacks
def test_general_load(auto_device, bus):
    device = epyqlib.device.Device(
        file=auto_device.path,
        archive_code=example_archive_code,
        node_id=247,
        bus=bus,
    )

    with device:
        yield device.extension.no_gui_load_parameters()
        yield wait_until_present(device)


@pytest.mark.require_device
@pytest_twisted.inlineCallbacks
def test_invalid_serial(auto_device, bus):
    # string should never match a serial number
    create_example_auto_device(
        version=auto_device.version,
        target=auto_device.path,
        serial_number='a',
    )

    device = epyqlib.device.Device(
        file=auto_device.path,
        archive_code=example_archive_code,
        node_id=247,
        bus=bus,
    )

    with device:
        with pytest.raises(epyqlib.utils.general.UnmatchedSerialNumberError):
            yield device.extension.no_gui_load_parameters()
        yield wait_until_present(device)


@pytest.mark.require_device
@pytest_twisted.inlineCallbacks
def test_valid_serial(auto_device, tmpdir, bus):
    temporary_directory = pathlib.Path(tmpdir)

    device = epyqlib.device.Device(
        file=auto_device.path,
        archive_code=example_archive_code,
        node_id=247,
        bus=bus,
    )

    with device:
        serial_nv = device.extension.nvs.signal_from_names(
            *device.extension.serial_number_names,
        )
        present_serial, _ = yield device.extension.nv_protocol.read(
            nv_signal=serial_nv,
            meta=epyqlib.nv.MetaEnum.value,
        )

    device_path = temporary_directory/'serial_locked_auto_device.epz'

    auto_device = create_example_auto_device(
        version=auto_device.version,
        target=device_path,
        serial_number=present_serial,
    )

    device = epyqlib.device.Device(
        file=auto_device.path,
        archive_code=example_archive_code,
        node_id=247,
        bus=bus,
    )

    with device:
        yield device.extension.no_gui_load_parameters()
        yield wait_until_present(device)
