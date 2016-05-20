#!/usr/bin/env python3

#TODO: """DocString if there is one"""

import can
import epyq.pyqabstractitemmodel
import functools
import sys
import time

from collections import OrderedDict
from epyq.abstractcolumns import AbstractColumns
from epyq.treenode import TreeNode
from PyQt5.QtCore import (Qt, QVariant, QModelIndex, pyqtSignal, pyqtSlot,
                          QPersistentModelIndex)
from PyQt5.QtWidgets import QFileDialog

# See file COPYING in this source tree
__copyright__ = 'Copyright 2016, EPC Power Corp.'
__license__ = 'GPLv2+'


class Columns(AbstractColumns):
    _members = ['name', 'bitrate']

Columns.indexes = Columns.indexes()

bitrates = OrderedDict([
    (1000000, '1 MBit/s'),
    (500000, '500 kBit/s'),
    (250000, '250 kBit/s'),
    (125000, '125 kBit/s')
])

default_bitrate = 500000

def available_buses():
    valid = []

    for interface in can.interface.VALID_INTERFACES:
        if interface == 'pcan':
            for n in range(1, 9):
                channel = 'PCAN_USBBUS{}'.format(n)
                try:
                    bus = can.interface.Bus(bustype=interface, channel=channel)
                except:
                    pass
                else:
                    bus.shutdown()
                    valid.append({'interface': interface,
                                  'channel': channel})
        elif interface == 'socketcan':
            for n in range(9):
                channel = 'can{}'.format(n)
                try:
                    bus = can.interface.Bus(bustype=interface, channel=channel)
                except:
                    pass
                else:
                    bus.shutdown()
                    valid.append({'interface': interface,
                                  'channel': channel})
            for n in range(9):
                channel = 'vcan{}'.format(n)
                try:
                    bus = can.interface.Bus(bustype=interface, channel=channel)
                except:
                    pass
                else:
                    bus.shutdown()
                    valid.append({'interface': interface,
                                  'channel': channel})
        else:
            print('Availability check not implemented for {}'
                  .format(interface), file=sys.stderr)

    return valid


class Bus(TreeNode):
    def __init__(self, interface, channel):
        TreeNode.__init__(self)

        self.interface = interface
        self.channel = channel

        self.bitrate = default_bitrate
        self.separator = ' - '

        self.bus = epyq.busproxy.BusProxy()

        self.fields = Columns(name='{}{}{}'.format(self.interface,
                                                   self.separator,
                                                   self.channel),
                              bitrate=bitrates[self.bitrate])

        self._checked = Qt.Unchecked

    def set_data(self, data):
        for key, value in bitrates.items():
            if data == value:
                self.bitrate = key
                self.fields.bitrate = data

                self.set_bus()

        raise ValueError('{} not found in {}'.format(
            data,
            ', '.join(bitrates.values())
        ))

    def enumeration_strings(self):
        return bitrates.values()

    def unique(self):
        return '{} - {}'.format(self.interface, self.channel)

    def append_child(self, child):
        TreeNode.append_child(self, child)

    def checked(self, column=None):
        return self._checked

    def set_checked(self, checked):
        self._checked = checked

        if self._checked == Qt.Checked:
            for device in self.children:
                if device.checked() != Qt.Unchecked:
                    device.set_checked(Qt.Checked)
        elif self._checked == Qt.Unchecked:
            for device in self.children:
                if device.checked() != Qt.Unchecked:
                    device.set_checked(Qt.PartiallyChecked)

        self.set_bus()

    def set_bus(self):
        if self.interface == 'offline':
            return
        self.bus.set_bus(None)

        if self._checked == Qt.Checked:
            real_bus = can.interface.Bus(bustype=self.interface,
                                         channel=self.channel,
                                         bitrate=self.bitrate)
            # TODO: Yuck, but it helps recover after connecting to a bus with
            #       the wrong speed.  So, find a better way.
            time.sleep(0.5)
        else:
            real_bus = None

        self.bus.set_bus(bus=real_bus)


