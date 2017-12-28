import PyQt5.QtCore
import PyQt5.QtWidgets
import attr
import epyqlib.attrsmodel
import epyqlib.pm.parametermodel
import epyqlib.searchbox
import epyqlib.tests.test_attrsmodel
import epyqlib.treenode
import epyqlib.utils.general
import epyqlib.utils.qt
import graham

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


@graham.schemify('parameter')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Parameter(epyqlib.treenode.TreeNode):
    type = attr.ib(default='parameter', init=False)
    name = attr.ib(default='New Parameter')
    default = attr.ib(default=None, convert=epyqlib.attrsmodel.to_decimal_or_none)
    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()


@graham.schemify('Group')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Group(epyqlib.treenode.TreeNode):
    type = attr.ib(default='group', init=False)
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

types = epyqlib.attrsmodel.Types(
    types=(Root, Parameter, Group),
)

columns = epyqlib.attrsmodel.columns(
    (
        (Parameter, 'name'),
        (Group, 'name'),
    ),
    ((Parameter, 'default'),),
)



def make_a_model():
    root = Root()

    model = epyqlib.attrsmodel.Model(
        root=root,
        columns=columns,
    )

    group_a = Group(name='Group A')
    parameter_a_a = Parameter(name='Parameter A A')
    group_a_b = Group(name='Group A B')
    parameter_b = Parameter(name='Parameter B', default=42)
    group_c = Group(name='Group C')

    root.append_child(group_a)
    group_a.append_child(parameter_a_a)
    group_a.append_child(group_a_b)

    root.append_child(parameter_b)

    root.append_child(group_c)

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
    )


def test_proxy_search_column_0(qtbot):
    proxy_search_in_column(0, 'Parameter B')


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
    )

    match_node = model.node_from_index(proxy.mapToSource(index))

    index = proxy.search(
        text=target,
        search_from=model.index_from_node(model.root),
        column=column,
    )

    search_node = model.node_from_index(proxy.mapToSource(index))

    assert match_node is search_node


def test_array_addable_types():
    array = epyqlib.pm.parametermodel.Array()

    value_types = (
        epyqlib.pm.parametermodel.Parameter,
        epyqlib.pm.parametermodel.Group,
        # epcpm.parametermodel.Array,
    )

    assert array.addable_types() == epyqlib.attrsmodel.create_addable_types(
        value_types,
    )

    for value_type in value_types:
        child = value_type()
        array.append_child(child)

        assert array.addable_types() == epyqlib.attrsmodel.create_addable_types(
            (),
        )

        array.remove_child(child=child)

        assert array.addable_types() == epyqlib.attrsmodel.create_addable_types(
            value_types,
        )


def test_array_update_children_length():
    array = epyqlib.pm.parametermodel.Array()
    parameter = epyqlib.pm.parametermodel.Parameter()

    assert len(array.children) == 0

    array.append_child(parameter)

    assert len(array.children) == 1

    for n in (3, 7, 4, 1, 5):
        array.length = n
        assert len(array.children) == n


def test_array_passthrough_nv():
    array = epyqlib.pm.parametermodel.Array()
    parameter = epyqlib.pm.parametermodel.Parameter()
    array.append_child(parameter)

    array.length = 5

    assignments = (
        (3, True),
        (1, False),
        (0, True),
    )

    for index, value in assignments:
        array.children[index].nv = value
        assert all(child.nv == value for child in array.children)


def test_all_addable_also_in_types():
    # Since addable types is dynamic and could be anything... this
    # admittedly only checks the addable types on default instances.
    for cls in epyqlib.pm.parametermodel.types.types.values():
        addable_types = cls.all_addable_types().values()
        assert set(addable_types) - set(
            epyqlib.pm.parametermodel.types) == set()


def assert_incomplete_types(name):
    assert [] == [
        cls
        for cls in epyqlib.pm.parametermodel.types.types.values()
        if not hasattr(cls, name)
    ]


def test_all_have_can_drop_on():
    assert_incomplete_types('can_drop_on')


def test_all_have_can_delete():
    assert_incomplete_types('can_delete')


def test_all_fields_in_columns():
    epyqlib.tests.test_attrsmodel.all_fields_in_columns(
        types=epyqlib.pm.parametermodel.types,
        root_type=epyqlib.pm.parametermodel.Root,
        columns=epyqlib.pm.parametermodel.columns,
    )
