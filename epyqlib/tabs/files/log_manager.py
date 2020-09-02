import hashlib
import inspect
import json
import os
import shutil
from datetime import datetime
from enum import Enum
from os import path
from typing import Union, List, Callable, Coroutine

import attr

from epyqlib.tabs.files.files_utils import ensure_dir

NewLogListener = Callable[[str], Coroutine]


@attr.s(slots=True, auto_attribs=True)
class PendingLog:
    hash: str
    filename: str
    build_id: str = None
    serial_number: str = None
    username = "Current User"
    notes = ""
    timestamp = datetime.now()


class LogManager:
    _instance: "LogManager" = None
    _tag = "[Log Manager]"

    class EventType(Enum):
        log_generated = 1
        log_synced = 2

    def __init__(self, files_dir: str):
        # if LogManager._instance is not None:
        #     raise Exception("LogManager being created instead of using singleton")

        self._cache_dir = path.join(files_dir, "pending_logs")
        ensure_dir(self._cache_dir)

        self._pending_logs_file = path.join(files_dir, "pending-logs.json")
        self._pending_logs: List[PendingLog] = []

        self._listeners: List[NewLogListener] = []

    @staticmethod
    def get_instance():
        if LogManager._instance is None:
            raise Exception("LogManager being used before initialized")
        return LogManager._instance

    @staticmethod
    def init(files_dir: str):
        LogManager._instance = LogManager(files_dir)
        LogManager._instance._read_pending_log_file()
        return LogManager._instance

    async def add_pending_log(self, file_path: str, build_id: str, serial_number: str):
        basename = os.path.basename(file_path)
        hash = self._md5(file_path)
        shutil.copy2(file_path, path.join(self._cache_dir, hash))

        new_log = PendingLog(hash, basename, build_id, serial_number)
        self._pending_logs.append(new_log)
        self._save_pending_log_file()

        await self._notify_listeners(new_log)

    def _save_pending_log_file(self):
        # Don't save anything if there's nothing to save
        if len(self._pending_logs) == 0:
            if os.path.exists(self._pending_logs_file):
                os.unlink(self._pending_logs_file)
            return

        with open(self._pending_logs_file, "w") as file:
            data = [attr.asdict(log) for log in self._pending_logs]
            json.dump(data, file, indent=2)

    def _read_pending_log_file(self):
        if not path.exists(self._pending_logs_file):
            return

        with open(self._pending_logs_file, "r") as file:
            data: List[dict] = json.load(file)
            for log in data:
                self._pending_logs.append(PendingLog(**log))

    def get_path_to_log(self, hash: str):
        return path.join(self._cache_dir, hash)

    def get_pending_logs(self) -> List[PendingLog]:
        return self._pending_logs

    def get_next_pending_log(self) -> Union[PendingLog, None]:
        if len(self._pending_logs) > 0:
            return self._pending_logs[0]
        else:
            return None

    def remove_pending(self, log: PendingLog):
        self._pending_logs.remove(log)
        self._save_pending_log_file()

    def _md5(self, filename: str) -> str:
        md5 = hashlib.md5()
        with open(filename, "rb") as file:
            for chunk in iter(lambda: file.read(4096), b""):
                md5.update(chunk)
        return md5.hexdigest()

    def get_file_ref(self, filename: str, mode: str):
        return open(path.join(self._cache_dir, filename), mode)

    def stat(self, filename) -> os.stat_result:
        return os.stat(path.join(self._cache_dir, filename))

    ## Listener Management
    ## Listener fires when new log is added
    def add_listener(self, listener: NewLogListener):
        self._listeners.append(listener)

    def remove_listener(self, listener: NewLogListener):
        self._listeners.remove(listener)

    async def _notify_listeners(self, log: PendingLog):
        for listener in self._listeners:
            result = listener(log)
            if inspect.iscoroutine(result):
                await result
