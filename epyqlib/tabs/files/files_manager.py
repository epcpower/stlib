import hashlib
import os
from os import path

from epyqlib.tabs.files.files_utils import ensure_dir


class FilesManager:
    def __init__(self, files_dir):
        cache_dir = path.join(files_dir, "files")
        ensure_dir(cache_dir)
        self._cache_dir = cache_dir

    def verify_cache(self):
        for filename in self.hashes():
            hash = self._md5(filename)
            if hash != filename:
                print(f"File {filename} failed hash verification. Deleting.")
                os.unlink(path.join(self._cache_dir, filename))

    def _md5(self, filename: str) -> str:
        md5 = hashlib.md5()
        with open(path.join(self._cache_dir, filename), "rb") as file:
            for chunk in iter(lambda: file.read(4096), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def hashes(self):
        return os.listdir(self._cache_dir)

    def has_hash(self, hash: str) -> bool:
        return path.exists(path.join(self._cache_dir, hash))

    def get_file_path(self, filename: str):
        return path.join(self._cache_dir, filename)

    def stat(self, filename) -> os.stat_result:
        return os.stat(path.join(self._cache_dir, filename))

    def move_into_cache(self, file_path: str):
        basename = os.path.basename(file_path)
        return os.rename(file_path, path.join(self._cache_dir, basename))

    def delete_from_cache(self, hash: str):
        os.unlink(path.join(self._cache_dir, hash))
