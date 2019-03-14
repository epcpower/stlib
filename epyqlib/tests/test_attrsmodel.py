import collections
import inspect
import itertools
import sys

import attr
import graham
import PyQt5.QtCore
import PyQt5.QtWidgets
import pytest
from pytestqt.qt_compat import qt_api

import epyqlib.attrsmodel
import epyqlib.tests.common
import epyqlib.searchbox
import epyqlib.treenode
import epyqlib.utils.general
import epyqlib.utils.qt

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


@graham.schemify(tag='parameter')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Parameter(epyqlib.treenode.TreeNode):
    name = attr.ib(default='New Parameter')
    value = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_decimal_or_none,
    )
    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self, node):
        return False

    can_delete = epyqlib.attrsmodel.childless_can_delete
    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


@graham.schemify(tag='group')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Group(epyqlib.treenode.TreeNode):
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

    def can_delete(self, node=None):
        if node is None:
            return self.tree_parent.can_delete(node=self)

        return True

    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


Root = epyqlib.attrsmodel.Root(
    default_name='Parameters',
    valid_types=(Parameter, Group)
)

types = epyqlib.attrsmodel.Types(
    types=(
        Root,
        Parameter,
        Group,
    ),
)

# TODO: CAMPid 943896754217967154269254167
def merge(name, *types):
    return tuple((x, name) for x in types)


columns = epyqlib.attrsmodel.columns(
    (
        (Parameter, 'name'),
        (Group, 'name'),
    ),
    ((Parameter, 'value'),),
    merge('uuid', *types.types.values()),
)


TestAttrsModel = epyqlib.attrsmodel.build_tests(
    types=types,
    root_type=Root,
    columns=columns,
)


def make_a_model(
    root_cls=Root,
    group_cls=Group,
    parameter_cls=Parameter,
    columns=columns,
):
    root = root_cls(uuid='0f68fa9c-705d-4ba6-9ffa-406cb549a4dd')

    model = epyqlib.attrsmodel.Model(
        root=root,
        columns=columns,
    )

    group_a = group_cls(
        name='Group A',
        uuid='f5b7569e-9d7e-4433-a034-29c3e04d1ad4',
    )
    parameter_a_a = parameter_cls(
        name='Parameter A A',
        uuid='df286eb3-67f0-42d6-b56a-8ee1ded49248',
    )
    group_a_b = group_cls(
        name='Group A B',
        uuid='aee15e15-c5df-4e73-ae1a-9a5d4eaa798a',
    )
    parameter_b = parameter_cls(
        name='Parameter B',
        value=42, uuid='a1fd7abb-4760-472e-bc94-1ef4d2cfad62',
    )
    group_c = group_cls(
        name='Group C',
        uuid='2777e016-a3e6-470d-b20c-7a44904df710',
    )
    parameter_d = parameter_cls(
        name='Parameter D',
        value=42, uuid='97f1f9e1-5601-4304-a583-561df79c47be',
    )

    root.append_child(group_a)
    group_a.append_child(parameter_a_a)
    group_a.append_child(group_a_b)

    root.append_child(parameter_b)

    root.append_child(group_c)

    root.append_child(parameter_d)

    return model


def test_column_header_text(qtbot):
    model = make_a_model()

    assert model.model.horizontalHeaderItem(0).text() == 'Name'
    assert model.model.horizontalHeaderItem(1).text() == 'Value'


def test_model(qtmodeltester):
    model = make_a_model()

    qtmodeltester.check(model.model)


def test_search_column_0(qtbot):
    search_in_column(0, 'Parameter B')


def test_search_column_2(qtbot):
    search_in_column(1, 42)


def search_in_column(column, target):
    model = make_a_model()

    proxy = PyQt5.QtCore.QSortFilterProxyModel()
    proxy.setSourceModel(model.model)

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
    proxy.setSourceModel(model.model)

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
        search_from=PyQt5.QtCore.QModelIndex(),
        column=column,
    )

    search_node = model.node_from_index(proxy.mapToSource(index))

    assert match_node is search_node


