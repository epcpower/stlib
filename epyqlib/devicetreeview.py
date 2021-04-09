#!/usr/bin/env python3

# TODO: """DocString if there is one"""

import math
import pathlib
import textwrap
import uuid

import can
from PyQt5 import QtWidgets
from PyQt5.QtWidgets import QHeaderView, QMenu, QMessageBox, QInputDialog
from PyQt5.QtCore import Qt, pyqtSignal, QItemSelectionModel

import epyqlib.datalogger
import epyqlib.device
import epyqlib.devicetree
import epyqlib.devicetreeview_ui
import epyqlib.flash
import epyqlib.hildevice
import epyqlib.utils.general
import epyqlib.utils.qt
import epyqlib.utils.twisted

# See file COPYING in this source tree
__copyright__ = "Copyright 2017, EPC Power Corp."
__license__ = "GPLv2+"


class UnsupportedError(Exception):
    pass


def load_device(bus=None, file=None, parent=None):
    # TODO  CAMPid 9561616237195401795426778
    if file is None:
        filters = [("EPC Packages", ["epc", "epz"]), ("All Files", ["*"])]
        file = epyqlib.utils.qt.file_dialog(filters, parent=parent)

        if file is None:
            return

    try:
        return epyqlib.device.Device(file=file, bus=bus)
    except epyqlib.device.CancelError:
        pass

    return


