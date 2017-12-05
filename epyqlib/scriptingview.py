import io
import os
import pathlib

from PyQt5 import QtCore, QtWidgets, uic

import epyqlib.utils.qt
import epyqlib.utils.twisted

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


class ScriptAlreadyActiveError(epyqlib.utils.general.ExpectedException):
    def expected_message(self):
        return 'Script already active.'


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

        self.ui.run_button.clicked.connect(self.run_clicked)
        self.ui.loop_button.clicked.connect(self.loop_clicked)

        self.model = None
        self.model_connections = []

        with open(pathlib.Path(__file__).parents[0] / 'scripting.csv') as f:
            self.ui.csv_edit.setPlaceholderText(f.read())

        self.run_deferred = None

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

    def run_clicked(self, checked):
        try:
            if checked:
                self.run()
            else:
                self.cancel_run()
        except:
            self.ui.run_button.setChecked(not checked)
            raise

    def run_errback(self):
        self.ui.run_button.setChecked(False)
        self.run_deferred = None

    def run(self):
        if self.run_deferred is not None:
            raise ScriptAlreadyActiveError()

        self.run_deferred = self.model.run_s(self.ui.csv_edit.toPlainText())
        self.run_deferred.addBoth(
            epyqlib.utils.twisted.detour_result,
            self.run_errback,
        )
        self.run_deferred.addErrback(epyqlib.utils.twisted.catch_expected)
        self.run_deferred.addErrback(epyqlib.utils.twisted.errbackhook)

    def cancel_run(self):
        if self.run_deferred is None:
            return

        self.run_deferred.cancel()

    def loop_clicked(self, checked):
        try:
            if checked:
                self.loop()
            else:
                self.cancel_loop()
        except:
            self.ui.loop_button.setChecked(not checked)
            raise

    def loop_errback(self):
        self.ui.loop_button.setChecked(False)
        self.run_deferred = None

    def loop(self):
        if self.run_deferred is not None:
            raise ScriptAlreadyActiveError()

        self.run_deferred = epyqlib.utils.twisted.mobius(
            f=self.model.run_s,
            event_string=self.ui.csv_edit.toPlainText(),
        )
        self.run_deferred.addErrback(
            epyqlib.utils.twisted.detour_result,
            self.loop_errback,
        )
        self.run_deferred.addErrback(epyqlib.utils.twisted.catch_expected)
        self.run_deferred.addErrback(epyqlib.utils.twisted.errbackhook)

    def cancel_loop(self):
        if self.run_deferred is None:
            return

        self.run_deferred.cancel()
