import inspect
import json
from collections import Callable
from datetime import datetime
import time
from os import path

import attr
from twisted.internet.defer import ensureDeferred


# @attr.s(slots=True, auto_attribs=True)
# class ParamSetEvent():
#     paramName: str
#     paramValue: str
#     type = "param-set"
#
#
# @attr.s(slots=True, auto_attribs=True)
# class FaultClearedEvent():
#     faultCode: str
#     type = "fault-cleared"
#
# @attr.s(slots=True, auto_attribs=True)
# class PushToInverterEvent():
#     type: str = attr.ib(default="push-to-inverter")


# EventDetails = Union[FaultClearedEvent, ParamSetEvent, PushToInverterEvent]
from epyqlib.tabs.files.configuration import Configuration


@attr.s(slots=True, auto_attribs=True)
class Event():
    inverter_id: str
    user_id: str
    # details: EventDetails
    type: str
    details: dict
    timestamp: str = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")

    @staticmethod
    def new_push_to_inverter(inverter_id: str, user_id: str):
        return Event(inverter_id, user_id, "push-to-inverter", {})

    @staticmethod
    def new_param_set_event(inverter_id: str, user_id: str, param_name: str, param_value: str):
        return Event(inverter_id, user_id, "param-set", {"paramName": param_name, "paramValue": param_value})

    def to_dict(self):
        return {
            'details': self.details,
            'inverterId': self.inverter_id,
            'timestamp': self.timestamp,
            'type': self.type,
            'userId': self.user_id
        }



class ActivityLog:
    _instance = None

    def __init__(self, file_dir=None):
        file_dir = file_dir or Configuration.get_instance().directory

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

    def _notify_listeners(self, event: Event):
        for listener in self._listeners:
            result = listener(event)
            if inspect.iscoroutine(result):
                ensureDeferred(result)

    ## Adding and removing events
    async def add(self, event: Event):
        self._activity_cache.append(event)

        cache_write = self._write_cache_file()

        self._notify_listeners(event)

        await cache_write


    def remove(self, event: Event):
        self._activity_cache.remove(event)

    ## Reading events
    def has_cached_events(self):
        return len(self._activity_cache) > 0

    def read_oldest_event(self):
        if not self.has_cached_events():
            return None

        return self._activity_cache[0]

    ## Cache file management
    def _read_cache_file(self):
        if path.exists(self._cache_file):
            with open(self._cache_file, 'rb') as cache:
                cached_events = json.load(cache)
                if not isinstance(cached_events, list):
                    raise Exception(f"Error reading from {self._cache_file}. Not a JSON file with a list as the root.")
                self._activity_cache = cached_events + self._activity_cache

    async def _write_cache_file(self):
        now = time.time()

        if (self._last_write_time + 1 > now):
            # Don't write more often than once/sec
            return

        self._last_write_time = now

        e: Event
        # event_dict = map(lambda e: e.to_dict(), self._activity_cache)
        event_dicts = [e.to_dict() for e in self._activity_cache]

        with open(self._cache_file, 'w') as file_ref:
            json.dump(event_dicts, file_ref, indent=2)


