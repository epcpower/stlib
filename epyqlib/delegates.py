import weakref

import attr
from PyQt5.QtCore import pyqtSlot, Qt, QCoreApplication, QEvent, QPoint
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QMouseEvent

import epyqlib.utils.qt


class Dispatch(QtWidgets.QStyledItemDelegate):
    def __init__(self, selector, parent):
        super().__init__(parent)

        self.selector = selector
        self.delegates = set()

        self.delegates_by_editor = weakref.WeakKeyDictionary()

    def createEditor(self, parent, option, index):
        delegate = self.selector(index)

        if delegate not in self.delegates:
            self.delegates.add(delegate)
            delegate.closeEditor.connect(self.closeEditor)
            delegate.commitData.connect(self.commitData)

        editor = delegate.createEditor(parent, option, index)

        self.delegates_by_editor[editor] = delegate

        return editor

    def destroyEditor(self, editor, *args, **kwargs):
        delegate = self.delegates_by_editor[editor]
        return delegate.destroyEditor(editor, *args, **kwargs)

    def setEditorData(self, editor, *args, **kwargs):
        delegate = self.delegates_by_editor[editor]
        return delegate.setEditorData(editor, *args, **kwargs)

    def setModelData(self, editor, *args, **kwargs):
        delegate = self.delegates_by_editor[editor]
        return delegate.setModelData(editor, *args, **kwargs)

    def updateEditorGeometry(self, editor, *args, **kwargs):
        delegate = self.delegates_by_editor[editor]
        return delegate.updateEditorGeometry(editor, *args, **kwargs)


def default(model, node, column):
    if hasattr(node, 'enumeration_strings'):
        if len(node.enumeration_strings()) > 0:
            return Delegate(creator=create_combo)

    if hasattr(node, 'secret'):
        if node.secret:
            return Delegate(modifier=modify_password)

    return Delegate()


@attr.s
class Delegate:
    creator = attr.ib(default=None)
    modifier = attr.ib(default=None)
    editor_setter = attr.ib(default=None)
    model_setter = attr.ib(default=None)


# TODO: CAMPid 374895478431714307074310
class CustomCombo(QtWidgets.QComboBox):
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


class ByFunction(QtWidgets.QStyledItemDelegate):
    def __init__(self, model, parent, function=default):
        QtWidgets.QStyledItemDelegate.__init__(self, parent=parent)

        self.model = model
        self.function = function

    def get_delegate_node(self, index):
        index = epyqlib.utils.qt.resolve_index_to_model(index)
        # TODO: way too particular
        node = self.model.node_from_index(index)

        delegate = self.function(
            model=self.model,
            node=node,
            column=index.column(),
        )

        return delegate, node

    def createEditor(self, parent, option, index):
        delegate, node = self.get_delegate_node(index=index)

        if delegate.creator is None:
            widget = super().createEditor(parent, option, index)
        else:
            widget = delegate.creator(index=index, node=node, parent=parent)

        if delegate.modifier is not None:
            delegate.modifier(widget=widget)

        return widget

    # def setEditorData(self, editor, index):
    #     delegate, node = self.get_delegate_node(index=index)
    #
    #     if delegate.editor_setter is None:
    #         return super().setEditorData(editor, index)
    #
    #     return delegate.editor_setter(editor=editor, index=index)

    def setModelData(self, editor, model, index):
        delegate, node = self.get_delegate_node(index=index)

        if delegate.model_setter is None:
            return super().setModelData(editor, model, index)

        return delegate.model_setter(
            editor=editor,
            model=model,
            index=index,
        )


def create_combo(index, node, parent):
    widget = CustomCombo(parent=parent)

    # TODO: use the userdata to make it easier to get in and out
    widget.addItems(node.enumeration_strings(include_values=True))

    present_string = str(node.fields[index.column()])
    index = widget.findText(present_string)
    if index == -1:
        widget.setCurrentIndex(0)
    else:
        widget.setCurrentIndex(index)

    view = widget.view()
    view.setMinimumWidth(calculate_combo_view_width(widget))

    event = QMouseEvent(QEvent.MouseButtonPress,
                        QPoint(),
                        Qt.LeftButton,
                        Qt.LeftButton,
                        Qt.NoModifier)
    QCoreApplication.postEvent(widget, event)

    return widget


def calculate_combo_view_width(widget):
    view = widget.view()
    metric = view.fontMetrics()
    scrollbar = view.verticalScrollBar()

    scrollbar_width = 0
    if scrollbar.isVisibleTo(view):
        scrollbar_width = scrollbar.width()

    text = (widget.itemText(i) for i in range(widget.count()))
    text_width = max(metric.width(s) for s in text)

    # consider width of icons, for example

    return text_width + scrollbar_width


def create_button(index, node, parent):
    text = node.button_text(index.column())
    widget = QtWidgets.QPushButton(parent=parent)
    widget.setText(text)

    return widget


def modify_password(widget):
    widget.setEchoMode(QtWidgets.QLineEdit.Password)
