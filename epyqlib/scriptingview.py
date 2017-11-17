import io
import os

from PyQt5 import QtCore, Qsci, QtWidgets, uic

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

        self.lexer = Qsci.QsciLexerPython(self.ui.editor)
        self.ui.editor.setLexer(self.lexer)
        self.ui.editor.setUtf8(True)

        self.ui.execute_button.clicked.connect(self.execute)

        self.model = None
        self.model_connections = []

    def set_model(self, model):
        for connection in self.model_connections:
            connection.disconnect()

        self.model = model

        self.model_connections.append(
            self.ui.demo_button.clicked.connect(model.demo)
        )

    def execute(self):
        exec(self.ui.editor.text())

