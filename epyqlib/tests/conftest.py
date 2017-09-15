import glob
import os
import shutil
import zipfile

import pytest

import epyqlib.collectdevices
import epyqlib.tests.common


def pytest_addoption(parser):
    parser.addoption(
        '--device-present',
        action='store_true',
        default=False,
        help='Run tests that require a device be connected'
    )
    parser.addoption(
        '--run-factory',
        action='store_true',
        default=False,
        help='Run tests that require a factory device file'
    )


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--device-present"):
        device_present = pytest.mark.skip(
            reason="need --device-present option to run",
        )
        for item in items:
            if "require_device" in item.keywords:
                item.add_marker(device_present)

    if not config.getoption("--run-factory"):
        factory = pytest.mark.skip(
            reason="need --run-factory option to run",
        )
        for item in items:
            if "factory" in item.keywords:
                item.add_marker(factory)


@pytest.fixture
def zipped_customer_device_path(tmpdir):
    name = 'customer'
    path = epyqlib.tests.common.devices['customer']

    epyqlib.collectdevices.collect(
        devices={
            name: {
                'file': os.path.basename(path),
                'groups': ('a',)
            },
        },
        output_directory=tmpdir,
        dry_run=False,
        groups=('a',),
        device_path=path,
        in_repo=False,
    )

    return os.path.join(tmpdir, '{}.epz'.format(name))


@pytest.fixture
def customer_device_path(tmpdir, zipped_customer_device_path):
    zip = zipfile.ZipFile(zipped_customer_device_path)
    zip.extractall(tmpdir)
    path, = glob.glob(os.path.join(tmpdir, '**', '*.epc'), recursive=True)

    return path
