from epyqlib._version import __version__, __sha__, __revision__
import epyqlib._build

__version_tag__ = 'v{}-{}'.format(__version__, __sha__)
__build_tag__ = epyqlib._build.job_id

from ._version import get_versions
__version__ = get_versions()['version']
del get_versions
