#!/usr/bin/env python3

#TODO: """DocString if there is one"""

import epyqlib.widgets.abstracttxwidget
import epyqlib.widgets.enum_ui


# See file COPYING in this source tree
__copyright__ = 'Copyright 2016, EPC Power Corp.'
__license__ = 'GPLv2+'


class Enum(epyqlib.widgets.abstracttxwidget.AbstractTxWidget):
    def __init__(self, parent=None, in_designer=False):
        self._frame = None
        self._signal = None

        super().__init__(
            ui_class=epyqlib.widgets.enum_ui.Ui_Form,
            parent=parent,
            in_designer=in_designer,
        )

        # TODO: CAMPid 398956661298765098124690765
        self.ui.value.currentTextChanged.connect(self.widget_value_changed)

    def set_value(self, value):
        if self.signal_object is not None:
            if len(self.signal_object.enumeration) > 0:
                value = self.signal_object.full_string
            else:
                value = self.signal_object.format_float()
        elif value is None:
            value = '-'
        else:
            # TODO: quit hardcoding this and it's better implemented elsewhere
            value = '{0:.2f}'.format(value)

        self.ui.value.setCurrentText(value)

    def set_signal(self, signal=None, force_update=False):
        if signal is not self.signal_object or force_update:
            if self.ui is not None:
                self.ui.value.clear()
            if signal is not None:


                full_strings = []
                # TODO: CAMPid 94562754956589992752348667
                for value in sorted(signal.enumeration.keys()):
                    # TODO: CAMPid 85478672616219005471279
                    enum_string = signal.enumeration[value]
                    full_strings.append(signal.enumeration_format_re['format'].format(
                        s=enum_string, v=value))

                self.ui.value.addItems(full_strings)

        super().set_signal(signal, force_update=force_update)


if __name__ == '__main__':
    import sys

    print('No script functionality here')
    sys.exit(1)     # non-zero is a failure
