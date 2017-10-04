import collections
import contextlib
import decimal
import json
import logging
import uuid
import weakref

import attr
from PyQt5 import QtCore
import PyQt5.QtCore

import epyqlib.abstractcolumns
import epyqlib.pyqabstractitemmodel
import epyqlib.treenode
import epyqlib.utils.general

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


logger = logging.getLogger()


@attr.s
class Column:
    name = attr.ib()
    fields = attr.ib()


@attr.s
class Columns:
    columns = attr.ib()

    def __getitem__(self, item):
        if isinstance(item, str):
            column, = (
                column
                for column in self.columns
                if column.name == item
            )
            return column

        if isinstance(item, tuple):
            column, = (
                column
                for column in self.columns
                if column.fields[item[0]] == item[1]
            )
            return column

        return self.columns[item]


def columns(*columns):
    def _name(column):
        cls, field_name = column

        field = getattr(attr.fields(cls), field_name)
        name = field.metadata.get('human name')

        if name is None:
            name = field.name.replace('_', ' ').title()

        return name

    return Columns(
        columns=tuple(
            Column(name=_name(c[0]), fields=dict(c))
            for c in columns
        ),
    )


@attr.s
class Types:
    types = attr.ib(
        convert=(
            lambda types:
            collections.OrderedDict((t.__name__, t) for t in types)
        ),
        default=(),
    )

    def __attrs_post_init__(self):
        for t in self.types.values():
            add_addable_types(cls=t, types=self)

    def __getitem__(self, item):
        return tuple(self.types.values())[item]

    def resolve(self, type_, default=None):
        if type_ is None and default is not None:
            return default

        if isinstance(type_, str):
            return self.types[type_]

        return type_


def add_addable_types(cls, attribute_name='children', types=None):
    if types is None:
        types = Types()

    if hasattr(cls, 'addable_types'):
        raise Exception(
            'Unable to add addable_types(), it is already defined')

    @classmethod
    def addable_types(cls):
        if cls.addable_types_cache is None:
            if not hasattr(cls, attribute_name):
                return {}

            resolved_types = tuple(
                types.resolve(type_=t, default=cls)
                for t in getattr(attr.fields(cls), attribute_name)
                    .metadata['valid_types']
            )

            cls.addable_types_cache = collections.OrderedDict()

            for t in resolved_types:
                type_attribute = attr.fields(t).type
                name = type_attribute.default.title()
                name = type_attribute.metadata.get('human name', name)
                cls.addable_types_cache[name] = t

        return cls.addable_types_cache

    cls.addable_types = addable_types
    cls.addable_types_cache = None
    cls.addable_types()

    return cls


def Root(default_name, valid_types):
    valid_types = tuple(valid_types)

    @epyqlib.utils.qt.pyqtify()
    @attr.s(hash=False)
    class Root(epyqlib.treenode.TreeNode):
        type = attr.ib(default='root', init=False)
        name = attr.ib(default=default_name)
        children = attr.ib(
            default=attr.Factory(list),
            metadata={
                'ignore': True,
                'valid_types': valid_types
            }
        )
        uuid = attr_uuid()

        def __attrs_post_init__(self):
            super().__init__()

        @classmethod
        def from_json(cls, obj):
            children = obj.pop('children')
            node = cls(**obj)

            for child in children:
                node.append_child(child)

            return node

        def to_json(self):
            return attr.asdict(
                self,
                recurse=False,
                dict_factory=collections.OrderedDict,
                filter=lambda a, _: a.metadata.get('to_file', True)
            )

        def can_drop_on(self, node):
            return isinstance(node, tuple(self.addable_types().values()))

    return Root


def attr_uuid(*args, **kwargs):
    return attr.ib(
        default=None,
        convert=lambda x: x if x is None else uuid.UUID(x),
        *args,
        **kwargs
    )


def to_decimal_or_none(s):
    if s is None:
        return None

    if isinstance(s, str) and len(s) == 0:
        return None

    try:
        result = decimal.Decimal(s)
    except decimal.InvalidOperation as e:
        raise ValueError('Invalid number: {}'.format(repr(s))) from e

    return result


def two_state_checkbox(v):
    return v in (QtCore.Qt.Checked, True)


