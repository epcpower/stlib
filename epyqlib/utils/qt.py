import enum
import functools
import io
import os
import signal
import sys
import textwrap
import time
import traceback
import uuid
import weakref

import epyqlib.utils.general

import attr
from PyQt5 import QtCore
from PyQt5 import QtWidgets
import PyQt5.uic
import twisted.internet.defer

__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


# TODO: CAMPid 953295425421677545429542967596754
log = os.path.join(os.getcwd(), 'epyq.log')


_version_tag = None
_build_tag = None
_parent = None


def exception_message_box_register_versions(version_tag, build_tag):
    global _version_tag
    global _build_tag

    _version_tag = version_tag
    _build_tag = build_tag


def exception_message_box_register_parent(parent):
    global _parent

    _parent = parent


def exception_message_box(excType=None, excValue=None, tracebackobj=None):
    epyqlib.utils.general.exception_logger(excType, excValue, tracebackobj)

    def join(iterable):
        return ''.join(iterable).strip()

    expected = isinstance(excValue, epyqlib.utils.general.ExpectedException)

    if expected:
        brief = excValue.expected_message()
    else:
        brief = join(traceback.format_exception_only(
            etype=excType,
            value=excValue
        ))

    extended = join(traceback.format_exception(
        etype=excType,
        value=excValue,
        tb=tracebackobj,
    ))

    if expected:
        box = raw_exception_message_box
    else:
        box = custom_exception_message_box

    box(
        brief=brief,
        extended=extended,
        stderr=False,
    )


def custom_exception_message_box(brief, extended='', **kwargs):
    email = "kyle.altendorf@epcpower.com"

    brief = textwrap.dedent('''\
        An unhandled exception occurred. Please report the problem via email to:
                        {email}

        {brief}''').format(
        email=email,
        brief=brief,
    )

    raw_exception_message_box(brief=brief, extended=extended, **kwargs)


def raw_exception_message_box(brief, extended, stderr=True):
    version = ''
    if _version_tag is not None:
        version = 'Version Tag: {}'.format(_version_tag)

    build = ''
    if _build_tag is not None:
        build = 'Build Tag: {}'.format(_build_tag)

    info = (version, build)
    info = '\n'.join(s for s in info if len(s) > 0)
    if len(info) > 0:
        info += '\n\n'

    time_string = time.strftime("%Y-%m-%d, %H:%M:%S %Z")

    details = textwrap.dedent('''\
        {info}A log has been written to "{log}".
        {time_string}''').format(
        info=info,
        log=log,
        time_string=time_string,
    )

    if len(extended) > 0:
        details = '\n'.join(s.strip() for s in (details, '-' * 70, extended))

    if stderr:
        sys.stderr.write('\n'.join((brief, details, '')))

    dialog(
        parent=_parent,
        title='Exception',
        message=brief,
        details=details,
        icon=QtWidgets.QMessageBox.Critical,
    )


# http://stackoverflow.com/a/35902894/228539
def message_handler(mode, context, message):
    mode_strings = {
        QtCore.QtInfoMsg: 'INFO',
        QtCore.QtWarningMsg: 'WARNING',
        QtCore.QtCriticalMsg: 'CRITICAL',
        QtCore.QtFatalMsg: 'FATAL'
    }

    mode = mode_strings.get(mode, 'DEBUG')

    print('qt_message_handler: f:{file} l:{line} f():{function}'.format(
        file=context.file,
        line=context.line,
        function=context.function
    ))
    print('  {}: {}\n'.format(mode, message))


