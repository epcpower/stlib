#!/usr/bin/env python3

#TODO: """DocString if there is one"""

from epyqlib.iopoint import IoPoint
from PyQt5.QtCore import pyqtProperty
from PyQt5 import QtWidgets

import epyqlib.iogroup_ui
import epyqlib.utils.qt


# See file COPYING in this source tree
__copyright__ = 'Copyright 2016, EPC Power Corp.'
__license__ = 'GPLv2+'


class IoGroup(QtWidgets.QWidget):
    def __init__(self, parent=None, in_designer=False):
        super().__init__(parent=parent)

        self.in_designer = in_designer

        self._status_frame = ''
        self._status_signal_format = ''
        self._set_frame = ''
        self._set_signal_format = ''
        self._override_frame = ''
        self._override_signal_format = ''

        self._quantity = 0
        self._tx = True

        self.points = []

        self.ui = epyqlib.iogroup_ui.Ui_Form()
        self.ui.setupUi(self)

    @pyqtProperty(bool)
    def tx(self):
        return self._tx

    @tx.setter
    def tx(self, tx):
        self._tx = bool(tx)

        self.update_configuration()

    @pyqtProperty(str)
    def box_title(self):
        return self.ui.box.title()

    @box_title.setter
    def box_title(self, title):
        self.ui.box.setTitle(title)

    @pyqtProperty(int)
    def quantity(self):
        return self._quantity

    @quantity.setter
    def quantity(self, quantity):
        self._quantity = quantity

        self.update_configuration()

    @pyqtProperty(str)
    def status_frame(self):
        return self._status_frame

    @status_frame.setter
    def status_frame(self, frame):
        self._status_frame = frame

        self.update_configuration()

    @pyqtProperty(str)
    def status_signal_format(self):
        return self._status_signal_format

    @status_signal_format.setter
    def status_signal_format(self, signal_format):
        self._status_signal_format = signal_format

        self.update_configuration()

    @pyqtProperty(str)
    def set_frame(self):
        return self._set_frame

    @set_frame.setter
    def set_frame(self, frame):
        self._set_frame = frame

        self.update_configuration()

    @pyqtProperty(str)
    def set_signal_format(self):
        return self._set_signal_format

    @set_signal_format.setter
    def set_signal_format(self, signal_format):
        self._set_signal_format = signal_format

        self.update_configuration()

    @pyqtProperty(str)
    def override_frame(self):
        return self._override_frame

    @override_frame.setter
    def override_frame(self, frame):
        self._override_frame = frame

        self.update_configuration()

    @pyqtProperty(str)
    def override_signal_format(self):
        return self._override_signal_format

    @override_signal_format.setter
    def override_signal_format(self, signal_format):
        self._override_signal_format = signal_format

        self.update_configuration()

    def update_configuration(self):
        while self.points:
            point = self.points.pop()
            self.ui.layout.removeWidget(point)
            point.setParent(None)

        for i in range(self.quantity):
            point = IoPoint(parent=self, in_designer=self.in_designer)
            point.index = i + 1
            point.tx = self._tx
            point.status_frame = self.status_frame
            point.status_signal = self.status_signal_format.format(point.index)
            point.set_frame = self.set_frame
            point.set_signal = self.set_signal_format.format(point.index)
            point.override_frame = self.override_frame
            point.override_signal = self.override_signal_format.format(
                point.index)
            self.ui.layout.addWidget(point)
            self.points.append(point)


if __name__ == '__main__':
    import sys

    print('No script functionality here')
    sys.exit(1)     # non-zero is a failure
