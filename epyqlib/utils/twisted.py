import decimal
import logging
import time

import attr
import twisted.internet.defer

import epyqlib.utils.general
import epyqlib.utils.qt

__copyright__ = 'Copyright 2016, EPC Power Corp.'
__license__ = 'GPLv2+'


logger = logging.getLogger(__name__)


class RequestTimeoutError(TimeoutError):
    pass


class WaitForTimedOut(Exception):
    pass


@twisted.internet.defer.inlineCallbacks
def wait_for(check, period=0.1, timeout=10, message=None):
    if message is None:
        message = f'Condition not satisfied within {timeout:.1f} seconds'

    start = time.monotonic()

    while True:
        done = yield check()
        if done:
            return

        if time.monotonic() - start > timeout:
            raise WaitForTimedOut(message)

        yield epyqlib.utils.twisted.sleep(period)


def ignore_cancelled(f):
    async def wrapper(*args, **kwargs):
        try:
            return await f(*args, **kwargs)
        except twisted.internet.defer.CancelledError:
            pass

    return wrapper


def ensure_deferred(f):
    def wrapper(*args, **kwargs):
        return twisted.internet.defer.ensureDeferred(f(*args, **kwargs))

    return wrapper


def errback_dialog(f):
    async def wrapper(*args, **kwargs):
        try:
            return await f(*args, **kwargs)
        except Exception as e:
            epyqlib.utils.twisted.errbackhook(
                twisted.python.failure.Failure(e),
            )

    return wrapper


def errbackhook(error):
    epyqlib.utils.qt.custom_exception_message_box(
        brief='{}\n{}'.format(error.type.__name__, error.value),
        extended=error.getTraceback(),
    )

    return error


def discard_cancelled(failure):
    if issubclass(failure.type, twisted.internet.defer.CancelledError):
        return None

    return failure


def catch_expected(error):
    if issubclass(error.type, epyqlib.utils.general.ExpectedException):
        epyqlib.utils.qt.raw_exception_message_box(
            brief=error.value.expected_message(),
            extended=error.getTraceback(),
        )

        return None

    return error


def detour_result(result, f, *args, **kwargs):
    f(*args, **kwargs)

    return result


def logit(it):
    logger.debug('logit(): ({}) {}'.format(type(it), it))

    if isinstance(it, twisted.python.failure.Failure):
        it.printDetailedTraceback()


@twisted.internet.defer.inlineCallbacks
def retry(function, times, acceptable=None):
    if acceptable is None:
        acceptable = []

    remaining = times
    while remaining > 0:
        try:
            result = yield function()
        except Exception as e:
            if type(e) not in acceptable:
                raise
        else:
            twisted.internet.defer.returnValue(result)

        remaining -= 1

    raise Exception('out of retries')


def timeout_retry(function, times=3, acceptable=None):
    if acceptable is None:
        acceptable = [RequestTimeoutError]

    # d = twisted.internet.defer.Deferred()
    # d.addCallback(retry(function=function, times=times, acceptable=acceptable))

    return retry(function=function, times=times, acceptable=acceptable)


def sleep(seconds=None):
    d = twisted.internet.defer.Deferred()

    if seconds is not None:
        if isinstance(seconds, decimal.Decimal):
            seconds = float(seconds)

        twisted.internet.reactor.callLater(seconds, d.callback, None)

    return d


class InvalidAction(Exception):
    pass


@attr.s
class DeferLaterChain:
    deferred = attr.ib(
        default=attr.Factory(twisted.internet.defer.Deferred),
        init=False,
    )
    paused = attr.ib(default=False, init=False)
    canceled = attr.ib(default=False, init=False)
    active = attr.ib(default=None, init=False)

    def add_delayed_callback(self, delay, c, *args, **kwargs):
        def defer_later():
            return twisted.internet.task.deferLater(
                clock=twisted.internet.reactor,
                delay=delay,
                callable=c,
                *args,
                **kwargs,
            )

        def callback(_):
            self.active = defer_later()
            return self.active

        self.deferred.addCallback(callback)

    def add_callback(self, *args, **kwargs):
        return self.deferred.addCallback(*args, **kwargs)

    def add_both(self, *args, **kwargs):
        return self.deferred.addBoth(*args, **kwargs)

    def add_errback(self, *args, **kwargs):
        return self.deferred.addErrback(*args, **kwargs)

    addCallback = add_callback
    addBoth = add_both
    addErrback = add_errback

    def run(self, arg=None):
        self.deferred.callback(arg)

    def cancel(self):
        self.deferred.cancel()
        self.canceled = True

    def pause(self):
        if self.canceled:
            raise InvalidAction('attempted to pause while canceled')

        if self.paused:
            raise InvalidAction('attempted to pause while paused')

        self.deferred.pause()
        self.active.pause()
        self.paused = True

    def unpause(self):
        if self.canceled:
            raise InvalidAction('attempted to unpause while canceled')

        if not self.paused:
            raise InvalidAction('attempted unpause while not paused')

        self.active.unpause()
        self.deferred.unpause()
        self.paused = False


