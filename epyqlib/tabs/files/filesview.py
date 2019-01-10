import pathlib

import attr
from PyQt5.QtCore import Qt

import PyQt5.uic
from PyQt5.QtWidgets import QPushButton, QTreeWidget, QTreeWidgetItem
from PyQt5.QtGui import QColor, QBrush

Ui, UiBase = PyQt5.uic.loadUiType(
    pathlib.Path(__file__).with_suffix('.ui'),
)


# TODO: what about `in_designer=False`


@attr.s
class FilesView(UiBase):
    btn_something: QPushButton
    btn_more: QPushButton
    btn_other: QPushButton

    files_grid: QTreeWidget

    model: QTreeWidgetItem
    flag: bool = False

    brush = QBrush(QColor(22, 22, 22, 22))

    ui = attr.ib(factory=Ui)

    @classmethod
    def build(cls):
        instance = cls()
        instance.setup_ui()

        return instance

    @classmethod
    def qt_build(cls, parent):
        instance = cls.build()
        instance.setParent(parent)

        return instance

    def __attrs_post_init__(self):
        super().__init__()

    def setup_ui(self):
        self.ui.setupUi(self)

        self.btn_something = self.ui.something
        self.btn_more = self.ui.more
        self.btn_other = self.ui.other

        self.files_grid = self.ui.treeWidget

        print("[Filesview] setup_ui called")
        self.btn_something.clicked.connect(self.echo)
        self.btn_more.setDisabled(True)
        self.btn_more.clicked.connect(self.more_clicked)

        self.files_grid.setHeaderLabels(["Filename", "Source", "Timestamp"])

        generic = QTreeWidgetItem(self.files_grid, ["Generic Files"])
        generic.setExpanded(True)

        self.model = QTreeWidgetItem(self.files_grid, ["Model-specific files"])
        self.model.setExpanded(True)

        generic1 = QTreeWidgetItem(generic, ["bar", "a", "1"])
        model1 = QTreeWidgetItem(self.model, ["baz", "b", "2"])
        model2 = QTreeWidgetItem(self.model, ["boo", "c", "0"])

        self.files_grid.itemClicked.connect(self.echo)

    def echo(self, item: QTreeWidgetItem, column: int):
        print("[Filesview] echo " + item.text(column))
        self.btn_more.setDisabled(False)

    def more_clicked(self):
        if self.flag:
            col = 1
        else:
            col = 2
        self.model.sortChildren(col, Qt.AscendingOrder)
        self.flag = not self.flag




# .ui files need a direct module attribute, not a class method, afaict.
FilesViewQtBuilder = FilesView.qt_build
