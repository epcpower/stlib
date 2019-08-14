#!/usr/bin/env python3

#TODO: """DocString if there is one"""

import functools

from PyQt5 import QtWidgets

import epyqlib.numberpad_ui
import epyqlib.utils.qt


# See file COPYING in this source tree
__copyright__ = 'Copyright 2016, EPC Power Corp.'
__license__ = 'GPLv2+'


class NumberPad(QtWidgets.QWidget):
    def __init__(self, parent=None, in_designer=False, action=None):
        super().__init__(parent=parent)

        self.in_designer = in_designer

        self.ui = epyqlib.numberpad_ui.Ui_Form()
        self.ui.setupUi(self)

        self.action = action
        self.ui.accept_button.clicked.connect(self.accept)
        self.ui.cancel_button.clicked.connect(
            functools.partial(self.exit, value=None))
        self.ui.up_button.clicked.connect(
            self.ui.cancel_button.clicked)

        numeric_buttons = []

        for number in range(10):
            button = getattr(self.ui, 'button_{}'.format(number))
            button.clicked.connect(
                functools.partial(
                    self.ui.edit.insert,
                    str(number)
                )
            )
            numeric_buttons.append(button)

        self.ui.button_decimal.clicked.connect(
            functools.partial(
                self.ui.edit.insert,
                '.'
            )
        )
        numeric_buttons.append(self.ui.button_decimal)

        self.ui.button_backspace.clicked.connect(self.ui.edit.backspace)

        for button in numeric_buttons:
            button.setStyleSheet('''
                QPushButton {
                    border: 0px;
                }
            ''')

    def focus(self, value, action, label=''):
        self.ui.label.setText(label)
        self.ui.edit.setText(str(value))
        self.action = action
        self.parent().setCurrentWidget(self)
        focused_widget = self.focusWidget()
        if focused_widget is not None:
            focused_widget.clearFocus()

    def accept(self):
        try:
            value = float(self.ui.edit.text())
        except ValueError:
            value = None

        self.exit(value=value)

    def exit(self, value):
        self.action(value=value)

if __name__ == '__main__':
    import sys

    print('No script functionality here')
    sys.exit(1)     # non-zero is a failure
