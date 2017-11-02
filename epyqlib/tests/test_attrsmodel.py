import collections
import inspect
import itertools

import attr
import graham
import PyQt5.QtCore
import PyQt5.QtWidgets
import pytest

import epyqlib.attrsmodel
import epyqlib.tests.common
import epyqlib.searchbox
import epyqlib.treenode
import epyqlib.utils.general
import epyqlib.utils.qt

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


@graham.schemify('parameter')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Parameter(epyqlib.treenode.TreeNode):
    type = attr.ib(default='test_parameter', init=False)
    name = attr.ib(default='New Parameter')
    value = attr.ib(default=None, convert=epyqlib.attrsmodel.to_decimal_or_none)
    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()


@graham.schemify('group')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Group(epyqlib.treenode.TreeNode):
    type = attr.ib(default='test_group', init=False)
    name = attr.ib(default='New Group')
    children = attr.ib(
        default=attr.Factory(list),
        cmp=False,
        init=False,
        metadata={'valid_types': (Parameter, None)}
    )
    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self, node):
        return isinstance(node, tuple(self.addable_types().values()))


Root = epyqlib.attrsmodel.Root(
    default_name='Parameters',
    valid_types=(Parameter, Group)
)

columns = epyqlib.attrsmodel.columns(
    (
        (Parameter, 'name'),
        (Group, 'name'),
    ),
    ((Parameter, 'value'),),
)


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


def all_fields_in_columns(types, root_type, columns):
    fields = set()

    for cls in types:
        if cls is root_type:
            continue

        for field in epyqlib.attrsmodel.fields(cls):
            if field.no_column:
                continue

            fields.add((cls, field.name))

    columns_list = [
        tuple(x)
        for x in itertools.chain(*(
            column.items()
            for column in columns
        ))
        if x[0] is not root_type
    ]

    columns = set(columns_list)

    assert len(columns_list) == len(columns)

    extra = columns - fields
    missing = fields - columns

    assert extra == set()
    assert missing == set(), columns_to_code(missing)


def make_a_model(root_cls=Root, group_cls=Group, parameter_cls=Parameter,
                 columns=columns):
    root = root_cls()

    model = epyqlib.attrsmodel.Model(
        root=root,
        columns=columns,
    )

    group_a = group_cls(name='Group A')
    parameter_a_a = parameter_cls(name='Parameter A A')
    group_a_b = group_cls(name='Group A B')
    parameter_b = parameter_cls(name='Parameter B', value=42)
    group_c = group_cls(name='Group C')
    parameter_d = parameter_cls(name='Parameter D', value=42)

    root.append_child(group_a)
    group_a.append_child(parameter_a_a)
    group_a.append_child(group_a_b)

    root.append_child(parameter_b)

    root.append_child(group_c)

    root.append_child(parameter_d)

    return model


def test_model(qtmodeltester):
    model = make_a_model()

    qtmodeltester.check(model)


def test_search_column_0(qtbot):
    search_in_column(0, 'Parameter B')


def test_search_column_2(qtbot):
    search_in_column(1, 42)


def search_in_column(column, target):
    model = make_a_model()

    proxy = PyQt5.QtCore.QSortFilterProxyModel()
    proxy.setSourceModel(model)

    view = PyQt5.QtWidgets.QTreeView()
    view.setModel(proxy)

    index, = proxy.match(
        proxy.index(0, column),
        PyQt5.QtCore.Qt.DisplayRole,
        target,
        1,
        PyQt5.QtCore.Qt.MatchRecursive,
    )


def test_proxy_search_column_0(qtbot):
    proxy_search_in_column(0, 'Parameter B')


def test_proxy_search_column_0_child(qtbot):
    proxy_search_in_column(0, 'Parameter A A')


def test_proxy_search_column_2(qtbot):
    proxy_search_in_column(1, 42)


