import inspect
from collections import Callable
from datetime import datetime
# from typing import Union

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


@attr.s(slots=True, auto_attribs=True)
class Event():
    inverterId: str
    userId: str
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



class ActivityLog:
    _instance = None

    def __init__(self):
        self._activity_cache: [Event] = []
        self._listeners = []

    @staticmethod
    def get_instance():
        if ActivityLog._instance is None:
            ActivityLog._instance = ActivityLog()
        return ActivityLog._instance

    def register_listener(self, listener: Callable):
        self._listeners.append(listener)

    def remove(self, event: Event):
        self._activity_cache.remove(event)

    def _notify_listeners(self, event: Event):
        for listener in self._listeners:
            result = listener(event)
            if inspect.iscoroutine(result):
                ensureDeferred(result)


    def add(self, event: Event):
        self._activity_cache.append(event)
        self._notify_listeners(event)

    def has_cached_events(self):
        return len(self._activity_cache) > 0

    def read_oldest_event(self):
        if not self.has_cached_events():
            return None

        return self._activity_cache[0]

