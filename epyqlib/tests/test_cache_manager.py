# noinspection PyUnresolvedReferences
import os
from os import path

from epyqlib.tabs.files.cache_manager import CacheManager

# noinspection PyUnresolvedReferences
from epyqlib.tests.utils.test_fixtures import temp_dir


def test_hashing(temp_dir):
    empty_file_hash = "d41d8cd98f00b204e9800998ecf8427e"

    with open(path.join(temp_dir, "test"), "w") as test:
        test.write("test")

    open(path.join(temp_dir, empty_file_hash), "w").close()

    manager = CacheManager(temp_dir)

    assert empty_file_hash in manager.hashes()
    assert "test" not in manager.hashes()
