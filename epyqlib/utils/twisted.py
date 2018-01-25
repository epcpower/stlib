import epyqlib.utils.general
import epyqlib.utils.qt
import logging
import sys
import twisted.internet.defer

import attr

__copyright__ = 'Copyright 2016, EPC Power Corp.'
__license__ = 'GPLv2+'


logger = logging.getLogger(__name__)


class RequestTimeoutError(TimeoutError):
    pass


def errbackhook(error):
    epyqlib.utils.qt.custom_exception_message_box(
        brief='{}\n{}'.format(error.type.__name__, error.value),
        extended=error.getTraceback(),
    )

    return error


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


def sleep(seconds):
    d = twisted.internet.defer.Deferred()
    from twisted.internet import reactor
    reactor.callLater(seconds, d.callback, None)
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

    def add_errback(self, *args, **kwargs):
        return self.deferred.addErrback(*args, **kwargs)

    addCallback = add_callback
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
