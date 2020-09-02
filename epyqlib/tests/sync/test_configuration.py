import tempfile
import os
import time

import pytest

from epyqlib.tabs.files.sync_config import SyncConfig, ConfigurationError, Vars

tempdir = tempfile.gettempdir()
filename = f'test-{int(time.time()) % 100000}.json'
full_path = os.path.join(tempdir, filename)

def load_configuration():
    print(f'Using temp dir {full_path}')
    return SyncConfig(tempdir, filename)

def cleanup():
    os.unlink(full_path)


def test_read():
    configuration = load_configuration()
    assert configuration.get("username") is None
    configuration.set("username", "123")
    assert configuration.get("username") == "123"

    configuration = load_configuration()
    assert configuration.get("username") == "123"

    cleanup()


def test_invalid_json():
    with open(full_path, 'w') as file:
        file.write("[1,2,3]")
    with pytest.raises(ConfigurationError):
        load_configuration()
    cleanup()



