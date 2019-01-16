import pathlib

import attr
from PyQt5.QtCore import Qt
from twisted.internet.defer import ensureDeferred

import PyQt5.uic
from PyQt5.QtWidgets import QPushButton, QTreeWidget, QTreeWidgetItem, QLineEdit, QFileDialog
from PyQt5.QtGui import QColor, QBrush

from epyqlib.utils import qt
from epyqlib.utils.twisted import errbackhook as show_error_dialog
import epyqlib.utils.twisted
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

    # Files grid is 0-indexed
    section_headers = Sections()
    controller = FilesController()

    flag: bool = False

    gray_brush = QBrush(QColor(22, 22, 22, 22))

    ui = attr.ib(factory=Ui)
    device_interface = attr.ib(default=None)

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

        self.ui.get_serial_number.clicked.connect(
            lambda: self.get_serial_number(),
        )

        self.bind()
        self.populate_tree()
        self.setup_buttons()

    def set_device_interface(self, device_interface):
        self.device_interface = device_interface

    def tab_selected(self):
        self.fetch_files()

    ### Setup methods
    # noinspection PyAttributeOutsideInit
    def bind(self):
        self.btn_download_file: QPushButton = self.ui.download_file
        self.btn_send_to_inverter: QPushButton = self.ui.send_to_inverter

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

        self.files_grid.itemClicked.connect(self.echo)

    def _enable_buttoms(self, enable):
        self.btn_download_file.setDisabled(enable)
        self.btn_send_to_inverter.setDisabled(enable)

    def setup_buttons(self):
        self._enable_buttoms(False)

        self.btn_download_file.clicked.connect(self._download_file_clicked)
        self.btn_send_to_inverter.clicked.connect(self._send_to_inverter_clicked)

    def fetch_files(self):
        print('[Filesview] About to fire off files request')
        deferred = ensureDeferred(self.controller.get_inverter_associations('TestInv'))
        deferred.addCallback(self.show_files)
        deferred.addErrback(show_error_dialog)

    def show_files(self, associations):
        print('[Filesview] Files request finished')
        print(associations)
        for item in associations['model']:
            if item['file'] is not None:
                QTreeWidgetItem(self.section_headers.model, [item['file']['filename']])

        for item in associations['inverter']:
            if item['file'] is not None:
                QTreeWidgetItem(self.section_headers.inverter, [item['file']['filename']])


    ### Actions
    def echo(self, item: QTreeWidgetItem, column: int):
        print("[Filesview] echo " + item.text(column))
        self.btn_more.setDisabled(False)

    def _download_file_clicked(self):
        # filename = qt.file_dialog(filters=['foo.epc'], save=True, parent=self.files_grid)
        directory = QFileDialog.getExistingDirectory(parent=self.files_grid, caption='Pick location to download')
        print(f'[Filesview] Filename picked: {directory}')


    def _send_to_inverter_clicked(self):
        pass

    @epyqlib.utils.twisted.ensure_deferred
    @epyqlib.utils.twisted.errback_dialog
    async def get_serial_number(self):
        serial_number = await self.device_interface.get_serial_number()
        epyqlib.utils.qt.dialog(
            parent=self,
            message=f'Serial Number: {serial_number}',
        )


# .ui files need a direct module attribute, not a class method, afaict.
FilesViewQtBuilder = FilesView.qt_build
