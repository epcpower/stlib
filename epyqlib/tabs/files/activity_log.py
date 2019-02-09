import inspect
from abc import ABC
from collections import Callable
from datetime import datetime

import attr
from typing import Union

from twisted.internet.defer import ensureDeferred


@attr.s(slots=True, auto_attribs=True)
class ParamSetEvent():
    paramName: str
    paramValue: str
    type = "param-set"


@attr.s(slots=True, auto_attribs=True)
class FaultClearedEvent():
    faultCode: str
    type = "fault-cleared"

@attr.s(slots=True, auto_attribs=True)
class PushToInverterEvent():
    type = "push-to-inverter"


EventDetails = Union[FaultClearedEvent, ParamSetEvent, PushToInverterEvent]


@attr.s(slots=True, auto_attribs=True)
class Event():
    inverterId: str
    userId: str
    details: EventDetails
    timestamp: str = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")


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