def proxy_search_in_column(column, target):
    model = make_a_model()

    proxy = epyqlib.utils.qt.PySortFilterProxyModel(filter_column=0)
    proxy.setSourceModel(model)

    view = PyQt5.QtWidgets.QTreeView()
    view.setModel(proxy)

    index, = proxy.match(
        proxy.index(0, column),
        PyQt5.QtCore.Qt.DisplayRole,
        target,
        1,
        PyQt5.QtCore.Qt.MatchRecursive,
    )

    match_node = model.node_from_index(proxy.mapToSource(index))
    assert match_node is not None

    index = proxy.search(
        text=target,
        search_from=model.index_from_node(model.root),
        column=column,
    )

    search_node = model.node_from_index(proxy.mapToSource(index))

    assert match_node is search_node


def node_from_name(model, name):
    index, = model.match(
        model.index(0, 0),
        PyQt5.QtCore.Qt.DisplayRole,
        name,
        1,
        PyQt5.QtCore.Qt.MatchRecursive,
    )

    return model.node_from_index(index)


@attr.s
class DataChangedCollector(PyQt5.QtCore.QObject):
    collected = PyQt5.QtCore.pyqtSignal('PyQt_PyObject')

    model = attr.ib()
    parameter = attr.ib()
    column = attr.ib()
    roles = attr.ib(default=(PyQt5.QtCore.Qt.DisplayRole,))

    def __attrs_post_init__(self):
        super().__init__()

    def collect(self, top_left, bottom_right, roles):
        # TODO: this is overly restrictive in that exactly the one cell
        #       must be changing rather than just being included in the
        #       range.

        right_one = all((
            self.parameter is self.model.node_from_index(top_left),
            self.parameter is self.model.node_from_index(bottom_right),
            self.column == top_left.column() == bottom_right.column(),
            tuple(roles) == self.roles,
        ))

        if right_one:
            parameter_index = self.model.index_from_node(self.parameter)
            parameter_name_index = self.model.index(
                parameter_index.row(),
                self.column,
                parameter_index.parent(),
            )

            self.collected.emit(self.model.data(
                parameter_name_index,
                PyQt5.QtCore.Qt.DisplayRole,
            ))


def test_data_changed(qtbot):
    model = make_a_model()

    parameter = node_from_name(model, 'Parameter B')

    values = epyqlib.tests.common.Values(
        initial=42,
        input=[42, 37],
        expected=['37'],
    )

    parameter.value = values.initial

    data_changed = DataChangedCollector(
        model=model,
        parameter=parameter,
        column=1,
        roles=(PyQt5.QtCore.Qt.DisplayRole,),
    )

    model.dataChanged.connect(data_changed.collect)
    data_changed.collected.connect(values.collect)

    for value in values.input:
        parameter.value = value

    parameter.tree_parent.remove_child(child=parameter)

    parameter.value += 1

    assert tuple(values.expected) == tuple(values.collected)


def test_other_data_did_not_change(qtbot):
    model = make_a_model()

    parameter = node_from_name(model, 'Parameter B')

    values = epyqlib.tests.common.Values(
        initial=42,
        input=[42, 37],
        expected=['37'],
    )

    parameter.value = values.initial

    data_changed = DataChangedCollector(
        model=model,
        parameter=parameter,
        column=1,
        roles=(PyQt5.QtCore.Qt.DisplayRole,),
    )

    other_parameter = node_from_name(model, 'Parameter D')

    other_values = epyqlib.tests.common.Values(
        initial=12,
        input=[],
        expected=[],
    )

    other_parameter.value = other_values.initial

    other_data_changed = DataChangedCollector(
        model=model,
        parameter=other_parameter,
        column=1,
        roles=(PyQt5.QtCore.Qt.DisplayRole,),
    )

    model.dataChanged.connect(data_changed.collect)
    data_changed.collected.connect(values.collect)

    model.dataChanged.connect(other_data_changed.collect)
    other_data_changed.collected.connect(other_values.collect)

    for value in values.input:
        parameter.value = value

    parameter.tree_parent.remove_child(child=parameter)

    parameter.value += 1

    assert tuple(values.expected) == tuple(values.collected)
    assert tuple(other_values.expected) == tuple(other_values.collected)


