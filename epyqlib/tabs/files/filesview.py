import pathlib
import time

import attr
from PyQt5.QtCore import Qt
from twisted.internet.defer import ensureDeferred

import PyQt5.uic
from PyQt5.QtWidgets import QPushButton, QTreeWidget, QTreeWidgetItem, QLineEdit, QFileDialog, QCheckBox, QLabel
from PyQt5.QtGui import QColor, QBrush

from epyqlib.utils import qt
from epyqlib.utils.twisted import errbackhook as show_error_dialog
from .files_controller import FilesController

Ui, UiBase = PyQt5.uic.loadUiType(
    pathlib.Path(__file__).with_suffix('.ui'),
)


# TODO: what about `in_designer=False`

class _Sections:
    params: QTreeWidgetItem
    pvms: QTreeWidgetItem
    firmware: QTreeWidgetItem
    fault_logs: QTreeWidgetItem
    other: QTreeWidgetItem

@attr.s
class FilesView(UiBase):


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
        self.section_headers = _Sections()
        self.controller = FilesController()

        print("[Filesview] setup_ui called")
        self.ui.setupUi(self)

        self.bind()
        self.populate_tree()
        self.setup_buttons()

    def tab_selected(self):
        if self.controller.should_sync():
            self.fetch_files()

    ### Setup methods
    # noinspection PyAttributeOutsideInit
    def bind(self):
        self.lbl_last_sync: QLabel = self.ui.last_sync
        self.btn_sync_now: QPushButton = self.ui.sync_now
        self.btn_login: QPushButton = self.ui.login
        self.btn_download_file: QPushButton = self.ui.download_file
        self.btn_send_to_inverter: QPushButton = self.ui.send_to_inverter
        self.chk_auto_sync: QCheckBox = self.ui.auto_sync

        self.files_grid: QTreeWidget = self.ui.treeWidget

    def populate_tree(self):
        self.files_grid.setHeaderLabels(["Filename", "Local", "Web", "Association", "Creator", "Created At", "Associated At", "Notes"])
        self.files_grid.setColumnWidth(0, 300)
        self.files_grid.setColumnWidth(1, 35)
        self.files_grid.setColumnWidth(2, 35)
        self.files_grid.setColumnWidth(7, 500)

        # make_entry = lambda caption:
        def make_entry(caption):
            val = QTreeWidgetItem(self.files_grid, [caption])
            val.setExpanded(True)
            return val

        self.section_headers.params = make_entry("Parameter Sets")
        self.section_headers.pvms = make_entry("Value Sets")
        self.section_headers.firmware = make_entry("Firmware")
        self.section_headers.fault_logs = make_entry("Fault Logs")
        self.section_headers.other = make_entry("Other files")

        self.files_grid.itemClicked.connect(self.echo)

    def _enable_buttons(self, enable):
        self.btn_download_file.setDisabled(enable)
        self.btn_send_to_inverter.setDisabled(enable)

    def setup_buttons(self):
        self._enable_buttons(False)

        self.btn_download_file.clicked.connect(self._download_file_clicked)
        self.btn_send_to_inverter.clicked.connect(self._send_to_inverter_clicked)

        self.btn_sync_now.clicked.connect(self.fetch_files)

    def fetch_files(self):
        print('[Filesview] About to fire off files request')
        deferred = ensureDeferred(self.controller.get_inverter_associations('TestInv'))
        deferred.addCallback(self.show_files)
        deferred.addErrback(show_error_dialog)

    def _remove_all_children(self, parent: QTreeWidgetItem):
        while parent.childCount() > 0:
            parent.removeChild(parent.child(0))

    def show_files(self, associations):
        print('[Filesview] Files request finished')
        print(associations)
        sync_time = self.controller.set_sync_time()
        self.lbl_last_sync.setText(f'Last sync at:{sync_time}')

        def _add_item(list: [dict], parent: QTreeWidgetItem):
            self._remove_all_children(parent)

            for item in list:
                if item['file'] is not None:
                    QTreeWidgetItem(parent, [item['file']['filename']])

        _add_item(associations['parameter'], self.section_headers.params)
        #_add_item(associations['pvms'], self.section_headers.pvms)
        _add_item(associations['firmware'], self.section_headers.firmware)
        #_add_item(associations['faultLogs'], self.section_headers.fault_logs)
        _add_item(associations['other'], self.section_headers.other)


    ### Actions
    def echo(self, item: QTreeWidgetItem, column: int):
        print("[Filesview] echo " + item.text(column))

    def _download_file_clicked(self):
        # filename = qt.file_dialog(filters=['foo.epc'], save=True, parent=self.files_grid)
        directory = QFileDialog.getExistingDirectory(parent=self.files_grid, caption='Pick location to download')
        print(f'[Filesview] Filename picked: {directory}')


    def _send_to_inverter_clicked(self):
        pass




# .ui files need a direct module attribute, not a class method, afaict.
FilesViewQtBuilder = FilesView.qt_build
