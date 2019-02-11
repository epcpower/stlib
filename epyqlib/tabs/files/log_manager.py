import hashlib
import json
import os
import shutil
from os import path


class LogManager:
    _instance: 'LogManager' = None

    def __init__(self, files_dir: str):
        # if LogManager._instance is not None:
        #     raise Exception("LogManager being created instead of using singleton")

        self._hashes_file = path.join(files_dir, "log-hashes.json")
        self._cache_dir = path.join(files_dir, "raw")
        self._ensure_dir(self._cache_dir)

        self._hashes: dict[str, str] = {}

        self._read_hashes_files()

        # self._verify_hashes()

    @staticmethod
    def get_instance():
        if LogManager._instance is None:
            raise Exception("LogManager being used before initialized")
        return LogManager._instance

    @staticmethod
    def init(files_dir: str):
        LogManager._instance = LogManager(files_dir)
        return LogManager._instance

    def copy_into_cache(self, file_path: str):
        basename = os.path.basename(file_path)
        hash = self._md5(file_path)
        shutil.copy2(file_path, path.join(self._cache_dir, hash))
        self._hashes[hash] = basename
        self._save_hashes_file()


    def _save_hashes_file(self):
        with open(self._hashes_file, 'w') as file:
            json.dump(self._hashes, file, indent=2)

    def _read_hashes_files(self):
        if path.exists(self._hashes_file):
            with open(self._hashes_file, 'r') as hashes:
                self._hashes = json.load(hashes)

    def _verify_hashes(self):
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

        self._save_hashes_file()

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

    def has_hash(self, hash: str) -> bool:
        return hash in self._hashes

    def get_file_ref(self, filename: str, mode: str):
        return open(path.join(self._cache_dir, filename), mode)

    def stat(self, filename) -> os.stat_result:
        return os.stat(path.join(self._cache_dir, filename))
