import operator

import epyqlib._build
import epyqlib._version


__version__, __sha__ = operator.itemgetter('version', 'full-revisionid')(
    epyqlib._version.get_versions(),
)

__version_tag__ = 'v{}-{}'.format(__version__, __sha__)
__build_tag__ = epyqlib._build.job_id
