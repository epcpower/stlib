import epyqlib.faultlogmodel
import epyqlib.tests.test_attrsmodel

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


def test_all_addable_also_in_types():
    # Since addable types is dynamic and could be anything... this
    # admittedly only checks the addable types on default instances.
    for cls in epyqlib.faultlogmodel.types.types.values():
        addable_types = cls.all_addable_types().values()
        assert set(addable_types) - set(epyqlib.faultlogmodel.types) == set()


def assert_incomplete_types(name):
    assert [] == [
        cls
        for cls in epyqlib.faultlogmodel.types.types.values()
        if not hasattr(cls, name)
    ]


def test_all_have_can_drop_on():
    assert_incomplete_types('can_drop_on')


def test_all_have_can_delete():
    assert_incomplete_types('can_delete')


def test_all_fields_in_columns():
    epyqlib.tests.test_attrsmodel.all_fields_in_columns(
        types=epyqlib.faultlogmodel.types,
        root_type=epyqlib.faultlogmodel.Root,
        columns=epyqlib.faultlogmodel.columns,
    )
