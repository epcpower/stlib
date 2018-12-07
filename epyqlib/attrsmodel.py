import collections
import contextlib
import decimal
import inspect
import itertools
import json
import locale
import logging
import sys
import uuid
import weakref

import attr
import graham
import graham.fields
import marshmallow
from PyQt5 import QtCore
from PyQt5 import QtGui
from PyQt5 import QtWidgets
import PyQt5.QtCore

import epyqlib.abstractcolumns
import epyqlib.delegates
import epyqlib.treenode
import epyqlib.utils.general
import epyqlib.utils.qt

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


logger = logging.getLogger()


class NotFoundError(Exception):
    pass


class MultipleFoundError(Exception):
    pass


def name_from_uuid(node, value, model):
    if value is None:
        return None

    target_node = model.node_from_uuid(value)

    return target_node.name


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


@attr.s
class Metadata:
    name = attr.ib(default=None)
    data_display = attr.ib(default=None)
    editable = attr.ib(default=True)
    human_name = attr.ib(default=None)
    converter = attr.ib(default=None)
    no_column = attr.ib(default=False)
    delegate = attr.ib(default=None)
    updating = attr.ib(default=False)


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

            if metadata.converter is None:
                metadata.converter = field.converter

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

def list_selection_roots(cls):
    d = {}
    for field in fields(cls):
        if field.delegate is not None:
            if field.delegate.list_selection_root:
                d[field.name] = field.delegate.list_selection_root
    return d


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

    def index_of(self, item):
        if isinstance(item, str):
            index, = (
                index
                for index, column in enumerate(self.columns)
                if column.name == item
            )
        elif isinstance(item, tuple):
            index, = (
                index
                for index, column in enumerate(self.columns)
                if column.fields[item[0]] == item[1]
            )

        return index


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
        converter=(
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
    
    def list_selection_roots(self):
        roots = set()
        for v in self.types.values():
            t = list_selection_roots(v)
            roots.update(t.values())
        
        return roots


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

        model = attr.ib(default=None)

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

    return Root


def convert_uuid(x):
    if x == '':
        return None

    if x is None or isinstance(x, uuid.UUID):
        return x

    return uuid.UUID(x)


def attr_uuid(
        metadata=None,
        human_name='UUID',
        data_display=None,
        list_selection_root=None,
        no_graham=False,
        default=attr.Factory(uuid.uuid4),
        **field_options,
):
    if metadata is None:
        metadata = {}

    attribute = attr.ib(
        default=default,
        converter=convert_uuid,
        metadata=metadata,
    )
    if not no_graham:
        graham.attrib(
            attribute=attribute,
            field=marshmallow.fields.UUID(**field_options),
        )
    attrib(
        attribute=attribute,
        human_name=human_name,
        data_display=data_display,
        delegate=epyqlib.attrsmodel.SingleSelectByRootDelegateCache(
            list_selection_root=list_selection_root,
        ),
    )

    return attribute


def to_decimal_or_none(s):
    if s is None:
        return None

    if isinstance(s, str) and len(s) == 0:
        return None

    if isinstance(s, str):
        s = locale.delocalize(s)

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

    if isinstance(s, str):
        s = locale.delocalize(s)

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


def to_source_model(index):
    model = index.model()
    while not isinstance(model, QtGui.QStandardItemModel):
        index = model.mapToSource(index)
        model = index.model()

    return index


def create_delegate(parent=None):
    selector = DelegateSelector(parent=parent)
    delegate = epyqlib.delegates.Dispatch(
        selector=selector.select,
        parent=parent,
    )

    return delegate


def get_connection_id(parent, child):
    if parent is not None:
        parent = parent.uuid

    return (parent, child.uuid)


@attr.s
class SingleSelectByRootDelegateCache:
    list_selection_root = attr.ib()
    text_column_name = attr.ib(default='Name')
    cached_delegate = attr.ib(default=None)

    def get_delegate(self, model, parent):
        if self.cached_delegate is not None:
            return self.cached_delegate

        root_node = model.list_selection_roots[
            self.list_selection_root
        ]

        self.cached_delegate = EnumerationDelegate(
            text_column_name=self.text_column_name,
            root=root_node,
            parent=parent,
        )

        return self.cached_delegate


class DelegateSelector:
    def __init__(self, parent=None):
        self.parent = parent
        self.regular = QtWidgets.QStyledItemDelegate(parent)
        self.enumerations = {}


    def select(self, index):
        index = to_source_model(index)
        model = index.model()
        item = model.itemFromIndex(index)
        node = item.data(epyqlib.utils.qt.UserRoles.node)
        field_name = item.data(epyqlib.utils.qt.UserRoles.field_name)
        model = item.data(epyqlib.utils.qt.UserRoles.attrs_model)

        metadata = getattr(fields(type(node)), field_name)
        
        if metadata.delegate is not None:
            delegate = metadata.delegate.get_delegate(model, self.parent)
        else:
            delegate = self.regular

        return delegate


# TODO: CAMPid 374895478431714307074310
class CustomCombo(PyQt5.QtWidgets.QComboBox):
    def hidePopup(self):
        super().hidePopup()

        QtCore.QCoreApplication.postEvent(
            self,
            QtGui.QKeyEvent(
                QtCore.QEvent.KeyPress,
                QtCore.Qt.Key_Enter,
                QtCore.Qt.NoModifier,
            ),
        )


class EnumerationDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, text_column_name, root, parent):
        super().__init__(parent)

        self.text_column_name = text_column_name
        self.root = root

    def createEditor(self, parent, option, index):
        return CustomCombo(parent=parent)

    def setEditorData(self, editor, index):
        super().setEditorData(editor, index)

        model_index = to_source_model(index)
        model = model_index.model()

        item = model.itemFromIndex(model_index)
        attrs_model = item.data(epyqlib.utils.qt.UserRoles.attrs_model)
        column = attrs_model.columns.index_of(self.text_column_name)
        root_index = attrs_model.index_from_node(self.root)

        editor.setModel(model)
        editor.setModelColumn(column)
        editor.setRootModelIndex(root_index)

        node = attrs_model.node_from_index(model_index)
        target_uuid = node.uuid

        if target_uuid is not None:
            target_node = attrs_model.node_from_uuid(target_uuid)
            target_index = attrs_model.index_from_node(target_node)

            editor.setCurrentIndex(target_index.row())

        editor.showPopup()

    def setModelData(self, editor, model, index):
        index = epyqlib.utils.qt.resolve_index_to_model(index)
        model = index.model()

        editor_index = editor.currentIndex()

        item = model.itemFromIndex(index)
        attrs_model = item.data(epyqlib.utils.qt.UserRoles.attrs_model)
        parent_index = attrs_model.index_from_node(self.root)

        selected_index = model.index(
            editor_index,
            0,
            parent_index,
        )
        selected_node = attrs_model.node_from_index(selected_index)

        datum = str(selected_node.uuid)
        model.setData(index, datum)


