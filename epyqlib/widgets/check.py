#!/usr/bin/env python3

#TODO: """DocString if there is one"""

import epyqlib.widgets.abstracttxwidget
import epyqlib.widgets.check_ui


# See file COPYING in this source tree
__copyright__ = 'Copyright 2016, EPC Power Corp.'
__license__ = 'GPLv2+'


class Check(epyqlib.widgets.abstracttxwidget.AbstractTxWidget):
    def __init__(self, parent=None, in_designer=False):
        self._frame = None
        self._signal = None

        super().__init__(
            ui_class=epyqlib.widgets.check_ui.Ui_Form,
            parent=parent,
            in_designer=in_designer,
        )

        # TODO: CAMPid 398956661298765098124690765
        self.ui.value.toggled.connect(self.widget_value_changed)

    def set_value(self, value):
        # TODO: quit hardcoding this and it's better implemented elsewhere
        if self.signal_object is not None:
            value = bool(self.signal_object.value)
        elif value is None:
            value = False
        else:
            value = bool(value)

        self.ui.value.setChecked(value)

    def signal_value_changed(self, value):
        self.ui.value.setChecked(bool(value))

    def set_unit_text(self, units):
        pass


if __name__ == '__main__':
    import sys

    print('No script functionality here')
    sys.exit(1)     # non-zero is a failure
