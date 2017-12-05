import epyqlib.utils.general
import epyqlib.utils.qt
import logging
import sys
import twisted.internet.defer

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

    def cancel(self, _):
        if self.private_deferred is not None:
            self.private_deferred.cancel()


def mobius(f, *args, **kwargs):
    repeater = DeferredRepeater(f, *args, **kwargs)
    repeater.repeat()

    return repeater.public_deferred
