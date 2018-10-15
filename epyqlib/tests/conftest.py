import contextlib
import glob
import os
import shutil
import zipfile

import pytest

with contextlib.suppress(ImportError):
    import epyqlib.collectdevices
import epyqlib.tests.common


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
