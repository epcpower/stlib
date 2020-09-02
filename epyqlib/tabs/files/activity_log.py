import inspect
import pickle
import time
from collections import Callable
from datetime import datetime
from os import path
from typing import Union

import attr

from epyqlib.tabs.files.sync_config import SyncConfig


@attr.s(slots=True, auto_attribs=True)
class Event:
    class Type:
        fault_cleared = "fault-cleared"
        firmware_flashed = "firmware-flashed"
        inverter_to_nv = "inverter-to-nv"
        load_param_file = "load-param-file"
        push_to_inverter = "push-to-inverter"
        param_set = "param-set"
        new_raw_log = "new-raw-log"

    inverter_id: str
    user_id: str
    type: str
    details: dict
    timestamp: str = attr.ib(
        factory=lambda: datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    @staticmethod
    def new_fault_cleared(inverter_id: str, user_id: str, fault_code: Union[str, int]):
        if isinstance(fault_code, int):
            fault_code = str(fault_code)

        details = {"faultCode": fault_code}
        return Event(inverter_id, user_id, Event.Type.fault_cleared, details)

    @staticmethod
    def new_firmware_flashed(inverter_id: str, user_id: str, build_id: str):
        details = {"buildId": build_id}
        return Event(inverter_id, user_id, Event.Type.firmware_flashed, details)

    @staticmethod
    def new_inverter_to_nv(inverter_id: str, user_id: str):
        return Event(inverter_id, user_id, Event.Type.inverter_to_nv, {})

    @staticmethod
    def new_param_set_event(
        inverter_id: str, user_id: str, param_name: str, param_value: str
    ):
        return Event(
            inverter_id,
            user_id,
            Event.Type.param_set,
            {"paramName": param_name, "paramValue": param_value},
        )

    @staticmethod
    def new_load_param_file(
        inverter_id: str, user_id: str, file_id: str, file_hash: str, filename: str
    ):
        details = {"fileId": file_id, "fileHash": file_hash, "filename": filename}
        return Event(inverter_id, user_id, Event.Type.load_param_file, details)

    @staticmethod
    def new_push_to_inverter(inverter_id: str, user_id: str):
        return Event(inverter_id, user_id, Event.Type.push_to_inverter, {})

    @staticmethod
    def new_raw_log(
        inverter_id: str,
        user_id: str,
        build_id: str,
        serial_number: str,
        filename: str,
        file_hash: str,
    ):
        details = {
            "buildId": build_id,
            "fileHash": file_hash,
            "filename": filename,
            "serialNumber": serial_number,
        }
        return Event(inverter_id, user_id, Event.Type.new_raw_log, details)


class ActivityLog:
    _instance = None

    def __init__(self, file_dir=None):
        file_dir = file_dir or SyncConfig.get_instance().config_dir

        self._cache_file = path.join(file_dir, "activity-cache.json")

        self._activity_cache: [Event] = []
        self._listeners = []
        self._last_write_time = 0

    @staticmethod
    def get_instance():
        if ActivityLog._instance is None:
            ActivityLog._instance = ActivityLog()
            ActivityLog._instance._read_cache_file()
        return ActivityLog._instance

    ## Managing listeners
    def register_listener(self, listener: Callable):
        self._listeners.append(listener)

    async def _notify_listeners(self, event: Event):
        coroutines = []
        for listener in self._listeners:
            result = listener(event)
            if inspect.iscoroutine(result):
                coroutines.append(result)

        for coroutine in coroutines:
            await coroutine

    ## Adding and removing events
    async def add(self, event: Event):
        self._activity_cache.append(event)

        cache_write = self._write_cache_file()

        await self._notify_listeners(event)

        await cache_write

    def remove(self, event: Event):
        self._activity_cache.remove(event)

    ## Reading events
    def has_cached_events(self):
        return len(self._activity_cache) > 0

    def read_oldest_event(self) -> Union[Event, None]:
        if not self.has_cached_events():
            return None

        return self._activity_cache[0]

    ## Cache file management
    def _read_cache_file(self):
        if path.exists(self._cache_file):
            with open(self._cache_file, "rb") as cache:
                cached_events = pickle.load(cache)
                if not isinstance(cached_events, list):
                    raise Exception(
                        f"Error reading from {self._cache_file}. Not a pickle file with a list as the root."
                    )
                self._activity_cache = cached_events + self._activity_cache

    async def _write_cache_file(self):
        now = time.time()

        if self._last_write_time + 1 > now:
            # Don't write more often than once/sec
            return

        self._last_write_time = now

        with open(self._cache_file, "wb") as file_ref:
            pickle.dump(self._activity_cache, file_ref)
