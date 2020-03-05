from PyQt5 import QtWidgets

import epyqlib.faultlogview_ui
import epyqlib.utils.qt


# See file COPYING in this source tree
__copyright__ = 'Copyright 2018, EPC Power Corp.'
__license__ = 'GPLv2+'


class FaultLogView(QtWidgets.QWidget):
    def __init__(self, parent=None, in_designer=False):
        super().__init__(parent=parent)

        self.in_designer = in_designer

        self.ui = epyqlib.faultlogview_ui.Ui_Form()
        self.ui.setupUi(self)

        view = self.ui.tree_view
        view.setSelectionBehavior(view.SelectRows)
        view.setSelectionMode(view.ExtendedSelection)

        self.model = None

        self.ui.clear_button.clicked.connect(self.clear)

    def set_model(self, model):
        self.model = model

        self.ui.tree_view.setModel(model)

    def clear(self):
        answer = QtWidgets.QMessageBox.question(
            self,
            'Clear Log',
            'Are you sure you want to clear the log?',
        )

        if answer != QtWidgets.QMessageBox.Yes:
            return

        children = list(self.model.root.children)
        for child in children:
            self.model.root.remove_child(child=child)
