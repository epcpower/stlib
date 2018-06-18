import collections
import json
import pathlib
import zipfile

import can
import pytest
import pytest_twisted

import epyqlib.autodevice.build
import epyqlib.device
import epyqlib.tests.common


example_archive_code = 'the archive code'
example_access_password = '1'
example_access_level = '2'


def create_example_auto_device(
        target,
        archive_code=example_archive_code,
        access_password=example_access_password,
        access_level=example_access_level,
):
    builder = epyqlib.autodevice.build.Builder()
    builder.archive_code = archive_code

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

    builder.load_pmvs(epyqlib.tests.common.defaults_path)

    builder.set_target(path=target)

    with open(epyqlib.tests.common.symbol_files['factory'], 'rb') as f:
        can_contents = f.read()

    with open(epyqlib.tests.common.devices['factory']) as f:
        original_raw_dict = json.load(
            f,
            object_pairs_hook=collections.OrderedDict,
        )

    builder.create(
        original_raw_dict=original_raw_dict,
        can_contents=can_contents,
    )


def test_overall(tmpdir):
    temporary_directory = pathlib.Path(tmpdir)
    target = temporary_directory / 'blue.epz'

    create_example_auto_device(target=target)

    assert target.is_file()


def test_contains_epc(tmpdir):
    temporary_directory = pathlib.Path(tmpdir)
    target = temporary_directory / 'blue.epz'

    create_example_auto_device(target=target)

    with zipfile.ZipFile(target) as z:
        assert any(name.endswith('.epc') for name in z.namelist())


@pytest.mark.require_device
@pytest_twisted.inlineCallbacks
def test_general_load(tmpdir):
    temporary_directory = pathlib.Path(tmpdir)
    device_path = temporary_directory/'device.epz'

    create_example_auto_device(target=device_path)

    real_bus = can.interface.Bus(bustype='socketcan', channel='can0')
    bus = epyqlib.busproxy.BusProxy(bus=real_bus)

    device = epyqlib.device.Device(
        file=device_path,
        archive_code=example_archive_code,
        node_id=247,
        bus=bus,
    )

    yield device.extension.no_gui_load_parameters()
