from PyQt5 import QtWidgets

import epyqlib.variableselectionview_ui
import epyqlib.utils.qt


# See file COPYING in this source tree
__copyright__ = 'Copyright 2016, EPC Power Corp.'
__license__ = 'GPLv2+'


class VariableSelectionView(QtWidgets.QWidget):
    def __init__(self, parent=None, in_designer=False):
        super().__init__(parent=parent)

        self.in_designer = in_designer

        self.ui = epyqlib.variableselectionview_ui.Ui_Form()
        self.ui.setupUi(self)

        self.ui.searchbox.connect_to_view(
            view=self.ui.tree_view,
            column=epyqlib.variableselectionmodel.Columns.indexes.name,
        )

    def set_model(self, model):
        self.ui.tree_view.setModel(model)
        model.setSortRole(epyqlib.utils.qt.UserRoles.sort)

        header = self.ui.tree_view.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(header.ResizeToContents)

    def set_sorting_enabled(self, enabled):
        self.ui.tree_view.setSortingEnabled(enabled)

    def sort_by_column(self, column, order):
        self.ui.tree_view.sortByColumn(column, order)

    @property
    def model(self):
        return self.ui.tree_view.model()
