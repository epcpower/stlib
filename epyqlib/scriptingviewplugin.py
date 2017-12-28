import epyqlib.scriptingview
import epyqlib.abstractpluginclass

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


class ScriptingViewPlugin(epyqlib.abstractpluginclass.AbstractPlugin):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self._group = 'EPC - General'
        self._init = epyqlib.scriptingview.ScriptingView
        self._module_path = 'epyqlib.scriptingview'
        self._name = 'ScriptingView'