class Progress(QtCore.QObject):
    # TODO: CAMPid 7531968542136967546542452
    updated = QtCore.pyqtSignal(int)
    completed = QtCore.pyqtSignal()
    done = QtCore.pyqtSignal()
    failed = QtCore.pyqtSignal()
    canceled = QtCore.pyqtSignal()

    default_progress_label = (
        '{elapsed} seconds elapsed, {remaining} seconds remaining'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.completed.connect(self.done)
        self.failed.connect(self.done)
        self.canceled.connect(self.done)

        self.done.connect(self._done)

        self.progress = None
        self.average = None
        self.average_timer = QtCore.QTimer()
        self.average_timer.setInterval(200)
        self.average_timer.timeout.connect(self._update_time_estimate)
        self._label_text_replace = None
        self._start_time = None

    def _done(self):
        self.average_timer.stop()
        self.average = None

        self.updated.disconnect(self.progress.setValue)
        self.progress.close()
        self.progress.deleteLater()
        self.progress = None

        self._start_time = None

    def _update_time_estimate(self):
        remaining = self.average.remaining_time(self.progress.maximum())
        try:
            remaining = round(remaining)
        except:
            pass
        self.progress.setLabelText(self._label_text_replace.format(
                elapsed=round(time.monotonic() - self._start_time),
                remaining=remaining
            )
        )

    def connect(self, progress, label_text=None):
        self.progress = progress

        if label_text is None:
            label_text = self.default_progress_label
        self._label_text_replace = label_text

        self.progress.setMinimumDuration(0)
        self.progress.setValue(0)
        # Default to a busy indicator, progress maximum can be set later
        self.progress.setMinimum(0)
        self.progress.setMaximum(0)
        self.updated.connect(self.progress.setValue)

        if self._start_time is None:
            self._start_time = time.monotonic()

        self.average = epyqlib.utils.general.AverageValueRate(seconds=30)
        self.average_timer.start()

    def configure(self, minimum=0, maximum=0):
        self.progress.setMinimum(minimum)
        self.progress.setMaximum(maximum)

    def complete(self, message=None):
        if message is not None:
            QtWidgets.QMessageBox.information(self.progress, 'EPyQ', message)

        self.completed.emit()

    def elapsed(self):
        return time.monotonic() - self._start_time

    def fail(self):
        self.failed.emit()

    def update(self, value):
        self.average.add(value)
        self.updated.emit(value)


def complete_filter_type(extension):
    if extension == '*':
        return extension

    return '*.' + extension

def create_filter_string(name, extensions):
    return '{} ({})'.format(
        name,
        ' '.join((complete_filter_type(e) for e in extensions)),
     )


def file_dialog(
        filters,
        default=0,
        save=False,
        multiple=False,
        caption='',
        parent=None,
        path_factory=str,
        **kwargs,
):
    # TODO: CAMPid 9857216134675885472598426718023132
    # filters = [
    #     ('EPC Packages', ['epc', 'epz']),
    #     ('All Files', ['*'])
    # ]
    # TODO: CAMPid 97456612391231265743713479129

    if save:
        multiple = False

    filter_strings = [create_filter_string(f[0], f[1]) for f in filters]
    filter_string = ';;'.join(filter_strings)

    if save:
        dialog = QtWidgets.QFileDialog.getSaveFileName
    elif multiple:
        dialog = QtWidgets.QFileDialog.getOpenFileNames
    else:
        dialog = QtWidgets.QFileDialog.getOpenFileName

    if 'dir' in kwargs:
        kwargs['directory'] = kwargs.pop('dir')

    selected = dialog(
        parent=parent,
        filter=filter_string,
        initialFilter=filter_strings[default],
        caption=caption,
        **kwargs
    )[0]

    if multiple:
        return [path_factory(path) for path in selected]

    if len(selected) == 0:
        return None

    return path_factory(selected)


def get_code():
    code = None

    code_file = QtCore.QFile(':/code')
    if code_file.open(QtCore.QIODevice.ReadOnly):
        code = bytes(code_file.readAll())
        code = code.decode('ascii').strip().encode('ascii')
        code_file.close()

    return code


def progress_dialog(parent=None, cancellable=False):
    progress = QtWidgets.QProgressDialog(parent)
    flags = progress.windowFlags()
    flags &= ~QtCore.Qt.WindowContextHelpButtonHint
    flags &= ~QtCore.Qt.WindowCloseButtonHint
    progress.setWindowFlags(flags)
    progress.setWindowModality(QtCore.Qt.WindowModal)
    progress.setAutoReset(False)
    if not cancellable:
        progress.setCancelButton(None)
    progress.setMinimumDuration(0)
    progress.setMinimum(0)
    progress.setMaximum(0)

    return progress


class FittedTextBrowser(QtWidgets.QTextBrowser):
    def sizeHint(self):
        default = super().sizeHint()

        if not default.isValid():
            return default

        document_size = self.document().size()

        desktops = QtWidgets.QApplication.desktop()
        screen_number = desktops.screenNumber(self.parent())
        geometry = desktops.screenGeometry(screen_number)

        if document_size.width() == 0:
            document_size.setWidth(geometry.width() * 0.25)
        if document_size.height() == 0:
            document_size.setHeight(geometry.height() * 0.4)

        scrollbar_width = QtWidgets.QApplication.style().pixelMetric(
            QtWidgets.QStyle.PM_ScrollBarExtent
        )

        width = sum((
            document_size.width(),
            self.contentsMargins().left(),
            self.contentsMargins().right(),
            scrollbar_width,
        ))

        height = sum((
            document_size.height(),
            self.contentsMargins().top(),
            self.contentsMargins().bottom(),
            scrollbar_width,
        ))

        return QtCore.QSize(width, height)


class DialogUi:
    def __init__(self, parent):
        self.layout = QtWidgets.QGridLayout(parent)
        self.icon = QtWidgets.QLabel(parent)
        self.message = FittedTextBrowser(parent)
        self.details = FittedTextBrowser(parent)
        self.copy = QtWidgets.QPushButton(parent)
        self.save = QtWidgets.QPushButton(parent)
        self.show_details = QtWidgets.QPushButton(parent)
        self.buttons = QtWidgets.QDialogButtonBox(parent)

        self.copy.setText('To Clipboard')
        self.save.setText('To File')
        self.show_details.setText('Details...')

        self.layout.addWidget(self.icon, 0, 0, 2, 1)
        self.layout.addWidget(self.message, 0, 1, 1, 4)
        self.layout.addWidget(self.details, 1, 1, 1, 4)
        self.layout.addWidget(self.copy, 2, 1)
        self.layout.addWidget(self.save, 2, 2)
        self.layout.addWidget(self.show_details, 2, 3)
        self.layout.addWidget(self.buttons, 2, 4)

        self.layout.setColumnStretch(4, 1)


class Dialog(QtWidgets.QDialog):
    def __init__(self, *args, cancellable=False, details=False,
                 save_filters=None, save_caption=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.save_filters = save_filters
        if self.save_filters is None:
            self.save_filters = (
                ('Text', ['txt']),
                ('All Files', ['*'])
            )

        self.save_caption = save_caption

        self.ui = DialogUi(parent=self)

        self.ui.details.setVisible(False)
        self.ui.show_details.setVisible(details)

        self.ui.buttons.accepted.connect(self.accept)
        self.ui.buttons.rejected.connect(self.reject)

        self.ui.copy.clicked.connect(self.copy)
        self.ui.save.clicked.connect(self.save)
        self.ui.show_details.clicked.connect(self.show_details)

        self.setLayout(self.ui.layout)
        buttons = QtWidgets.QDialogButtonBox.Ok
        if cancellable:
            buttons |= QtWidgets.QDialogButtonBox.Cancel

        self.ui.buttons.setStandardButtons(buttons)

        self.text = None
        self.html = None
        self.details_text = None
        self.details_html = None

        desktops = QtWidgets.QApplication.desktop()
        screen_number = desktops.screenNumber(self.parent())
        geometry = desktops.screenGeometry(screen_number)

        self.setMaximumHeight(geometry.height() * 0.7)
        self.setMaximumWidth(geometry.width() * 0.7)
        self.minimum_size = self.minimumSize()
        self.maximum_size = self.maximumSize()

    def all_as_text(self):
        message = self.ui.message.toPlainText().strip()
        details = self.ui.details.toPlainText().strip()

        if len(details) == 0:
            return message + '\n'

        return textwrap.dedent('''\
            {message}

             - - - - Details:

            {details}
            '''
                            ).format(
            message=message,
            details=details,
        )

    def copy(self):
        QtWidgets.QApplication.clipboard().setText(self.all_as_text())

    def save(self):
        extras = {}
        if self.save_caption is not None:
            extras['caption'] = self.save_caption

        path = epyqlib.utils.qt.file_dialog(
            filters=self.save_filters,
            parent=self,
            save=True,
            **extras,
        )

        if path is None:
            return

        with open(path, 'w') as f:
            f.write(self.all_as_text())

    def show_details(self):
        to_be_visible = not self.ui.details.isVisible()
        self.ui.details.setVisible(to_be_visible)
        self.set_size()

    def set_size(self):
        self.setFixedSize(self.sizeHint())
        self.setMinimumSize(self.minimum_size)
        self.setMaximumSize(self.maximum_size)

    def set_text(self, text):
        self.ui.message.setPlainText(text)

        self.html = None
        self.text = text

        self.ui.message.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)

    def set_html(self, html):
        self.ui.message.setHtml(html)

        self.html = html
        self.text = None

        self.ui.message.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)

    def set_details_text(self, text):
        self.ui.details.setPlainText(text)

        self.details_html = None
        self.details_text = text

        self.ui.details.setLineWrapMode(QtWidgets.QTextEdit.NoWrap)

    def set_details_html(self, html):
        self.ui.details.setHtml(html)

        self.details_html = html
        self.details_text = None

        self.ui.details.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)

    def set_message_box_icon(self, icon):
        self.ui.icon.setPixmap(QtWidgets.QMessageBox.standardIcon(icon))


