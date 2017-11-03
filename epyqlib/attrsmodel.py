import collections
import contextlib
import decimal
import inspect
import json
import logging
import uuid
import weakref

import attr
import graham
import graham.fields
import marshmallow
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

    def __iter__(self):
        return iter(self.fields)

    def items(self):
        return self.fields.items()


class ConsistencyError(Exception):
    pass


class NotFoundError(Exception):
    pass


@attr.s
class Metadata:
    name = attr.ib(default=None)
    data_display = attr.ib(default=None)
    editable = attr.ib(default=True)
    human_name = attr.ib(default=None)
    convert = attr.ib(default=None)
    no_column = attr.ib(default=False)


metadata_key = object()


@attr.s
class Attributes:
    fields = attr.ib()


def ify():
    def inner(cls):
        class Fields:
            def __iter__(self):
                return (
                    getattr(self, field.name)
                    for field in attr.fields(type(self))
                )

        for field in attr.fields(cls):
            setattr(Fields, field.name, attr.ib())

        Fields = attr.s(Fields)

        field_metadata = collections.defaultdict(dict)
        for field in attr.fields(cls):
            metadata = field.metadata.get(metadata_key)

            extras = {}
            if field.name == 'children':
                extras['no_column'] = True

            if metadata is None:
                metadata = Metadata(name=field.name, **extras)
            else:
                metadata = attr.evolve(metadata, name=field.name, **extras)

            if metadata.convert is None:
                metadata.convert = field.convert

            field_metadata[field.name] = metadata

        setattr(
            cls,
            attribute_name,
            Attributes(
                fields=Fields(**field_metadata),
            ),
        )

        return cls

    return inner


attribute_name = epyqlib.utils.general.identifier_path(Attributes)


def attributes(cls):
    return getattr(cls, attribute_name)


def fields(cls):
    return attributes(cls).fields


def attrib(*args, attribute, **kwargs):
    # https://github.com/python-attrs/attrs/issues/278
    if len(attribute.metadata) == 0:
        attribute.metadata = {}

    attribute.metadata[metadata_key] = Metadata(*args, **kwargs)

    return attribute


def data_processor(cls, data_field, attribute_field):
    metadata = getattr(attributes(cls).fields, data_field.name)
    d = getattr(metadata, attribute_field.name)

    return d


@attr.s
class Columns:
    columns = attr.ib()

    def __iter__(self):
        return iter(self.columns)

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

        field = getattr(fields(cls), field_name)
        name = field.human_name

        if name is None:
            name = field_name.replace('_', ' ').title()

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

        if isinstance(type_, marshmallow.Schema):
            return type_.data_class

        return type_


def create_addable_types(types):
    return collections.OrderedDict((
        (
            type_.__name__,
            type_,
        )
        for type_ in types
    ))


def add_addable_types(cls, attribute_name='children', types=None):
    if types is None:
        types = Types()

    if hasattr(cls, 'addable_types') or hasattr(cls, 'all_addable_types'):
        return

    @classmethod
    def addable_types(cls):
        if cls.addable_types_cache is None:
            field = graham.schema(cls).fields.get(attribute_name)
            if field is None:
                return {}

            resolved_types = tuple(
                types.resolve(type_=t.nested, default=cls)
                for t in field.instances
            )

            cls.addable_types_cache = create_addable_types(resolved_types)

        return cls.addable_types_cache

    cls.addable_types = addable_types
    cls.all_addable_types = addable_types
    cls.addable_types_cache = None
    cls.addable_types()

    return cls


def Root(default_name, valid_types):
    @graham.schemify(tag='root')
    @epyqlib.attrsmodel.ify()
    @epyqlib.utils.qt.pyqtify()
    @attr.s(hash=False)
    class Root(epyqlib.treenode.TreeNode):
        name = attr.ib(
            default=default_name,
        )
        graham.attrib(
            attribute=name,
            field=marshmallow.fields.String(),
        )

        children = attr.ib(
            default=attr.Factory(list),
        )
        graham.attrib(
            attribute=children,
            field=graham.fields.MixedList(fields=(
                marshmallow.fields.Nested(graham.schema(type_))
                for type_ in valid_types
                # marshmallow.fields.Nested('Group'),
                # marshmallow.fields.Nested(graham.schema(Leaf)),
            )),
        )

        uuid = attr_uuid()

        def __attrs_post_init__(self):
            super().__init__()


        def can_drop_on(self, node):
            return isinstance(node, tuple(self.addable_types().values()))

        @staticmethod
        def can_delete(node=None):
            if node is None:
                return False

            return True

        def nodes_by_attribute(self, attribute_value, attribute_name):
            def matches(node, matches):
                if not hasattr(node, attribute_name):
                    return

                if getattr(node, attribute_name) == attribute_value:
                    matches.add(node)

            nodes = set()
            self.traverse(
                call_this=matches,
                payload=nodes,
                internal_nodes=True
            )

            if len(nodes) == 0:
                raise NotFoundError(
                    '''Attribute '{}' with value '{}' not found'''.format(
                        attribute_name,
                        attribute_value,
                    )
                )

            return nodes

    return Root


def convert_uuid(x):
    if x is None or isinstance(x, uuid.UUID):
        return x

    return uuid.UUID(x)


def attr_uuid(metadata=None, default=attr.Factory(uuid.uuid4), **field_options):
    if metadata is None:
        metadata = {}

    attribute = attr.ib(
        default=default,
        convert=convert_uuid,
        metadata=metadata,
    )
    graham.attrib(
        attribute=attribute,
        field=marshmallow.fields.UUID(**field_options),
    )
    attrib(
        attribute=attribute,
        human_name='UUID',
    )

    return attribute


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


