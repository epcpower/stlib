import attr

from epyqlib.tabs.files.activity_log import ActivityLog, Event
from epyqlib.tabs.files.graphql import API


@attr.s(slots=True, auto_attribs=True)
class ActivitySyncer:
    activityLog: ActivityLog
    api: API
    _syncing: bool = attr.ib(default=False)
    _is_offline: bool = attr.ib(default=False)

    def set_offline(self, is_offline: bool):
        self._is_offline = is_offline

    async def listener(self, _: Event):
        if self._is_offline is True:
            return

        if self._syncing is True:
            return

        self._syncing = True
        try:
            while self.activityLog.has_cached_events() is True:
                event: Event = self.activityLog.read_oldest_event()
                result = await self.api.create_activity(event)
                self.activityLog.remove(event)
        finally:
            self._syncing = False
