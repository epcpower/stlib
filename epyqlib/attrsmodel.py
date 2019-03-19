import collections
import contextlib
import decimal
import functools
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


def create_str_attribute(default=''):
    return attr.ib(
        default=default,
        convert=str,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )


def create_str_or_none_attribute(default=None):
    return attr.ib(
        default=default,
        convert=to_str_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )


def create_name_attribute(default=None):
    return attr.ib(
        default=default,
        convert=to_str_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )


def create_reference_attribute():
    attribute = attr.ib(
        default=None,
        metadata=graham.create_metadata(
            field=epyqlib.attrsmodel.Reference(allow_none=True),
        ),
    )
    epyqlib.attrsmodel.attrib(
        attribute=attribute,
        no_column=True,
    )

    return attribute


# TODO: CAMPid 8695426542167924656654271657917491654
def name_from_uuid(node, value, model):
    if value is None:
        return None

    try:
        target_node = model.node_from_uuid(value)
    except NotFoundError:
        return str(value)

    return target_node.name


def names_from_uuid_list(node, value, model):
    if value is None:
        return None

    target_nodes = model.nodes_from_uuid_list(value)

    names = []
    for n in target_nodes:
        names.append(n.name)
    return names


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
    external_list_selection_roots = attr.ib(factory=set)

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
        roots = set(self.external_list_selection_roots)
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


def check_just_children(self):
    # TODO: ugh, circular dependencies
    import epyqlib.checkresultmodel

    if len(self.children) == 0:
        return None

    child_results = [
        child.check()
        for child in self.children
    ]
    child_results = [
        results
        for results in child_results
        if results is not None
    ]

    if len(child_results) == 0:
        return None

    return epyqlib.checkresultmodel.Node.build(
        name=self.name,
        node=self,
        child_results=child_results,
    )


def check_children(f):
    def wrapper(self):
        # TODO: ugh, circular dependencies
        import epyqlib.checkresultmodel

        result = check_just_children(self)

        if result is None:
            result = epyqlib.checkresultmodel.Node.build(
                name=self.name,
                node=self,
            )

        result = f(self=self, result=result)

        if len(result.children) == 0:
            return None

        return result

    return wrapper


def Root(default_name, valid_types):
    @graham.schemify(tag='root')
    @ify()
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

        remove_old_on_drop = default_remove_old_on_drop
        child_from = default_child_from
        internal_move = default_internal_move

        def check_and_append(self, parent=None):
            # TODO: ugh, circular dependencies
            import epyqlib.checkresultmodel

            if parent is None:
                parent = epyqlib.checkresultmodel.Root()

            for child in self.children:
                result = child.check()

                if result is not None:
                    parent.append_child(result)

            return parent

        def check(self):
            return self.check_and_append()

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


def convert_uuid_list(x):
    if x is None:
        return None

    l = []
    for y in x:
        if isinstance(y, uuid.UUID):
            l.append(y)
        else:
            l.append(convert_uuid(y.uuid))

    return l


def attr_uuid_list(
        metadata=None,
        human_name='UUID List',
        data_display=None,
        list_selection_root=None,
        no_graham=False,
        default=attr.Factory(list),
        **field_options,
):
    if metadata is None:
        metadata = {}

    attribute = attr.ib(
        default=default,
        converter=convert_uuid_list,
        metadata=metadata,
    )
    if not no_graham:
        graham.attrib(
            attribute=attribute,
            field=marshmallow.fields.List(marshmallow.fields.UUID(**field_options), **field_options),
        )
    attrib(
        attribute=attribute,
        human_name=human_name,
        data_display=data_display,
        delegate=epyqlib.attrsmodel.RootDelegateCache(
            list_selection_root=list_selection_root,
            multi_select=True,
        ),
    )

    return attribute


