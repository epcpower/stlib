import logging

logger = logging.getLogger(__name__)

import attr
import epyqlib.abstractcolumns
import epyqlib.chunkedmemorycache as cmc
import epyqlib.cmemoryparser
import epyqlib.pyqabstractitemmodel
import epyqlib.treenode
import epyqlib.twisted.cancalibrationprotocol as ccp
import epyqlib.utils.qt
import epyqlib.utils.twisted
import epyqlib.variableselectionmodel
import functools
import io
import itertools
import json
import math
import natsort
import sys
import textwrap
import time
import twisted.internet.defer
import twisted.internet.threads

from PyQt5.QtCore import (
    Qt,
    QVariant,
    QModelIndex,
    pyqtSignal,
    pyqtSlot,
    QTimer,
    QObject,
    QCoreApplication,
)
from PyQt5.QtWidgets import QMessageBox

# See file COPYING in this source tree
__copyright__ = "Copyright 2016, EPC Power Corp."
__license__ = "GPLv2+"


class Columns(epyqlib.abstractcolumns.AbstractColumns):
    _members = ["name", "type", "address", "size", "bits", "value", "file"]


Columns.indexes = Columns.indexes()


def hashes_match(this, that):
    return this.startswith(that) or that.startswith(this)


class Sender(QObject):
    array_truncated_signal = pyqtSignal(int, str, int)

    def __init__(self, slot, parent=None):
        super().__init__(parent=parent)

        self.array_truncated_signal.connect(slot)

    def array_truncated(self, maximum_children, name, length):
        self.array_truncated_signal.emit(maximum_children, name, length)


def build_node_tree(variables, array_truncated_slot):
    root = epyqlib.variableselectionmodel.Variables()

    for variable in variables:
        node = VariableNode(variable=variable)
        root.append_child(node)
        node.add_members(
            base_type=epyqlib.cmemoryparser.base_type(variable),
            address=variable.address,
        )

    return root