def to_str_or_none(s):
    if s is None:
        return None

    if isinstance(s, str):
        if len(s) == 0:
            return None

        return s

    return str(s)


def to_int_or_none(s):
    if s is None:
        return None

    if isinstance(s, str) and len(s) == 0:
        return None

    try:
        result = int(s)
    except ValueError as e:
        raise ValueError('Invalid number: {}'.format(repr(s))) from e

    return result


def two_state_checkbox(v):
    return v in (QtCore.Qt.Checked, True)


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


def childless_can_delete(self, node=None):
    if node is not None:
        raise ConsistencyError(
            'No children to be considered'
        )

    return self.tree_parent.can_delete(node=self)


class Model(epyqlib.pyqabstractitemmodel.PyQAbstractItemModel):
    def __init__(self, root, columns, parent=None):
        super().__init__(root=root, parent=parent)

        self.mime_type = 'application/com.epcpower.pm.attrsmodel'

        self.columns = columns
        self.headers = tuple(c.name for c in self.columns)

        self.droppable_from = set()

        self.connected_signals = {}

        check_uuids(self.root)

        def connect(node, _):
            self.pyqtify_connect(node.tree_parent, node)

        self.root.traverse(
            call_this=connect,
            internal_nodes=True,
        )


    def add_drop_sources(self, *sources):
        self.droppable_from.update(sources)
        check_uuids(self.root, *self.droppable_from)

    def flags(self, index):
        flags = super().flags(index)

        field = self.get_field(index)

        if field is not None:
            node = self.node_from_index(index)

            if field.convert is two_state_checkbox:
                flags |= QtCore.Qt.ItemIsUserCheckable
            elif getattr(fields(node), field.name).editable:
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

    def data_display(self, index, replace_none='-'):
        field = self.get_field(index)

        if field is None:
            return ''

        if field.convert is two_state_checkbox:
            return ''

        node = self.node_from_index(index)

        data = getattr(node, field.name)
        processor = data_processor(type(node), field, Metadata.data_display)
        if processor is not None:
            return processor(data)

        if data is None:
            return replace_none

        return str(data)

    def data_edit(self, index):
        return self.data_display(index, replace_none='')

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
        def key_value(instance, name, slot):
            signal = inspect.getattr_static(obj=instance, attr=name)
            return ((signal, (instance, slot)),)

        connections = {}
        if (parent, child) in self.connected_signals:
            raise ConsistencyError('already connected: {}'.format((parent, child)))
        self.connected_signals[(parent, child)] = connections

        for i, column in enumerate(self.columns):
            name = column.fields.get(type(child))
            if name is None:
                continue

            def slot(_, i=i):
                self.changed(
                    child, i,
                    child, i,
                    (PyQt5.QtCore.Qt.DisplayRole,),
                )

            connections.update(key_value(
                instance=child.__pyqtify_instance__.changed,
                name='_pyqtify_signal_' + name,
                slot=slot,
            ))

        connections.update(key_value(
            instance=child.pyqt_signals,
            name='child_added',
            slot=self.child_added,
        ))
        connections.update(key_value(
            instance=child.pyqt_signals,
            name='child_removed',
            slot=self.deleted,
        ))

        for signal, (instance, slot) in connections.items():
            signal.__get__(instance).connect(slot)

    def pyqtify_disconnect(self, parent, child):
        connections = self.connected_signals.pop((parent, child))

        for signal, (instance, slot) in connections.items():
            signal.__get__(instance).disconnect(slot)

    def child_added(self, child, row):
        parent = child.tree_parent

        from_index = None
        if len(parent.children) == 1:
            from_index = self.index_from_node(parent)
            persistent_index = PyQt5.QtCore.QPersistentModelIndex(from_index)
            self.layoutAboutToBeChanged.emit([persistent_index])

        self.begin_insert_rows(parent, row, row)

        self.pyqtify_connect(parent, child)

        if child.uuid is None:
            check_uuids(self.root)

        self.end_insert_rows()

        if from_index is not None:
            to_index = self.index_from_node(parent)
            self.changePersistentIndex(from_index, to_index)
            self.layoutChanged.emit([persistent_index])

    def deleted(self, parent, node, row):
        from_index = None
        if len(parent.children) == 1:
            from_index = self.index_from_node(parent)
            persistent_index = PyQt5.QtCore.QPersistentModelIndex(from_index)
            self.layoutAboutToBeChanged.emit([persistent_index])

        self.begin_remove_rows(parent, row, row)

        self.pyqtify_disconnect(parent, node)

        self.end_remove_rows()

        if from_index is not None:
            to_index = self.index_from_node(parent)
            self.changePersistentIndex(from_index, to_index)
            self.layoutChanged.emit([persistent_index])

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
                node.tree_parent.remove_child(child=node)
                new_parent.insert_child(row, node)

                return True
            else:
                new_child = new_parent.child_from(node)
                new_parent.append_child(new_child)

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

        if len(nodes) == 0:
            raise NotFoundError('''UUID '{}' not found'''.format(u))

        [node] = nodes

        return node

    def canDropMimeData(self, mime, action, row, column, parent):
        node, new_parent, _ = self.source_target_for_drop(
            column, mime, parent, row)
        can_drop = new_parent.can_drop_on(node=node)

        logger.debug('canDropMimeData: {}: {}, {}'.format(
            new_parent.name, row, can_drop))

        return can_drop


class Reference(marshmallow.fields.UUID):
    def _serialize(self, value, attr, obj):
        return super()._serialize(value.uuid, attr, obj)
