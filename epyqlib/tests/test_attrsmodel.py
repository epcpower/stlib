import PyQt5.QtCore
import PyQt5.QtWidgets
import attr

import epyqlib.attrsmodel
import epyqlib.searchbox
import epyqlib.treenode
import epyqlib.utils.general
import epyqlib.utils.qt

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


@attr.s(hash=False)
class Parameter(epyqlib.treenode.TreeNode):
    type = attr.ib(default='test_parameter', init=False)
    name = attr.ib(default='New Parameter')
    value = attr.ib(default=None, convert=epyqlib.attrsmodel.to_decimal_or_none)
    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()


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

types = (Root, Parameter, Group)

columns = epyqlib.attrsmodel.columns(
    (
        (Parameter, 'name'),
        (Group, 'name'),
    ),
    ((Parameter, 'value'),),
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
    parameter_b = Parameter(name='Parameter B', value=42)
    group_c = Group(name='Group C')

    model.add_child(parent=root, child=group_a)
    model.add_child(parent=group_a, child=parameter_a_a)
    model.add_child(parent=group_a, child=group_a_b)

    model.add_child(parent=root, child=parameter_b)

    model.add_child(parent=root, child=group_c)

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
    assert match_node is not None

    index = proxy.search(
        text=target,
        search_from=model.index_from_node(model.root),
        column=column,
    )

    search_node = model.node_from_index(proxy.mapToSource(index))

    assert match_node is search_node
