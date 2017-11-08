import epyqlib.pm.valuesetmodel
import epyqlib.tests.test_attrsmodel

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


def test_all_addable_also_in_types():
    # Since addable types is dynamic and could be anything... this
    # admittedly only checks the addable types on default instances.
    for cls in epyqlib.pm.valuesetmodel.types.types.values():
        addable_types = cls.all_addable_types().values()
        assert set(addable_types) - set(epyqlib.pm.valuesetmodel.types) == set()


def assert_incomplete_types(name):
    assert [] == [
        cls
        for cls in epyqlib.pm.valuesetmodel.types.types.values()
        if not hasattr(cls, name)
    ]


def test_all_have_can_drop_on():
    assert_incomplete_types('can_drop_on')


def test_all_have_can_delete():
    assert_incomplete_types('can_delete')


def test_all_fields_in_columns():
    epyqlib.tests.test_attrsmodel.all_fields_in_columns(
        types=epyqlib.pm.valuesetmodel.types,
        root_type=epyqlib.pm.valuesetmodel.Root,
        columns=epyqlib.pm.valuesetmodel.columns,
    )
