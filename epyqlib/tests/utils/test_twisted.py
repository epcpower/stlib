import gc
import time

import attr
import pytest
import twisted.internet.defer
import twisted.logger

import epyqlib.utils.twisted


@attr.s
class Elapsed:
    clock = attr.ib(default=time.monotonic)
    start = attr.ib()

    @start.default
    def _(self):
        return self.clock()

    def number_string(self):
        now = time.monotonic() - self.start
        return now, 'T+ {:.1f}s'.format(now)


@attr.s
class Result:
    time = attr.ib()
    data = attr.ib()


@attr.s
class ActionLogger:
    elapsed = attr.ib(default=attr.Factory(Elapsed))
    log = attr.ib(default=attr.Factory(list))

    expected = attr.ib(default=attr.Factory(list))

    def action(self, data):
        now, s = self.elapsed.number_string()
        print(s, data)
        self.log.append(Result(time=now, data=data))

    def check(self):
        assert len(self.expected) == len(self.log)
        for result, expected in zip(self.log, self.expected):
            assert abs(result.time - expected.time) < 0.050
            assert expected.data == result.data


@pytest.fixture(
    params=[
        pytest.param(
            'flaky',
            marks=pytest.mark.flaky(reruns=5),
        ),
    ],
)
def action_logger():
    logger = ActionLogger()
    yield logger
    logger.check()


# https://github.com/pytest-dev/pytest-twisted/issues/4#issuecomment-360888462
class Observer:
    def __init__(self):
        self.failures = []

    def __call__(self, event_dict):
        is_error = event_dict.get('isError')
        s = 'Unhandled error in Deferred'.casefold()
        is_unhandled = s in event_dict.get('log_format', '').casefold()

        if is_error and is_unhandled:
            self.failures.append(event_dict)

    def check(self):
        assert [] == self.failures


@pytest.fixture
def assert_no_unhandled_errbacks():
    observer = Observer()
    twisted.logger.globalLogPublisher.addObserver(observer)

    yield

    # deferred's err for being unhandled in __del__ so...  try and hope
    gc.collect()
    twisted.logger.globalLogPublisher.removeObserver(observer)

    observer.check()


@pytest.inlineCallbacks
def test_sequence_normal(action_logger, assert_no_unhandled_errbacks):
    sequence = epyqlib.utils.twisted.Sequence()
    t = 0
    delay = 0.3
    for n in range(3):
        sequence.add_delayed(delay, action_logger.action, n)
        t += delay
        action_logger.expected.append(Result(time=t, data=n))

    yield sequence.run()


@pytest.inlineCallbacks
def test_sequence_cancelled(action_logger, assert_no_unhandled_errbacks):
    sequence = epyqlib.utils.twisted.Sequence()
    t = 0
    delay = 0.3
    for n in range(3):
        sequence.add_delayed(delay, action_logger.action, n)
        t += delay
        action_logger.expected.append(Result(time=t, data=n))

    cancel_time = action_logger.expected.pop().time - (delay / 2)

    deferred = sequence.run()

    yield epyqlib.utils.twisted.sleep(cancel_time)
    sequence.cancel()

    with pytest.raises(twisted.internet.defer.CancelledError):
        yield deferred


@pytest.inlineCallbacks
def test_sequence_loop(action_logger, assert_no_unhandled_errbacks):
    sequence = epyqlib.utils.twisted.Sequence()
    t = 0
    delay = 0.3
    for repeat in (False, True, True):
        for n in range(3):
            if not repeat:
                sequence.add_delayed(delay, action_logger.action, n)
            t += delay
            action_logger.expected.append(Result(time=t, data=n))

    cancel_time = action_logger.expected[-1].time + (delay / 2)

    deferred = sequence.run(loop=True)

    yield epyqlib.utils.twisted.sleep(cancel_time)
    sequence.cancel()

    with pytest.raises(twisted.internet.defer.CancelledError):
        yield deferred


@pytest.inlineCallbacks
def test_sequence_pause(action_logger, assert_no_unhandled_errbacks):
    sequence = epyqlib.utils.twisted.Sequence()
    t = 0
    delay = 0.3
    for n in range(3):
        sequence.add_delayed(delay, action_logger.action, n)
        t += delay
        action_logger.expected.append(Result(time=t, data=n))

    pause_before = 1

    pause_time = action_logger.expected[pause_before].time - (delay / 2)
    unpause_time = pause_time + 1

    for expected in action_logger.expected[pause_before:]:
        expected.time += unpause_time - pause_time

    deferred = sequence.run()

    twisted.internet.reactor.callLater(pause_time, sequence.pause)
    twisted.internet.reactor.callLater(unpause_time, sequence.unpause)

    yield deferred


@pytest.inlineCallbacks
def test_sequence_pause_event(action_logger, assert_no_unhandled_errbacks):
    sequence = epyqlib.utils.twisted.Sequence()
    t = 0
    delay = 0.3
    for n in range(3):
        sequence.add_delayed(delay, action_logger.action, n, )
        t += delay
        action_logger.expected.append(Result(time=t, data=n))

    pause_before = 2

    pause_data = object()

    def pause():
        sequence.pause()
        action_logger.action(pause_data)

    pause_time = sequence.events[pause_before].time
    pause_event = epyqlib.utils.twisted.Event(
        time=pause_time,
        action=epyqlib.utils.twisted.Action(f=pause),
    )

    sequence.events.insert(pause_before, pause_event)
    action_logger.expected.insert(
        pause_before,
        Result(time=pause_time, data=pause_data),
    )

    pause_duration = 1
    unpause_time = pause_time + pause_duration

    for expected in action_logger.expected[pause_before + 1:]:
        expected.time += pause_duration

    deferred = sequence.run()

    yield epyqlib.utils.twisted.sleep(unpause_time)
    sequence.unpause()

    yield deferred


@pytest.inlineCallbacks
def test_sequence_stop_while_paused(action_logger, assert_no_unhandled_errbacks):
    sequence = epyqlib.utils.twisted.Sequence()
    t = 0
    delay = 0.3
    for n in range(3):
        sequence.add_delayed(delay, action_logger.action, n)
        t += delay
        action_logger.expected.append(Result(time=t, data=n))

    pause_before = 2

    pause_time = action_logger.expected[pause_before].time - (delay / 2)

    action_logger.expected = action_logger.expected[:pause_before]

    deferred = sequence.run()

    yield epyqlib.utils.twisted.sleep(pause_time)
    sequence.pause()

    yield epyqlib.utils.twisted.sleep(1)
    sequence.cancel()

    with pytest.raises(twisted.internet.defer.CancelledError):
        yield deferred
