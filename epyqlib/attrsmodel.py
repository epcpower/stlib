import collections
import contextlib
import decimal
import inspect
import json
import locale
import logging
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
    list_selection_root = attr.ib(default=None)


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
        if field.list_selection_root:
            d[field.name] = field.list_selection_root
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

    # def __len__(self):
    #     return len(self.columns)

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
    if x is None or isinstance(x, uuid.UUID):
        return x

    print('convert_uuid()', repr(x))
    import traceback
    traceback.print_stack()

    return uuid.UUID(x)


def attr_uuid(
        metadata=None,
        human_name='UUID',
        data_display=None,
        list_selection_root=None,
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
    graham.attrib(
        attribute=attribute,
        field=marshmallow.fields.UUID(**field_options),
    )
    attrib(
        attribute=attribute,
        human_name=human_name,
        data_display=data_display,
        list_selection_root=list_selection_root,
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


class DelegateSelector:
    def __init__(self, parent=None):
        self.parent = parent
        self.regular = QtWidgets.QStyledItemDelegate(parent)
        self.enumerations = {}

    def enumeration_delegate(self, root):
        return self.enumerations.setdefault(
            root,
            EnumerationDelegate(
                text_column_name='Name',
                root=root,
                parent=self.parent,
            ),
        )

    def select(self, index):
        index = to_source_model(index)
        model = index.model()
        if isinstance(model, QtGui.QStandardItemModel):
            item = model.itemFromIndex(index)
            node = item.data(epyqlib.utils.qt.UserRoles.node)
            field_name = item.data(epyqlib.utils.qt.UserRoles.field_name)
            model = item.data(epyqlib.utils.qt.UserRoles.attrs_model)
        else:
            # continue supporting PyQAbstractItemModel
            node = model.node_from_index(index)

            column = model.columns[index.column()]
            field_name = column.fields[type(node)]

        list_selection_root = getattr(fields(type(node)), field_name)
        list_selection_root = list_selection_root.list_selection_root

        if list_selection_root is not None:
            list_selection_root = model.list_selection_roots[
                list_selection_root
            ]
            delegate = self.enumeration_delegate(list_selection_root)
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

        if isinstance(model, QtGui.QStandardItemModel):
            item = model.itemFromIndex(model_index)
            attrs_model = item.data(epyqlib.utils.qt.UserRoles.attrs_model)
            column = attrs_model.columns.index_of(self.text_column_name)
            root_index = attrs_model.index_from_node(self.root)
        else:
            # continue supporting PyQAbstractItemModel
            column = model.columns.index_of(self.text_column_name)
            root_index = model.index_from_node(self.root)

        editor.setModel(model)
        editor.setModelColumn(column)
        editor.setRootModelIndex(root_index)

        # target_uuid = model.data(
        #     model_index,
        #     epyqlib.utils.qt.UserRoles.raw,
        # )

        node = attrs_model.node_from_index(model_index)
        target_uuid = node.uuid

        if target_uuid is not None:
            if isinstance(model, QtGui.QStandardItemModel):
                target_node = attrs_model.node_from_uuid(target_uuid)
                target_index = attrs_model.index_from_node(target_node)

            else:
                # continue supporting PyQAbstractItemModel
                target_node = model.node_from_uuid(target_uuid)
                target_index = model.index_from_node(target_node)

            editor.setCurrentIndex(target_index.row())

        editor.showPopup()

    def setModelData(self, editor, model, index):
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

        node = attrs_model.node_from_index(index)

        # datum = model.data(selected_index)
        datum = str(selected_node.uuid)
        print('setting -- - -- -', repr(datum))
        print('                 ', node)
        model.setData(index, datum)
        print('                 ', node)

        return

        index = to_source_model(index)

        if isinstance(model, QtGui.QStandardItemModel):
            item = model.itemFromIndex(index)
            attrs_model = item.data(epyqlib.utils.qt.UserRoles.attrs_model)
            parent_index = attrs_model.index_from_node(self.root)
            model = attrs_model.model
        else:
            # continue supporting PyQAbstractItemModel
            model = index.model()
            parent_index = model.index_from_node(self.root)

        editor_index = editor.currentIndex()

        selected_index = model.index(
            editor_index,
            0,
            parent_index,
        )

        if not selected_index.isValid():
            raise Exception('editor_index {}'.format(editor_index))

        if isinstance(model, QtGui.QStandardItemModel):
            node = attrs_model.node_from_index(selected_index)
            print('combo selected', node)
        else:
            # continue supporting PyQAbstractItemModel
            node = model.node_from_index(selected_index)

        print('column', index.column())
        datum = str(node.uuid)
        print('repr(datum)', repr(datum))
        print('model.itemFromIndex(index).text()', model.itemFromIndex(index).text())
        print('repr(model.itemFromIndex(index).data(epyqlib.utils.qt.UserRoles.raw))', repr(model.itemFromIndex(index).data(epyqlib.utils.qt.UserRoles.raw)))
        success = model.setData(selected_index, datum, role=QtCore.Qt.EditRole)
        if not success:
            raise Exception('failed to set')

    def _setModelData(self, editor, model, index):
        index = to_source_model(index)

        if isinstance(model, QtGui.QStandardItemModel):
            item = model.itemFromIndex(index)
            attrs_model = item.data(epyqlib.utils.qt.UserRoles.attrs_model)
            parent_index = attrs_model.index_from_node(self.root)
            model = attrs_model.model
        else:
            # continue supporting PyQAbstractItemModel
            model = index.model()
            parent_index = model.index_from_node(self.root)

        editor_index = editor.currentIndex()

        selected_index = model.index(
            editor_index,
            0,
            parent_index,
        )

        if not selected_index.isValid():
            raise Exception('editor_index {}'.format(editor_index))

        if isinstance(model, QtGui.QStandardItemModel):
            node = attrs_model.node_from_index(selected_index)
            print('combo selected', node)
        else:
            # continue supporting PyQAbstractItemModel
            node = model.node_from_index(selected_index)

        print('column', index.column())
        datum = str(node.uuid)
        print('repr(datum)', repr(datum))
        print('model.itemFromIndex(index).text()', model.itemFromIndex(index).text())
        print('repr(model.itemFromIndex(index).data(epyqlib.utils.qt.UserRoles.raw))', repr(model.itemFromIndex(index).data(epyqlib.utils.qt.UserRoles.raw)))
        success = model.setData(selected_index, datum, role=QtCore.Qt.EditRole)
        if not success:
            raise Exception('failed to set')


class Model:
    def __init__(self, root, columns, parent=None):
        self.root = root

        self.model = QtGui.QStandardItemModel()

        self.mime_type = 'application/com.epcpower.pm.attrsmodel'

        self.columns = columns
        self.headers = tuple(c.name for c in self.columns)

        self.droppable_from = set()

        self.connected_signals = {}

        self.list_selection_roots = {}

        check_uuids(self.root)

        self.pyqtify_connect(None, self.root)
        self.model.itemChanged.connect(self.item_changed)

    def add_drop_sources(self, *sources):
        self.droppable_from.update(sources)
        check_uuids(self.root, *self.droppable_from)

    # def flags(self, index):
    #     flags = super().flags(index)
    #
    #     field = self.get_field(index)
    #
    #     if field is not None:
    #         node = self.node_from_index(index)
    #
    #         if field.converter is two_state_checkbox:
    #             flags |= QtCore.Qt.ItemIsUserCheckable
    #         elif getattr(fields(node), field.name).editable:
    #             flags |= QtCore.Qt.ItemIsEditable
    #
    #         flags |= QtCore.Qt.ItemIsDragEnabled | QtCore.Qt.ItemIsDropEnabled
    #
    #     return flags

    def get_field(self, index):
        c = index.column()
        t = type(self.node_from_index(index))
        name = self.columns[c].fields.get(t)

        if name is None:
            return None

        return getattr(attributes(t).fields, name)

    # def data_raw(self, index):
    #     field = self.get_field(index)
    #     node = self.node_from_index(index)
    #     return getattr(node, field.name)
    #
    # def data_display(self, index, replace_none='-'):
    #     field = self.get_field(index)
    #
    #     if field is None:
    #         return ''
    #
    #     if field.converter is two_state_checkbox:
    #         return ''
    #
    #     node = self.node_from_index(index)
    #
    #     data = getattr(node, field.name)
    #     processor = data_processor(
    #         cls=type(node),
    #         data_field=field,
    #         attribute_field=attr.fields(Metadata).data_display,
    #     )
    #     if processor is not None:
    #         return processor(node, model=self, value=data)
    #
    #     if data is None:
    #         return replace_none
    #
    #     return str(data)
    #
    # def data_edit(self, index):
    #     return self.data_display(index, replace_none='')
    #
    # def data_check_state(self, index):
    #     node = self.node_from_index(index)
    #
    #     attribute = self.get_field(index)
    #     if attribute is not None:
    #         if attribute.converter is two_state_checkbox:
    #             if getattr(node, attribute.name):
    #                 return QtCore.Qt.Checked
    #             else:
    #                 return QtCore.Qt.Unchecked
    #
    #     return None

    def item_changed(self, item):
        node = self.node_from_item(item)

        index = self.index_from_node(node)
        index = index.siblingAtColumn(
            item.data(epyqlib.utils.qt.UserRoles.column_index),
        )



        # field = self.get_field(index)
        #
        # c = index.column()
        # t = type(self.node_from_index(index))
        # name = self.columns[c].fields.get(t)
        #
        # if name is None:
        #     return None
        #
        # field = getattr(attributes(t).fields, name)



        field_name = item.data(epyqlib.utils.qt.UserRoles.field_name)
        field = getattr(attributes(type(node)).fields, field_name)
        if field_name is None:
            # TODO: why is it getting changed if there's nothing there?
            print('field name is none')
            return
        print('field', field_name, field)
        datum = item.data(QtCore.Qt.DisplayRole)
        if field.converter is not None:
            datum = field.converter(datum)

        print('  setattr', node, field_name, repr(datum))
        setattr(node, field_name, datum)
        # print('  setattr', node, field_name, repr(datum))

        return

        index = self.index_from_node(node)
        field = self.get_field(index)

        if field is None:
            # TODO: why is it getting changed if there's nothing there?
            return

        datum = item.data(QtCore.Qt.DisplayRole)
        if field.converter is not None:
            datum = field.converter(datum)

        print('setting', field.name, 'on', node, 'to', repr(datum))
        setattr(node, field.name, datum)

    # def setData(self, index, data, role=None):
    #     node = self.node_from_index(index)
    #     attribute = self.get_field(index)
    #
    #     if role == QtCore.Qt.EditRole:
    #         converter = attribute.converter
    #         if converter is not None:
    #             try:
    #                 converted = converter(data)
    #             except ValueError:
    #                 return False
    #         else:
    #             converted = data
    #
    #         setattr(node, attribute.name, converted)
    #
    #         self.dataChanged.emit(index, index)
    #         return True
    #     elif role == QtCore.Qt.CheckStateRole:
    #         setattr(node, attribute.name, attribute.converter(data))
    #
    #         return True
    #
    #     return False

    def pyqtify_connect(self, parent, child):
        def visit(node, nodes):
            if node is child:
                this_parent = parent
            else:
                this_parent = node.tree_parent

            nodes.append({'parent': this_parent, 'child': node})

        nodes = []
        child.traverse(call_this=visit, payload=nodes, internal_nodes=True)

        for kwargs in nodes:
            self._pyqtify_connect(**kwargs)

    def item_from_node(self, node):
        items = self._all_items(role=None)
        item, = [
            item
            for item in items
            if item.data(epyqlib.utils.qt.UserRoles.node) is node
        ]

        return item

    def node_from_item(self, item):
        return item.data(epyqlib.utils.qt.UserRoles.node)

    def _pyqtify_connect(self, parent, child):
        def key_value(instance, name, slot):
            signal = inspect.getattr_static(obj=instance, attr=name)
            return ((signal, (instance, slot)),)

        connections = {}
        connection_id = get_connection_id(parent=parent, child=child)
        if connection_id in self.connected_signals:
            raise ConsistencyError('already connected: {}'.format((parent, child)))
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

                    # item.setText(str(getattr(child, field_name)))

                    def slot(datum, item=item):
                        # print('   |', field_name)
                        # print('   |', child)
                        #
                        # print('   |', child, field_name)
                        # print('   /', repr(datum))
                        # print('   \\', repr(str(datum)))
                        item.setText(str(datum))
                        item.setData(datum, epyqlib.utils.qt.UserRoles.raw)

                    # changed_signals[name].connect(slot)
                    connections.update(key_value(
                        instance=changed_signals,
                        name='_pyqtify_signal_' + field_name,
                        slot=slot,
                    ))
                    print('initializing item for', child, field_name)
                    slot(getattr(child, field_name))
                    # connections.update((
                    #     (inspect.getattr_static(obj=changed_signals)
                    # ))

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

    def _all_items(
            self,
            model=None,
            parent=None,
            role=QtCore.Qt.DisplayRole,
            include_root=True,
    ):
        if model is None:
            model = self.model

        if parent is None:
            parent = QtCore.QModelIndex()

        data = []
        if include_root:
            datum = self.model.invisibleRootItem()
            if role is not None:
                datum = datum.data(role)
            data.append(datum)

        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            if role is not None:
                datum = model.data(index, role)
            else:
                datum = model.itemFromIndex(index)
            data.append(datum)

            if model.hasChildren(index):
                data.extend(self._all_items(
                    model=model,
                    parent=index,
                    role=role,
                    include_root=False,
                ))

        return data

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

    def child_added(self, child, row):
        parent = child.tree_parent

        self.pyqtify_connect(parent, child)

        if child.uuid is None:
            check_uuids(self.root)

    def deleted(self, parent, node, row):
        item = self.item_from_node(parent)
        item.takeRow(row)

    def supportedDropActions(self):
        return QtCore.Qt.MoveAction

    def mimeTypes(self):
        return (self.mime_type,)

    def node_from_index(self, index):
        item = self.model.itemFromIndex(index)
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
            print('checking -', node.name, repr(node.uuid))
            if node.uuid == u:
                print('matched')
                matches.add(node)

        print(self._all_items())
        print('looking for', repr(u))
        if isinstance(u, str):
            print('ack it is a string --------')

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

    def update_nodes(self):
        def visit(node, _):
            update = getattr(node, 'update', None)

            if update is not None:
                update()

        self.root.traverse(call_this=visit, internal_nodes=True)


class Reference(marshmallow.fields.UUID):
    def _serialize(self, value, attr, obj):
        return super()._serialize(value.uuid, attr, obj)
