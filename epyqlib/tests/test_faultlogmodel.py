import epyqlib.faultlogmodel
import epyqlib.tests.test_attrsmodel

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


TestAttrsModel = epyqlib.attrsmodel.build_tests(
    types=epyqlib.faultlogmodel.types,
    root_type=epyqlib.faultlogmodel.Root,
    columns=epyqlib.faultlogmodel.columns,
)