class DeviceTreeView(QtWidgets.QWidget):
    device_selected = pyqtSignal(epyqlib.device.Device)

    def __init__(self, parent=None, in_designer=False):
        super().__init__(parent=parent)

        self.in_designer = in_designer

        self.ui = epyqlib.devicetreeview_ui.Ui_Form()
        self.ui.setupUi(self)

        self.resize_columns = epyqlib.devicetree.Columns(
            name=True,
            nickname=True,
            bitrate=True,
            transmit=True,
        )

        self.ui.tree_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ui.tree_view.customContextMenuRequested.connect(self.context_menu)

        self.model = None

    def _current_changed(self, new_index, old_index):
        node = self.model.node_from_index(new_index)
        if isinstance(node, epyqlib.devicetree.Device):
            device = node.device
            self.device_selected.emit(device)

    def context_menu(self, position):
        index = self.ui.tree_view.indexAt(position)

        if not index.isValid():
            return

        node = self.model.node_from_index(index)

        add_device_action = None
        remove_device_action = None
        check_software_hash_action = None
        change_device_number_action = None
        flash_action = None
        pull_raw_log_action = None
        check_compatibility_action = None
        write_to_epz_action = None
        blink_action = None

        menu = QMenu()
        if isinstance(node, epyqlib.devicetree.Device):
            offline = (
                not node.tree_parent._checked.name
                and not node.tree_parent.fields.name == "Offline"
            )

            pull_raw_log_action = menu.addAction("Pull Raw Log...")
            pull_raw_log_action.setEnabled(offline)

            write_to_epz_action = menu.addAction("Write To Epz...")
            write_to_epz_action.setEnabled(not node.device.from_zip)
            # TODO: stdlib zipfile can't create an encrypted .zip
            #       make a good solution that will...
            write_to_epz_action.setVisible(False)

            check_compatibility_action = menu.addAction("Check Compatibility")
            check_compatibility_action.setEnabled(not offline)

            remove_device_action = menu.addAction("Close")
        if isinstance(node, epyqlib.devicetree.Bus):
            add_device_action = menu.addAction("Open device file...")
            check_software_hash_action = menu.addAction("Check software hash...")
            check_software_hash_action.setEnabled(
                not node._checked.name
                and not node.fields.name == "Offline"
                and node.interface == "pcan"
                and node.bus.bus is None
            )
            change_device_number_action = menu.addAction("Change device number...")
            change_device_number_action.setEnabled(
                not node._checked.name
                and not node.fields.name == "Offline"
                and node.interface == "pcan"
                and node.bus.bus is None
            )
            flash_action = menu.addAction("Load firmware...")
            flash_action.setEnabled(
                not node._checked.name and not node.fields.name == "Offline"
            )
            blink_action = menu.addAction("Blink adapter")
            blink_action.setEnabled(
                node.interface == "pcan" and node.bus.bus is not None
            )

        action = menu.exec_(self.ui.tree_view.viewport().mapToGlobal(position))

        if action is None:
            pass
        elif action is remove_device_action:
            self.remove_device(node)
        elif action is add_device_action:
            device = self.add_device(node)
            if device is not None:
                self.ui.tree_view.selectionModel().setCurrentIndex(
                    self.model.index_from_node(device),
                    QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
                )
        elif action is check_software_hash_action:
            self.check_software_hash(node)
        elif action is change_device_number_action:
            self.change_device_number(node)
        elif action is flash_action:
            self.flash(interface=node.interface, channel=node.channel)
        elif action is pull_raw_log_action:
            self.pull_raw_log(node=node)
        elif action is write_to_epz_action:
            self.write_to_epz(device=node.device)
        elif action is check_compatibility_action:
            self.check_compatibility(device=node.device)
        elif action is blink_action:
            self.blink(bus=node.bus)

    def blink(self, bus):
        bus.flash()

    def check_compatibility(self, device):
        shas = device.compatibility_shas
        if len(shas) == 0:
            self.compatibility_notification(
                message="No compatible revisions specified for this device.",
                compatible=False,
            )
        else:
            try:
                signal = device.nvs.signal_from_names("SoftwareHash", "SoftwareHash")
            except epyqlib.nv.NotFoundError as e:
                raise UnsupportedError(
                    "Compatibility check is not supported for this device"
                ) from e

            d = device.nvs.protocol.read(signal)
            d.addCallback(self._check_compatibility, device=device)
            d.addErrback(epyqlib.utils.twisted.errbackhook)

    def _check_compatibility(self, value, device):
        sha = "{:07x}".format(int(value))

        compatible = any(s.startswith(sha) for s in device.compatibility_shas)
        print("alskflasdfasdfaslkfdasdfjsdjfasdfsd")
        print(sha)
        print(device.compatibility_shas)

        if compatible:
            message = "Embedded SHA {} found in compatibility list.".format(sha)
        else:
            message = "Embedded SHA {} not found in compatibility list.".format(sha)

        self.compatibility_notification(message=message, compatible=compatible)

    def compatibility_notification(self, message, compatible):
        if compatible:
            icon = QtWidgets.QMessageBox.Information
        else:
            icon = QtWidgets.QMessageBox.Warning

        epyqlib.utils.qt.dialog(
            parent=self,
            message=message,
            icon=icon,
        )

    def pull_raw_log(self, node):
        bus_node = node.tree_parent
        real_bus = can.interface.Bus(
            bustype=bus_node.interface,
            channel=bus_node.channel,
            bitrate=bus_node.bitrate,
        )
        bus = epyqlib.busproxy.BusProxy(bus=real_bus, auto_disconnect=False)

        d = epyqlib.datalogger.pull_raw_log(device=node.device, bus=bus, parent=self)
        d.addBoth(epyqlib.utils.twisted.detour_result, bus.set_bus)

    def add_device(self, bus, device=None):
        if device is None:
            device = load_device(parent=self)

        if device is not None:
            device.on_offline_bus = bus.fields.name == "Offline"
            device = epyqlib.devicetree.Device(device=device)

            self.model.add_device(bus, device)
            index = self.model.index_from_node(bus)
            index = self.model.index(index.row(), 0, index.parent())
            self.ui.tree_view.setExpanded(index, True)

        return device

    @epyqlib.utils.twisted.ensure_deferred
    @epyqlib.utils.twisted.errback_dialog
    async def check_software_hash(self, node):
        pcan_bus = can.interface.Bus(bustype=node.interface, channel=node.channel)

        try:
            # Recieve N messages on the PCAN bus.
            # Discover the node ID from the arbitration ID.
            # Store the found node ID's in a set.
            node_id_set = set()
            for i in range(100):
                recv_id = pcan_bus.recv(0.1)
                if recv_id is not None:
                    id = recv_id.arbitration_id & 0xFF
                    node_id_set.add(id)

            # Set up the device.
            factory_epc_path = pathlib.Path(epyqlib.tests.common.devices["factory"])
            device = epyqlib.hildevice.Device(
                definition_path=factory_epc_path,
            )
            device.load()
            bus_proxy = epyqlib.busproxy.BusProxy(
                bus=pcan_bus,
                auto_disconnect=False,
            )
            device.set_bus(bus_proxy)

            # Assumption that the UUID for software hash will not change.
            software_hash_parameter = device.parameter_from_uuid(
                uuid_=uuid.UUID("b132073c-740d-4390-96fc-e2c2f6cd8e50"),
            )
            hash = await software_hash_parameter.get()
            hash = int(hash)

            # Pop up dialog with software hash and node ID information.
            self.pcan_software_hash_pop_up_dialog(hash, node, node_id_set)
        finally:
            pcan_bus.shutdown()

    def pcan_software_hash_pop_up_dialog(self, hash, node, node_id_set):
        if len(node_id_set) == 0:
            node_id_out = "None Found"
        elif len(node_id_set) == 1:
            node_id_out = list(node_id_set)[0]
        else:
            node_id_out = list(node_id_set)
        text = "<table>"
        text += "<tr><td>PCAN Device: </td><td>"
        text += " - ".join([node.channel, str(node.device_number)])
        text += f"</td></tr><tr><td>Software Hash: </td><td>{hex(hash)}</td></tr>"
        text += f"<tr><td>Node ID: </td><td>{node_id_out}</td></tr>"
        text += "</table>"
        epyqlib.utils.qt.dialog(
            parent=self,
            title="Hash",
            message=text,
            icon=QtWidgets.QMessageBox.Information,
            rich_text=True,
            cancellable=False,
        )

    def change_device_number(self, node):
        pcan_bus = can.interface.Bus(bustype=node.interface, channel=node.channel)
        try:
            current_device_number = pcan_bus.get_device_number()
            new_device_number, ok = QInputDialog.getInt(
                None,
                *(("Device ID",) * 2),
                current_device_number,
                0,
                255,
            )

            if ok:
                if pcan_bus.set_device_number(new_device_number):
                    node.set_device_number(new_device_number)
                else:
                    raise Exception(
                        f"Unable to change device number from '{current_device_number}' to '{new_device_number}'."
                    )
        finally:
            pcan_bus.shutdown()

    def flash(self, interface, channel):
        # TODO  CAMPid 9561616237195401795426778
        filters = [("TICOFF Binaries", ["out"]), ("All Files", ["*"])]
        file = epyqlib.utils.qt.file_dialog(filters, parent=self)

        if file is not None:
            text = textwrap.dedent(
                """\
            Flashing {file}

            <ol>
              <li> Prepare module for programming
                <ul>
                  <li> Remove all high power from the module </li>
                  <li> Remove 24V control power </li>
                  <li> Install jumper between J1 pin 1 and pin 2 (+24V to Boot Enable), but do not reconnect 24V at this time </li>
                  <li> Ensure that the USB to CAN device is installed and connected to the appropriate CAN network </li>
                  <br>
                  <br>
                  <i> <b>Note:</b> no other devices may be active on the CAN network during programming operations </i>
                  <br>
                  <i> <b>Note:</b> firmware programming occurs at a CAN baud rate of 250kbits/sec.  If any CAN tools are in use during programming, they should be set to a baud rate of 250kbits/sec </i>
                </ul>
              </li>
              <br>
              <li> Apply firmware update via CAN
                <ul>
                  <li> Click OK </li>
                  <li> Reapply 24V control power </li>
                  <li> EPyQ will search for the module and should find it within a second or two </li>
                  <li> EPyQ will initiate clearing of module's flash memory </li>
                  <li> EPyQ will flash the device providing progress status </li>
                  <li> This whole process should take 1-2 minutes </li>
                </ul>
              </li>
              <br>
              <li> Restore System
                <ul>
                  <li> Remove 24V control power </li>
                  <li> Remove Boot Enable jumper </li>
                  <li> Power up module normally </li>
                </ul>
              </li>
            </ol>
            """.format(
                    file=file
                )
            )

            accepted = epyqlib.utils.qt.dialog(
                parent=self,
                title="Flashing",
                message=text,
                icon=QtWidgets.QMessageBox.Information,
                rich_text=True,
                cancellable=True,
            )

            if accepted:
                with open(file, "rb") as f:
                    real_bus = can.interface.Bus(
                        bustype=interface, channel=channel, bitrate=250000
                    )
                    bus = epyqlib.busproxy.BusProxy(bus=real_bus, auto_disconnect=False)

                    progress = epyqlib.utils.qt.progress_dialog(
                        parent=self, cancellable=True
                    )

                    flasher = epyqlib.flash.Flasher(
                        file=f,
                        bus=bus,
                        progress=progress,
                        retries=math.inf,
                        parent=self,
                    )

                    failed_box = QMessageBox(parent=self)
                    failed_box.setText(
                        textwrap.dedent(
                            """\
                    Flashing failed
                    """
                        )
                    )

                    canceled_box = QMessageBox(parent=self)
                    canceled_box.setText(
                        textwrap.dedent(
                            """\
                    Flashing canceled
                    """
                        )
                    )

                    flasher.done.connect(progress.close)
                    flasher.done.connect(progress.deleteLater)
                    flasher.done.connect(bus.set_bus)

                    completed_format = textwrap.dedent(
                        """\
                    Flashing completed successfully

                    Data time: {:.3f} seconds for {} bytes or {:.0f} bytes/second"""
                    )
                    flasher.completed.connect(
                        lambda f=flasher: print(
                            completed_format.format(
                                f.data_delta_time,
                                f.download_bytes,
                                f.download_bytes / f.data_delta_time,
                            )
                        )
                    )
                    flasher.completed.connect(
                        lambda f=flasher: QMessageBox.information(
                            self,
                            "EPyQ",
                            completed_format.format(
                                f.data_delta_time,
                                f.download_bytes,
                                f.download_bytes / f.data_delta_time,
                            ),
                        )
                    )
                    flasher.failed.connect(failed_box.exec)
                    flasher.canceled.connect(canceled_box.exec)
                    flasher.done.connect(bus.set_bus)

                    flasher.flash()

    def remove_device(self, device):
        self.ui.tree_view.clearSelection()
        self.model.remove_device(device)

    def write_to_epz(self, device):
        print(device.referenced_files)

        filters = [("EPZ", ["epz"]), ("All Files", ["*"])]
        filename = epyqlib.utils.qt.file_dialog(filters, save=True, parent=self)

        if filename is not None:
            epyqlib.utils.general.write_device_to_zip(
                zip_path=filename,
                epc_dir="",
                referenced_files=device.referenced_files,
                code=epyqlib.utils.qt.get_code(),
            )

    def setModel(self, model):
        self.model = model
        self.ui.tree_view.setModel(model)

        self.ui.tree_view.header().setStretchLastSection(False)

        for i, resize in enumerate(self.resize_columns):
            if resize:
                self.ui.tree_view.header().setSectionResizeMode(
                    i, QtWidgets.QHeaderView.ResizeToContents
                )

        self.ui.tree_view.setItemDelegateForColumn(
            epyqlib.devicetree.Columns.indexes.bitrate,
            epyqlib.delegates.ByFunction(model=model, parent=self),
        )

        self.ui.tree_view.selectionModel().currentChanged.connect(self._current_changed)

        widths = [
            self.ui.tree_view.columnWidth(i) for i in epyqlib.devicetree.Columns.indexes
        ]
        width = sum(widths)
        width += 2 * self.ui.tree_view.frameWidth()

        self.ui.tree_view.setMinimumWidth(1.25 * width)

        self.ui.tree_view.header().setSectionResizeMode(
            epyqlib.devicetree.Columns.indexes.name, QHeaderView.Stretch
        )


if __name__ == "__main__":
    import sys

    print("No script functionality here")
    sys.exit(1)  # non-zero is a failure
