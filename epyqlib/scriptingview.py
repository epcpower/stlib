import io
import os
import pathlib

from PyQt5 import QtCore, Qsci, QtWidgets, uic

import epyqlib.utils.qt

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


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

        self.model = None
        self.model_connections = []

        with open(pathlib.Path(__file__).parents[0] / 'scripting.csv') as f:
            self.ui.csv_edit.setPlaceholderText(f.read())

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
            self.ui.csv_edit.setText(f.read())

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
            if f[-1] != '\n':
                f.write('\n')

    def run(self):
        self.model.runs(self.ui.csv_edit.toPlainText())
