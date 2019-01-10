import pathlib

import attr
import PyQt5.uic
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QPushButton, QListView, QTableWidget
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

    list_widget: QListWidget
    list_view: QTableWidget

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

        self.list_view = self.ui.listView
        self.list_widget = self.ui.listWidget

        print("[Filesview] setup_ui called")
        self.btn_something.clicked.connect(self.echo)
        self.btn_more.setDisabled(True)
        self.list_widget.itemClicked.connect(self.item_clicked)

        self.list_view.itemClicked.connect(self.item_clicked)

    def echo(self):
        print("[Filesview] echo")

        item = QListWidgetItem("Foo!")
        item.setBackground(self.brush)
        self.list_widget.addItem(item)

    def item_clicked(self):
        self.btn_more.setDisabled(self.list_widget.currentRow() == 0)


# .ui files need a direct module attribute, not a class method, afaict.
FilesViewQtBuilder = FilesView.qt_build