def node_from_name(model, name):
    index, = model.model.match(
        model.model.index(0, 0),
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
            set(self.roles).issubset(roles),
        ))

        if right_one:
            parameter_name_index = top_left.siblingAtColumn(self.column)

            self.collected.emit(parameter_name_index.data(
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

    model.model.dataChanged.connect(data_changed.collect)
    data_changed.collected.connect(values.collect)

    for value in values.input:
        parameter.value = value

    parameter.tree_parent.remove_child(child=parameter)

    parameter.value += 1

    assert tuple(values.collected) == tuple(values.expected)


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

    model.model.dataChanged.connect(data_changed.collect)
    data_changed.collected.connect(values.collect)

    model.model.dataChanged.connect(other_data_changed.collect)
    other_data_changed.collected.connect(other_values.collect)

    for value in values.input:
        parameter.value = value

    parameter.tree_parent.remove_child(child=parameter)

    parameter.value += 1

    assert tuple(values.expected) == tuple(values.collected)
    assert tuple(other_values.expected) == tuple(other_values.collected)


def test_local_drag_n_drop(qtbot):
    model = make_a_model()
    model.add_drop_sources(model)

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

    model.model.dataChanged.connect(data_changed.collect)
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

    parameter = Parameter(
        name='Parameter A',
        value=values.initial,
    )

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

    model.model.dataChanged.connect(data_changed.collect)
    data_changed.collected.connect(values.collect)

    for value in values.input:
        parameter.value = value

    assert tuple(values.expected) == tuple(values.collected)


def test_postpopulated_connections(qtbot):
    values = epyqlib.tests.common.Values(
        initial=42,
        input=[42, 37, 23],
        expected=['37', '23'],
    )

    parameter = Parameter(
        name='Parameter A',
        value=values.initial,
    )

    root = Root()
    model = epyqlib.attrsmodel.Model(
        root=root,
        columns=columns,
    )

    root.append_child(parameter)

    data_changed = DataChangedCollector(
        model=model,
        parameter=parameter,
        column=1,
        roles=(PyQt5.QtCore.Qt.DisplayRole,),
    )

    model.model.dataChanged.connect(data_changed.collect)
    data_changed.collected.connect(values.collect)

    for value in values.input:
        parameter.value = value

    assert tuple(values.expected) == tuple(values.collected)


def test_with_pyqtpropertys(qtbot):
    @graham.schemify(tag='pyqtproperty_parameter')
    @epyqlib.attrsmodel.ify()
    @epyqlib.utils.qt.pyqtify(
        property_decorator=lambda: PyQt5.QtCore.pyqtProperty('PyQt_PyObject'),
    )
    @attr.s(hash=False)
    class PyQtPropertyParameter(epyqlib.treenode.TreeNode):
        type = attr.ib(default='test_parameter', init=False)
        name = attr.ib(default='New Parameter')
        value = attr.ib(
            default=None,
            converter=epyqlib.attrsmodel.to_decimal_or_none,
        )
        uuid = epyqlib.attrsmodel.attr_uuid()

        def __attrs_post_init__(self):
            super().__init__()

    Root = epyqlib.attrsmodel.Root(
        default_name='Parameters',
        valid_types=(PyQtPropertyParameter, Group)
    )

    columns = epyqlib.attrsmodel.columns(
        ((PyQtPropertyParameter, 'name'),),
        ((PyQtPropertyParameter, 'value'),),
    )

    model = make_a_model(
        root_cls=Root,
        parameter_cls=PyQtPropertyParameter,
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

    model.model.dataChanged.connect(data_changed.collect)
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


@graham.schemify(tag='pass_through')
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
    value = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_decimal_or_none,
    )
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
        model.model.dataChanged.connect(collectors[name].collect)
        collectors[name].collected.connect(values[name].collect)

    passthrough_a.original = original

    assert passthrough_a.value == passthrough_b.value == original.value

    passthrough_a.value = 5

    assert passthrough_a.value == passthrough_b.value == original.value

    for name, value in values.items():
        assert tuple(value.expected) == tuple(value.collected)


def test_to_decimal_or_none_re_locale():
    decimal_string = '1,000.00'

    with epyqlib.tests.common.use_locale(('C', None)):
        with pytest.raises(ValueError, match=repr(decimal_string)):
            epyqlib.attrsmodel.to_decimal_or_none(decimal_string)

    with epyqlib.tests.common.use_locale(('en_US', 'utf8'), 'us'):
        epyqlib.attrsmodel.to_decimal_or_none(decimal_string)


def test_to_int_or_none_re_locale():
    int_string = '1,000'

    with epyqlib.tests.common.use_locale(('C', None)):
        with pytest.raises(ValueError, match=repr(int_string)):
            epyqlib.attrsmodel.to_int_or_none(int_string)

    with epyqlib.tests.common.use_locale(('en_US', 'utf8'), 'us'):
        epyqlib.attrsmodel.to_int_or_none(int_string)


def test_two_state_checkbox():
    @graham.schemify(tag='checkbox_parameter')
    @epyqlib.attrsmodel.ify()
    @epyqlib.utils.qt.pyqtify()
    @attr.s(hash=False)
    class CheckboxParameter(epyqlib.treenode.TreeNode):
        type = attr.ib(default='test_parameter', init=False)
        name = attr.ib(default='New Parameter')
        value = attr.ib(
            default=None,
            converter=epyqlib.attrsmodel.two_state_checkbox,
        )
        uuid = epyqlib.attrsmodel.attr_uuid()

        def __attrs_post_init__(self):
            super().__init__()

    Root = epyqlib.attrsmodel.Root(
        default_name='Parameters',
        valid_types=(CheckboxParameter, Group)
    )

    columns = epyqlib.attrsmodel.columns(
        (
            (CheckboxParameter, 'name'),
            (Group, 'name'),
        ),
        ((CheckboxParameter, 'value'),),
    )

    root = Root()
    model = epyqlib.attrsmodel.Model(
        root=root,
        columns=columns,
    )

    parameter = CheckboxParameter()
    root.append_child(parameter)

    index = model.index_from_node(parameter)
    column_index = columns.index_of('Value')
    index = index.siblingAtColumn(column_index)

    flags = model.model.flags(index)
    assert flags & PyQt5.QtCore.Qt.ItemIsUserCheckable


def test_enumeration(qtbot):
    @graham.schemify(tag='leaf')
    @epyqlib.attrsmodel.ify()
    @epyqlib.utils.qt.pyqtify()
    @attr.s(hash=False)
    class TestEnumerationLeaf(epyqlib.treenode.TreeNode):
        name = attr.ib(default='New Leaf')
        enumeration_uuid = attr.ib(
            default=None,
            converter=epyqlib.attrsmodel.convert_uuid,
        )
        epyqlib.attrsmodel.attrib(
            attribute=enumeration_uuid,
            delegate=epyqlib.attrsmodel.RootDelegateCache(
                list_selection_root='test list_selection_root',
            ),
            converter=epyqlib.attrsmodel.convert_uuid,
        )
        uuid = epyqlib.attrsmodel.attr_uuid()

        def __attrs_post_init__(self):
            super().__init__()

    @graham.schemify(tag='group')
    @epyqlib.attrsmodel.ify()
    @epyqlib.utils.qt.pyqtify()
    @attr.s(hash=False)
    class TestEnumerationGroup(epyqlib.treenode.TreeNode):
        name = attr.ib(default='New Group')
        children = attr.ib(
            default=attr.Factory(list),
            cmp=False,
            init=False,
            metadata={'valid_types': (TestEnumerationLeaf,)}
        )
        uuid = epyqlib.attrsmodel.attr_uuid()

        def __attrs_post_init__(self):
            super().__init__()

        def can_drop_on(self, node):
            return isinstance(node, tuple(self.addable_types().values()))

    Root = epyqlib.attrsmodel.Root(
        default_name='Test',
        valid_types=(TestEnumerationLeaf, TestEnumerationGroup)
    )

    columns = epyqlib.attrsmodel.columns(
        (
            (TestEnumerationLeaf, 'name'),
            (TestEnumerationGroup, 'name'),
        ),
        ((TestEnumerationLeaf, 'enumeration_uuid'),),
    )

    root = Root(uuid='b05c413f-215c-4376-a107-5bce992ed7a3')
    model = epyqlib.attrsmodel.Model(
        root=root,
        columns=columns,
    )
    model.add_drop_sources(model)

    item = TestEnumerationLeaf(
        name='Outside',
        uuid='cdedbbd2-c596-42cc-be45-7eb7953cc5ad',
    )
    root.append_child(item)

    group = TestEnumerationGroup(
        name='Enumerations',
        uuid='06c2a6ad-00b2-49ac-a836-057daa1ddc2f',
    )
    root.append_child(group)
    model.list_selection_roots['test list_selection_root'] = group

    enumerator_a = TestEnumerationLeaf(
        name='Inside A',
        uuid='1900f7e3-7230-40c1-9f5f-b838e2c33710',
    )
    group.append_child(enumerator_a)
    enumerator_b = TestEnumerationLeaf(
        name='Inside B',
        uuid='b9aeea0a-94ea-4fe6-a627-50caa942fbb5',
    )
    group.append_child(enumerator_b)
    enumerator_c = TestEnumerationLeaf(
        name='Inside C',
        uuid='a6a4e027-e128-4860-9f64-8be93708916e',
    )
    group.append_child(enumerator_c)

    view = PyQt5.QtWidgets.QTreeView()
    view.setItemDelegate(epyqlib.attrsmodel.create_delegate())
    view.setModel(model.model)

    target_index = model.index_from_node(item)
    target_index = target_index.siblingAtColumn(
        columns.index_of('Enumeration Uuid'),
    )

    item.enumeration_uuid = enumerator_a.uuid

    application = qt_api.QApplication.instance()

    for row, enumerator in enumerate(group.children):
        assert view.edit(
            target_index,
            PyQt5.QtWidgets.QAbstractItemView.AllEditTriggers,
            None,
        )
        editor, = view.findChildren(PyQt5.QtWidgets.QComboBox)

        editor.setCurrentIndex(row)

        PyQt5.QtCore.QCoreApplication.postEvent(
            editor,
            PyQt5.QtGui.QKeyEvent(
                PyQt5.QtCore.QEvent.KeyPress,
                PyQt5.QtCore.Qt.Key_Enter,
                PyQt5.QtCore.Qt.NoModifier,
            ),
        )

        # this is fun.  if you get weird issues try doing this more times
        for _ in range(3):
            application.processEvents()

        assert enumerator.uuid == item.enumeration_uuid


def test_all_selection_roots_avail():
    @graham.schemify(tag='parameter')
    @epyqlib.attrsmodel.ify()
    @epyqlib.utils.qt.pyqtify()
    @attr.s(hash=False)
    class C(epyqlib.treenode.TreeNode):
        a = attr.ib(default=None)
        b = attr.ib(default=None)
        c = attr.ib(default=None)
        epyqlib.attrsmodel.attrib(
            attribute=c,
            delegate=epyqlib.attrsmodel.RootDelegateCache(
                list_selection_root='c root',
            ),
        )
        d = attr.ib(default=None)
        epyqlib.attrsmodel.attrib(
            attribute=d,
            delegate=epyqlib.attrsmodel.RootDelegateCache(
                list_selection_root='d root',
            ),
        )

        def __attrs_post_init__(self):
            super().__init__()

    expected = {'c':'c root', 'd':'d root'}
    assert  epyqlib.attrsmodel.list_selection_roots(C) == expected


def test_types_list_selection_roots():
    @graham.schemify(tag='parameter')
    @epyqlib.attrsmodel.ify()
    @epyqlib.utils.qt.pyqtify()
    @attr.s(hash=False)
    class C(epyqlib.treenode.TreeNode):
        a = attr.ib(default=None)
        b = attr.ib(default=None)

        c = attr.ib(default=None)
        epyqlib.attrsmodel.attrib(
            attribute=c,
            delegate=epyqlib.attrsmodel.RootDelegateCache(
                list_selection_root='c root',
            ),
        )

        d = attr.ib(default=None)
        epyqlib.attrsmodel.attrib(
            attribute=d,
            delegate=epyqlib.attrsmodel.RootDelegateCache(
                list_selection_root='d root',
            ),
        )

        def __attrs_post_init__(self):
            super().__init__()

    @graham.schemify(tag='parameter')
    @epyqlib.attrsmodel.ify()
    @epyqlib.utils.qt.pyqtify()
    @attr.s(hash=False)
    class D(epyqlib.treenode.TreeNode):
        e = attr.ib(default=None)
        f = attr.ib(default=None)

        g = attr.ib(default=None)
        epyqlib.attrsmodel.attrib(
            attribute=g,
            delegate=epyqlib.attrsmodel.RootDelegateCache(
                list_selection_root='g root',
            ),
        )

        h = attr.ib(default=None)
        epyqlib.attrsmodel.attrib(
            attribute=h,
            delegate=epyqlib.attrsmodel.RootDelegateCache(
                list_selection_root='h root',
            ),
        )

        def __attrs_post_init__(self):
            super().__init__()

    types = epyqlib.attrsmodel.Types(types=(C, D))

    expected = {
        'c root',
        'd root',
        'g root',
        'h root',
    }

    assert set(types.list_selection_roots()) == expected


def test_noneditable_columns():
    model = make_a_model()

    group = model.root.children[0]
    assert isinstance(group, Group)

    base_index = model.index_from_node(group)

    index = base_index.siblingAtColumn(columns.index_of('Value'))
    item = model.model.itemFromIndex(index)
    assert not item.isEditable()


def test_editable_columns():
    model = make_a_model()

    group = model.root.children[0]
    assert isinstance(group, Group)

    base_index = model.index_from_node(group)

    index = base_index.siblingAtColumn(columns.index_of('Name'))
    item = model.model.itemFromIndex(index)
    assert item.isEditable()


def test_none_values_show_dash():
    model = make_a_model()

    group = model.root.children[0]
    assert isinstance(group, Group)

    base_index = model.index_from_node(group)
    index = base_index.siblingAtColumn(columns.index_of('Name'))
    item = model.model.itemFromIndex(index)

    group.name = "The Name"
    assert group.name == item.data(PyQt5.QtCore.Qt.DisplayRole)
    assert group.name == item.data(PyQt5.QtCore.Qt.EditRole)


    group.name = None
    # TODO: CAMPid 0794305784527546542452654254679680
    # The display role is supposed to be '-' for None but they can't be
    # different
    #
    # http://doc.qt.io/qt-5/qstandarditem.html#data
    #   The default implementation treats Qt::EditRole and Qt::DisplayRole
    #   as referring to the same data
    assert '' == item.data(PyQt5.QtCore.Qt.DisplayRole)
    assert '' == item.data(PyQt5.QtCore.Qt.EditRole)