def dialog(parent, message, title=None, icon=None,
           rich_text=False, details='', details_rich_text=False,
           cancellable=False, modal=True, **kwargs):
    box = Dialog(
        parent=parent,
        cancellable=cancellable,
        details=len(details) > 0,
        **kwargs,
    )

    box.setModal(modal)

    if rich_text:
        box.set_html(message)
    else:
        box.set_text(message)

    if details_rich_text:
        box.set_details_html(details)
    else:
        box.set_details_text(details)

    if icon is not None:
        box.set_message_box_icon(icon)

    if title is not None:
        parent_title = QtWidgets.QApplication.instance().applicationName()

        if len(parent_title) > 0:
            title = ' - '.join((
                parent_title,
                title,
            ))


        box.setWindowTitle(title)

    box.finished.connect(box.deleteLater)

    if modal:
        return box.exec()

    box.show()
    return


def dialog_from_file(parent, title, file_name):
    # The Qt Installer Framework (QtIFW) likes to do a few things to license files...
    #  * '\n' -> '\r\n'
    #   * even such that '\r\n' -> '\r\r\n'
    #  * Recodes to something else (probably cp-1251)
    #
    # So, we'll just try different encodings and hope one of them works.

    encodings = [None, 'utf-8']

    for encoding in encodings:
        try:
            with open(os.path.join('Licenses', file_name), encoding=encoding) as in_file:
                message = in_file.read()
        except UnicodeDecodeError:
            pass
        else:
            break

    dialog(
        parent=parent,
        title=title,
        message=message,
    )


