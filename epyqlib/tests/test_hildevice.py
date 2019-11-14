import os
import shutil
import pathlib

import attr
import pytest

import epyqlib.tests.common
import epyqlib.hildevice


@pytest.fixture
def factory_definition():
    return epyqlib.hildevice.Definition.loadp(
        epyqlib.tests.common.devices['factory'],
    )


def test_definition_format_version_validator(factory_definition):
    with pytest.raises(epyqlib.hildevice.FormatVersionError):
        attr.evolve(factory_definition, format_version=[1])
    with pytest.raises(epyqlib.hildevice.FormatVersionError):
        attr.evolve(factory_definition, format_version=[3])


def test_definition_load(factory_definition):
    assert factory_definition.base_path.is_dir()
    assert factory_definition.can_path.exists()
    assert factory_definition.access_level_path is not None
    assert factory_definition.access_password_path is not None


def test_definition_loads():
    path = pathlib.Path(epyqlib.tests.common.devices['factory'])

    # Hack to avoid needing to update test files to latest version
    # Probably need to identify better way of checking files
    # without needing to upload actual development .epc/.epz/.pmvs ...
    if not epyqlib.updateepc.is_latest(path):
        path_old = pathlib.Path(str(path.resolve()) + '_old')
        shutil.copy2(path, path_old)
        path = pathlib.Path(epyqlib.updateepc.convert(
            path_old,
            os.path.dirname(path_old),
        ))

    with open(path) as f:
        s = f.read()

    epyqlib.hildevice.Definition.loads(
        s=s,
        base_path=path.parents[0],
    )


def test_load():
    device = epyqlib.hildevice.Device(
        definition_path=epyqlib.tests.common.devices['factory'],
    )
    device.load()


def test_device_reload():
    device = epyqlib.hildevice.Device(
        definition_path=epyqlib.tests.common.devices['factory'],
    )
    device.load()

    with pytest.raises(epyqlib.hildevice.AlreadyLoadedError):
        device.load()
