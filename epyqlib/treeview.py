from PyQt5 import QtCore, QtWidgets

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


class TreeView(QtWidgets.QTreeView):
    def __init__(self, *args, **kwargs):
        kwargs.pop('in_designer', None)
        super().__init__(*args, **kwargs)

        self.row_columns = set()
        self.no_update_columns = set()

    def selectionCommand(self, index, event):
        column = index.column()
        is_row_column = column in self.row_columns

        if column in self.no_update_columns and not is_row_column:
            return QtCore.QItemSelectionModel.NoUpdate

        result = super().selectionCommand(index, event)

        if is_row_column:
            result |= QtCore.QItemSelectionModel.Rows

        return result