class PySortFilterProxyModel(QtCore.QSortFilterProxyModel):
    def __init__(self, *args, filter_column, **kwargs):
        super().__init__(*args, **kwargs)

        # TODO: replace with filterKeyColumn
        self.filter_column = filter_column

        self.wildcard = QtCore.QRegExp()
        self.wildcard.setPatternSyntax(QtCore.QRegExp.Wildcard)

    def lessThan(self, left, right):
        left_model = left.model()
        left_data = (
            left_model.data(left, self.sortRole())
            if left_model else
            None
        )

        right_model = right.model()
        right_data = (
            right_model.data(right, self.sortRole())
            if right_model else
            None
        )

        return left_data < right_data

    def filterAcceptsRow(self, row, parent):
        # TODO: do i need to invalidate any time i set the 'regexp'?
        # http://doc.qt.io/qt-5/qsortfilterproxymodel.html#invalidateFilter

        pattern = self.filterRegExp().pattern()
        if pattern == '':
            return True

        pattern = '*{}*'.format(pattern)

        model = self.sourceModel()
        result = False
        index = model.index(row, self.filter_column, parent)
        self_index = self.index(row, self.filter_column, parent)
        result |= self.hasChildren(self_index)
        self.wildcard.setPattern(pattern)
        result |= self.wildcard.exactMatch(model.data(index, QtCore.Qt.DisplayRole))

        return result

    def next_row(self, index):
        return self.sibling(
            index.row() + 1,
            index.column(),
            index,
        )

    def next_index(self, index, allow_children=True):
        if allow_children and self.hasChildren(index):
            return self.index(0, index.column(), index), False

        next_ = self.next_row(index)
        if not next_.isValid():
            while True:
                index = index.parent()
                if not index.isValid():
                    return self.index(0, 0, QtCore.QModelIndex()), True

                next_ = self.next_row(index)
                if next_.isValid():
                    break

        return next_, False

    def search(self, text, search_from, column):
        def set_row_column(index, row=None, column=None):
            if row is None:
                row = index.row()

            if column is None:
                column = index.column()

            return self.index(
                row,
                column,
                index.parent(),
            )

        if text == '':
            return None

        text = '*{}*'.format(text)

        flags = (
            QtCore.Qt.MatchContains
            | QtCore.Qt.MatchRecursive
            | QtCore.Qt.MatchWildcard
        )

        wrapped = False

        if search_from.isValid():
            search_from, wrapped = self.next_index(search_from)
        else:
            search_from = self.index(0, 0, QtCore.QModelIndex())

        while True:
            next_indexes = self.match(
                set_row_column(index=search_from, column=column),
                QtCore.Qt.DisplayRole,
                text,
                1,
                flags,
            )

            if len(next_indexes) > 0:
                next_index, = next_indexes

                if not next_index.isValid():
                    break

                return next_index
            elif wrapped:
                break

            search_from, wrapped = self.next_index(search_from)

        # TODO: report not found and/or wrap
        print('reached end')
        return None


