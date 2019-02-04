import pathlib
from enum import Enum

import PyQt5.uic
import attr
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QBrush, QTextCursor
from PyQt5.QtWidgets import QPushButton, QTreeWidget, QTreeWidgetItem, QLineEdit, QCheckBox, QLabel, \
    QPlainTextEdit
from twisted.internet.defer import ensureDeferred

from epyqlib.tabs.files.graphql import InverterNotFoundException

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


class Cols:
    filename = 0
    local = 1
    web = 2
    association = 3
    creator = 4
    created_at = 5
    associated_at = 6
    version = 7
    notes = 8


class Relationships(Enum):
    inverter = QBrush(QColor(187, 187, 187))  # Gray
    model = QBrush(QColor(112, 173, 71))  # Green
    customer = QBrush(QColor(143, 170, 220))  # Blue
    site = QBrush(QColor(255, 208, 64))  # Yellow



def get_keys(obj):
    return [key for key in obj.__dict__.keys() if not key.startswith("__")]

def get_values(obj):
    return [obj.__dict__[key] for key in get_keys(obj)]

@attr.s
class FilesView(UiBase):
    gray_brush = QBrush(QColor(22, 22, 22, 22))
    check_icon = u'✅'
    question_icon = u'❓'

    time_format = '%l:%M%p %m/%d'

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

    # noinspection PyAttributeOutsideInit
    def setup_ui(self):
        self.ui.setupUi(self)

        from .files_controller import FilesController
        self.controller = FilesController(self)
        self.controller.setup()


    def tab_selected(self):
        self.controller.tab_selected()

    ### Setup methods
    # noinspection PyAttributeOutsideInit
    def bind(self):
        self.section_headers = _Sections()

        self.lbl_last_sync: QLabel = self.ui.last_sync
        self.btn_sync_now: QPushButton = self.ui.sync_now
        self.btn_login: QPushButton = self.ui.login
        self.btn_save_file_as: QPushButton = self.ui.save_file_as
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



        # Bind click events
        self.btn_save_file_as.clicked.connect(self._save_file_as_clicked)
        self.btn_sync_now.clicked.connect(self.controller.sync_now_clicked)
        self.chk_auto_sync.clicked.connect(self.controller.auto_sync_checked)
        self.inverter_id.returnPressed.connect(self.controller.sync_now_clicked)

        self.files_grid.itemClicked.connect(self.controller.file_item_clicked)

        self.notes.textChanged.connect(self._notes_changed)

        self.btn_reset_notes.clicked.connect(self._reset_notes)


    def populate_tree(self):
        self.files_grid.setAlternatingRowColors(True)

        self.files_grid.setHeaderLabels(get_keys(Cols))
        self.files_grid.setColumnWidth(Cols.filename, 250)
        self.files_grid.setColumnWidth(Cols.local, 35)
        self.files_grid.setColumnWidth(Cols.web, 30)
        self.files_grid.setColumnWidth(Cols.association, 150)
        self.files_grid.setColumnWidth(Cols.notes, 500)

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

    def _enable_buttons(self, enable):
        self.btn_save_file_as.setDisabled(enable)
        self.btn_send_to_inverter.setDisabled(enable)

    def setup_buttons(self):
        self._enable_buttons(False)

        self.inverter_id.setReadOnly(False)  #TODO: Link to whether or not they have admin access
        self.show_inverter_id_error(None)


    def _remove_all_children(self, parent: QTreeWidgetItem):
        while parent.childCount() > 0:
            parent.removeChild(parent.child(0))

    # def show_files(self, associations):
    #     print('[Filesview] Files request finished')
    #     print(associations)
    #     sync_time = self.controller.get_sync_time()
    #     self.lbl_last_sync.setText(f'Last sync at:{sync_time}')
    #
    #     def _add_item(list: [dict], parent: QTreeWidgetItem):
    #         self._remove_all_children(parent)
    #
    #         for item in list:
    #             if item['file'] is not None:
    #                 cols = [
    #                     item['file']['filename'],
    #                     self.question_icon,
    #                     self.check_icon
    #
    #                 ]
    #                 widget = QTreeWidgetItem(parent, cols)
    #                 widget.obj = item
    #
    #     _add_item(associations['parameter'], self.section_headers.params)
    #     #_add_item(associations['pvms'], self.section_headers.pvms)
    #     _add_item(associations['firmware'], self.section_headers.firmware)
    #     #_add_item(associations['faultLogs'], self.section_headers.fault_logs)
    #     _add_item(associations['other'], self.section_headers.other)



    def attach_row_to_parent(self, type: str, filename):
        parents = {
            'firmware': self.section_headers.firmware,
            'log': self.section_headers.fault_logs,
            'other': self.section_headers.other,
            'parameter': self.section_headers.params,
            'pvms': self.section_headers.pvms
        }

        parent = parents[type]
        row = QTreeWidgetItem(parent, [filename, self.question_icon, self.check_icon])
        row.setTextAlignment(Cols.local, Qt.AlignRight)
        return row

    def remove_row(self, row: QTreeWidgetItem):
        self.files_grid.removeItemWidget(row)

    def show_relationship(self, row: QTreeWidgetItem, relationship: Relationships, rel_text: str):
        row.setBackground(Cols.association, relationship.value)
        row.setText(Cols.association, rel_text)

    ### Action
    def _notes_changed(self):
        ensureDeferred(self._disable_notes_buttons())

    def _reset_notes(self):
        self.notes.setPlainText(self.controller.old_notes)
        self.notes.moveCursor(QTextCursor.End)

    async def _disable_notes_buttons(self):
        changed = self.controller.notes_modified(self.notes.toPlainText())

        self.btn_save_notes.setDisabled(not changed)
        self.btn_reset_notes.setDisabled(not changed)

    def inverter_error_handler(self, error):
        if error.type is InverterNotFoundException:  #Twisted wraps errors in its own class
            self.show_inverter_id_error("Error: Inverter ID not found.")
        else:
            raise error


    ### UI Update methods
    def show_file_details(self, association):
        if association is not None:
            self.filename.setText(association['file']['filename'])
            self.version.setText(association['file']['version'])
            self.controller.set_original_notes(association['file']['notes'])
            self.notes.setPlainText(association['file']['notes'])
            self.notes.setReadOnly(False)
        else:
            self.filename.clear()
            self.version.clear()
            self.notes.setReadOnly(True)
            self.notes.clear()

    def enable_file_action_buttons(self, enabled):
        self.btn_send_to_inverter.setDisabled(not enabled)
        self.btn_save_file_as.setDisabled(not enabled)

    def show_inverter_id_error(self, error):
        if error is None:
            self.inverter_id_error.setText("")
        else:
            self.inverter_id_error.setText(f"<font color='red'>{error}</font>")

    def _save_file_as_clicked(self):
        ensureDeferred(self.controller.save_file_as_clicked())

# .ui files need a direct module attribute, not a class method, afaict.
FilesViewQtBuilder = FilesView.qt_build