class VariableNode(epyqlib.treenode.TreeNode):
    def __init__(
        self,
        variable,
        name=None,
        address=None,
        bits=None,
        tree_parent=None,
        comparison_value=None,
    ):
        epyqlib.treenode.TreeNode.__init__(self, parent=tree_parent)

        self.variable = variable
        name = name if name is not None else variable.name
        address = address if address is not None else variable.address
        if bits is None:
            bits = ""

        filename = ""
        if hasattr(variable, "file"):
            filename = variable.file

        base_type = epyqlib.cmemoryparser.base_type(variable)
        type_name = epyqlib.cmemoryparser.type_name(variable)

        self.fields = Columns(
            name=name,
            type=type_name,
            address="0x{:08X}".format(address),
            size=base_type.bytes,
            bits=bits,
            value=None,
            file=filename,
        )

        self.comparison_value = comparison_value

        self._checked = Columns.fill(Qt.Unchecked)

    def unique(self):
        return id(self)

    def checked(self, column=Columns.indexes.name):
        return self._checked[column]

    def set_checked(self, checked, column=Columns.indexes.name):
        was_checked = self._checked[column]
        self._checked[column] = checked

        if was_checked != checked and Qt.Checked in [was_checked, checked]:
            if self.tree_parent.tree_parent is None:
                self.update_checks()
            else:
                self.tree_parent.update_checks()

    def address(self):
        return int(self.fields.address, 16)

    def addresses(self):
        address = self.address()
        return [address + offset for offset in range(self.fields.size)]

    def update_checks(self):
        def append_address(node, addresses):
            if node.checked() == Qt.Checked:
                addresses |= set(node.addresses())

        addresses = set()

        top_ancestor = self
        while top_ancestor.tree_parent.tree_parent is not None:
            top_ancestor = top_ancestor.tree_parent

        top_ancestor.traverse(
            call_this=append_address, payload=addresses, internal_nodes=True
        )

        def set_partially_checked(node, _):
            if node.checked() != Qt.Checked:
                if not set(node.addresses()).isdisjoint(addresses):
                    check = Qt.PartiallyChecked
                else:
                    check = Qt.Unchecked

                node.set_checked(check)

        self.traverse(call_this=set_partially_checked, internal_nodes=True)

        ancestor = self
        while ancestor.tree_parent is not None:
            if ancestor.checked() != Qt.Checked:
                if not set(ancestor.addresses()).isdisjoint(addresses):
                    change_to = Qt.PartiallyChecked
                else:
                    change_to = Qt.Unchecked

                ancestor.set_checked(change_to)

            ancestor = ancestor.tree_parent

    def path(self):
        path = []
        node = self
        while isinstance(node, type(self)):
            path.insert(0, node.fields.name)
            node = node.tree_parent

        return path

    def qualified_name(self):
        names = iter(self.path())

        qualified_name = next(names)

        for name in names:
            if name.startswith("["):
                n = int(name[1:-1])
                qualified_name += "[{}]".format(n)
            else:
                qualified_name += "." + name

        return qualified_name

    def chunk_updated(self, data):
        self.fields.value = self.variable.unpack(data)

    def add_members(self, base_type, address, expand_pointer=False, sender=None):
        new_members = []

        if isinstance(base_type, epyqlib.cmemoryparser.Struct):
            new_members.extend(self.add_struct_members(base_type, address))

        if isinstance(base_type, epyqlib.cmemoryparser.ArrayType):
            new_members.extend(
                self.add_array_members(base_type, address, sender=sender)
            )

        if expand_pointer and isinstance(base_type, epyqlib.cmemoryparser.PointerType):
            new_members.extend(self.add_pointer_members(base_type, address))

        if isinstance(base_type, epyqlib.cmemoryparser.Union):
            new_members.extend(self.add_union_members(base_type, address))

        for child in self.children:
            base_type = epyqlib.cmemoryparser.base_type(child.variable)
            address = child.address()
            if self.child_is_multidimensional_array_inner_node():
                base_type = epyqlib.cmemoryparser.base_type(self.variable)
                address = self.address()

            new_members.extend(
                child.add_members(
                    base_type=base_type,
                    address=address,
                    # do not expand child pointers since we won't have their values
                )
            )

        return new_members

    def add_struct_members(self, base_type, address):
        new_members = []
        for name, member in base_type.members.items():
            child_address = address + base_type.offset_of([name])
            child_node = VariableNode(
                variable=member, name=name, address=child_address, bits=member.bit_size
            )
            self.append_child(child_node)
            new_members.append(child_node)

        return new_members

    def child_is_multidimensional_array_inner_node(self):
        if isinstance(self.variable.type, epyqlib.cmemoryparser.ArrayType):
            indexes = self.array_indexes()
            if len(indexes) + 1 < len(self.variable.type.dimensions):
                return True

        return False

    def array_indexes(self):
        indexes = ()
        parent = self
        while parent.tree_parent is not None and parent.fields.name.startswith("["):
            indexes += (int(parent.fields.name[1:-1]),)
            parent = parent.tree_parent

        return indexes

    def add_array_members(self, base_type, address, sender=None):
        indexes = self.array_indexes()

        new_members = []
        digits = len(str(base_type.dimensions[len(indexes)]))
        format = "[{{:0{}}}]".format(digits)

        maximum_children = 256

        if self.child_is_multidimensional_array_inner_node():
            child_type = base_type
        else:
            child_type = base_type.type

        # Check for the case where base_type.dimensions is [None].
        if None not in base_type.dimensions:
            for index in range(
                min(base_type.dimensions[len(indexes)], maximum_children)
            ):
                child_address = address + base_type.offset_of(*(indexes + (index,)))
                variable = epyqlib.cmemoryparser.Variable(
                    name=format.format(index),
                    type=child_type,
                    address=child_address,
                )
                child_node = VariableNode(variable=variable, comparison_value=index)
                self.append_child(child_node)
                new_members.append(child_node)

            if base_type.dimensions[len(indexes)] > maximum_children:
                if sender is not None:
                    sender.array_truncated(
                        maximum_children, self.fields.name, base_type.length()
                    )

                # TODO: add a marker showing visually that it has been truncated

        return new_members

    def add_pointer_members(self, base_type, address):
        new_members = []
        target_type = epyqlib.cmemoryparser.base_type(base_type.type)
        if not isinstance(target_type, epyqlib.cmemoryparser.UnspecifiedType):
            variable = epyqlib.cmemoryparser.Variable(
                name="*{}".format(self.fields.name),
                type=base_type.type,
                address=self.fields.value,
            )
            child_node = VariableNode(variable=variable)
            self.append_child(child_node)
            new_members.append(child_node)

        return new_members

    def add_union_members(self, base_type, address):
        new_members = []

        for name, member in base_type.members.items():
            child_node = VariableNode(
                variable=member,
                name=name,
                address=address,
            )
            self.append_child(child_node)
            new_members.append(child_node)

        return new_members

    def get_node(self, *variable_path, root=None):
        if root is None:
            root = self

        variable = root

        for name in variable_path:
            if name is None:
                raise TypeError("Unable to search by None")

            (variable,) = (
                v
                for v in variable.children
                if name in (v.fields.name, v.comparison_value)
            )

        return variable