def attr_uuid(
        metadata=None,
        human_name='UUID',
        data_display=None,
        list_selection_root=None,
        list_selection_path=None,
        override_delegate=None,
        no_graham=False,
        default=attr.Factory(uuid.uuid4),
        editable=True,
        no_column=False,
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

    if list_selection_path is not None:
        if list_selection_root is not None:
            raise MultipleFoundError(
                    'list_selection_path and list_selection_root both definded'
            )
        else:
            attrib(
                attribute=attribute,
                human_name=human_name,
                data_display=data_display,
                delegate=CustomDelegate(
                    list_selection_path=list_selection_path,
                    override_delegate=override_delegate,
                ),
                editable=editable,
                no_column=no_column,
            )
    else:
        attrib(
            attribute=attribute,
            human_name=human_name,
            data_display=data_display,
            delegate=RootDelegateCache(
                list_selection_root=list_selection_root
            ),
            editable=editable,
            no_column=no_column,
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


def default_remove_old_on_drop(self, node):
    return node.find_root() == self.find_root()


@staticmethod
def default_child_from(node):
    return node


def default_internal_move(self, node, node_to_insert_before):
    return False


@classmethod
def empty_all_addable_types(cls):
    return epyqlib.attrsmodel.create_addable_types(())


def empty_addable_types(self):
    return {}


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


def hide_popup(self):
    QtCore.QCoreApplication.postEvent(
        self,
        QtGui.QKeyEvent(
            QtCore.QEvent.KeyPress,
            QtCore.Qt.Key_Enter,
            QtCore.Qt.NoModifier,
        ),
    )


@attr.s
class RootDelegateCache:
    list_selection_root = attr.ib()
    text_column_name = attr.ib(default='Name')
    cached_delegate = attr.ib(default=None)
    multi_select = attr.ib(default=False)

    def get_delegate(self, model, parent):
        if self.cached_delegate is not None:
            return self.cached_delegate

        root_node = model.list_selection_roots[
            self.list_selection_root
        ]

        delegate = EnumerationDelegate
        if self.multi_select:
            delegate = EnumerationDelegateMulti

        self.cached_delegate = delegate(
            text_column_name=self.text_column_name,
            root=root_node,
            parent=parent,
        )

        return self.cached_delegate


@attr.s
class CustomDelegate:
    list_selection_path = attr.ib(default=None)
    override_delegate = attr.ib(default=None)
    text_column_name = attr.ib(default='Name')

    def get_delegate(self, node, parent):
        root_node = node
        for element in self.list_selection_path:
            if element == '/':
                root_node = root_node.find_root()
            elif element == '..':
                root_node = root_node.tree_parent
            else:
                root_node = root_node.child_by_name(element)

        delegate = EnumerationDelegate
        if self.override_delegate is not None:
            delegate = self.override_delegate

        return delegate(
            text_column_name=self.text_column_name,
            root=root_node,
            parent=parent,
        )


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
            node_or_model = model
            if isinstance(metadata.delegate, epyqlib.attrsmodel.CustomDelegate):
                node_or_model = node
            delegate = metadata.delegate.get_delegate(node_or_model, self.parent)
        else:
            delegate = self.regular

        return delegate


# TODO: CAMPid 374895478431714307074310
class CustomCombo(PyQt5.QtWidgets.QComboBox):
    def hidePopup(self):
        super().hidePopup()
        hide_popup(self)


class CustomMulti(PyQt5.QtWidgets.QListWidget):
    def hidePopup(self):
        super().hidePopup()
        hide_popup(self)


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

        editor.setModel(root_index.model())
        editor.setModelColumn(column)
        editor.setRootModelIndex(root_index)

        target_uuid = model_index.data(epyqlib.utils.qt.UserRoles.raw)

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

        enumeration_model = parent_index.model()
        enumeration_attrs_model = parent_index.data(
            epyqlib.utils.qt.UserRoles.attrs_model,
        )

        selected_index = enumeration_model.index(
            editor_index,
            0,
            parent_index,
        )
        selected_node = enumeration_attrs_model.node_from_index(
            selected_index,
        )

        datum = str(selected_node.uuid)
        model.setData(index, datum)


class EnumerationDelegateMulti(QtWidgets.QStyledItemDelegate):
    def __init__(self, text_column_name, root, parent):
        super().__init__(parent)

        self.text_column_name = text_column_name
        self.root = root

    def createEditor(self, parent, option, index):
        return CustomMulti(parent=parent)

    def setEditorData(self, editor, index):
        super().setEditorData(editor, index)

        model_index = to_source_model(index)
        model = model_index.model()

        raw = model.data(model_index, epyqlib.utils.qt.UserRoles.raw)
        editor.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        for node in self.root.children:
            it = PyQt5.QtWidgets.QListWidgetItem(editor)
            it.setText(node.name)
            it.uuid = node.uuid
            for r in raw:
                if r == it.uuid:
                    it.setSelected(True)

        editor.setMinimumHeight(editor.sizeHint().height())
        editor.show()

    def setModelData(self, editor, model, index):
        index = epyqlib.utils.qt.resolve_index_to_model(index)
        model = index.model()

        selected_items = editor.selectedItems()
        model.setData(index, selected_items)


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
    def __init__(self, root, columns, drop_sources=(), parent=None):
        self.root = root
        self.root.model = self
        self._all_items_dict = {}
        self.node_to_item = {}
        self.uuid_to_node = {}

        self.model = PyQStandardItemModel.build(
            can_drop_mime_data=self.canDropMimeData,
            mime_types=self.mimeTypes,
            mime_data=self.mimeData,
            drop_mime_data=self.dropMimeData,
            supported_drop_actions=self.supportedDropActions,
        )

        self.model.invisibleRootItem().setData(
            self,
            epyqlib.utils.qt.UserRoles.attrs_model,
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

        self.add_drop_sources(*drop_sources)

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

            uneditable_highlight = QtGui.QColor('grey')
            uneditable_highlight.setAlphaF(0.4)
            droppable_highlight = QtGui.QColor('orange')
            droppable_highlight.setAlphaF(0.4)
            droppable_row = hasattr(row, 'addable_types') or hasattr(row, 'all_addable_types')

            for i, column in enumerate(self.columns):
                field_name = column.fields.get(type(child))

                item = QtGui.QStandardItem()
                editable = False
                has_field = False
                field_for_column = column.fields.get(type(child))
                if field_for_column is not None:
                    metadata = getattr(fields(type(child)), field_for_column)
                    editable = metadata.editable
                    has_field = True

                item.setEditable(editable)
                if not editable and has_field:
                    if droppable_row:
                        item.setData(
                            uneditable_highlight,
                            QtCore.Qt.ItemDataRole.BackgroundRole,
                        )
                    else:
                        item.setData(
                            droppable_highlight,
                            QtCore.Qt.ItemDataRole.BackgroundRole,
                        )

                if i == 0:
                    self._all_items_dict[(
                        item.data(epyqlib.utils.qt.UserRoles.node),
                        item.column(),
                    )] = item
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
                    checkable = (
                        getattr(fields(type(child)), field_name).converter
                        == two_state_checkbox
                    )
                    item.setCheckable(checkable)

                    def slot(
                            datum,
                            item=item,
                            field_name=field_name,
                            editable=editable,
                    ):
                        node = item.data(epyqlib.utils.qt.UserRoles.node)
                        model = node.find_root().model
                        field_metadata = getattr(
                            fields(node),
                            field_name,
                        )
                        data_display = field_metadata.data_display

                        field_metadata.updating = True
                        try:
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
                                # edit_text = ''
                                if editable:
                                    decoration = QtGui.QColor('green')
                                    decoration.setAlphaF(0.4)
                                else:
                                    decoration = None
                            else:
                                display_text = str(display_datum)
                                # edit_text = display_text
                                decoration = None

                            item.setData(display_text, PyQt5.QtCore.Qt.DisplayRole)
                            # item.setData(edit_text, PyQt5.QtCore.Qt.EditRole)
                            item.setData(decoration, PyQt5.QtCore.Qt.DecorationRole)
                            item.setData(datum, epyqlib.utils.qt.UserRoles.raw)
                            if item.isCheckable():
                                item.setCheckState(
                                    PyQt5.QtCore.Qt.Checked
                                    if datum
                                    else PyQt5.QtCore.Qt.Unchecked,
                                )
                        finally:
                            field_metadata.updating = False

                    connections[getattr(changed_signals, '_pyqtify_signal_' + field_name)] = slot

                    slot(getattr(child, field_name))

                items.append(item)

            parent_item.insertRow(row, items)

        connections[child.pyqt_signals.child_added] = self.child_added
        connections[child.pyqt_signals.child_removed] = self.deleted

        for signal, slot in connections.items():
            signal.connect(slot)

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

        for signal, slot in connections.items():
            signal.disconnect(slot)

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
                del self._all_items_dict[(
                    taken_item.data(epyqlib.utils.qt.UserRoles.node),
                    taken_item.column(),
                )]
            except KeyError:
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
        for root in {self} | self.droppable_from:
            try:
                item = root.item_from_node(node)
            except KeyError:
                continue
            index = root.model.indexFromItem(item)
            return index

        return None

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

        node_to_insert_before = None
        if row != -1:
            node_to_insert_before = new_parent.child_at_row(row)

        if action == QtCore.Qt.MoveAction:
            logger.debug('node name: {}'.format(
                getattr(node, 'name', '<missing attribute>'),
            ))
            logger.debug((data, action, row, column, parent))
            logger.debug('dropped on: {}'.format(
                getattr(new_parent, 'name', '<no name attribute>'),
            ))

            moved = False

            if new_parent is node.tree_parent:
                moved = new_parent.internal_move(
                    node=node,
                    node_to_insert_before=node_to_insert_before,
                )

            if not moved:
                if new_parent.remove_old_on_drop(node=node):
                    node.tree_parent.remove_child(child=node)

                new_child = new_parent.child_from(node=node)

                if new_child is None:
                    pass
                elif row == -1:
                    new_parent.append_child(new_child)
                else:
                    new_row = new_parent.row_of_child(node_to_insert_before)
                    new_parent.insert_child(new_row, new_child)

        # Always returning False so that Qt won't do anything...  like
        # thinking it knows which row of items to delete to finish the
        # move.
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

    def nodes_from_uuid_list(self, u):
        nodes = []
        for i in u:
            try:
                target_node = self.node_from_uuid(i)
            except NotFoundError:
                target_node = str(u)
            
            nodes.append(target_node)

        return nodes

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
        if value is None:
            uuid = None
        else:
            uuid = value.uuid

        return super()._serialize(uuid, attr, obj)


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

    def test_all_have_remove_old_on_drop(self):
        self.assert_incomplete_types(
            name='remove_old_on_drop',
            signature=['node'],
        )

    def test_all_have_child_from(self):
        self.assert_incomplete_types(
            name='child_from',
            signature=['node'],
        )

    def test_all_have_internal_move(self):
        self.assert_incomplete_types(
            name='internal_move',
            signature=['node', 'node_to_insert_before'],
        )

    def test_all_have_check(self):
        self.assert_incomplete_types(
            name='check',
            signature=[],
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
        missing = []
        bad_signature = []
        signature = list(signature)

        for cls in self.types.types.values():
            attribute = getattr(cls, name, None)
            if attribute is None:
                missing.append((cls, name))
            elif signature is not None:
                if isinstance(cls.__dict__[name], staticmethod):
                    tweaked_signature = signature
                elif isinstance(cls.__dict__[name], classmethod):
                    tweaked_signature = ['cls', *signature]
                else:
                    tweaked_signature = ['self', *signature]

                actual_signature = inspect.signature(attribute)
                actual_signature = actual_signature.parameters.keys()
                actual_signature = list(actual_signature)
                if tweaked_signature != actual_signature:
                    bad_signature.append(
                        (cls, tweaked_signature, actual_signature),
                    )
                    continue

        sys.stderr.write('\n')
        for cls, attribute in missing:
            sys.stderr.write(
                '{path}  {name} is missing: {attribute}\n'.format(
                    path=epyqlib.utils.general.path_and_line(cls),
                    name=cls,
                    attribute=attribute,
                ),
            )
        for cls, expected, actual in bad_signature:
            sys.stderr.write(
                '{path}  {name} has signature {actual}, should be {expected}\n'.format(
                    path=epyqlib.utils.general.path_and_line(
                        getattr(cls, name)),
                    name=cls,
                    actual=actual,
                    expected=expected,
                ),
            )
        assert [] == missing
        assert [] == bad_signature


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
