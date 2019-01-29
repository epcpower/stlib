import hashlib
import json
import os
from os import path


class CacheManager:
    _hashes_file = path.join(os.getcwd(), 'hashes.json')

    def __init__(self, cache_dir="cache"):
        cache_dir = path.join(os.getcwd(), cache_dir)
        self._ensure_dir(cache_dir)
        self._cache_dir = cache_dir

        self._verify_hashes()

    def _save(self):
        with open(self._hashes_file, 'w') as file:
            json.dump(self._hashes, file, indent=2)

    def _verify_hashes(self):
        if path.exists(self._hashes_file):
            with open(self._hashes_file, 'r') as hashes:
                self._hashes = json.load(hashes)
        else:
            self._hashes = {}

        to_remove = []
        # Clear out files that are gone
        for hash, filename in self._hashes.items():
            if not path.exists(path.join(self._cache_dir, filename)):
                to_remove.append(hash)

        for hash in to_remove:
            del(self._hashes[hash])

        # Make sure every file on disk is in our hashes
        for file in os.listdir(self._cache_dir):
            filename = path.join(self._cache_dir, file)
            self._hashes[self._md5(filename)] = file

        self._save()

    def _md5(self, filename: str) -> str:
        md5 = hashlib.md5()
        with open(filename, "rb") as file:
            for chunk in iter(lambda: file.read(4096), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def _ensure_dir(self, dir_name):
        if path.exists(dir_name):
            if path.isdir(dir_name):
                return
            else:
                raise NotADirectoryError(f"Files cache dir {dir_name} already exists but is not a directory")
        os.mkdir(dir_name)

    def filenames(self):
        return self._hashes.values()

    def stat(self, filename) -> os.stat_result:
        return os.stat(path.join(self._cache_dir, filename))
