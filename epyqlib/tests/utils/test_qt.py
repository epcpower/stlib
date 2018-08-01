import inspect
import itertools

import attr
import pytest
import PyQt5.QtCore
import PyQt5.QtGui

import epyqlib.tests.common
import epyqlib.utils.qt


@epyqlib.utils.qt.pyqtify()
@attr.s
class P(PyQt5.QtCore.QObject):
    a = attr.ib()
    b = attr.ib()
    c = attr.ib()

    def __attrs_post_init__(self):
        super().__init__()
        self.get = None
        self.set = None

    @PyQt5.QtCore.pyqtProperty('PyQt_PyObject')
    def pyqtify_c(self):
        x = epyqlib.utils.qt.pyqtify_get(self, 'c')
        self.get = True
        return x

    @pyqtify_c.setter
    def pyqtify_c(self, value):
        self.set = True
        return epyqlib.utils.qt.pyqtify_set(self, 'c', value)


def test_types(qtbot):
    p = P(a=1, b=2, c=3)

    # TODO: this would be nice but all ideas so far are ugly
    # assert isinstance(P.a, attr.Attribute)

    assert isinstance(attr.fields(P).a, attr.Attribute)
    assert isinstance(inspect.getattr_static(p, 'a'), property)
    assert isinstance(inspect.getattr_static(p, 'c'), PyQt5.QtCore.pyqtProperty)


def assert_attrs_as_expected(x, values):
    assert attr.asdict(x) == {
        k: tuple(itertools.chain((v.initial,), v.expected))[-1]
        for k, v in values.items()
    }


def test_overall(qtbot):
    values = {
        'a': epyqlib.tests.common.Values(
            initial=1,
            input=[12, 12, 13],
            expected=[12, 13],
        ),
        'b': epyqlib.tests.common.Values(
            initial=2,
            input=[42, 42, 37],
            expected=[42, 37],
        ),
        'c': epyqlib.tests.common.Values(
            initial=3,
            input=[4],
            expected=[4],
        ),
    }

    p = P(**{k: v.initial for k, v in values.items()})
    fields = attr.fields(P)
    assert len(fields) == len(values)

    signals = epyqlib.utils.qt.pyqtify_signals(p)
    for name, v in values.items():
        getattr(signals, name).connect(v.collect)

    for name, v in values.items():
        for value in v.input:
            setattr(p, name, value)

    for name, v in values.items():
        assert tuple(v.expected) == tuple(v.collected)

    assert_attrs_as_expected(p, values)

    p.c = object()
    assert p.pyqtify_c is p.c

    p.get = False
    p.c
    assert p.get

    p.set = False
    p.c = 0
    assert p.set


def test_independence(qtbot):
    ad = {'a': 1, 'b': 2, 'c': 3}
    a = P(**ad)

    bd = {'a': 10, 'b': 20, 'c': 30}
    b = P(**bd)

    assert(attr.asdict(a) == ad)
    assert(attr.asdict(b) == bd)


@epyqlib.utils.qt.pyqtify()
@attr.s
class Q(PyQt5.QtCore.QObject):
    a = attr.ib()
    b = attr.ib()

    def __attrs_post_init__(self):
        super().__init__()
        self.get = None
        self.set = None

    @PyQt5.QtCore.pyqtProperty('PyQt_PyObject')
    def pyqtify_b(self):
        return epyqlib.utils.qt.pyqtify_get(self, 'b')

    @pyqtify_b.setter
    def pyqtify_b(self, value):
        # self.a = min(self.a, value)
        if value < self.a:
            self.a = value

        epyqlib.utils.qt.pyqtify_set(self, 'b', value)