class Device(TreeNode):
    def __init__(self, device):
        TreeNode.__init__(self)

        self.device = device

        self.fields = Columns(name=device.name,
                              bitrate='')

        self._checked = Qt.Unchecked

    def unique(self):
        return self.device.name

    def checked(self, column=None):
        return self._checked

    def set_checked(self, checked):
        if checked == Qt.Checked:
            if self.tree_parent.checked() == Qt.Checked:
                self._checked = Qt.Checked
            else:
                if self._checked == Qt.Unchecked:
                    self._checked = Qt.PartiallyChecked
                else:
                    self._checked = Qt.Unchecked
        elif checked == Qt.PartiallyChecked:
            self._checked = Qt.PartiallyChecked
        else:
            self._checked = Qt.Unchecked

        if self._checked == Qt.Unchecked:
            self.device.bus.set_bus()
        else:
            self.device.bus.set_bus(self.tree_parent.bus)


class Tree(TreeNode):
    def __init__(self):
        TreeNode.__init__(self)


class Model(epyq.pyqabstractitemmodel.PyQAbstractItemModel):
    device_removed = pyqtSignal(epyq.device.Device)

    def __init__(self, root, parent=None):
        for bus in available_buses() + [{'interface': 'offline', 'channel': ''}]:
            bus = Bus(interface=bus['interface'],
                      channel=bus['channel'])
            root.append_child(bus)
            went_offline = functools.partial(self.went_offline, node=bus)
            bus.bus.went_offline.connect(went_offline)

        editable_columns = Columns.fill(False)
        editable_columns.bitrate = True

        checkbox_columns = Columns.fill(False)
        checkbox_columns.name = True

        epyq.pyqabstractitemmodel.PyQAbstractItemModel.__init__(
                self, root=root, editable_columns=editable_columns,
                checkbox_columns=checkbox_columns, parent=parent)

        self.headers = Columns(name='Name',
                               bitrate='Bitrate')

    def went_offline(self, node):
        # TODO: trigger gui update, or find a way that does it automatically
        node.set_checked(Qt.Unchecked)
        self.changed(node, Columns.indexes.name,
                     node, Columns.indexes.name,
                     [Qt.CheckStateRole])

    def setData(self, index, data, role=None):
        if index.column() == Columns.indexes.bitrate:
            if role == Qt.EditRole:
                node = self.node_from_index(index)
                try:
                    node.set_data(data)
                except ValueError:
                    return False
                self.dataChanged.emit(index, index)
                return True
        elif index.column() == Columns.indexes.name:
            if role == Qt.CheckStateRole:
                node = self.node_from_index(index)

                node.set_checked(checked=data)

                children = len(node.children)
                if children > 0:
                    self.changed(node.children[0], Columns.indexes.name,
                                 node.children[-1], Columns.indexes.name,
                                 [Qt.CheckStateRole])

                return True

        return False

    def add_device(self, bus, device):
        index = len(bus.children)

        # TODO: move to TreeNode?
        self.begin_insert_rows(bus, index, index)
        bus.append_child(device)
        self.end_insert_rows()

        persistent_index = QPersistentModelIndex(self.index_from_node(bus))
        self.layoutChanged.emit([persistent_index])

    def remove_device(self, device):
        bus = device.tree_parent
        row = bus.children.index(device)

        self.begin_remove_rows(bus, row, row)
        bus.remove_child(row)
        self.end_remove_rows()

        persistent_index = QPersistentModelIndex(self.index_from_node(bus))
        self.layoutChanged.emit([persistent_index])

        # TODO: This reset should not be needed but I have been unable
        #       so far to resolve them otherwise.  Since this doesn't
        #       happen much the performance cost is low but it does
        #       collapse the entire tree...
        self.beginResetModel()
        self.endResetModel()

        self.device_removed.emit(device.device)

if __name__ == '__main__':
    import sys

    print('No script functionality here')
    sys.exit(1)     # non-zero is a failure
