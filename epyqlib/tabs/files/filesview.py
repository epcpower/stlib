import pathlib

import attr
from PyQt5.QtCore import Qt
from twisted.internet.defer import ensureDeferred

import PyQt5.uic
from PyQt5.QtWidgets import QPushButton, QTreeWidget, QTreeWidgetItem, QLineEdit
from PyQt5.QtGui import QColor, QBrush

from .files_controller import FilesController

Ui, UiBase = PyQt5.uic.loadUiType(
    pathlib.Path(__file__).with_suffix('.ui'),
)


# TODO: what about `in_designer=False`


@attr.s
class FilesView(UiBase):
    class Sections:
        model: QTreeWidgetItem
        customer: QTreeWidgetItem
        site: QTreeWidgetItem
        inverter: QTreeWidgetItem

    section_headers = Sections()
    controller = FilesController()

    flag: bool = False

    gray_brush = QBrush(QColor(22, 22, 22, 22))

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
        print("[Filesview] setup_ui called")
        self.ui.setupUi(self)

        self.bind()
        self.populate_tree()
        self.setup_buttons()

        self.fetch_files()

    ### Setup methods
    # noinspection PyAttributeOutsideInit
    def bind(self):
        self.btn_something: QPushButton = self.ui.something
        self.btn_more: QPushButton = self.ui.more
        # self.btn_other: QPushButton = self.ui.other

        self.txt_col_width: QLineEdit = self.ui.txt_col_width
        self.btn_set_col_width: QPushButton = self.ui.set_col_width

        self.files_grid: QTreeWidget = self.ui.treeWidget

    def populate_tree(self):
        self.files_grid.setHeaderLabels(["Filename", "Source", "Timestamp", "Notes"])
        self.files_grid.setColumnWidth(0, 300)
        self.files_grid.setColumnWidth(4, 500)

        self.section_headers.model = QTreeWidgetItem(self.files_grid, ["Model-specific files"])
        self.section_headers.model.setExpanded(True)
        self.section_headers.customer = QTreeWidgetItem(self.files_grid, ["Customer-specific files"])
        self.section_headers.customer.setExpanded(True)
        self.section_headers.site = QTreeWidgetItem(self.files_grid, ["Site-specific files"])
        self.section_headers.site.setExpanded(True)
        self.section_headers.inverter = QTreeWidgetItem(self.files_grid, ["Inverter-specific files"])
        self.section_headers.inverter.setExpanded(True)

        # model1 = QTreeWidgetItem(self.section_headers.model, ["bar", "a", "1"])
        # customer1 = QTreeWidgetItem(self.section_headers.customer, ["baz", "b", "2"])
        # customer2 = QTreeWidgetItem(self.section_headers.customer, ["boo", "c", "0"])

        self.files_grid.itemClicked.connect(self.echo)

    def setup_buttons(self):
        self.btn_something.clicked.connect(self.echo)
        self.btn_more.setDisabled(True)
        self.btn_more.clicked.connect(self.more_clicked)
        self.btn_set_col_width.clicked.connect(self.set_col_width_clicked)

    def fetch_files(self):
        print('[Filesview] About to fire off files request')
        deferred = ensureDeferred(self.controller.get_inverter_associations('TestInv'))
        deferred.addCallback(self.show_files)
        deferred.addErrback(self.files_err)

    def show_files(self, associations):
        print('[Filesview] Files request finished')
        print(associations)
        for item in associations['model']:
            QTreeWidgetItem(self.section_headers.model, [item['file']['filename']])

        for item in associations['inverter']:
            QTreeWidgetItem(self.section_headers.inverter, [item['file']['filename']])

    def files_err(self, error):
        print('ERROR Fetching files')
        print(error)


    ### Actions
    def echo(self, item: QTreeWidgetItem, column: int):
        print("[Filesview] echo " + item.text(column))
        self.btn_more.setDisabled(False)

    def more_clicked(self):
        if self.flag:
            col = 1
        else:
            col = 2
        self.section_headers.customer.sortChildren(col, Qt.AscendingOrder)
        self.flag = not self.flag

    def set_col_width_clicked(self):
        self.files_grid.setColumnWidth(0, int(self.txt_col_width.text()))



# .ui files need a direct module attribute, not a class method, afaict.
FilesViewQtBuilder = FilesView.qt_build
