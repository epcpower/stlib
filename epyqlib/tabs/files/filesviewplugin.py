import epyqlib.filesview
import epyqlib.abstractpluginclass

# See file COPYING in this source tree
__copyright__ = 'Copyright 2018, EPC Power Corp.'
__license__ = 'GPLv2+'


class FilesViewPlugin(epyqlib.abstractpluginclass.AbstractPlugin):
    def __init__(self, parent=None):
        super().__init__(parent=parent)

        self._group = 'EPC - General'
        self._init = epyqlib.filesview.FilesViewQtBuilder
        self._module_path = 'epyqlib.filesview'
        self._name = 'FilesView'
