import pathlib

import attr
import pytest

import epyqlib.tests.common
import epyqlib.hildevice


@pytest.fixture
def factory_definition():
    original = pathlib.Path(epyqlib.tests.common.devices['factory'])
    with epyqlib.updateepc.updated(original) as updated:
        return epyqlib.hildevice.Definition.loadp(updated)


@pytest.mark.parametrize('version', [[1], [3]])
def test_definition_format_version_validator(factory_definition, version):
    with pytest.raises(epyqlib.hildevice.FormatVersionError):
        attr.evolve(factory_definition, format_version=version)


def test_definition_load(factory_definition):
    assert factory_definition.access_level_path is not None
    assert factory_definition.access_password_path is not None


def test_definition_loads():
    path = pathlib.Path(epyqlib.tests.common.devices['factory'])

    with epyqlib.updateepc.updated(path) as updated:
        with open(updated) as f:
            s = f.read()

        epyqlib.hildevice.Definition.loads(
            s=s,
            base_path=updated.parents[0],
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