@attr.s
class DiffProxyModel(QtCore.QIdentityProxyModel):
    parent = attr.ib(default=None)
    columns = attr.ib(factory=set, converter=set)
    _reference_column = attr.ib(default=None)
    diff_highlights = attr.ib(factory=dict)
    reference_highlights = attr.ib(factory=dict)
    diff_role = attr.ib(default=QtCore.Qt.ItemDataRole.DisplayRole)

    def __attrs_post_init__(self):
        super().__init__(self.parent)

    def data(self, index, role):
        column = index.column()

        if self.reference_column is not None:
            if (
                column == self.reference_column
                and role in self.reference_highlights
            ):
                return self.reference_highlights[role]
            elif (
                column != self.reference_column
                and role in self.diff_highlights
                and column in self.columns
            ):
                this_value = super().data(
                    index,
                    self.diff_role,
                )
                that_value = super().data(
                    index.siblingAtColumn(self.reference_column),
                    self.diff_role,
                )

                if this_value != that_value:
                    return self.diff_highlights[role]

        return super().data(index, role)

    @property
    def reference_column(self):
        return self._reference_column

    @reference_column.setter
    def reference_column(self, column):
        self._reference_column = column
        self.all_changed()

    def column_group_limits(self):
        return [
            (group[0], group[-1])
            for group in epyqlib.utils.general.contiguous_groups(
                sorted(self.columns),
            )
        ]

    def roles(self):
        return {*self.diff_highlights, *self.reference_highlights}

    def all_changed(self):
        indexes = [QtCore.QModelIndex()]

        while len(indexes) > 0:
            parent = indexes.pop()
            if self.hasChildren(parent):
                row_count = self.rowCount(parent)

                indexes.extend([
                    self.index(row, 0, parent)
                    for row in range(row_count)
                ])

                for start, end in self.column_group_limits():
                    self.dataChanged.emit(
                        self.index(0, start, parent),
                        self.index(row_count - 1, end, parent),
                        self.roles(),
                    )

    def setData(self, index, value, role):
        changed = super().setData(index, value)

        if changed and role == self.diff_role:
            column = index.column()
            if column == self.reference_column:
                for start, end in self.column_group_limits():
                    self.dataChanged.emit(
                        index.siblingAtColumn(start),
                        index.siblingAtColumn(end),
                        self.diff_highlights,
                    )
            elif column in self.columns:
                self.dataChanged.emit(index, index, self.diff_highlights)

        return changed


