import io
import os.path

import PyQt5.Qt
import PyQt5.uic

# See file COPYING in this source tree
__copyright__ = 'Copyright 2018, EPC Power Corp.'
__license__ = 'GPLv2+'


class FaultLogView(PyQt5.Qt.QWidget):
    def __init__(self, parent=None, in_designer=False):
        super().__init__(parent=parent)

        self.in_designer = in_designer

        ui = 'faultlogview.ui'
        # TODO: CAMPid 9549757292917394095482739548437597676742
        if not PyQt5.Qt.QFileInfo(ui).isAbsolute():
            ui_file = os.path.join(
                PyQt5.Qt.QFileInfo.absolutePath(PyQt5.Qt.QFileInfo(__file__)),
                ui,
            )
        else:
            ui_file = ui
        ui_file = PyQt5.Qt.QFile(ui_file)
        ui_file.open(PyQt5.Qt.QFile.ReadOnly | PyQt5.Qt.QFile.Text)
        ts = PyQt5.Qt.QTextStream(ui_file)
        sio = io.StringIO(ts.readAll())
        self.ui = PyQt5.uic.loadUi(sio, self)

        view = self.ui.tree_view
        view.setSelectionBehavior(view.SelectRows)
        view.setSelectionMode(view.ExtendedSelection)

        self.model = None

    def set_model(self, model):
        self.model = model

        self.ui.tree_view.setModel(model)
