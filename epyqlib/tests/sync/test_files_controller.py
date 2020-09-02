from unittest.mock import MagicMock

import pytest
from twisted.internet.defer import ensureDeferred

from epyqlib.tabs.files.files_manager import FilesManager
from epyqlib.tabs.files.files_controller import FilesController
from epyqlib.tabs.files.filesview import FilesView

# noinspection PyUnresolvedReferences
from epyqlib.tests.utils.test_fixtures import temp_dir


@pytest.inlineCallbacks
@pytest.mark.skip(reason="Could break at any time if database changes")
def test_get_associations():
    view = MagicMock(spec=FilesView)
    controller = FilesController(view)

    deferred = ensureDeferred(controller.get_inverter_associations("0"))
    results = yield deferred

    view.attach_row_to_parent.assert_called()


@pytest.mark.skip(reason="Just for local testing")
@pytest.inlineCallbacks
def test_get_file(temp_dir):
    view = MagicMock(spec=FilesView)
    controller = FilesController(view)

    hash = "52e2678f71a591e9e0edfcf249ff07ae"

    controller.cache_manager = FilesManager(temp_dir)

    assert controller.cache_manager.has_hash(hash) is False

    output = yield ensureDeferred(controller.download_file(hash))
    # assert output is None

    assert controller.cache_manager.has_hash(hash) is True