def load_ui(filepath, base_instance):
    # TODO: CAMPid 9549757292917394095482739548437597676742
    ui_file = QtCore.QFile(filepath)
    ui_file.open(QtCore.QFile.ReadOnly | QtCore.QFile.Text)
    ts = QtCore.QTextStream(ui_file)
    sio = io.StringIO(ts.readAll())

    return PyQt5.uic.loadUi(sio, base_instance)


def search_view(view, text, column):
    if text == '':
        return

    model = view.model()

    models = []

    while model is not None:
        models.append(model)
        search = getattr(model, 'search', None)
        if search is not None:
            break

        model = model.sourceModel()
    else:
        raise Exception('ack')

    index = search(
        text=text,
        column=column,
        search_from=view.currentIndex(),
    )

    if index is not None:
        parent = index.parent()
        # TODO: not sure why but this must be set to zero or the row
        #       won't be highlighted.  it still gets expanded and printing
        #       the display role data still works.
        parent = model.index(parent.row(), 0, parent.parent())
        index = model.index(index.row(), index.column(), parent)

        for model in reversed(models[:-1]):
            index = model.mapFromSource(index)

        view.setCurrentIndex(index)
        view.selectionModel().select(
            index,
            QtCore.QItemSelectionModel.ClearAndSelect,
        )


class NotAPyQtifyInstance(Exception):
    pass


def pyqtified(instance):
    return instance.__pyqtify_instance__


@attr.s
class PyQtifyInstance:
    display_name = attr.ib()
    values = attr.ib(default={})
    changed = attr.ib(default=None)

    @classmethod
    def fill(cls, display_name, attrs_class):
        return cls(
            display_name=display_name,
            values={
                field.name: None
                for field in attr.fields(attrs_class)
            },
        )


def pyqtify(name=None, property_decorator=lambda: property):
    def inner(cls):
        if name is None:
            display_name = cls.__name__
        else:
            display_name = name

        names = tuple(field.name for field in attr.fields(cls))

        def __getitem__(self, key):
            if key not in self.names:
                raise KeyError(key)

            return getattr(self, signal_name(key))

        def __getattr__(self, name):
            if name not in self.names:
                raise AttributeError(
                    "'{class_name}' object has no attribute '{name}'".format(
                        class_name=type(self).__name__,
                        attribute=name,
                    )
                )

            return getattr(self, signal_name(name))

        def signal_name(name):
            return '_pyqtify_signal_{}'.format(name)

        SignalContainer = type(
            'SignalContainer',
            (PyQt5.QtCore.QObject,),
            {
                'names': names,
                '__getattr__': __getattr__,
                '__getitem__': __getitem__,
                **{
                    signal_name(name): PyQt5.QtCore.pyqtSignal('PyQt_PyObject')
                    for name in names
                },
            },
        )

        old_init = cls.__init__

        def __init__(self, *args, **kwargs):
            self.__pyqtify_instance__ = PyQtifyInstance.fill(
                display_name=display_name,
                attrs_class=type(self),
            )

            self.__pyqtify_instance__.changed = SignalContainer()

            try:
                old_init(self, *args, **kwargs)
            except TypeError as e:
                raise TypeError(
                    '.'.join((
                        type(self).__module__,
                        type(self).__qualname__,
                        e.args[0],
                    )),
                ) from e

        cls.__init__ = __init__

        for name_ in names:
            property_ = getattr(cls, 'pyqtify_{}'.format(name_), None)

            if property_ is None:
                @property_decorator()
                def property_(self, name=name_):
                    return pyqtify_get(self, name)

                @property_.setter
                def property_(self, value, name=name_):
                    pyqtify_set(self, name, value)

            setattr(cls, name_, property_)

        return cls

    return inner


