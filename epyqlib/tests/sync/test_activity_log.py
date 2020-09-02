import os
import time

import pytest
from twisted.internet.defer import ensureDeferred

from epyqlib.tabs.files.activity_log import ActivityLog, Event
# noinspection PyUnresolvedReferences
from epyqlib.tests.utils.test_fixtures import temp_dir

@pytest.inlineCallbacks
def test_activity_log(temp_dir):
    activity_log = ActivityLog(temp_dir)

    class Listener():
        def __init__(self):
            self.type = ""

        def inc(self, event: Event):
            self.type = event.type

    listener = Listener()

    activity_log.register_listener(listener.inc)
    yield ensureDeferred(activity_log.add(Event.new_push_to_inverter("", "")))

    assert listener.type == "push-to-inverter"

@pytest.inlineCallbacks
def test_removing(temp_dir):
    activity_log = ActivityLog(temp_dir)

    class RemovingListener():
        def event(self, event: Event):
            activity_log.remove(event)

    assert len(activity_log._activity_cache) == 0

    yield ensureDeferred(activity_log.add(Event.new_push_to_inverter("", "")))

    assert len(activity_log._activity_cache) == 1

    activity_log.register_listener(RemovingListener().event)
    yield ensureDeferred(activity_log.add(Event.new_push_to_inverter("", "")))

    assert len(activity_log._activity_cache) == 1


@pytest.inlineCallbacks
def test_writing_to_file(temp_dir):
    activity_log = ActivityLog(temp_dir)
    print(f"Using: {temp_dir}")
    cache_file = os.path.join(temp_dir, "activity-cache.json")
    assert not os.path.exists(cache_file)

    yield ensureDeferred(activity_log.add(Event.new_push_to_inverter("", "")))

    assert os.path.exists(cache_file)

@pytest.inlineCallbacks
def test_writing_and_reading_from_file(temp_dir):
    activity_log = ActivityLog(temp_dir)
    print(f"Using: {temp_dir}")
    event1 = Event.new_push_to_inverter("testInvId", "testUserId")
    yield ensureDeferred(activity_log.add(event1))

    activity_log = ActivityLog(temp_dir)

    assert activity_log.has_cached_events() is False
    activity_log._read_cache_file()

    event2 = activity_log.read_oldest_event()
    assert event1.inverter_id == event2.inverter_id

@pytest.inlineCallbacks
@pytest.mark.skip("Just here for benchmarking to make sure it's not too slow")
def test_benchmark_mass_writes(temp_dir):
    activity_log = ActivityLog(temp_dir)
    print(f"Using: {temp_dir}")

    start = time.time()
    for _ in range(1000):
        event = Event.new_push_to_inverter("testInvId", "testUserId")
        yield ensureDeferred(activity_log.add(event))
    elapsed = time.time() - start
    print(f"Writing 1000 events took {elapsed:.2f}")

    time.sleep(1)

    start = time.time()
    event = Event.new_push_to_inverter("testInvId", "testUserId")
    yield ensureDeferred(activity_log.add(event))
    elapsed = time.time() - start
    print(f"Writing last event took {elapsed:.2f}")

    activity_log = ActivityLog(temp_dir)
    start = time.time()
    activity_log._read_cache_file()
    elapsed = time.time() - start
    print(f"Reading 1001 events took {elapsed:.2f}")