class Variables(epyqlib.treenode.TreeNode):
    # TODO: just Rx?
    changed = pyqtSignal(
        epyqlib.treenode.TreeNode, int, epyqlib.treenode.TreeNode, int, list
    )
    begin_insert_rows = pyqtSignal(epyqlib.treenode.TreeNode, int, int)
    end_insert_rows = pyqtSignal()

    def __init__(self):
        epyqlib.treenode.TreeNode.__init__(self)

        self.fields = Columns.fill("")

    def unique(self):
        return id(self)


@attr.s
class CacheAndRawChunks:
    cache = attr.ib()
    raw_chunks = attr.ib()


class VariableModel(epyqlib.pyqabstractitemmodel.PyQAbstractItemModel):
    binary_loaded = pyqtSignal()

    def __init__(
        self,
        nvs,
        nv_model,
        bus,
        tx_id=0x1FFFFFFF,
        rx_id=0x1FFFFFF7,
        parent=None,
    ):
        checkbox_columns = Columns.fill(False)
        checkbox_columns.name = True

        root = epyqlib.variableselectionmodel.Variables()

        epyqlib.pyqabstractitemmodel.PyQAbstractItemModel.__init__(
            self, root=root, checkbox_columns=checkbox_columns, parent=parent
        )

        self.headers = Columns(
            name="Name",
            type="Type",
            address="Address",
            size="Size",
            bits="Bits",
            value="Value",
            file="File",
        )

        self.nvs = nvs
        self.nv_model = nv_model
        self.bus = bus

        self.git_hash = None

        self.bits_per_byte = None

        self.cache = None

        self.pull_log_progress = epyqlib.utils.qt.Progress()

        if self.nvs is not None:
            signal = self.nvs.neo.signal_by_path("CCP", "Connect", "CommandCounter")
            self.protocol = ccp.Handler(
                endianness="little" if signal.little_endian else "big",
                tx_id=tx_id,
                rx_id=rx_id,
            )
            from twisted.internet import reactor

            self.transport = epyqlib.twisted.busproxy.BusProxy(
                protocol=self.protocol, reactor=reactor, bus=self.bus
            )
        else:
            self.protocol = None
            self.transport = None

        # TODO: consider using locale?  but maybe not since it's C code not
        #       raw strings
        self.sort_key = natsort.natsort_keygen(alg=natsort.ns.IGNORECASE)
        self.role_functions[epyqlib.utils.qt.UserRoles.sort] = self.data_sort

    def data_sort(self, index):
        node = self.node_from_index(index)

        return self.sort_key(node.fields[index.column()])

    def array_truncated_message(self, maximum_children, name, length):
        message = (
            "Arrays over {} elements are truncated.\n"
            "This has happened to `{}`[{}].".format(maximum_children, name, length)
        )
        epyqlib.utils.qt.dialog(
            parent=None,
            message=message,
            icon=QMessageBox.Information,
        )

    def setData(self, index, data, role=None):
        if index.column() == Columns.indexes.name:
            if role == Qt.CheckStateRole:
                node = self.node_from_index(index)

                node.set_checked(data)

                # TODO: CAMPid 9349911217316754793971391349
                parent = node.tree_parent
                self.changed(
                    parent.children[0],
                    Columns.indexes.name,
                    parent.children[-1],
                    Columns.indexes.name,
                    [Qt.CheckStateRole],
                )

                return True

    # TODO: CAMPid 0754876134967813496896843168
    @twisted.internet.defer.inlineCallbacks
    def update_from_loaded_binary(self, binary_info):
        names, variables, bits_per_byte = binary_info

        self.bits_per_byte = bits_per_byte
        self.names = names

        [self.git_hash] = [
            v for v in variables if v.name.startswith("dataLogger_gitRev_")
        ]
        self.git_hash = self.git_hash.name.split("0x", 1)[1]

        logger.debug("Updating from binary, {} variables".format(len(variables)))

        root = yield twisted.internet.threads.deferToThread(
            build_node_tree,
            variables=variables,
            array_truncated_slot=self.array_truncated_message,
        )

        logger.debug("Creating cache")
        cache = yield twisted.internet.threads.deferToThread(
            self.create_cache, only_checked=False, subscribe=True, root=root
        )
        logger.debug("Done creating cache")

        self.beginResetModel()
        self.root = root
        self.endResetModel()

        self.cache = cache

        self.binary_loaded.emit()

    # TODO: CAMPid 0754876134967813496896843168
    def update_from_loaded_binary_without_threads(self, binary_info):
        names, variables, bits_per_byte = binary_info

        self.bits_per_byte = bits_per_byte
        self.names = names

        [self.git_hash] = [
            v for v in variables if v.name.startswith("dataLogger_gitRev_")
        ]
        self.git_hash = self.git_hash.name.split("0x", 1)[1]

        logger.debug("Updating from binary, {} variables".format(len(variables)))

        root = build_node_tree(
            variables=variables, array_truncated_slot=self.array_truncated_message
        )

        logger.debug("Creating cache")
        cache = self.create_cache(only_checked=False, subscribe=True, root=root)
        logger.debug("Done creating cache")

        self.beginResetModel()
        self.root = root
        self.endResetModel()

        self.cache = cache

    def assign_root(self, root):
        self.root = root

    def save_selection(self, filename):
        selected = []

        def add_if_checked(node, selected):
            if node is self.root:
                return

            if node.checked() == Qt.Checked:
                selected.append(node.path())

        self.root.traverse(
            call_this=add_if_checked, payload=selected, internal_nodes=True
        )

        with open(filename, "w") as f:
            json.dump(selected, f, indent="    ")

    def load_selection(self, filename):
        with open(filename, "r") as f:
            selected = json.load(f)

        def check_if_selected(node, _):
            if node is self.root:
                return

            if node.path() in selected:
                node.set_checked(Qt.Checked)

        self.root.traverse(call_this=check_if_selected, internal_nodes=True)

    def create_cache(
        self,
        only_checked=True,
        subscribe=False,
        include_partially_checked=False,
        test=None,
        root=None,
    ):
        def default_test(node):
            acceptable_states = {Qt.Unchecked, Qt.PartiallyChecked, Qt.Checked}

            if only_checked:
                acceptable_states.discard(Qt.Unchecked)

                if not include_partially_checked:
                    acceptable_states.discard(Qt.PartiallyChecked)

            return node.checked() in acceptable_states

        if test is None:
            test = default_test

        if root is None:
            root = self.root

        cache = cmc.Cache(bits_per_byte=self.bits_per_byte)

        def update_parameter(node, cache):
            if node is root:
                return

            if test(node):
                # Check specifically for None value. Zero shouldn't be a value for size, but just in case.
                if node.fields.size is not None:
                    # TODO: CAMPid 0457543543696754329525426
                    chunk = cache.new_chunk(
                        address=int(node.fields.address, 16),
                        bytes=self.zero_bytes(node.fields.size),
                        reference=node,
                    )
                    cache.add(chunk)

                    if subscribe:
                        callback = functools.partial(
                            self.update_chunk,
                            node=node,
                        )
                        cache.subscribe(callback, chunk)

        root.traverse(call_this=update_parameter, payload=cache, internal_nodes=True)

        return cache

    def zero_bytes(self, length):
        return b"\x00" * (self.bits_per_byte // 8) * length

    def update_chunk(self, data, node):
        node.chunk_updated(data)

        self.changed(
            node,
            Columns.indexes.value,
            node,
            Columns.indexes.value,
            roles=[Qt.DisplayRole],
        )

        if isinstance(node.variable.type, epyqlib.cmemoryparser.PointerType):
            # http://doc.qt.io/qt-5/qabstractitemmodel.html#layoutChanged
            # TODO: review other uses of layoutChanged and possibly 'correct' them
            self.layoutAboutToBeChanged.emit()
            index = self.index_from_node(node)
            for row, child in enumerate(node.children):
                self.unsubscribe(node=child, recurse=True)
                node.remove_child(row=row)
            new_members = node.add_members(
                base_type=epyqlib.cmemoryparser.base_type(node.variable.type),
                address=node.address(),
                expand_pointer=True,
            )
            self.changePersistentIndex(index, self.index_from_node(node))
            self.layoutChanged.emit()

            for node in new_members:
                # TODO: CAMPid 0457543543696754329525426
                chunk = self.cache.new_chunk(
                    address=int(node.fields.address, 16),
                    bytes=self.zero_bytes(node.fields.size),
                    reference=node,
                )
                self.cache.add(chunk)

                self.subscribe(node=node, chunk=chunk)

    def update_parameters(self, parent=None):
        cache = self.create_cache()

        set_frames = self.nvs.logger_set_frames()

        chunks = cache.contiguous_chunks()

        frame_count = len(set_frames)
        chunk_count = len(chunks)
        if chunk_count == 0:
            result = QMessageBox.question(
                parent,
                "Clear all logging parameters?",
                ("No variables are selected.  " "Do you want to clear all logging?"),
            )

            if result == QMessageBox.No:
                return
        elif chunk_count > frame_count:
            chunks = chunks[:frame_count]

            message_box = QMessageBox(parent=parent)
            message_box.setStandardButtons(QMessageBox.Ok)

            text = (
                "Variable selection yields {chunks} memory chunks but "
                "is limited to {frames}.  Selection has been truncated.".format(
                    chunks=chunk_count, frames=frame_count
                )
            )

            epyqlib.utils.qt.dialog(
                parent=parent,
                message=text,
                icon=QMessageBox.Warning,
            )

        destination_column = epyqlib.nv.Columns.indexes.value

        self.nv_model.start_transaction()

        for chunk, frame in itertools.zip_longest(
            chunks, set_frames, fillvalue=cache.new_chunk(0, 0)
        ):
            print(
                "{address}+{size}".format(
                    address="0x{:08X}".format(chunk._address),
                    size=len(chunk._bytes) // (self.bits_per_byte // 8),
                )
            )

            address_signal = frame.signal_by_name("Address")
            bytes_signal = frame.signal_by_name("Bytes")

            index = self.nv_model.index_from_node(address_signal)
            self.nv_model.setData(
                index=index.siblingAtColumn(destination_column),
                data=chunk._address,
                role=Qt.EditRole,
            )

            index = self.nv_model.index_from_node(bytes_signal)
            self.nv_model.setData(
                index=index.siblingAtColumn(destination_column),
                data=len(chunk._bytes) // (self.bits_per_byte // 8),
                role=Qt.EditRole,
            )

        self.nv_model.submit_transaction()

    def record_header_length(self):
        [x] = self.names["DataLogger_RecordHeader"]
        return x.type.bytes * (self.bits_per_byte // 8)

    def block_header_length(self):
        try:
            [block_header] = self.names["DataLogger_BlockHeader"]
        except KeyError:
            block_header_bytes = 0
        else:
            block_header_bytes = block_header.type.bytes

        return block_header_bytes * (self.bits_per_byte // 8)

    def parse_log(self, data, csv_path):
        data_stream = io.BytesIO(data)
        raw_header = data_stream.read(self.block_header_length())

        [x] = self.names["DataLogger_BlockHeader"]
        block_header_node = self.parse_block_header_into_node(
            raw_header=raw_header, bits_per_byte=self.bits_per_byte, block_header_type=x
        )

        cache_and_raw_chunk = self.create_log_cache(block_header_node)
        cache = cache_and_raw_chunk.cache
        raw_chunks = cache_and_raw_chunk.raw_chunks

        [x] = self.names["DataLogger_RecordHeader"]
        # TODO: hardcoded 32-bit addressing and offset assumption
        #       intended to avoid collision
        record_header_address = 2 ** 32 + 100
        record_header = epyqlib.cmemoryparser.Variable(
            name=".record_header", type=x, address=record_header_address
        )
        record_header_node = VariableNode(variable=record_header)
        record_header_node.add_members(
            base_type=epyqlib.cmemoryparser.base_type(record_header),
            address=record_header.address,
        )
        for node in record_header_node.leaves():
            chunk = cache.new_chunk(
                address=int(node.fields.address, 16),
                bytes=self.zero_bytes(node.fields.size),
                reference=node,
            )
            cache.add(chunk)

        raw_chunks.insert(
            0,
            cache.new_chunk(
                address=record_header_node.variable.address,
                bytes=self.zero_bytes(record_header_node.variable.type.bytes),
            ),
        )

        if self.git_hash is not None:
            [hash_node] = [
                n for n in block_header_node.children if n.fields.name == "softwareHash"
            ]

            if hash_node.fields.value is not None:
                log_hash = "{:07x}".format(hash_node.fields.value)
            else:
                log_hash = str(hash_node.fields.value)

            if not hashes_match(self.git_hash, log_hash):
                d = twisted.internet.defer.Deferred()
                d.errback(
                    Exception(
                        "Git hashes from .out ({}) and the log ({}) do not match".format(
                            self.git_hash, log_hash
                        )
                    )
                )
                return d

        [sample_period_node] = [
            n for n in block_header_node.children if n.fields.name == "samplePeriod_us"
        ]
        sample_period_us = sample_period_node.fields.value

        chunks = sorted(
            cache.contiguous_chunks(),
            key=lambda c: (c._address != record_header_address, c),
        )

        variables_and_chunks = {chunk.reference: chunk for chunk in cache._chunks}

        d = twisted.internet.threads.deferToThread(
            epyqlib.datalogger.parse_log,
            cache=cache,
            chunks=chunks,
            csv_path=csv_path,
            data_stream=data_stream,
            variables_and_chunks=variables_and_chunks,
            sample_period_us=sample_period_us,
            raw_chunks=raw_chunks,
        )

        return d

    def create_log_cache(self, block_header_node):
        chunk_ranges = []
        chunks_node = block_header_node.get_node("chunks")
        for chunk in chunks_node.children:
            address = chunk.get_node("address")
            address = address.fields.value
            size = chunk.get_node("bytes")
            size = size.fields.value
            chunk_ranges.append((address, size))

        def contained_by_a_chunk(node):
            if len(node.children) > 0:
                return False

            node_lower = int(node.fields.address, 16)
            node_upper = node_lower + node.fields.size - 1

            for lower, size in chunk_ranges:
                upper = lower + size - 1
                if lower <= node_lower and node_upper <= upper:
                    return True

            return False

        cache = self.create_cache(test=contained_by_a_chunk, subscribe=False)
        raw_chunks = [
            cache.new_chunk(
                address=address,
                bytes=self.zero_bytes(size),
            )
            for address, size in chunk_ranges
            if address != 0 and size != 0
        ]

        return CacheAndRawChunks(cache=cache, raw_chunks=raw_chunks)

    def parse_block_header_into_node(
        self, raw_header, bits_per_byte, block_header_type
    ):
        # TODO: hardcoded 32-bit addressing and offset assumption
        #       intended to avoid collision
        block_header_cache = cmc.Cache(bits_per_byte=bits_per_byte)
        block_header = epyqlib.cmemoryparser.Variable(
            name=".block_header", type=block_header_type, address=0
        )
        block_header_node = VariableNode(variable=block_header)
        block_header_node.add_members(
            base_type=epyqlib.cmemoryparser.base_type(block_header),
            address=block_header.address,
        )
        for node in block_header_node.leaves():
            chunk = block_header_cache.new_chunk(
                address=int(node.fields.address, 16),
                bytes=self.zero_bytes(node.fields.size),
                reference=node,
            )
            block_header_cache.add(chunk)

            block_header_cache.subscribe(node.chunk_updated, chunk)
        block_header_chunk = block_header_cache.new_chunk(
            address=int(block_header_node.fields.address, 16),
            bytes=self.zero_bytes(block_header_node.fields.size),
        )
        block_header_chunk.set_bytes(raw_header)
        block_header_cache.update(block_header_chunk)
        return block_header_node

    def get_variable_nodes_by_type(self, type_name):
        return (node for node in self.root.children if node.fields.type == type_name)

    @twisted.internet.defer.inlineCallbacks
    def get_variable_value(self, *variable_path):
        variable = self.root.get_node(*variable_path)
        value = yield self._get_variable_value(variable)

        twisted.internet.defer.returnValue(value)

    @twisted.internet.defer.inlineCallbacks
    def _get_variable_value(self, variable):
        # TODO: hardcoded station address, tsk-tsk
        yield self.protocol.connect(station_address=0)
        data = yield self.protocol.upload_block(
            address_extension=ccp.AddressExtension.raw,
            address=variable.address(),
            octets=variable.fields.size * (self.bits_per_byte // 8),
        )
        yield self.protocol.disconnect()

        value = variable.variable.unpack(data)

        twisted.internet.defer.returnValue(value)

    def subscribe(self, node, chunk):
        callback = functools.partial(
            self.update_chunk,
            node=node,
        )
        self.cache.subscribe(callback, chunk, reference=node)

    def unsubscribe(self, node, recurse=True):
        self.cache.unsubscribe_by_reference(reference=node)

        if recurse:
            for child in node.children:
                self.unsubscribe(node=child, recurse=recurse)

    def read(self, variable):
        d = self._read(variable)
        d.addErrback(epyqlib.utils.twisted.errbackhook)

    @twisted.internet.defer.inlineCallbacks
    def _read(self, variable):
        # TODO: just call get_variable_value()?
        chunk = self.cache.new_chunk(
            address=int(variable.fields.address, 16),
            bytes=self.zero_bytes(variable.fields.size),
        )

        # TODO: hardcoded station address, tsk-tsk
        yield self.protocol.connect(station_address=0)
        data = yield self.protocol.upload_block(
            address_extension=ccp.AddressExtension.raw,
            address=variable.address(),
            octets=variable.fields.size * (self.bits_per_byte // 8),
        )
        yield self.protocol.disconnect()

        chunk.set_bytes(data)
        self.cache.update(update_chunk=chunk)
