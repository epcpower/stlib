import io
import textwrap

import pytest
from PyQt5 import QtWidgets
import PyQt5.uic

import epyqlib.tabs.files.filesview


def test_init(qtbot):
    view = epyqlib.tabs.files.filesview.FilesView()
    qtbot.add_widget(view)

    view.show()
    qtbot.wait_for_window_shown(widget=view)

    assert view.parent() is None
    assert isinstance(view.ui, epyqlib.tabs.files.filesview.Ui)
    assert not hasattr(view.ui, 'something')


def test_build(qtbot):
    view = epyqlib.tabs.files.filesview.FilesView.build()
    qtbot.add_widget(view)

    view.show()
    qtbot.wait_for_window_shown(widget=view)

    assert view.parent() is None
    assert isinstance(view.ui, epyqlib.tabs.files.filesview.Ui)
    assert hasattr(view.ui, 'files_grid')