def pyqtify_get(instance, name):
    return instance.__pyqtify_instance__.values[name]


def pyqtify_set(instance, name, value):
    if value != instance.__pyqtify_instance__.values[name]:
        instance.__pyqtify_instance__.values[name] = value
        try:
            instance.__pyqtify_instance__.changed[name].emit(value)
        except RuntimeError:
            pass


def pyqtify_signals(instance):
    try:
        instance = instance.__pyqtify_instance__
    except AttributeError as e:
        raise NotAPyQtifyInstance from e

    return instance.changed


def pyqtify_passthrough_properties(original, field_names):
    def inner(cls):
        old_init = cls.__init__

        def __init__(self, *args, **kwargs):
            old_init(self, *args, **kwargs)

            original_object = getattr(self, original)
            signals = epyqlib.utils.qt.pyqtify_signals(self)

            def original_changed(new_original, self=self):
                # TODO: need to be disconnecting as well
                signals = epyqlib.utils.qt.pyqtify_signals(self)

                try:
                    new_original_signals = (
                        epyqlib.utils.qt.pyqtify_signals(new_original)
                    )
                except NotAPyQtifyInstance:
                    pass
                else:
                    for name in field_names:
                        new_original_signals[name].connect(signals[name])

            getattr(signals, original).connect(original_changed)
            original_changed(original_object)

        cls.__init__ = __init__

        for name in field_names:
            @property
            def property_(self, name=name):
                original_ = getattr(self, original)
                if original_ is None or isinstance(original_, uuid.UUID):
                    return pyqtify_get(self, name)

                return getattr(original_, name)

            @property_.setter
            def property_(self, value, name=name):
                original_ = getattr(self, original)
                if original_ is None:
                    pyqtify_set(self, name, value)
                else:
                    setattr(original_, name, value)

            setattr(cls, 'pyqtify_' + name, property_)

        return cls

    return inner


class TargetModelNotReached(Exception):
    pass


def resolve_models(model, target=None):
    sentinel = object()
    if target is None:
        target = sentinel

    models = [model]

    while isinstance(models[-1], PyQt5.QtCore.QAbstractProxyModel):
        models.append(models[-1].sourceModel())

        if models[-1] is target:
            break

    if target is not sentinel and models[-1] is not target:
        raise TargetModelNotReached()

    return models


def resolve_index_to_model(index, target=None):
    model = index.model()

    if model is target:
        return index

    model_pairs = epyqlib.utils.general.pairwise(
        resolve_models(model=model, target=target),
    )

    for first, second in model_pairs:
        index = first.mapToSource(index)

        if second is target:
            return index

    return index


def resolve_index_from_model(model, view, index):
    models = resolve_models(model=view.model(), target=model)

    for model in models[-2::-1]:
        index = model.mapFromSource(index)

    return index


def sigint_handler(signal_number, stack_frame):
    QtWidgets.QApplication.exit(128 + signal_number)


def setup_sigint():
    signal.signal(signal.SIGINT, sigint_handler)

    # Regularly give Python a chance to receive signals such as ctrl+c
    timer = QtCore.QTimer()
    timer.start(200)
    timer.timeout.connect(lambda: None)

    return timer


# class SignalWrapper(PyQt5.QtCore.pyqtBoundSignal):
#     def __init__(self, owner, wrapped):
#         self.wrapped = wrapped
#         self.owner = owner
#
#     def __getattribute__(self, item):
#         if item == '__repr__':
#             return super().__getattribute__(item)
#
#         wrapped = super().__getattribute__('wrapped')
#         return getattr(wrapped, item)
#
#     def __repr__(self):
#         owner = super().__getattribute__('owner')
#         wrapped = super().__getattribute__('wrapped')
#
#         return '<{} of {}>'.format(
#             repr(wrapped)[1:-1],
#             repr(owner).rsplit('.', 1)[1][:-1],
#         )
#
#
# def signal_repr(self):
#     owner = super().__getattribute__('owner')
#     wrapped = super().__getattribute__('wrapped')
#
#     return '<{} of {}>'.format(
#         repr(wrapped)[1:-1],
#         repr(owner).rsplit('.', 1)[1][:-1],
#     )


