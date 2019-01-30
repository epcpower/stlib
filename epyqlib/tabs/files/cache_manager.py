import hashlib
import json
import os
from os import path


class CacheManager:

    def __init__(self, cache_dir="cache"):
        cache_dir = path.join(os.getcwd(), cache_dir)
        self._ensure_dir(cache_dir)
        self._cache_dir = cache_dir

        self._verify_hashes()

    def _verify_hashes(self):
        for filename in self.hashes():
            hash = self._md5(filename)
            if (hash != filename):
                print(f"File {filename} failed hash verification. Deleting.")
                os.unlink(path.join(self._cache_dir, filename))

    def _md5(self, filename: str) -> str:
        md5 = hashlib.md5()
        with open(path.join(self._cache_dir, filename), "rb") as file:
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

    def hashes(self):
        return os.listdir(self._cache_dir)

    def has_hash(self, hash: str) -> bool:
        return path.exists(path.join(self._cache_dir, hash))

    def get_file_ref(self, filename: str, mode: str):
        return open(path.join(self._cache_dir, filename), mode)

    def stat(self, filename) -> os.stat_result:
        return os.stat(path.join(self._cache_dir, filename))
