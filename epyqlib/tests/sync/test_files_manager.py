from os import path

from epyqlib.tabs.files.files_manager import FilesManager

# noinspection PyUnresolvedReferences
from epyqlib.tests.utils.test_fixtures import temp_dir


def test_hashing(temp_dir):
    empty_file_hash = "d41d8cd98f00b204e9800998ecf8427e"

    manager = FilesManager(temp_dir)
    with open(path.join(manager._cache_dir, "test"), "w") as test:
        test.write("test")

    open(path.join(manager._cache_dir, empty_file_hash), "w").close()

    manager.verify_cache()

    assert empty_file_hash in manager.hashes()
    assert "test" not in manager.hashes()