class Signal:
    attribute_name = None

    def __init__(self, *args, **kwargs):
        class _SignalQObject(QtCore.QObject):
            signal = QtCore.pyqtSignal(*args, **kwargs)

        self.object_cls = _SignalQObject

    def __get__(self, instance, owner):
        if instance is None:
            return self

        d = getattr(instance, self.attribute_name, None)

        if d is None:
            d = {}
            setattr(instance, self.attribute_name, d)

        o = d.get(self.object_cls)
        if o is None:
            o = self.object_cls()
            d[self.object_cls] = o

        signal = o.signal
        # signal.__repr__ = signal_repr
        # return SignalWrapper(owner=instance, wrapped=o.signal)
        return signal

    def qobject_host(self, instance):
        """Return the QObject which hosts the pyqtSignal on the passed instance.
                
        ``TheClass.the_signal.qobject_host(an_instance)`` will return the ``QObject``
        instance used to host the signal ``an_instance.the_signal``.
        """
        return getattr(instance, self.attribute_name)[self.object_cls]


Signal.attribute_name = epyqlib.utils.general.identifier_path(Signal)


class Connections:
    def __init__(self, signal, slot=None, slots=(), connect=True):
        self.signal = signal
        self.slots = slots

        if slot is not None:
            self.slots = (slot,) + self.slots

        if connect:
            self.connect()

    def connect(self):
        for slot in self.slots:
            self.signal.connect(slot)

    def disconnect(self):
        for slot in self.slots:
            self.signal.disconnect(slot)


def set_expanded_tree(view, index, expanded):
    if not expanded:
        view.setExpanded(index, expanded)

    for row in range(index.model().rowCount(index)):
        set_expanded_tree(
            view=view,
            index=index.child(row, 0),
            expanded=expanded,
        )

    if expanded:
        view.setExpanded(index, expanded)


@enum.unique
class UserRoles(epyqlib.utils.general.AutoNumberIntEnum):
    unique = QtCore.Qt.UserRole
    sort = None
    raw = None
    node = None
    field_name = None
    attrs_model = None
    column_index = None


def child_text_list_from_index(index, model, recurse=True):
    row_count = model.rowCount(index)
    if row_count == 0:
        return []

    lines = []
    for i in range(row_count):
        child = model.index(i, 0, index)
        lines.append(child.data())
        if recurse:
            lines.append(child_text_list_from_index(index=child, model=model))

    return lines


def indented_text_from_model(model, index=None):
    if index is None:
        index = QtCore.QModelIndex()

    lines = child_text_list_from_index(
        index=index,
        model=model,
        recurse=True,
    )
    lines = [
        'Root',
        lines,
    ]

    return epyqlib.utils.general.format_nested_lists(lines, indent="'   ")


@attr.s
class DeferredForSignal:
    signal = attr.ib()
    deferred = attr.ib(
        default=attr.Factory(
            factory=lambda self: twisted.internet.defer.Deferred(
                canceller=self.cancelled,
            ),
            takes_self=True,
        ),
    )
    timeout_call = attr.ib(default=None)

    def connect(self, timeout=None):
        self.signal.connect(self.slot)

        if timeout is not None:
            import twisted.internet.reactor
            self.timeout_call = twisted.internet.reactor.callLater(
                timeout,
                self.time_out,
            )

    def time_out(self):
        self.signal.disconnect(self.slot)
        self.deferred.errback(epyqlib.utils.twisted.RequestTimeoutError())

    def disconnect(self):
        self.signal.disconnect(self.slot)
        if self.timeout_call is not None:
            self.timeout_call.cancel()

    def cancelled(self, deferred):
        self.disconnect()

    def slot(self, *args):
        self.disconnect()
        self.deferred.callback(args)


def signal_as_deferred(signal, timeout=None, f=None, *args, **kwargs):
    dfs = DeferredForSignal(signal=signal)
    dfs.connect(timeout=timeout)

    if f is not None:
        f(*args, **kwargs)

    return dfs.deferred
