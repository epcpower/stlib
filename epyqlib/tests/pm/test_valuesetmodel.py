import epyqlib.pm.valuesetmodel
import epyqlib.tests.test_attrsmodel

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


TestAttrsModel = epyqlib.attrsmodel.build_tests(
    types=epyqlib.pm.valuesetmodel.types,
    root_type=epyqlib.pm.valuesetmodel.Root,
    columns=epyqlib.pm.valuesetmodel.columns,
)