class DeferredRepeater:
    def __init__(self, f, *args, **kwargs):
        self.callable = f
        self.args = args
        self.kwargs = kwargs

        self.public_deferred = twisted.internet.defer.Deferred(
            canceller=self.cancel)
        self.private_deferred = None

    def repeat(self):
        self.private_deferred = self.callable(*self.args, **self.kwargs)
        self.private_deferred.addCallback(lambda _: self.repeat())
        self.private_deferred.addErrback(self.public_deferred.errback)

    def cancel(self, _=None):
        if self.private_deferred is not None:
            self.private_deferred.cancel()

    def pause(self):
        return self.private_deferred.pause()

    def unpause(self):
        return self.private_deferred.unpause()


@attr.s
class Mobius:
    f = attr.ib()
    args = attr.ib(default=())
    kwargs = attr.ib(default=attr.Factory(dict))
    repeater = attr.ib()
    public_deferred = attr.ib()

    @repeater.default
    def _(self):
        return DeferredRepeater(self.f, *self.args, **self.kwargs)

    @public_deferred.default
    def _(self):
        return twisted.internet.defer.Deferred(
            canceller=self.repeater.cancel,
        )

    def __attrs_post_init__(self):
        self.repeater.public_deferred.addErrback(self.public_deferred.errback)

    @classmethod
    def build(cls, f, *args, **kwargs):
        return cls(f=f, args=args, kwargs=kwargs)

    def add_errback(self, *args, **kwargs):
        self.public_deferred.addErrback(*args, **kwargs)

    addErrback = add_errback

    def run(self):
        self.repeater.repeat()

        return self.public_deferred

    def cancel(self):
        return self.public_deferred.cancel()

    def pause(self):
        self.public_deferred.pause()
        self.repeater.pause()

    def unpause(self):
        self.public_deferred.unpause()
        self.repeater.unpause()


@attr.s
class Action:
    f = attr.ib()
    args = attr.ib(default=())
    kwargs = attr.ib(default=attr.Factory(dict))

    def __call__(self):
        return self.f(*self.args, **self.kwargs)


@attr.s
class Event:
    action = attr.ib()
    time = attr.ib()


@attr.s
class Sequence:
    events = attr.ib(default=attr.Factory(list))
    tolerance = attr.ib(default=0.005)
    clock = attr.ib(default=time.monotonic)

    virtual_time = attr.ib(default=0, init=False)
    clock_time = attr.ib(default=0, init=False)
    deferred = attr.ib(default=None, init=False)
    paused = attr.ib(default=False, init=False)
    run_deferred = attr.ib(default=None, init=False)

    def add_delayed(self, delay, f, *args, **kwargs):
        last_time = 0
        if len(self.events) > 0:
            last_time = self.events[-1].time

        self.events.append(Event(
            action=Action(f=f, args=args, kwargs=kwargs),
            time=last_time + delay,
        ))

    def run(self, loop=False):
        self.run_deferred = self._run(loop=loop)

        return self.run_deferred

    @twisted.internet.defer.inlineCallbacks
    def _run(self, loop=False):
        self.update_time(virtual_time=0)

        run = True
        while run:
            run = loop

            base_time = self.virtual_time

            for event in self.events:
                while True:
                    delay = (base_time + event.time) - self.virtual_time
                    logger.debug(
                        'self.virtual_time: {}'.format(self.virtual_time),
                    )
                    logger.debug('delay: {}'.format(delay))
                    if delay > self.tolerance:
                        self.deferred = epyqlib.utils.twisted.sleep(
                            delay - (self.tolerance / 2),
                        )
                        try:
                            yield self.deferred
                        except twisted.internet.defer.CancelledError:
                            if not self.paused:
                                raise
                        self.deferred = None

                    self.update_time()

                    if not self.paused:
                        break

                    if self.paused:
                        self.deferred = sleep()
                        try:
                            yield self.deferred
                        except twisted.internet.defer.CancelledError:
                            if self.paused:
                                raise
                        finally:
                            self.deferred = None

                        self.update_time(virtual_time=self.virtual_time)

                event.action()
                self.update_time()

    def update_time(self, virtual_time=None):
        now = self.clock()

        if virtual_time is None:
            self.virtual_time += now - self.clock_time

        self.clock_time = now

    def cancel(self):
        self.run_deferred.cancel()

    def pause(self):
        self.paused = True
        if self.deferred is not None:
            self.deferred.cancel()

    def unpause(self):
        self.paused = False
        if self.deferred is not None:
            self.deferred.cancel()