def test_local_drag_n_drop(qtbot):
    model = make_a_model()
    model.add_drop_sources(model.root)

    parameter = node_from_name(model, 'Parameter B')
    group = node_from_name(model, 'Group C')

    values = epyqlib.tests.common.Values(
        initial=42,
        input=[42, 37, 23],
        expected=['37', '23'],
    )

    values_after_drop = epyqlib.tests.common.Values(
        initial=int(values.expected[-1]),
        input=[11, 13],
        expected=['11', '13'],
    )

    parameter.value = values.initial

    data_changed = DataChangedCollector(
        model=model,
        parameter=parameter,
        column=1,
        roles=(PyQt5.QtCore.Qt.DisplayRole,),
    )

    model.dataChanged.connect(data_changed.collect)
    data_changed.collected.connect(values.collect)

    for value in values.input:
        parameter.value = value

    assert tuple(values.expected) == tuple(values.collected)

    mime_data = model.mimeData((model.index_from_node(parameter),))

    model.dropMimeData(
        data=mime_data,
        action=PyQt5.QtCore.Qt.MoveAction,
        row=-1,
        column=0,
        parent=model.index_from_node(group),
    )

    data_changed.collected.connect(values_after_drop.collect)

    for value in values_after_drop.input:
        parameter.value = value

    parameter.tree_parent.remove_child(child=parameter)

    parameter.value += 1

    assert (
        tuple(values_after_drop.expected)
        == tuple(values_after_drop.collected)
    )


def test_prepopulated_connections(qtbot):
    values = epyqlib.tests.common.Values(
        initial=42,
        input=[42, 37, 23],
        expected=['37', '23'],
    )

    parameter = Parameter(name='Parameter A', value=values.initial)

    root = Root()
    root.append_child(parameter)

    model = epyqlib.attrsmodel.Model(
        root=root,
        columns=columns,
    )

    data_changed = DataChangedCollector(
        model=model,
        parameter=parameter,
        column=1,
        roles=(PyQt5.QtCore.Qt.DisplayRole,),
    )

    model.dataChanged.connect(data_changed.collect)
    data_changed.collected.connect(values.collect)

    for value in values.input:
        parameter.value = value

    assert tuple(values.expected) == tuple(values.collected)


def test_with_pyqtpropertys(qtbot):
    @graham.schemify('parameter')
    @epyqlib.attrsmodel.ify()
    @epyqlib.utils.qt.pyqtify(
        property_decorator=lambda: PyQt5.QtCore.pyqtProperty('PyQt_PyObject'),
    )
    @attr.s(hash=False)
    class Parameter(epyqlib.treenode.TreeNode):
        type = attr.ib(default='test_parameter', init=False)
        name = attr.ib(default='New Parameter')
        value = attr.ib(default=None,
                        convert=epyqlib.attrsmodel.to_decimal_or_none)
        uuid = epyqlib.attrsmodel.attr_uuid()

        def __attrs_post_init__(self):
            super().__init__()

    Root = epyqlib.attrsmodel.Root(
        default_name='Parameters',
        valid_types=(Parameter, Group)
    )

    columns = epyqlib.attrsmodel.columns(
        ((Parameter, 'name'),),
        ((Parameter, 'value'),),
    )

    model = make_a_model(
        root_cls=Root,
        parameter_cls=Parameter,
        columns=columns,
    )

    parameter = node_from_name(model, 'Parameter B')

    values = epyqlib.tests.common.Values(
        initial=42,
        input=[42, 37],
        expected=['37'],
    )

    parameter.value = values.initial

    data_changed = DataChangedCollector(
        model=model,
        parameter=parameter,
        column=1,
        roles=(PyQt5.QtCore.Qt.DisplayRole,),
    )

    model.dataChanged.connect(data_changed.collect)
    data_changed.collected.connect(values.collect)

    for value in values.input:
        parameter.value = value

    parameter.tree_parent.remove_child(child=parameter)

    parameter.value += 1

    assert tuple(values.expected) == tuple(values.collected)