def test_property_cross_effect(qtbot):
    values = {
        'a': epyqlib.tests.common.Values(
            initial=10,
            input=[],
            expected=[9],
        ),
        'b': epyqlib.tests.common.Values(
            initial=20,
            input=[30, 10, 9, 20],
            expected=[30, 10, 9, 20],
        ),
    }

    p = Q(**{k: v.initial for k, v in values.items()})
    fields = attr.fields(Q)
    assert len(fields) == len(values)

    signals = epyqlib.utils.qt.pyqtify_signals(p)
    for name, v in values.items():
        getattr(signals, name).connect(v.collect)

    for name, v in values.items():
        for value in v.input:
            setattr(p, name, value)

    for name, v in values.items():
        assert tuple(v.expected) == tuple(v.collected)

    assert_attrs_as_expected(p, values)


def test_pyqtified_name():
    assert Q.__name__ == 'Q'


def test_pyqtified_module():
    class C:
        pass

    assert Q.__module__ == C.__module__


def test_(qtbot):
    q = Q(a=1, b=2)

    signals = epyqlib.utils.qt.pyqtify_signals(q)

    # TODO: Actually assert they are 'the same'.  Until we know how to
    #       just access them to make sure they are available
    signals._pyqtify_signal_a
    signals.a
    signals['a']


def test_resolve_index_to_model():
    model = PyQt5.QtCore.QStringListModel()

    back_proxy = PyQt5.QtCore.QSortFilterProxyModel()
    back_proxy.setSourceModel(model)

    middle_proxy = PyQt5.QtCore.QSortFilterProxyModel()
    middle_proxy.setSourceModel(back_proxy)

    proxy = PyQt5.QtCore.QSortFilterProxyModel()
    proxy.setSourceModel(middle_proxy)

    view = PyQt5.QtWidgets.QListView()
    view.setModel(proxy)

    assert (
        epyqlib.utils.qt.resolve_models(model=view.model())
        == [proxy, middle_proxy, back_proxy, model]
    )

    strings = ['a', 'b', 'c']
    model.setStringList(strings)
    assert model.rowCount() == 3
    assert model.stringList() == strings

    proxy_first_index = proxy.index(0, 0, PyQt5.QtCore.QModelIndex())

    model_first_index = model.index(0, 0, PyQt5.QtCore.QModelIndex())

    target_data = model.data(model_first_index, PyQt5.QtCore.Qt.DisplayRole)

    assert target_data == 'a'

    with pytest.raises(epyqlib.utils.qt.TargetModelNotReached):
        epyqlib.utils.qt.resolve_index_to_model(
            index=proxy_first_index,
            target=object(),
        )

    index = epyqlib.utils.qt.resolve_index_to_model(
        index=proxy_first_index,
    )

    found_data = model.data(index, PyQt5.QtCore.Qt.DisplayRole)

    assert found_data == target_data
    assert index.model() == model

    proxy_index = epyqlib.utils.qt.resolve_index_from_model(
        model=model,
        view=view,
        index=model_first_index,
    )

    assert (
        proxy.data(proxy_index, PyQt5.QtCore.Qt.DisplayRole)
        == model.data(model_first_index, PyQt5.QtCore.Qt.DisplayRole)
    )


def test_attrs_no_recurse_in_init():
    @epyqlib.utils.qt.pyqtify()
    @attr.s
    class Child:
        a = attr.ib(default=42)

    @epyqlib.utils.qt.pyqtify()
    @attr.s
    class Parent:
        child = attr.ib(default=attr.Factory(Child))

    p = Parent()

    assert p.child == Child()


def test_signal_independence():
    class C:
        a = epyqlib.utils.qt.Signal(int)
        b = epyqlib.utils.qt.Signal(int)

    value_checkers = {
        'a': epyqlib.tests.common.Values(
            initial=None,
            input=[1, 2, 3],
            expected=[1, 2, 3],
        ),
        'b': epyqlib.tests.common.Values(
            initial=None,
            input=[10, 20, 30],
            expected=[10, 20, 30],
        ),
    }

    c = C()
    for name, checker in value_checkers.items():
        getattr(c, name).connect(checker.collect)

    for name, checker in value_checkers.items():
        for value in checker.input:
            getattr(c, name).emit(value)

    for name, checker in value_checkers.items():
        assert tuple(checker.expected) == tuple(checker.collected)


