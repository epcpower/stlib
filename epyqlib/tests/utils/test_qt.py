import inspect
import itertools

import attr
import pytest
import PyQt5.QtCore

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
        epyqlib.utils.qt.resolve_models(view)
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
            view=view,
            index=proxy_first_index,
            target=object(),
        )

    index, found_model = epyqlib.utils.qt.resolve_index_to_model(
        view=view,
        index=proxy_first_index,
    )

    found_data = model.data(index, PyQt5.QtCore.Qt.DisplayRole)

    assert found_data == target_data
    assert found_model == model

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
