from epyqlib.tabs.files.activity_log import ActivityLog, Event, PushToInverterEvent


def test_activity_log():
    activity_log = ActivityLog()

    class Listener():
        def __init__(self):
            self.type = ""

        def inc(self, event: Event):
            self.type = event.details.type

    listener = Listener()

    activity_log.register_listener(listener.inc)
    activity_log.add(Event("", "", PushToInverterEvent()))

    assert listener.type == "push-to-inverter"

def test_removing():
    activity_log = ActivityLog()

    class RemovingListener():
        def event(self, event: Event):
            activity_log.remove(event)

    assert len(activity_log._activity_cache) == 0

    activity_log.add(Event("", "", PushToInverterEvent()))

    assert len(activity_log._activity_cache) == 1

    activity_log.register_listener(RemovingListener().event)
    activity_log.add(Event("", "", PushToInverterEvent()))

    assert len(activity_log._activity_cache) == 1

