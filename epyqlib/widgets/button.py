#!/usr/bin/env python3

# TODO: """DocString if there is one"""

import epyqlib.widgets.abstracttxwidget
import epyqlib.widgets.button_ui
from PyQt5.QtCore import pyqtProperty


# See file COPYING in this source tree
__copyright__ = "Copyright 2016, EPC Power Corp."
__license__ = "GPLv2+"


class Button(epyqlib.widgets.abstracttxwidget.AbstractTxWidget):
    def __init__(self, parent=None, in_designer=False):
        self._frame = None
        self._signal = None
        self._on_value = 1
        self._off_value = 0

        super().__init__(
            ui_class=epyqlib.widgets.button_ui.Ui_Form,
            parent=parent,
            in_designer=in_designer,
        )

        # TODO: CAMPid 398956661298765098124690765
        self.ui.value.pressed.connect(self.pressed)
        self.ui.value.released.connect(self.released)

    @pyqtProperty(int)
    def on_value(self):
        return self._on_value

    @on_value.setter
    def on_value(self, new_on_value):
        self._on_value = int(new_on_value)

    @pyqtProperty(int)
    def off_value(self):
        return self._off_value

    @off_value.setter
    def off_value(self, new_off_value):
        self._off_value = int(new_off_value)
        self.set(self.off_value)

    def set_signal(self, signal=None, force_update=False):
        super().set_signal(signal, force_update=force_update)

        if signal is not None:
            self.set(self.off_value)

            def get_text_width(widget, text):
                return widget.fontMetrics().boundingRect(text).width()

            button = self.ui.value
            # TODO: it would be nice to use the 'normal' extra width
            # initial_margin = button.width() - get_text_width(button,
            #                                                  button.text())

            if len(self.signal_object.enumeration):
                widths = []
                for text in [
                    self.calculate_text(v) for v in self.signal_object.enumeration
                ]:
                    widths.append(get_text_width(button, text))

                button.setMinimumWidth(int(1.3 * max(widths)))
        else:
            if self.ui is not None:
                self.ui.value.setText("")

    def set(self, value):
        self.widget_value_changed(value)
        self.set_text(value)

    def calculate_text(self, value):
        if self.label_visible and self.signal_object is not None:
            # TODO: CAMPid 85478672616219005471279
            enum_string = self.signal_object.enumeration[value]
            text = self.signal_object.enumeration_format_re["format"].format(
                s=enum_string, v=value
            )

            return text
        else:
            return self.ui.label.text()

    def set_text(self, value):
        self.ui.value.setText(self.calculate_text(value))

    def pressed(self):
        self.set(self.on_value)

    def released(self):
        self.set(self.off_value)

    def set_value(self, value):
        # TODO  exception?
        pass

    def set_unit_text(self, units):
        pass

    def showEvent(self, event):
        epyqlib.widgets.abstracttxwidget.AbstractTxWidget.showEvent(self, event)
        self.set(self.off_value)


if __name__ == "__main__":
    import sys

    print("No script functionality here")
    sys.exit(1)  # non-zero is a failure
