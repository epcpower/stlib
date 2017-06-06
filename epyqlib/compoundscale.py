#!/usr/bin/env python3

#TODO: """DocString if there is one"""

import io
import os

from PyQt5 import uic
from PyQt5.QtCore import pyqtProperty, QFile, QFileInfo, QTextStream
from PyQt5.QtWidgets import QWidget

# See file COPYING in this source tree
__copyright__ = 'Copyright 2016, EPC Power Corp.'
__license__ = 'GPLv2+'


class CompoundScale(QWidget):
    def __init__(self, parent=None, in_designer=False):
        QWidget.__init__(self, parent=parent)

        self.in_designer = in_designer

        ui = os.path.join(QFileInfo.absolutePath(QFileInfo(__file__)),
                          'compoundscale.ui')

        # TODO: CAMPid 9549757292917394095482739548437597676742
        if not QFileInfo(ui).isAbsolute():
            ui_file = os.path.join(
                QFileInfo.absolutePath(QFileInfo(__file__)), ui)
        else:
            ui_file = ui
        ui_file = QFile(ui_file)
        ui_file.open(QFile.ReadOnly | QFile.Text)
        ts = QTextStream(ui_file)
        sio = io.StringIO(ts.readAll())
        self.ui = uic.loadUi(sio, self)

        self.ui.command.in_designer = in_designer
        self.ui.echo.in_designer = in_designer
        self.ui.status.in_designer = in_designer
        self.ui.numeric_status.in_designer = in_designer

        self.update_echo_visibility()

    def update_echo_visibility(self):
        self.ui.echo.setHidden(self.echo_signal_path[0] in {None, ''})
        self.ui.echo.ignore = True

    @pyqtProperty('QString')
    def command_signal_path(self):
        return self.ui.command.signal_path

    @command_signal_path.setter
    def command_signal_path(self, value):
        self.ui.command.signal_path = value

    @pyqtProperty('QString')
    def echo_signal_path(self):
        return ';'.join(self.ui.echo.signal_path)

    @echo_signal_path.setter
    def echo_signal_path(self, value):
        self.ui.echo.signal_path = value
        self.update_echo_visibility()

    @pyqtProperty('QString')
    def status_signal_path(self):
        return self.ui.status.signal_path

    @status_signal_path.setter
    def status_signal_path(self, value):
        self.ui.status.signal_path = value
        self.ui.numeric_status.signal_path = value

    @pyqtProperty(bool)
    def status_override_range(self):
        return self.ui.status.override_range

    @status_override_range.setter
    def status_override_range(self, override):
        self.ui.status.override_range = override

    @pyqtProperty(float)
    def status_minimum(self):
        return self.ui.status.minimum

    @status_minimum.setter
    def status_minimum(self, min):
        self.ui.status.minimum = float(min)

    @pyqtProperty(float)
    def status_maximum(self):
        return self.ui.status.maximum

    @status_maximum.setter
    def status_maximum(self, max):
        self.ui.status.maximum = float(max)

    @pyqtProperty(str)
    def status_label(self):
        return self.ui.numeric_status.label_override

    @status_label.setter
    def status_label(self, label):
        self.ui.numeric_status.label_override = label


if __name__ == '__main__':
    import sys

    print('No script functionality here')
    sys.exit(1)     # non-zero is a failure
