import os

# noinspection PyUnresolvedReferences
import pytest
from twisted.internet.defer import ensureDeferred

from epyqlib.tests.utils.test_fixtures import temp_dir
from epyqlib.tabs.files.activity_log import ActivityLog, Event


def test_activity_log(temp_dir):
    activity_log = ActivityLog(temp_dir)

    class Listener():
        def __init__(self):
            self.type = ""

        def inc(self, event: Event):
            self.type = event.type

    listener = Listener()

    activity_log.register_listener(listener.inc)
    activity_log.add(Event.new_push_to_inverter("", ""))

    assert listener.type == "push-to-inverter"

def test_removing(temp_dir):
    activity_log = ActivityLog(temp_dir)

    class RemovingListener():
        def event(self, event: Event):
            activity_log.remove(event)

    assert len(activity_log._activity_cache) == 0

    activity_log.add(Event.new_push_to_inverter("", ""))

    assert len(activity_log._activity_cache) == 1

    activity_log.register_listener(RemovingListener().event)
    activity_log.add(Event.new_push_to_inverter("", ""))

    assert len(activity_log._activity_cache) == 1


@pytest.inlineCallbacks
def test_writing_to_file(temp_dir):
    activity_log = ActivityLog(temp_dir)
    print(f"Using: {temp_dir}")
    cache_file = os.path.join(temp_dir, "activity-cache.json")
    assert not os.path.exists(cache_file)

    yield ensureDeferred(activity_log.add(Event.new_push_to_inverter("", "")))

    assert os.path.exists(cache_file)

    # with open(cache_file, "r") as file:
    #     for lines in file.readlines():
    #         print(lines, end='')