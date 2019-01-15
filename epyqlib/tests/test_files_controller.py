import pytest
from twisted.internet.defer import ensureDeferred
from twisted.plugins.twisted_reactors import asyncio

from epyqlib.tabs.files.files_controller import FilesController


@pytest.inlineCallbacks
@pytest.mark.skip(reason="Could break at any time if database changes")
def test_get_associations():
    controller = FilesController()

    deferred = ensureDeferred(controller.get_inverter_associations("TestInv"))
    output = yield deferred
    assert output is not None
    assert output['model'] is not None
    assert output['model'][0] is not None

@pytest.inlineCallbacks
@pytest.mark.skip(reason="Just for local testing")
def test_get_file():
    controller = FilesController()

    output = yield ensureDeferred(controller.download_file("test_large.out", "/Users/benb/Desktop/test.out"))
    assert output is None
