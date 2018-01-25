import io
import os
import pathlib

from PyQt5 import QtCore, QtWidgets, uic
import twisted.internet.defer

import epyqlib.utils.qt
import epyqlib.utils.twisted

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


class ScriptAlreadyActiveError(epyqlib.utils.general.ExpectedException):
    def expected_message(self):
        return 'Script already active.'


class ScriptNotActiveError(epyqlib.utils.general.ExpectedException):
    def expected_message(self):
        return 'Script is not active.'


class ScriptAlreadyPausedError(epyqlib.utils.general.ExpectedException):
    def expected_message(self):
        return 'Script already paused.'


class ScriptNotPausedError(epyqlib.utils.general.ExpectedException):
    def expected_message(self):
        return 'Script is not paused.'


def cancelled_handler(error):
    if isinstance(error.value, twisted.internet.defer.CancelledError):
        epyqlib.utils.qt.raw_exception_message_box(
            brief='Script cancelled by user request.',
            extended=error.getTraceback(),
        )

        return None

    return error


class ScriptingView(QtWidgets.QWidget):
    def __init__(self, parent=None, in_designer=False):
        super().__init__(parent=parent)

        self.in_designer = in_designer

        ui = 'scriptingview.ui'
        # TODO: CAMPid 9549757292917394095482739548437597676742
        if not QtCore.QFileInfo(ui).isAbsolute():
            ui_file = os.path.join(
                QtCore.QFileInfo.absolutePath(QtCore.QFileInfo(__file__)), ui)
        else:
            ui_file = ui
        ui_file = QtCore.QFile(ui_file)
        ui_file.open(QtCore.QFile.ReadOnly | QtCore.QFile.Text)
        ts = QtCore.QTextStream(ui_file)
        sio = io.StringIO(ts.readAll())
        self.ui = uic.loadUi(sio, self)

        self.ui.load_button.clicked.connect(self.load)
        self.ui.save_button.clicked.connect(self.save)

        self.ui.run_button.clicked.connect(self.run)
        self.ui.loop_button.clicked.connect(self.loop)
        self.ui.stop_button.clicked.connect(self.stop)

        self.ui.pause_button.clicked.connect(self.pause)
        self.ui.continue_button.clicked.connect(self.unpause)

        self.model = None
        self.model_connections = []

        with open(pathlib.Path(__file__).parents[0] / 'scripting.csv') as f:
            self.ui.csv_edit.setPlaceholderText(f.read())

        self.run_deferred = None
        self.run_deferred_paused = False
        self.update_buttons()

    def update_buttons(self):
        active = self.run_deferred is not None

        self.ui.run_button.setEnabled(not active)
        self.ui.loop_button.setEnabled(not active)
        self.ui.stop_button.setEnabled(active)

        self.ui.pause_button.setEnabled(active and not self.run_deferred_paused)
        self.ui.continue_button.setEnabled(active and self.run_deferred_paused)

    def set_model(self, model):
        for connection in self.model_connections:
            connection.disconnect()

        self.model = model

    def load(self):
        filters = [
            ('CSV', ['csv']),
            ('All Files', ['*'])
        ]
        filename = epyqlib.utils.qt.file_dialog(
            filters,
            parent=self.ui,
        )

        if filename is None:
            return

        with open(filename) as f:
            self.ui.csv_edit.setPlainText(f.read())

    def save(self):
        filters = [
            ('CSV', ['csv']),
            ('All Files', ['*'])
        ]
        filename = epyqlib.utils.qt.file_dialog(
            filters,
            save=True,
            parent=self.ui,
        )

        if filename is None:
            return

        with open(filename, 'w') as f:
            text = self.ui.csv_edit.toPlainText()
            f.write(text)
            if text[-1] != '\n':
                f.write('\n')

    def stop(self):
        if self.run_deferred is None:
            return

        self.run_deferred.cancel()
        self.run_deferred_paused = False
        self.run_deferred = None
        self.update_buttons()

    def errback(self):
        self.run_deferred = None
        self.update_buttons()

    def run(self):
        if self.run_deferred is not None:
            raise ScriptAlreadyActiveError()

        self.run_deferred = self.model.run_s(self.ui.csv_edit.toPlainText())
        self.run_deferred_paused = False
        self.update_buttons()

        self.run_deferred.addBoth(
            epyqlib.utils.twisted.detour_result,
            self.errback,
        )
        self.run_deferred.addErrback(epyqlib.utils.twisted.catch_expected)
        self.run_deferred.addErrback(cancelled_handler)
        self.run_deferred.addErrback(epyqlib.utils.twisted.errbackhook)

    def loop(self):
        if self.run_deferred is not None:
            raise ScriptAlreadyActiveError()

        m = epyqlib.utils.twisted.Mobius.build(
            f=self.model.run_s,
            event_string=self.ui.csv_edit.toPlainText(),
        )
        m.run()
        self.run_deferred = m

        self.run_deferred_paused = False
        self.update_buttons()

        self.run_deferred.addErrback(
            epyqlib.utils.twisted.detour_result,
            self.errback,
        )
        self.run_deferred.addErrback(epyqlib.utils.twisted.catch_expected)
        self.run_deferred.addErrback(cancelled_handler)
        self.run_deferred.addErrback(epyqlib.utils.twisted.errbackhook)

    def pause(self):
        if self.run_deferred is None:
            raise ScriptNotActiveError()

        if self.run_deferred_paused:
            raise ScriptAlreadyPausedError()

        self.run_deferred.pause()
        self.run_deferred_paused = True
        self.update_buttons()

    def unpause(self):
        if self.run_deferred is None:
            raise ScriptNotActiveError()

        if not self.run_deferred_paused:
            raise ScriptNotPausedError()

        self.run_deferred.unpause()
        self.run_deferred_paused = False
        self.update_buttons()
