import pathlib
from datetime import datetime
from enum import Enum

from epyqlib.tabs.files.log_manager import PendingLog
from typing import Dict

import PyQt5.uic
import attr
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QColor, QBrush, QTextCursor, QFont
from PyQt5.QtWidgets import (
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QLineEdit,
    QLabel,
    QPlainTextEdit,
    QGridLayout,
    QMenu,
    QTextEdit,
    QAction,
)
from twisted.internet.defer import ensureDeferred, inlineCallbacks

from epyqlib.utils.twisted import errbackhook as open_error_dialog

# noinspection PyUnreachableCode
if False:  # Tell the editor about the type, but don't invoke a cyclic depedency
    from epyqlib.device import DeviceInterface


from epyqlib.tabs.files.graphql import InverterNotFoundException

Ui, UiBase = PyQt5.uic.loadUiType(
    pathlib.Path(__file__).with_suffix(".ui"),
)


class _Sections:
    params: QTreeWidgetItem
    pmvs: QTreeWidgetItem
    firmware: QTreeWidgetItem
    raw_logs: QTreeWidgetItem
    other: QTreeWidgetItem


class Cols:
    filename = 0
    local = 1
    web = 2
    association = 3
    creator = 4
    uploaded_at = 5
    version = 6
    description = 7


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
    fa_check = ""
    fa_cross = ""
    fa_wifi = ""
    fa_question = ""

    fontawesome = QFont("fontawesome")
    color_black = QColor("black")
    color_blue = QColor("#1E93F6")
    color_green = QColor("green")
    color_gray = QColor("gray")
    color_red = QColor("red")

    device_interface: "DeviceInterface" = attr.ib(init=False)
    pending_log_rows: Dict[str, QTreeWidgetItem] = {}  # Hash -> Row

    time_format = "%m/%d %I:%M%p "

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

    def set_device_interface(self, device_interface):
        self.controller.device_interface_set(device_interface)

    def tab_selected(self):
        ensureDeferred(self.controller.tab_selected()).addErrback(open_error_dialog)

    def on_bus_status_changed(self):
        ensureDeferred(self.controller.on_bus_status_changed()).addErrback(
            open_error_dialog
        )

    ### Setup methods
    # noinspection PyAttributeOutsideInit
    def bind(self):
        self._log_text = ""
        self._current_file_id: str = None

        self.section_headers = _Sections()

        self.root: QGridLayout = self.ui.gridLayout

        self.lbl_login_status: QLabel = self.ui.lbl_login_status
        self.btn_login: QPushButton = self.ui.login

        self.lbl_serial_number: QLabel = self.ui.lbl_serial_number
        self.serial_number: QLineEdit = self.ui.serial_number
        self.inverter_error: QLabel = self.ui.lbl_inverter_error

        self.files_grid: QTreeWidget = self.ui.files_grid

        self.assigned_by: QLineEdit = self.ui.assigned_by
        self.assigned_time: QLineEdit = self.ui.assigned_time
        self.description: QLineEdit = self.ui.description
        self.filename: QLineEdit = self.ui.filename
        self.upload_time: QLineEdit = self.ui.upload_time
        self.version: QLineEdit = self.ui.version

        self.notes: QPlainTextEdit = self.ui.notes
        self.btn_save_notes: QPushButton = self.ui.save_notes
        self.btn_reset_notes: QPushButton = self.ui.reset_notes

        self.lbl_last_sync: QLabel = self.ui.last_sync
        self.btn_sync_now: QPushButton = self.ui.sync_now
        self.btn_sync_all: QPushButton = self.ui.sync_all

        self.event_log: QTextEdit = self.ui.event_log

        # Bind click events
        self.btn_login.clicked.connect(self._login_clicked)
        self.serial_number.returnPressed.connect(self._serial_number_entered)

        self.files_grid.itemClicked.connect(self.controller.file_item_clicked)

        self.btn_sync_now.clicked.connect(self._sync_now_clicked)
        self.btn_sync_all.clicked.connect(self._sync_all_clicked)

        self.notes.textChanged.connect(self._notes_changed)
        self.description.textChanged.connect(self._notes_changed)
        self.btn_save_notes.clicked.connect(self._save_notes_clicked)
        self.btn_reset_notes.clicked.connect(self._reset_notes)

        # Debug button
        self.btn_debug: QPushButton = self.ui.btn_debug
        self.btn_debug.setVisible(False)
        self.btn_debug.clicked.connect(self._debug_clicked)

        # Set initial state

    def populate_tree(self):
        self.files_grid.setAlternatingRowColors(True)

        self.files_grid.setHeaderLabels(get_keys(Cols))
        self.files_grid.setColumnWidth(Cols.filename, 250)
        self.files_grid.setColumnWidth(Cols.local, 35)
        self.files_grid.setColumnWidth(Cols.web, 30)
        self.files_grid.setColumnWidth(Cols.association, 150)
        self.files_grid.setColumnWidth(Cols.description, 500)
        self.files_grid.setColumnWidth(Cols.uploaded_at, 125)

        def make_entry(caption):
            val = QTreeWidgetItem(self.files_grid, [caption])
            val.setExpanded(True)
            return val

        self.section_headers.params = make_entry("Parameter Files")
        self.section_headers.pmvs = make_entry("Value Sets")
        self.section_headers.firmware = make_entry("Firmware")
        self.section_headers.raw_logs = make_entry("Fault Logs")
        self.section_headers.other = make_entry("Other files")

    def initialize_ui(self):
        self.files_grid.setContextMenuPolicy(Qt.CustomContextMenu)
        self.files_grid.customContextMenuRequested.connect(self._render_context_menu)

        self.btn_sync_now.setDisabled(True)

        self.serial_number.setReadOnly(
            False
        )  # TODO: Link to whether or not they have admin access
        self.show_inverter_error(None)

    def disable_serial_number_input(self, disable: bool):
        self.serial_number.setReadOnly(disable)

    def _remove_all_children(self, parent: QTreeWidgetItem):
        while parent.childCount() > 0:
            parent.removeChild(parent.child(0))

    def sort_grid_items(self):
        self.section_headers.raw_logs.sortChildren(
            Cols.uploaded_at, Qt.SortOrder.AscendingOrder
        )
        self.section_headers.params.sortChildren(
            Cols.filename, Qt.SortOrder.AscendingOrder
        )
        self.section_headers.other.sortChildren(
            Cols.filename, Qt.SortOrder.AscendingOrder
        )

    def set_serial_number(self, serial_number: str):
        self.serial_number.setText(serial_number)

    def inverter_error_handler(self, error):
        if (
            error.type is InverterNotFoundException
        ):  # Twisted wraps errors in its own class
            self.show_inverter_error("Error: Inverter ID not found.")
        else:
            raise error

    def get_parent_for_association_type(self, association_type: str):
        parents = {
            "firmware": self.section_headers.firmware,
            "log": self.section_headers.raw_logs,
            "other": self.section_headers.other,
            "parameter": self.section_headers.params,
            "pmvs": self.section_headers.pmvs,
        }

        return parents[association_type.lower()]

    def ensure_correct_parent_for_row(self, row: QTreeWidgetItem, type: str):
        new_parent = self.get_parent_for_association_type(type)
        if row.parent() is not new_parent:
            row.parent().removeChild(row)
            new_parent.addChild(row)

    def attach_row_to_parent(self, association_type: str, filename):
        parent = self.get_parent_for_association_type(association_type)
        row = QTreeWidgetItem(parent, [filename])
        row.setFont(Cols.local, self.fontawesome)
        row.setFont(Cols.web, self.fontawesome)

        row.setTextAlignment(Cols.local, Qt.AlignCenter)
        row.setTextAlignment(Cols.web, Qt.AlignCenter)

        return row

    def remove_row(self, row: QTreeWidgetItem):
        row.parent().removeChild(row)

    def render_association_to_row(self, association, row: QTreeWidgetItem):
        uploaded = association["file"]["createdAt"][:-1]  # Trim trailing "Z"
        uploaded = datetime.fromisoformat(uploaded)

        row.setText(Cols.filename, association["file"]["filename"])
        row.setText(Cols.version, association["file"]["version"])
        row.setText(Cols.uploaded_at, uploaded.strftime(self.time_format))
        row.setText(Cols.description, association["file"]["description"])

        if association["file"]["owner"] == "epc":
            font: QFont = row.font(Cols.creator)
            font.setBold(True)
            row.setFont(Cols.creator, font)
            row.setForeground(Cols.creator, self.color_blue)
            row.setFont(Cols.creator, row.font(Cols.creator))
            row.setText(Cols.creator, "EPC Power")
        else:
            row.setFont(Cols.creator, row.font(Cols.uploaded_at))
            row.setForeground(Cols.creator, self.color_black)
            row.setText(Cols.creator, association["file"].get("createdBy"))

        if association.get("model"):
            model_name = " " + association["model"]["name"]

            if association.get("customer"):
                relationship = Relationships.customer
                rel_text = association["customer"]["name"] + "," + model_name
            elif association.get("site"):
                relationship = Relationships.site
                rel_text = association["site"]["name"] + "," + model_name
            else:
                relationship = Relationships.model
                rel_text = "All" + model_name
        else:
            relationship = Relationships.inverter
            rel_text = "SN: " + association["inverter"]["serialNumber"]

        self.show_relationship(row, relationship, rel_text)

    def add_new_pending_log_row(self, log: PendingLog, ctime: datetime):
        row = self.attach_row_to_parent("log", log.filename)

        self.show_check_icon(row, Cols.local)
        self.show_question_icon(row, Cols.web)

        self.show_relationship(row, Relationships.inverter, f"SN: {log.serial_number}")
        row.setText(Cols.uploaded_at, ctime.strftime(self.time_format))
        row.setText(Cols.creator, log.username)

        self.pending_log_rows[log.hash] = row

    def show_relationship(
        self, row: QTreeWidgetItem, relationship: Relationships, rel_text: str
    ):
        row.setBackground(Cols.association, relationship.value)
        row.setText(Cols.association, rel_text)

    ### Action
    def _serial_number_entered(self):
        self.controller._serial_number = self.serial_number.text()
        ensureDeferred(self.controller.sync_now()).addErrback(open_error_dialog)

    def _debug_clicked(self):
        sync_def = ensureDeferred(self.controller.debug())
        sync_def.addErrback(open_error_dialog)

    def _sync_now_clicked(self):
        sync_def = ensureDeferred(self.controller.sync_now())
        sync_def.addErrback(open_error_dialog)

    def _sync_all_clicked(self):
        sync_def = ensureDeferred(self.controller.sync_all())
        sync_def.addErrback(open_error_dialog)

    def _login_clicked(self):
        ensureDeferred(self.controller.login_clicked()).addErrback(open_error_dialog)

    def _notes_changed(self):
        changed = self.controller.notes_modified(
            self.description.text(), self.notes.toPlainText()
        )
        ensureDeferred(self._disable_notes_buttons(not changed)).addErrback(
            open_error_dialog
        )

    def _save_notes_clicked(self):
        new_desc = self.description.text()
        new_text = self.notes.toPlainText()
        ensureDeferred(
            self.controller.save_notes(self._current_file_id, new_desc, new_text)
        ).addCallback(
            lambda _: ensureDeferred(self._disable_notes_buttons(True))
        ).addErrback(
            open_error_dialog
        )

    def _reset_notes(self):
        self.notes.setPlainText(self.controller.old_notes)
        self.notes.moveCursor(QTextCursor.End)

    async def _disable_notes_buttons(self, disabled: bool):
        self.btn_save_notes.setDisabled(disabled)
        self.btn_reset_notes.setDisabled(disabled)

    def _render_context_menu(self, position: QPoint):
        item = self.files_grid.itemAt(position)
        if item is None:
            # User clicked empty space below the list items
            return
        parent = item.parent()

        menu_pos = self.files_grid.viewport().mapToGlobal(position)

        if parent is self.section_headers.raw_logs:
            self._render_raw_log_menu(menu_pos, item)
        elif parent is self.section_headers.other:
            self._render_other_file_menu(menu_pos, item)
        elif parent is self.section_headers.firmware:
            self._render_firmware_menu(menu_pos, item)
        elif parent is self.section_headers.params:
            self._render_param_file_menu(menu_pos, item)

    def _render_firmware_menu(self, menu_pos: QPoint, item: QTreeWidgetItem):
        menu = QMenu(self.files_grid)
        send_to_inverter = menu.addAction("Flash to inverter")
        send_to_inverter.setDisabled(True)
        save_as = menu.addAction("Save firmware as...")

        action = menu.exec(menu_pos)

        if action is None:
            pass
        elif action is save_as:
            ensureDeferred(self.controller.save_file_as_clicked(item))
        elif action is send_to_inverter:
            pass  # TODO: [EPC] Implement this

    def _render_other_file_menu(self, menu_pos: QPoint, item: QTreeWidgetItem):
        menu = QMenu(self.files_grid)
        open = menu.addAction("Open file")
        save_as = menu.addAction("Save file as...")

        action = menu.exec(menu_pos)

        if action is None:
            pass
        elif action is open:
            self.controller.open_file(item)
        elif action is save_as:
            ensureDeferred(self.controller.save_file_as_clicked(item))

    def _render_param_file_menu(self, menu_pos: QPoint, item: QTreeWidgetItem):
        menu = QMenu(self.files_grid)
        dummy = menu.addAction("Send dummy File Loaded event to web tool")
        scratch = menu.addAction("Send to scratch")
        active = menu.addAction("Send to active")
        inverter = menu.addAction("Send to inverter")
        save_as = menu.addAction("Save file as...")

        btn: QAction
        [btn.setDisabled(True) for btn in [scratch, active, inverter]]

        action = menu.exec(menu_pos)

        if action is None:
            pass
        elif action is dummy:
            ensureDeferred(self.controller.send_dummy_param_event(item))
        elif action is scratch:
            pass
        elif action is active:
            pass
        elif action is inverter:
            pass
        elif action is save_as:
            ensureDeferred(self.controller.save_file_as_clicked(item))

    def _render_raw_log_menu(self, menu_pos: QPoint, item: QTreeWidgetItem):
        # item_hash = next(hash for hash, row in self.pending_log_rows.items() if row == item)
        cached = self.controller.is_file_cached_locally(item)

        menu = QMenu(self.files_grid)
        download_local = menu.addAction("Download local copy")
        process_log = menu.addAction("Process raw log")
        save_as = menu.addAction("Save file as...")
        delete_local = menu.addAction("Delete local copy")

        download_local.setDisabled(cached)
        process_log.setDisabled(True and not cached)  # Disable until implemented
        save_as.setDisabled(not cached)
        delete_local.setDisabled(not cached)

        action = menu.exec(menu_pos)

        if action is None:
            pass
        elif action is download_local:
            file_hash = self.controller.get_hash_for_row(item)
            ensureDeferred(self.controller.download_log(file_hash)).addErrback(
                open_error_dialog
            ).addCallback(lambda _: self.show_check_icon(item, Cols.local))
        elif action is process_log:
            pass
            # TODO: Implement this
        elif action is save_as:
            ensureDeferred(self.controller.save_file_as_clicked(item))
        elif action is delete_local:
            file_hash = self.controller.get_hash_for_row(item)
            self.controller.cache_manager.delete_from_cache(file_hash)
            self.show_cross_status_icon(item, Cols.local)
            pass

    def _show_sync_status_icon(
        self, row: QTreeWidgetItem, col: int, icon: str, color: QColor
    ):
        row.setText(col, icon)
        row.setForeground(col, color)

    def show_check_icon(self, row: QTreeWidgetItem, col: int):
        self._show_sync_status_icon(row, col, self.fa_check, self.color_green)

    def show_question_icon(self, row: QTreeWidgetItem, col: int):
        self._show_sync_status_icon(row, col, self.fa_question, self.color_red)

    def show_cross_status_icon(self, row: QTreeWidgetItem, col: int):
        self._show_sync_status_icon(row, col, self.fa_cross, self.color_gray)

    ### UI Update methods
    def show_logged_out_warning(self):
        error = (
            "Warning: You are not currently logged in to EPC Sync. "
            + "To sync the latest configuration files for this inverter, login here:"
        )
        self.lbl_login_status.setText(f"<font color='red'><b>{error}</b></font>")
        self._show_login_bar_widgets(False)

    def show_logged_in_status(self, connected: bool, username: str = None):
        status = "connected" if connected else "offline"
        message = f"Internet status: {status}."
        if connected:
            message = f"Logged in as {username}. " + message

        self.lbl_login_status.setText(message)
        self._show_login_bar_widgets(True)

    def _show_login_bar_widgets(self, enabled: bool):
        self.btn_login.setHidden(enabled)

        self.lbl_serial_number.setHidden(not enabled)
        self.serial_number.setHidden(not enabled)
        self.inverter_error.setHidden(not enabled)

    def show_file_details(self, association, readonly_description=False):
        if association is None:
            # Clicked on a section header
            self.filename.clear()
            self.version.clear()
            self.controller.set_original_notes("", "")
            self.description.clear()
            self.description.setReadOnly(True)
            self.notes.clear()
            self.notes.setReadOnly(True)
            return

        self.controller.set_original_notes(
            association["file"]["description"], association["file"]["notes"]
        )

        self._current_file_id = association["file"]["id"]
        self.filename.setText(association["file"]["filename"])
        self.version.setText(association["file"]["version"])
        self.description.setText(association["file"]["description"])
        self.description.setReadOnly(readonly_description)
        self.notes.setPlainText(association["file"]["notes"])
        self.notes.setReadOnly(readonly_description)

    def show_inverter_error(self, error):
        if error is None:
            self.inverter_error.setText("")
        else:
            self.inverter_error.setText(f"<font color='red'>{error}</font>")

    def show_sync_time(self, time: datetime):
        self.lbl_last_sync.setText(f"Last sync at: {time.strftime(self.time_format)}")

    def add_log_error_line(self, message: str):
        self.add_log_line(f"<font color='#cc0000'>{message}</font>")

    def add_log_line(self, message: str):
        timestamp = datetime.now()
        new_text = f"<font color='lightGray'>[{timestamp.strftime(self.time_format).strip()}]</font> {message}<br/>"
        self._log_text = new_text + self._log_text
        self.event_log.setText(self._log_text)


# .ui files need a direct module attribute, not a class method, afaict.
FilesViewQtBuilder = FilesView.qt_build