def ignored_attribute_filter(attribute):
    return not attribute.metadata.get('ignore', False)


class Decoder(json.JSONDecoder):
    types = ()

    def __init__(self, *args, **kwargs):
        super().__init__(object_hook=self.object_hook,
                         parse_float=decimal.Decimal,
                         parse_int=decimal.Decimal,
                         *args,
                         **kwargs)

    def object_hook(self, obj):
        obj_type = obj.get('type', None)

        if isinstance(obj, list):
            return obj

        for t in self.types:
            if obj_type == attr.fields(t).type.default:
                obj.pop('type')
                return t.from_json(obj)

        raise Exception('Unexpected object found: {}'.format(obj))


class Encoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, list):
            return obj

        elif type(obj) == epyqlib.treenode.TreeNode:
            if obj.tree_parent is None:
                return [self.default(c) for c in obj.children]

        if isinstance(obj, decimal.Decimal):
            i = int(obj)
            if i == obj:
                d = i
            else:
                d = float(obj)
        elif isinstance(obj, uuid.UUID):
            d = str(obj)
        else:
            d = obj.to_json()

        return d


def check_uuids(*roots):
    def collect(node, uuids):
        if node.uuid is not None:
            if node.uuid in uuids:
                raise Exception('Duplicate uuid found: {}'.format(node.uuid))

            uuids.add(node.uuid)

    def set_nones(node, uuids):
        if node.uuid is None:
            while node.uuid is None:
                u = uuid.uuid4()
                if u not in uuids:
                    node.uuid = u
                    uuids.add(node.uuid)

    uuids = set()

    for root in set(roots):
        root.traverse(call_this=collect, payload=uuids, internal_nodes=True)

    for root in set(roots):
        root.traverse(call_this=set_nones, payload=uuids, internal_nodes=True)