def test_signal_chaining():
    class C:
        a = epyqlib.utils.qt.Signal(int)
        b = epyqlib.utils.qt.Signal(int)

    input = [1, 2, 3]

    value_checkers = {
        'a': epyqlib.tests.common.Values(
            initial=None,
            input=input,
            expected=input,
        ),
        'b': epyqlib.tests.common.Values(
            initial=None,
            input=None,
            expected=input,
        ),
    }

    c = C()
    c.a.connect(c.b)

    for name, checker in value_checkers.items():
        getattr(c, name).connect(checker.collect)

    for value in value_checkers['a'].input:
        c.a.emit(value)

    for name, checker in value_checkers.items():
        assert tuple(checker.expected) == tuple(checker.collected)


def test_signal_to_pyqtslot():
    class Signal:
        signal = epyqlib.utils.qt.Signal()

    class Slot(PyQt5.QtCore.QObject):
        @PyQt5.QtCore.pyqtSlot()
        def slot(self):
            pass

    s = Signal()
    q = Slot()

    s.signal.connect(q.slot)


# def test_signal_repr():
#     class C:
#         signal = epyqlib.utils.qt.Signal()
#
#     c = C()
#
#     expected = (
#         '<bound PYQT_SIGNAL signal of _SignalQObject object at 0x'
#         ' of C object at 0x'
#     )
#
#     actual = repr(c.signal)
#     print(actual)
#     actual = actual.split()
#
#     for index in (-1, -6):
#         actual[index] = actual[index][:2]
#
#     actual = ' '.join(actual)
#
#     assert actual == expected


@attr.s(slots=True)
class DiffProxy:
    model = attr.ib()
    proxy = attr.ib()

    def visit_all(self, visitor):
        for row in range(self.proxy.rowCount()):
            for column in range(self.proxy.columnCount()):
                visitor(row, column)

    def lists(self, fill=None):
        return [
            [fill for _ in range(self.proxy.rowCount())]
            for _ in range(self.proxy.columnCount())
        ]

    def role_lists(self, fill=None):
        return {
            role: self.lists(fill=fill)
            for role in self.roles()
        }

    def roles(self):
        return {*self.proxy.diff_highlights, *self.proxy.reference_highlights}

    def collect(self):
        results = {
            self.proxy.diff_role: self.lists(),
            **{
                role: self.lists()
                for role in self.roles()
            },
        }

        def collect(row, column, collected=results):
            for role, lists in collected.items():
                index = self.proxy.index(
                    row,
                    column,
                    PyQt5.QtCore.QModelIndex(),
                )

                lists[row][column] = self.proxy.data(index, role)

        self.visit_all(visitor=collect)

        return results


@pytest.fixture
def diff_proxy_test_model():
    rows = 4
    columns = 4

    model = PyQt5.QtGui.QStandardItemModel(rows, columns)

    for row in range(rows):
        for column in range(columns):
            model.setItem(row, column, PyQt5.QtGui.QStandardItem())

    proxy = epyqlib.utils.qt.DiffProxyModel(
        columns=range(1, rows),
        diff_highlights={
            PyQt5.QtCore.Qt.ItemDataRole.BackgroundRole: (
                PyQt5.QtGui.QColor('orange')
            )
        },
        reference_highlights={
            PyQt5.QtCore.Qt.ItemDataRole.BackgroundRole: (
                PyQt5.QtGui.QColor('green')
            )
        },
    )
    proxy.setSourceModel(model)

    return DiffProxy(model=model, proxy=proxy)


def test_diffproxymodel_no_reference_column(diff_proxy_test_model):
    diff_proxy_test_model.proxy.reference_column = None

    results = diff_proxy_test_model.collect()
    results = {
        role: results[role]
        for role in diff_proxy_test_model.proxy.diff_highlights
    }

    expected = diff_proxy_test_model.role_lists()

    assert expected == results


