from PyQt5 import QtCore, QtWidgets

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


class TreeView(QtWidgets.QTreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.row_columns = {}
        self.no_update_columns = {}

    def selectionCommand(self, index, event):
        if index.column() in self.no_update_columns:
            return QtCore.QItemSelectionModel.NoUpdate

        result = super().selectionCommand(index, event)

        if index.column() in self.row_columns:
            result |= QtCore.QItemSelectionModel.Rows

        return result