def test_columns():
    columns = epyqlib.attrsmodel.columns(
        ((Parameter, 'name'), (Group, 'name')),
        ((Parameter, 'value'),),
    )

    name_column = epyqlib.attrsmodel.Column(
        name='Name',
        fields={Parameter: 'name', Group: 'name'},
    )

    assert columns[0] == name_column
    # TODO: using the human name?  seems kinda bad in code
    assert columns['Name'] == name_column
    assert columns[Parameter, 'name'] == name_column


def test_children_property_retained():
    @epyqlib.attrsmodel.ify()
    @epyqlib.utils.qt.pyqtify()
    @attr.s(hash=False)
    class N(epyqlib.treenode.TreeNode):
        children = attr.ib(default=attr.Factory(list), init=False)

        def __attrs_post_init__(self):
            super().__init__()

    n = N()

    assert isinstance(inspect.getattr_static(n, 'children'), property)


def test_children_changed_signals():
    model = make_a_model()

    group = node_from_name(model, 'Group C')

    added_items = []

    def added(item, row):
        added_items.append((item, row))

    removed_items = []

    def removed(parent, item, row):
        removed_items.append((parent, item, row))

    group.pyqt_signals.child_added.connect(added)
    group.pyqt_signals.child_removed.connect(removed)

    parameter = Parameter()
    group.append_child(parameter)
    assert added_items == [(parameter, 0)]

    group.remove_child(child=parameter)

    assert added_items == [(parameter, 0)]
    assert removed_items == [(group, parameter, 0)]


@graham.schemify('pass_through')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@epyqlib.utils.qt.pyqtify_passthrough_properties(
    original='original',
    field_names=('value',),
)
@attr.s(hash=False)
class PassThrough(epyqlib.treenode.TreeNode):
    original = attr.ib(
        metadata=graham.create_metadata(
            field=epyqlib.attrsmodel.Reference(),
        ),
    )
    value = attr.ib(default=None)
    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()

PassThroughRoot = epyqlib.attrsmodel.Root(
    default_name='Pass Through',
    valid_types=(Parameter, PassThrough)
)


def test_original_signals(qtbot):
    root = PassThroughRoot()

    columns = epyqlib.attrsmodel.columns(
        ((Parameter, 'name'),),
        (
            (Parameter, 'value'),
            (PassThrough, 'value'),
        ),
    )

    model = epyqlib.attrsmodel.Model(
        root=root,
        columns=columns,
    )

    original = Parameter()
    passthrough_a = PassThrough(original=None, value=None)
    passthrough_b = PassThrough(original=original, value=None)

    root.append_child(original)
    root.append_child(passthrough_a)
    root.append_child(passthrough_b)

    common_expected = ['5']

    values = {
        'original': epyqlib.tests.common.Values(
            initial=None,
            input=None,
            expected=common_expected,
        ),
        'a': epyqlib.tests.common.Values(
            initial=None,
            input=None,
            expected=common_expected,
        ),
        'b': epyqlib.tests.common.Values(
            initial=None,
            input=None,
            expected=common_expected,
        ),
    }

    column = 1
    collectors = {
        'original': DataChangedCollector(
            model=model,
            parameter=original,
            column=column,
            roles=(PyQt5.QtCore.Qt.DisplayRole,),
        ),
        'a': DataChangedCollector(
            model=model,
            parameter=passthrough_a,
            column=column,
            roles=(PyQt5.QtCore.Qt.DisplayRole,),
        ),
        'b': DataChangedCollector(
            model=model,
            parameter=passthrough_b,
            column=column,
            roles=(PyQt5.QtCore.Qt.DisplayRole,),
        ),
    }

    for name in values:
        model.dataChanged.connect(collectors[name].collect)
        collectors[name].collected.connect(values[name].collect)

    passthrough_a.original = original

    assert passthrough_a.value == passthrough_b.value == original.value

    passthrough_a.value = 5

    assert passthrough_a.value == passthrough_b.value == original.value

    for name, value in values.items():
        assert tuple(value.expected) == tuple(value.collected)