class Model(epyqlib.pyqabstractitemmodel.PyQAbstractItemModel):
    def __init__(self, root, columns, parent=None):
        super().__init__(root=root, parent=parent)

        self.mime_type = 'application/com.epcpower.pm.attrsmodel'

        self.columns = columns
        self.headers = tuple(c.name for c in self.columns)

        self.droppable_from = set()

        self.connected_signals = {}

        check_uuids(self.root)

        def connect(node, _, root=root):
            if node is not root:
                self.pyqtify_connect(node.tree_parent, node)

        self.root.traverse(
            call_this=connect,
            internal_nodes=True,
        )

    @classmethod
    def from_json_string(cls, s, columns, types,
                         decoder=Decoder):
        # Ugly but maintains the name 'types' both for the parameter
        # and in D.
        t = types
        del types

        class D(Decoder):
            types = t

        root = json.loads(s, cls=D)

        return cls(
            root=root,
            columns=columns
        )

    def to_json_string(self):
        return json.dumps(self.root, cls=Encoder, indent=4)

    def add_drop_sources(self, *sources):
        self.droppable_from.update(sources)
        check_uuids(self.root, *self.droppable_from)

    def flags(self, index):
        flags = super().flags(index)

        field = self.get_field(index)

        if field is not None:
            if field.convert is two_state_checkbox:
                flags |= QtCore.Qt.ItemIsUserCheckable
            elif field.metadata.get('editable', True):
                flags |= QtCore.Qt.ItemIsEditable

            flags |= QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled

        return flags

    def get_field(self, index):
        c = index.column()
        t = type(self.node_from_index(index))
        name = self.columns[c].fields.get(t)

        if name is None:
            return None

        return getattr(attr.fields(t), name)

    def data_display(self, index):
        field = self.get_field(index)

        if field is None:
            return ''

        if field.convert is two_state_checkbox:
            return ''

        node = self.node_from_index(index)

        data = getattr(node, field.name)
        if data is None:
            return '-'

        return str(data)

    def data_edit(self, index):
        return self.data_display(index)

    def data_check_state(self, index):
        node = self.node_from_index(index)

        attribute = self.get_field(index)
        if attribute is not None:
            if attribute.convert is two_state_checkbox:
                if getattr(node, attribute.name):
                    return QtCore.Qt.Checked
                else:
                    return QtCore.Qt.Unchecked

        return None

    def setData(self, index, data, role=None):
        node = self.node_from_index(index)
        attribute = self.get_field(index)

        if role == QtCore.Qt.EditRole:
            convert = attribute.convert
            if convert is not None:
                try:
                    converted = convert(data)
                except ValueError:
                    return False
            else:
                converted = data

            setattr(node, attribute.name, converted)

            self.dataChanged.emit(index, index)
            return True
        elif role == QtCore.Qt.CheckStateRole:
            setattr(node, attribute.name, attribute.convert(data))

            return True

        return False

    def pyqtify_connect(self, parent, child):
        connections = {}
        self.connected_signals[(parent, child)] = connections

        for i, column in enumerate(self.columns):
            name = column.fields.get(type(child))
            if name is None:
                continue

            signal = getattr(child.__pyqtify_instance__.changed, name)

            def slot(_):
                self.changed(
                    child, i,
                    child, i,
                    (PyQt5.QtCore.Qt.DisplayRole,),
                )

            connections[signal] = slot
            signal.connect(slot)

    def pyqtify_disconnect(self, parent, child):
        connections = self.connected_signals.pop((parent, child))

        for signal, slot in connections.items():
            signal.disconnect(slot)

    def add_child(self, parent, child):
        row = len(parent.children)
        self.begin_insert_rows(parent, row, row)
        parent.append_child(child)

        self.pyqtify_connect(parent, child)

        if child.uuid is None:
            check_uuids(self.root)

        self.end_insert_rows()

    def delete(self, node):
        row = node.tree_parent.row_of_child(node)
        self.begin_remove_rows(node.tree_parent, row, row)

        self.pyqtify_disconnect(node.tree_parent, node)

        node.tree_parent.remove_child(child=node)
        self.end_remove_rows()

    def supportedDropActions(self):
        return QtCore.Qt.MoveAction

    def mimeTypes(self):
        return (self.mime_type,)

    def mimeData(self, indexes):
        [node] = {self.node_from_index(i) for i in indexes}
        m = QtCore.QMimeData()
        m.setData(self.mime_type, node.uuid.bytes)

        return m

    def dropMimeData(self, data, action, row, column, parent):
        logger.debug('entering dropMimeData()')
        logger.debug((data, action, row, column, parent))

        node, new_parent, row = self.source_target_for_drop(
            column, data, parent, row)

        if action == QtCore.Qt.MoveAction:
            logger.debug('node name: {}'.format(node.name))
            logger.debug((data, action, row, column, parent))
            logger.debug('dropped on: {}'.format(new_parent.name))

            local = node.find_root() == self.root

            if local:
                from_row = node.tree_parent.row_of_child(node)

                success = self.beginMoveRows(
                    self.index_from_node(node.tree_parent),
                    from_row,
                    from_row,
                    self.index_from_node(new_parent),
                    row
                )

                if not success:
                    return False

                self.pyqtify_disconnect(node.tree_parent, node)
                node.tree_parent.remove_child(child=node)

                self.index_from_node_cache = weakref.WeakKeyDictionary()

                new_parent.insert_child(row, node)
                self.pyqtify_connect(new_parent, node)

                self.endMoveRows()

                return True
            else:
                new_child = new_parent.child_from(node)
                self.add_child(new_parent, new_child)

        return False

    def source_target_for_drop(self, column, data, parent, row):
        new_parent = self.node_from_index(parent)
        if row == -1 and column == -1:
            if parent.isValid():
                row = 0
            else:
                row = len(self.root.children)
        u = uuid.UUID(bytes=bytes(data.data(self.mime_type)))
        source = self.node_from_uuid(u)
        return source, new_parent, row

    def node_from_uuid(self, u):
        def uuid_matches(node, matches):
            if node.uuid == u:
                matches.add(node)

        nodes = set()
        for root in self.droppable_from:
            root.traverse(
                call_this=uuid_matches,
                payload=nodes,
                internal_nodes=True
            )

        [node] = nodes

        return node

    def canDropMimeData(self, mime, action, row, column, parent):
        node, new_parent, _ = self.source_target_for_drop(
            column, mime, parent, row)
        can_drop = new_parent.can_drop_on(node=node)

        logger.debug('canDropMimeData: {}: {}, {}'.format(
            new_parent.name, row, can_drop))

        return can_drop
