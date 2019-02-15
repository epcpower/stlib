import hashlib
import inspect
import json
import os
import shutil
from enum import Enum
from os import path

from typing import Tuple, Callable, Coroutine

from epyqlib.tabs.files.bucket_manager import BucketManager

LogSyncedListener = Callable[[str], Coroutine]

class LogManager:
    _instance: 'LogManager' = None

    class EventType(Enum):
        log_generated = 1
        log_synced = 2

    def __init__(self, files_dir: str):
        # if LogManager._instance is not None:
        #     raise Exception("LogManager being created instead of using singleton")

        self._hashes_file = path.join(files_dir, "log-hashes.json")
        self._cache_dir = path.join(files_dir, "raw")
        self._ensure_dir(self._cache_dir)
        self._listeners: list[LogSyncedListener] = []

        # self._hashes: set[Tuple[str, str]] = set()
        self._hashes: dict[str, str] = {}

        self._read_hashes_files()

        self._bucket_manager = BucketManager() # Does not necessarily need to be singleton?

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

        self._notify_listeners(LogManager.EventType.log_generated, hash)

    def _save_hashes_file(self):
        with open(self._hashes_file, 'w') as file:
            json.dump(self._hashes, file, indent=2)

    def _read_hashes_files(self):
        if path.exists(self._hashes_file):
            with open(self._hashes_file, 'r') as hashes:
                self._hashes = json.load(hashes)


    def _verify_hashes(self):
        to_remove = set()
        # Clear out files that are gone
        for item in self._hashes.items():
            hash, filename = item
            if not path.exists(path.join(self._cache_dir, filename)):
                to_remove.add(hash)

        for item in to_remove:
            del(self._hashes[item])

        # Make sure every file on disk is in our hashes
        for filename in os.listdir(self._cache_dir):
            full_path = path.join(self._cache_dir, filename)
            self._hashes[self._md5(full_path)] = filename

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

    async def sync_logs_to_server(self):
        uploaded_logs = self._bucket_manager.fetch_uploaded_log_names()
        for hash, filename in self._hashes.items():
            if hash not in uploaded_logs:
                await self._bucket_manager.upload_log(path.join(self._cache_dir, hash), hash)

            for listener in self._listeners:
                result = listener(LogManager.EventType.log_synced, hash)
                if inspect.iscoroutine(result):
                    await result

    def items(self):
        return self._hashes.items()

    def filenames(self):
        return self._hashes.values()

    def has_hash(self, hash: str) -> bool:
        return hash in self._hashes

    def get_file_ref(self, filename: str, mode: str):
        return open(path.join(self._cache_dir, filename), mode)

    def stat(self, filename) -> os.stat_result:
        return os.stat(path.join(self._cache_dir, filename))

    ## Listener Management
    def register_listener(self, listener: Callable):
        self._listeners.append(listener)

    async def _notify_listeners(self, event_type: EventType, hash: str):
        for listener in self._listeners:
            result = listener(event_type, hash)
            if inspect.iscoroutine(result):
                await result
