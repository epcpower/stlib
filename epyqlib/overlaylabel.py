from PyQt5 import QtWidgets
from PyQt5.QtCore import pyqtProperty, Qt
from PyQt5.QtGui import QFontMetrics

import epyqlib.overlaylabel_ui
import epyqlib.utils.qt


# See file COPYING in this source tree
__copyright__ = 'Copyright 2018, EPC Power Corp.'
__license__ = 'GPLv2+'


styles = {
    'red': "background-color: rgba(255, 255, 255, 0);"
                           "color: rgba(255, 85, 85, 25);",
    'blue': "background-color: rgba(255, 255, 255, 0);"
                           "color: rgba(85, 85, 255, 25);"
}


class OverlayLabel(QtWidgets.QWidget):
    def __init__(self, parent=None, in_designer=False):
        super().__init__(parent=parent)

        self.in_designer = in_designer

        self._width_ratio = 0.8
        self._height_ratio = 0.8

        self.setStyleSheet(styles['red'])

        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        self.ui = epyqlib.overlaylabel_ui.Ui_Form()
        self.ui.setupUi(self)

    @pyqtProperty(str)
    def text(self):
        self.ui.label.text()

    @text.setter
    def text(self, text):
        self.ui.label.setText(text)

    @pyqtProperty(float)
    def width_ratio(self):
        return self._width_ratio

    @width_ratio.setter
    def width_ratio(self, value):
        self._width_ratio = value

    @pyqtProperty(float)
    def height_ratio(self):
        return self._height_ratio

    @height_ratio.setter
    def height_ratio(self, value):
        self._height_ratio = value

    def resizeEvent(self, event):
        QtWidgets.QWidget.resizeEvent(self, event)

        self.update_overlay_size(event.size())

    def update_overlay_size(self, size):
        text = self.ui.label.text()
        if not text:
            text = '-'
        font = self.ui.label.font()
        font.setPixelSize(1000)
        metric = QFontMetrics(font)
        rect = metric.boundingRect(text)

        pixel_size_width = (
            font.pixelSize() *
            (size.width() * self.width_ratio) / rect.width()
        )

        pixel_size_height = (
            font.pixelSize() *
            (size.height() * self.height_ratio) / rect.height()
        )

        self.ui.label.setStyleSheet('font-size: {}px; font-weight: bold'.format(
            round(min(pixel_size_width, pixel_size_height))))