class PyQStandardItemModel(QtGui.QStandardItemModel):
    # maybe events instead?
    # http://doc.qt.io/qt-5/dnd.html

    def canDropMimeData(self, *args, **kwargs):
        return self.can_drop_mime_data(*args, **kwargs)

    def mimeTypes(self, *args, **kwargs):
        return self.mime_types(*args, **kwargs)

    def mimeData(self, *args, **kwargs):
        return self.mime_data(*args, **kwargs)

    def dropMimeData(self, *args, **kwargs):
        return self.drop_mime_data(*args, **kwargs)

    def supportedDropActions(self, *args, **kwargs):
        return self.supported_drop_actions(*args, **kwargs)

    @classmethod
    def build(
            cls,
            *args,
            can_drop_mime_data,
            mime_types,
            mime_data,
            drop_mime_data,
            supported_drop_actions,
            **kwargs,
    ):
        model = cls(*args, **kwargs)
        model.can_drop_mime_data = can_drop_mime_data
        model.mime_types = mime_types
        model.mime_data = mime_data
        model.drop_mime_data = drop_mime_data
        model.supported_drop_actions = supported_drop_actions

        return model


class Model:
    def __init__(self, root, columns, parent=None):
        self.root = root
        self.root.model = self
        self._all_items_list = []
        self.node_to_item = {}
        self.uuid_to_node = {}

        self.model = PyQStandardItemModel.build(
            can_drop_mime_data=self.canDropMimeData,
            mime_types=self.mimeTypes,
            mime_data=self.mimeData,
            drop_mime_data=self.dropMimeData,
            supported_drop_actions=self.supportedDropActions,
        )

        self.mime_type = 'application/com.epcpower.pm.attrsmodel'

        self.columns = columns
        self.header_items = [
            QtGui.QStandardItem(column.name)
            for column in self.columns
        ]

        for i, item in enumerate(self.header_items):
            self.model.setHorizontalHeaderItem(i, item)

        self.droppable_from = set()

        self.connected_signals = {}

        self.list_selection_roots = {}

        check_uuids(self.root)

        self.pyqtify_connect(None, self.root)
        self.model.itemChanged.connect(self.item_changed)

    def add_drop_sources(self, *sources):
        self.droppable_from.update(sources)
        roots = [
            model.root
            for model in {self} | self.droppable_from
        ]

        check_uuids(*roots)

    def get_field(self, index):
        c = index.column()
        t = type(self.node_from_index(index))
        name = self.columns[c].fields.get(t)

        if name is None:
            return None

        return getattr(attributes(t).fields, name)

    def item_changed(self, item):
        node = self.node_from_item(item)

        field_name = item.data(
            epyqlib.utils.qt.UserRoles.field_name,
        )
        field_metadata = getattr(
            attributes(node).fields,
            field_name,
        )
        if field_metadata.updating:
            return

        if field_name is None:
            # TODO: why is it getting changed if there's nothing there?
            return
        datum = item.data(QtCore.Qt.DisplayRole)
        if field_metadata.converter is not None:
            if field_metadata.converter == two_state_checkbox:
                datum = item.data(QtCore.Qt.CheckStateRole)

            datum = field_metadata.converter(datum)

        setattr(node, field_name, datum)

    def pyqtify_connect(self, parent, child):
        def visit(node, nodes):
            if node is child:
                this_parent = parent
            else:
                this_parent = node.tree_parent

            nodes.append({'parent': this_parent, 'child': node})

        nodes = []
        child.traverse(call_this=visit, payload=nodes, internal_nodes=True)

        self.uuid_to_node.update({
            child.uuid: child
            for child in (
                d['child']
                for d in nodes
            )
        })

        for kwargs in nodes:
            self._pyqtify_connect(**kwargs)

    def item_from_node(self, node):
        if node is self.root:
            return self.model.invisibleRootItem()

        return self.node_to_item[node]

    def node_from_item(self, item):
        return item.data(epyqlib.utils.qt.UserRoles.node)

    def _pyqtify_connect(self, parent, child):
        def key_value(instance, name, slot):
            signal = inspect.getattr_static(obj=instance, attr=name)
            return ((signal, (instance, slot)),)

        connections = {}
        connection_id = get_connection_id(parent=parent, child=child)
        if connection_id in self.connected_signals:
            raise ConsistencyError('already connected: {}'.format((parent.uuid, child.uuid)))
        self.connected_signals[connection_id] = connections

        if child is self.root:
            root_item = self.model.invisibleRootItem()
            root_item.setData(child, epyqlib.utils.qt.UserRoles.node)
            root_item.setText('root')
        else:
            if parent is self.root:
                parent_item = self.model.invisibleRootItem()
            else:
                parent_item = self.item_from_node(parent)
            row = parent.row_of_child(child)

            items = []

            changed_signals = epyqlib.utils.qt.pyqtified(child).changed

            for i, column in enumerate(self.columns):
                field_name = column.fields.get(type(child))

                item = QtGui.QStandardItem()
                item.setEditable(type(child) in column.fields)
                if i == 0:
                    self._all_items_list.append(item)
                    self.node_to_item[child] = item
                item.setData(child, epyqlib.utils.qt.UserRoles.node)
                item.setData(i, epyqlib.utils.qt.UserRoles.column_index)
                item.setData(
                    field_name,
                    epyqlib.utils.qt.UserRoles.field_name,
                )
                item.setData(
                    self,
                    epyqlib.utils.qt.UserRoles.attrs_model,
                )

                if field_name is not None:
                    fields = attributes(type(child)).fields
                    checkable = (
                            getattr(fields, field_name).converter
                            == two_state_checkbox
                    )
                    item.setCheckable(checkable)

                    def slot(datum, item=item):
                        node = item.data(epyqlib.utils.qt.UserRoles.node)
                        model = item.data(
                            epyqlib.utils.qt.UserRoles.attrs_model,
                        )
                        field_name = item.data(
                            epyqlib.utils.qt.UserRoles.field_name,
                        )
                        field_metadata = getattr(
                            attributes(node).fields,
                            field_name,
                        )
                        data_display = field_metadata.data_display

                        field_metadata.updating = True

                        display_datum = datum
                        if data_display is not None:
                            display_datum = data_display(
                                node,
                                value=display_datum,
                                model=model,
                            )
                        elif field_metadata.converter == two_state_checkbox:
                            display_datum = ''

                        if display_datum is None:
                            # TODO: CAMPid 0794305784527546542452654254679680
                            # The display role is supposed to be '-' for None
                            # but they can't be different
                            #
                            # http://doc.qt.io/qt-5/qstandarditem.html#data
                            #   The default implementation treats Qt::EditRole
                            #   and Qt::DisplayRole as referring to the same
                            #   data
                            display_text = ''
                            edit_text = ''
                        else:
                            display_text = str(display_datum)
                            edit_text = display_text

                        item.setData(display_text, PyQt5.QtCore.Qt.DisplayRole)
                        item.setData(edit_text, PyQt5.QtCore.Qt.EditRole)
                        item.setData(datum, epyqlib.utils.qt.UserRoles.raw)

                        field_metadata.updating = False

                    connections.update(key_value(
                        instance=changed_signals,
                        name='_pyqtify_signal_' + field_name,
                        slot=slot,
                    ))

                    slot(getattr(child, field_name))

                items.append(item)

            parent_item.insertRow(row, items)


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
        def visit(node, nodes):
            if node is child:
                this_parent = parent
            else:
                this_parent = node.tree_parent

            nodes.append({'parent': this_parent, 'child': node})

        nodes = []
        child.traverse(call_this=visit, payload=nodes, internal_nodes=True)

        for kwargs in nodes:
            self._pyqtify_disconnect(**kwargs)

    def _pyqtify_disconnect(self, parent, child):
        connection_id = get_connection_id(parent=parent, child=child)
        try:
            connections = self.connected_signals.pop(
                connection_id,
            )
        except KeyError:
            # TODO: why is this even happening?
            return

        for signal, (instance, slot) in connections.items():
            signal.__get__(instance).disconnect(slot)

        self.uuid_to_node.pop(child.uuid)

    def child_added(self, child, row):
        parent = child.tree_parent

        self.pyqtify_connect(parent, child)

        if child.uuid is None:
            check_uuids(self.root)

    def deleted(self, parent, node, row):
        item = self.item_from_node(parent)
        taken_items = item.takeRow(row)
        self.node_to_item.pop(node)
        for taken_item in taken_items:
            try:
                self._all_items_list.remove(taken_item)
            except ValueError:
                pass
        self.pyqtify_disconnect(parent, node)

    def supportedDropActions(self):
        return QtCore.Qt.MoveAction

    def mimeTypes(self):
        return (self.mime_type,)

    def node_from_index(self, index):
        item = self.model.itemFromIndex(index)
        if item is None:
            node = self.root
        else:
            node = item.data(epyqlib.utils.qt.UserRoles.node)
        return node

    def index_from_node(self, node):
        item = self.item_from_node(node)
        index = self.model.indexFromItem(item)
        return index

    def mimeData(self, indexes):
        [node] = {self.node_from_index(i) for i in indexes}
        m = QtCore.QMimeData()
        m.setData(self.mime_type, node.uuid.bytes)

        return m

    def dropMimeData(self, data, action, row, column, parent):
        logger.debug('entering dropMimeData()')
        logger.debug((data, action, row, column, parent))

        node, new_parent, source_row = self.source_target_for_drop(
            column, data, parent, row)

        if action == QtCore.Qt.MoveAction:
            logger.debug('node name: {}'.format(node.name))
            logger.debug((data, action, row, column, parent))
            logger.debug('dropped on: {}'.format(new_parent.name))

            local = node.find_root() == self.root

            if local:
                node.tree_parent.remove_child(child=node)
                new_child = node
            else:
                new_child = new_parent.child_from(node)

            if row == -1:
                new_parent.append_child(new_child)
            else:
                new_parent.insert_child(row, new_child)

            return local

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
        for model in {self} | self.droppable_from:
            node = model.uuid_to_node.get(u)
            if node is not None:
                return node

        raise NotFoundError('''UUID '{}' not found'''.format(u))

    def canDropMimeData(self, mime, action, row, column, parent):
        node, new_parent, _ = self.source_target_for_drop(
            column, mime, parent, row)
        can_drop = new_parent.can_drop_on(node=node)

        logger.debug('canDropMimeData: {}: {}, {}'.format(
            getattr(new_parent, 'name', '<no name attribute>'), row, can_drop))

        return can_drop

    def update_nodes(self):
        def visit(node, _):
            update = getattr(node, 'update', None)

            if update is not None:
                update()

        self.root.traverse(call_this=visit, internal_nodes=True)