def test_diffproxymodel_some_differences(diff_proxy_test_model):
    reference_column = 2
    root = diff_proxy_test_model.model.invisibleRootItem()
    rows = root.rowCount()
    columns = root.columnCount()

    for row in range(rows):
        for column in range(columns):
            root.child(row, column).setData(row)

    diff = {
        (2, 1): 42,
        (3, 3): 42,
    }

    expected = diff_proxy_test_model.role_lists()

    for (row, column), value in diff.items():
        item = root.child(row, column)
        item.setData(
            value,
            diff_proxy_test_model.proxy.diff_role,
        )

        diff_highlights = diff_proxy_test_model.proxy.diff_highlights.items()
        for role, highlight in diff_highlights:
            expected[role][row][column] = highlight

    reference_highlights = (
        diff_proxy_test_model.proxy.reference_highlights.items()
    )
    for row in range(rows):
        for role, highlight in reference_highlights:
            expected[role][row][reference_column] = highlight

    diff_proxy_test_model.proxy.reference_column = reference_column

    results = diff_proxy_test_model.collect()
    results = {
        role: results[role]
        for role in diff_proxy_test_model.proxy.diff_highlights
    }

    assert expected == results


@attr.s(slots=True)
class ChangedData:
    start = attr.ib()
    end = attr.ib()
    roles = attr.ib()


@attr.s(slots=True)
class DataChanges:
    # waiting on https://github.com/python-attrs/attrs/pull/420
    __weakref__ = attr.ib(
        repr=False,
        cmp=False,
        hash=False,
        init=False,
    )
    changes = attr.ib(factory=list)

    def collect(self, start, end, roles):
        self.changes.append(ChangedData(
            start=start,
            end=end,
            roles=roles,
        ))

    def results(self, container):
        for changed_data in self.changes:
            start = changed_data.start
            end = changed_data.end

            for row in range(start.row(), end.row() + 1):
                for column in range(start.column(), end.column() + 1):
                    for role in changed_data.roles:
                        if role in container:
                            container[role][row][column] = True

        return container


def test_diffproxymodel_all_changed(diff_proxy_test_model):
    changes = DataChanges()

    diff_proxy_test_model.proxy.dataChanged.connect(changes.collect)
    diff_proxy_test_model.proxy.all_changed()

    expected = diff_proxy_test_model.role_lists(fill=False)

    root = diff_proxy_test_model.model.invisibleRootItem()

    for role in diff_proxy_test_model.proxy.diff_highlights:
        for row in range(root.rowCount()):
            for column in diff_proxy_test_model.proxy.columns:
                expected[role][row][column] = True

    assert expected == changes.results(
        container=diff_proxy_test_model.role_lists(fill=False),
    )


def test_diffproxymodel_edit_reference_emits(diff_proxy_test_model):
    diff_proxy_test_model.proxy.reference_column = 2
    changes = DataChanges()

    proxy = diff_proxy_test_model.proxy
    proxy.dataChanged.connect(changes.collect)
    row = 0
    assert proxy.setData(
        index=proxy.index(row, proxy.reference_column),
        value=42,
        role=proxy.diff_role,
    )

    expected = diff_proxy_test_model.role_lists(fill=False)
    for role in proxy.diff_highlights:
        for column in proxy.columns:
            expected[role][row][column] = True

    assert expected == changes.results(
        container=diff_proxy_test_model.role_lists(fill=False),
    )


def test_diffproxymodel_edit_nonreference_emits(diff_proxy_test_model):
    diff_proxy_test_model.proxy.reference_column = 2
    edit_column = 1
    changes = DataChanges()

    proxy = diff_proxy_test_model.proxy
    proxy.dataChanged.connect(changes.collect)
    row = 0
    assert proxy.setData(
        index=proxy.index(row, edit_column),
        value=42,
        role=proxy.diff_role,
    )

    expected = diff_proxy_test_model.role_lists(fill=False)
    for role in proxy.diff_highlights:
        expected[role][row][edit_column] = True

    assert expected == changes.results(
        container=diff_proxy_test_model.role_lists(fill=False),
    )
