import json
import pathlib
import time

import attr
from PyQt5.QtCore import Qt
from twisted.internet.defer import ensureDeferred

import PyQt5.uic
from PyQt5.QtWidgets import QPushButton, QTreeWidget, QTreeWidgetItem, QLineEdit, QFileDialog, QCheckBox, QLabel, \
    QPlainTextEdit
from PyQt5.QtGui import QColor, QBrush, QTextCursor

from epyqlib.tabs.files.graphql import InverterNotFoundException
from epyqlib.utils import qt
from epyqlib.utils.twisted import errbackhook as show_error_dialog
from .files_controller import FilesController

Ui, UiBase = PyQt5.uic.loadUiType(
    pathlib.Path(__file__).with_suffix('.ui'),
)


# TODO: what about `in_designer=False`

class QTreeWidgetItemWithObj(QTreeWidgetItem):
    def __init__(self):
        super().__init__()
        self.obj = None

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
        self.ui.setupUi(self)

        self.bind()
        self.populate_tree()
        self.setup_buttons()

    def tab_selected(self):
        if self.controller.should_sync():
            self.fetch_files('TestInv')

    ### Setup methods
    # noinspection PyAttributeOutsideInit
    def bind(self):
        self.section_headers = _Sections()
        self.controller = FilesController()

        self.lbl_last_sync: QLabel = self.ui.last_sync
        self.btn_sync_now: QPushButton = self.ui.sync_now
        self.btn_login: QPushButton = self.ui.login
        self.btn_download_file: QPushButton = self.ui.download_file
        self.btn_send_to_inverter: QPushButton = self.ui.send_to_inverter
        self.chk_auto_sync: QCheckBox = self.ui.auto_sync

        self.inverter_id: QLineEdit = self.ui.inverter_id
        self.inverter_id_error: QLabel = self.ui.inverter_id_error

        self.files_grid: QTreeWidget = self.ui.treeWidget

        self.assigned_by: QLineEdit = self.ui.assigned_by
        self.assigned_time: QLineEdit = self.ui.assigned_time
        self.filename: QLineEdit = self.ui.filename
        self.upload_time: QLineEdit = self.ui.upload_time
        self.version: QLineEdit = self.ui.version

        self.notes: QPlainTextEdit = self.ui.notes
        self.btn_save_notes: QPushButton = self.ui.save_notes
        self.btn_reset_notes: QPushButton = self.ui.reset_notes


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

        self.notes.textChanged.connect(self._notes_changed)

        self.files_grid.itemClicked.connect(self._file_item_clicked)

    def _enable_buttons(self, enable):
        self.btn_download_file.setDisabled(enable)
        self.btn_send_to_inverter.setDisabled(enable)

    def setup_buttons(self):
        self._enable_buttons(False)

        self.inverter_id.returnPressed.connect(self.inverter_id_changed)
        self.inverter_id.setReadOnly(False)  #TODO: Link to whether or not they have admin access
        self._show_inverter_id_error(None)

        self.btn_sync_now.clicked.connect(self.fetch_files)
        self.btn_reset_notes.clicked.connect(self._reset_notes)

    def fetch_files(self, inverter_id):
        print('[Filesview] About to fire off files request')
        deferred = ensureDeferred(self.controller.get_inverter_associations(inverter_id))
        deferred.addCallback(self.show_files)
        deferred.addErrback(self.inverter_error_handler)
        deferred.addErrback(show_error_dialog)

    def _remove_all_children(self, parent: QTreeWidgetItem):
        while parent.childCount() > 0:
            parent.removeChild(parent.child(0))

    def show_files(self, associations):
        print('[Filesview] Files request finished')
        print(associations)
        sync_time = self.controller.get_sync_time()
        self.lbl_last_sync.setText(f'Last sync at:{sync_time}')

        def _add_item(list: [dict], parent: QTreeWidgetItem):
            self._remove_all_children(parent)

            for item in list:
                if item['file'] is not None:
                    widget = QTreeWidgetItem(parent, [item['file']['filename']])
                    widget.obj = item

        _add_item(associations['parameter'], self.section_headers.params)
        #_add_item(associations['pvms'], self.section_headers.pvms)
        _add_item(associations['firmware'], self.section_headers.firmware)
        #_add_item(associations['faultLogs'], self.section_headers.fault_logs)
        _add_item(associations['other'], self.section_headers.other)


    ### Actions
    def _file_item_clicked(self, item: QTreeWidgetItem, column: int):
        if hasattr(item, 'obj'):
            self._show_file_details(item.obj)

    def _download_file_clicked(self):
        directory = QFileDialog.getExistingDirectory(parent=self.files_grid, caption='Pick location to download')
        print(f'[Filesview] Filename picked: {directory}')


    def _notes_changed(self):
        ensureDeferred(self._disable_notes())

    def _reset_notes(self):
        self.notes.setPlainText(self.controller.old_notes)
        self.notes.moveCursor(QTextCursor.End)

    async def _disable_notes(self):
        changed = self.controller.notes_modified(self.notes.toPlainText())

        self.btn_save_notes.setDisabled(not changed)
        self.btn_reset_notes.setDisabled(not changed)

    def inverter_id_changed(self):
        self._show_inverter_id_error(None)
        self.fetch_files(self.inverter_id.text())

    def inverter_error_handler(self, error):
        if error.type is InverterNotFoundException:  #Twisted wraps errors in its own class
            self._show_inverter_id_error("Error: Inverter ID not found.")
        else:
            raise error


    ### UI Update methods
    def _show_file_details(self, association):
        self.filename.setText(association['file']['filename'])
        self.version.setText(association['file']['version'])
        self.controller.set_original_notes(association['file']['notes'])
        self.notes.setPlainText(association['file']['notes'])

    def _show_inverter_id_error(self, error):
        if error is None:
            self.inverter_id_error.setText("")
        else:
            self.inverter_id_error.setText(f"<font color='red'>{error}</font>")



# .ui files need a direct module attribute, not a class method, afaict.
FilesViewQtBuilder = FilesView.qt_build