class Reference(marshmallow.fields.UUID):
    def _serialize(self, value, attr, obj):
        return super()._serialize(value.uuid, attr, obj)


def columns_to_code(c):
    columns = collections.defaultdict(list)

    for x in c:
        columns[x[1]].append(x[0])

    code = []

    for name, types in columns.items():
        if len(types) == 0:
            pass
        elif len(types) == 1:
            code.append(f"(({types[0].__name__}, '{name}'),),")
        else:
            type_code = ', '.join(sorted(cls.__name__ for cls in types))
            type_code = f'({type_code})'
            code.append(f"tuple((x, '{name}') for x in {type_code}),")

    # with this you can copy/paste to fill in the missing columns
    return '\n' + '\n'.join(code)


class Tests:
    def test_all_fields_in_columns(self):
        fields = set()

        for cls in self.types:
            if cls is self.root_type:
                continue

            for field in epyqlib.attrsmodel.fields(cls):
                if field.no_column:
                    continue

                fields.add((cls, field.name))

        columns_list = [
            tuple(x)
            for x in itertools.chain(*(
                column.items()
                for column in self.columns
            ))
            if x[0] is not self.root_type
        ]

        columns = set(columns_list)

        assert len(columns_list) == len(columns)

        extra = columns - fields
        missing = fields - columns

        assert extra == set()
        assert missing == set(), columns_to_code(missing)

    def test_all_have_can_drop_on(self):
        self.assert_incomplete_types(
            name='can_drop_on',
            signature=['node'],
        )

    def test_all_have_can_delete(self):
        self.assert_incomplete_types(
            name='can_delete',
            signature=['node'],
        )

    def test_all_addable_also_in_types(self):
        # Since addable types is dynamic and could be anything... this
        # admittedly only checks the addable types on default instances.
        for cls in self.types.types.values():
            addable_types = cls.all_addable_types().values()
            assert (
                (set(addable_types) - set(self.types))
                 == set()
             )

    def test_hashability(self):
        expected = []
        bad = []
        for cls in self.types:
            instance = cls()
            try:
                hash(instance)
            except TypeError :
                bad.append(cls)

        sys.stderr.write('\n')
        for cls in bad:
            sys.stderr.write(
                '{path}  {name}\n'.format(
                    path=epyqlib.utils.general.path_and_line(cls),
                    name=cls.__name__,
                ),
            )

        assert bad == expected

    def test_has_uuid(self):
        for cls in self.types:
            assert hasattr(cls, 'uuid')

    def assert_incomplete_types(self, name, signature=None):
        bad = []
        signature = list(signature)

        for cls in self.types.types.values():
            if isinstance(cls.__dict__[name], staticmethod):
                tweaked_signature = signature
            elif isinstance(cls.__dict__[name], classmethod):
                tweaked_signature = ['cls', *signature]
            else:
                tweaked_signature = ['self', *signature]

            attribute = getattr(cls, name)
            if attribute is None:
                bad.append(cls)
            elif signature is not None:
                actual_signature = inspect.signature(attribute)
                actual_signature = actual_signature.parameters.keys()
                actual_signature = list(actual_signature)
                if tweaked_signature != actual_signature:
                    bad.append(cls)
                    continue

        sys.stderr.write('\n')
        for cls in bad:
            sys.stderr.write(
                '{path}  {name}\n'.format(
                    path=epyqlib.utils.general.path_and_line(
                        getattr(cls, name)),
                    name=cls,
                ),
            )
        assert [] == bad


def build_tests(types, root_type, columns):
    return type(
        'BuiltTests',
        (Tests,),
        {
            'types': types,
            'root_type': root_type,
            'columns': columns,
        },
    )
