import collections
import itertools
import json
import pathlib

import attr
import graham
import pytest
from PyQt5 import QtCore

import epyqlib.pm.parametermodel


with open(pathlib.Path(__file__).with_suffix('.json')) as f:
    serialized_sample = f.read()


@attr.s
class SampleModel:
    root = attr.ib(
        factory=lambda: epyqlib.pm.parametermodel.Root(
            uuid='ce63b990-8061-4b9f-9ad7-d2b60fe8b4c9',
        ),
    )
    model = attr.ib(default=None)
    group_a = attr.ib(default=None)
    enumerations = attr.ib(default=None)
    letters_enumeration = attr.ib(default=None)
    letters_enumerators = attr.ib(factory=dict)
    numbers_enumeration = attr.ib(default=None)
    numbers_enumerators = attr.ib(factory=dict)
    table = attr.ib(default=None)

    @classmethod
    def build(cls):
        sample_model = cls()
        sample_model.model = epyqlib.attrsmodel.Model(
            root=sample_model.root,
            columns=epyqlib.pm.parametermodel.columns,
        )

        return sample_model

    def fill(self):
        self.group_a = epyqlib.pm.parametermodel.Group(
            name='Group A',
            uuid='78fb0043-b46f-4198-86ed-3ba8d48bf4c8',
        )
        parameter_a_a = epyqlib.pm.parametermodel.Parameter(
            name='Parameter A A',
            uuid='fd184494-35a2-4b3a-970c-9a3d98cc15cd',
        )
        group_a_b = epyqlib.pm.parametermodel.Group(
            name='Group A B',
            uuid='5db07237-82c8-488f-925b-1a2a2802fb5b',
        )
        parameter_b = epyqlib.pm.parametermodel.Parameter(
            name='Parameter B',
            default=42,
            uuid='ee545382-a651-479b-9dc2-a4c3d42c230c',
        )
        group_c = epyqlib.pm.parametermodel.Group(
            name='Group C',
            uuid='7878effc-2d29-4719-bf0d-192e18d0f27c',
        )

        self.root.append_child(self.group_a)
        self.group_a.append_child(parameter_a_a)
        self.group_a.append_child(group_a_b)

        self.root.append_child(parameter_b)

        self.root.append_child(group_c)

        self.enumerations = epyqlib.pm.parametermodel.Enumerations(
            name='Enumerations',
            uuid='4f71f673-af26-4c70-8d3e-910902163e98',
        )
        self.root.append_child(self.enumerations)

        self.letters_enumeration = epyqlib.pm.parametermodel.Enumeration(
            name='Letters',
            uuid='fd1b8036-8aef-4914-9165-ed3118bd8ecd',
        )
        self.enumerations.append_child(self.letters_enumeration)
        self.letters_enumerators = {
            letter: epyqlib.pm.parametermodel.Enumerator(
                name=letter,
                uuid=uuid
            )
            for letter, uuid in (
                ('a', 'a2cf0c0c-c55a-4a0c-b830-571b5abe089b'),
                ('b', 'effdff81-7da1-4cd8-863f-44f33c75813e'),
                ('c', '2902368d-352e-441b-99e0-45998bad0d6d'),
                ('d', '37ffb8b2-668a-46e1-a0d9-6a561ad5db7c'),
                ('e', '519d3d04-239b-4423-9693-c961ca955c34'),
                ('f', 'c23a395a-dbd0-46f2-ae10-ee057ea098d5'),
                ('g', '23195ab8-b62e-4cb0-a521-5b774ae7c3e5'),
            )
        }
        for letter, enumerator in sorted(self.letters_enumerators.items()):
            self.letters_enumeration.append_child(enumerator)
            
        self.numbers_enumeration = epyqlib.pm.parametermodel.Enumeration(
            name='numbers',
            uuid='86111e99-624c-499e-a560-6a77db461e43',
        )
        self.enumerations.append_child(self.numbers_enumeration)
        self.numbers_enumerators = {
            number: epyqlib.pm.parametermodel.Enumerator(
                name=number,
                uuid=uuid,
            )
            for number, uuid in (
                ('1', '165ccc7b-7ffc-4546-add2-11f0855f86d1'),
                ('2', '64e3e07c-dd4f-439a-850c-69508bfd545c'),
                ('3', '98f4f322-06ee-44bd-8063-4b174af22b2c'),
                ('4', 'd152135a-991c-464e-bee0-81115f9159b6'),
                ('5', '371a8511-a6d4-4c9c-be5c-5cc6cba6e190'),
                ('6', '6f448d09-1b42-432d-ac07-5e1470e70e3e'),
            )
        }
        for number, enumerator in sorted(self.numbers_enumerators.items()):
            self.numbers_enumeration.append_child(enumerator)

        self.table = epyqlib.pm.parametermodel.Table(
            name='Table A',
            uuid='58b7bf0d-4dec-4707-a976-d49a856eb3ba',
        )
        self.group_a.append_child(self.table)
        self.table.append_child(
            epyqlib.pm.parametermodel.TableEnumerationReference(
                name='Numbers',
                uuid='3d98c907-0b81-4e29-be9b-2620ef44ce26',
                enumeration_uuid=self.numbers_enumeration.uuid,
            ),
        )
        self.table.append_child(
            epyqlib.pm.parametermodel.TableEnumerationReference(
                name='Letters',
                uuid='d80162ea-bd8c-4936-bca1-732b11205423',
                enumeration_uuid=self.letters_enumeration.uuid,
            ),
        )

        array_a = epyqlib.pm.parametermodel.Array(
            name='Table Array A',
            uuid='77ed47bb-fbea-4756-b1c4-2e2be02aebc7',
        )
        array_a.append_child(
            epyqlib.pm.parametermodel.Parameter(
                name='A0',
                uuid='a32ea0c1-0838-430f-8d3c-192b5bff3047',
            )
        )
        array_a.length = 2
        array_a.children[1].name = 'A1'
        self.table.append_child(array_a)

        array_b = epyqlib.pm.parametermodel.Array(
            name='Table Array B',
            uuid='acda3b53-785c-4588-8b35-d58a9f2e10a8',
        )
        array_b.append_child(
            epyqlib.pm.parametermodel.Parameter(
                name='B0',
                uuid='1c7d0fac-aaa6-415b-b7c1-08d1f5d07097',
            )
        )
        array_b.length = 2
        array_b.children[1].name = 'B1'
        self.table.append_child(array_b)

        self.model.update_nodes()


@pytest.fixture
def sample():
    sample_model = SampleModel.build()
    sample_model.fill()

    return sample_model


default_column_index, = (
    index
    for index, column in enumerate(epyqlib.pm.parametermodel.columns)
    if column.name == 'Default'
)


@pytest.mark.parametrize('column,target', (
    (0, 'Parameter B'),
    (default_column_index, 42),
))
def test_search_in_column(sample, column, target):
    proxy = QtCore.QSortFilterProxyModel()
    proxy.setSourceModel(sample.model.model)

    index, = proxy.match(
        proxy.index(0, column),
        QtCore.Qt.DisplayRole,
        target,
    )


@pytest.mark.parametrize('column,target', (
    (0, 'Parameter B'),
    (default_column_index, 42),
))
def test_proxy_search_in_column(sample, column, target):
    proxy = epyqlib.utils.qt.PySortFilterProxyModel(filter_column=0)
    proxy.setSourceModel(sample.model.model)

    index, = proxy.match(
        proxy.index(0, column),
        QtCore.Qt.DisplayRole,
        target,
    )

    match_node = sample.model.node_from_index(proxy.mapToSource(index))

    index = proxy.search(
        text=target,
        search_from=sample.model.index_from_node(sample.model.root),
        column=column,
    )

    search_node = sample.model.node_from_index(proxy.mapToSource(index))

    assert match_node is search_node


def test_sample_dumps_consistently(sample):
    dumped = graham.dumps(sample.root, indent=4)

    def load(s):
        return json.loads(s, object_pairs_hook=collections.OrderedDict)

    print()
    print(dumped.data)

    assert load(dumped.data) == load(serialized_sample)


def test_sample_loads_consistently(sample):
    loaded = graham.schema(type(sample.root)).loads(serialized_sample)

    assert sample.root == loaded.data


def test_table_addition(sample):
    table = epyqlib.pm.parametermodel.Table()
    sample.group_a.append_child(table)

    seconds = epyqlib.pm.parametermodel.Array(name='seconds')
    table.append_child(seconds)
    hertz = epyqlib.pm.parametermodel.Array(name='hertz')
    table.append_child(hertz)

    letters_reference = epyqlib.pm.parametermodel.TableEnumerationReference()
    letters_reference.link(sample.letters_enumeration)
    table.append_child(letters_reference)

    numbers_reference = epyqlib.pm.parametermodel.TableEnumerationReference()
    numbers_reference.link(sample.numbers_enumeration)
    table.append_child(numbers_reference)

    # assert letters_reference.name == sample.letters_enumeration.name


def test_table_add_enumeration_with_uuid(sample):
    punctuation_enumeration = epyqlib.pm.parametermodel.Enumeration(
        name='punctuation',
    )
    sample.enumerations.append_child(punctuation_enumeration)
    punctuation_enumerators = {
        punctuation: epyqlib.pm.parametermodel.Enumerator(name=punctuation)
        for punctuation in '!@#$%^'
    }
    for punctuation, enumerator in sorted(punctuation_enumerators.items()):
        punctuation_enumeration.append_child(enumerator)

    ref = epyqlib.pm.parametermodel.TableEnumerationReference(
        enumeration_uuid=punctuation_enumeration.uuid,
    )

    sample.table.append_child(ref)


def verify_table_automatic_groups(sample):
    groups = [
        child
        for child in sample.table.children
        if isinstance(child, epyqlib.pm.parametermodel.TableGroupElement)
    ]

    assert len(groups) == 1

    group, = groups

    enumeration_references = [
        child
        for child in sample.table.children
        if isinstance(child, epyqlib.pm.parametermodel.TableEnumerationReference)
    ]

    enumerations = []
    for enumeration_reference in enumeration_references:
        enumeration, = sample.root.nodes_by_attribute(
            attribute_name='uuid',
            attribute_value=enumeration_reference.enumeration_uuid,
        )
        enumerations.append(enumeration)

    arrays = [
        child
        for child in sample.table.children
        if isinstance(child, epyqlib.pm.parametermodel.Array)
    ]

    zipped = itertools.zip_longest(
        group.children,
        enumerations[0].children,
    )
    for child, enumerator in zipped:
        print('checking: {}'.format((
            enumerator.name)))
        assert child.name == enumerator.name

        zipped = itertools.zip_longest(
            child.children,
            enumerations[1].children,
        )
        for subchild, subenumerator in zipped:
            print('checking: {}'.format((
                enumerator.name, subenumerator.name)))
            assert subchild.name == subenumerator.name

            zipped = itertools.zip_longest(
                subchild.children,
                arrays,
            )
            for subsubchild, array in zipped:
                print('checking: {}'.format((
                                            enumerator.name, subenumerator.name,
                                            array.name)))
                assert subsubchild.name == array.name

                zipped = itertools.zip_longest(
                    subsubchild.children,
                    array.children,
                )
                for subsubsubchild, element in zipped:
                    print('checking: {}'.format((enumerator.name, subenumerator.name, array.name, element.name)))
                    assert subsubsubchild.name == element.name


def test_table_automatic_groups(sample):
    verify_table_automatic_groups(sample)


def test_table_automatic_groups_add_another(sample):
    array_c = epyqlib.pm.parametermodel.Array(
        name='Table Array A',
        uuid='eb812b66-f98b-4e8f-a7e8-4f76c853e437',
    )

    sample.table.append_child(array_c)

    verify_table_automatic_groups(sample)


def test_array_addable_types():
    array = epyqlib.pm.parametermodel.Array()

    value_types = (
        epyqlib.pm.parametermodel.Parameter,
        epyqlib.pm.parametermodel.Group,
    )

    assert array.addable_types() == epyqlib.attrsmodel.create_addable_types(
        value_types,
    )

    for value_type in value_types:
        child = value_type()
        array.append_child(child)

        assert array.addable_types() == epyqlib.attrsmodel.create_addable_types(
            (),
        )

        array.remove_child(child=child)

        assert array.addable_types() == epyqlib.attrsmodel.create_addable_types(
            value_types,
        )


def test_array_update_children_length():
    array = epyqlib.pm.parametermodel.Array()
    parameter = epyqlib.pm.parametermodel.Parameter()

    assert len(array.children) == 0

    array.append_child(parameter)

    assert len(array.children) == 1

    for n in (3, 7, 4, 1, 5):
        array.length = n
        assert len(array.children) == n


def test_all_addable_also_in_types():
    # Since addable types is dynamic and could be anything... this
    # admittedly only checks the addable types on default instances.
    for cls in epyqlib.pm.parametermodel.types.types.values():
        addable_types = cls.all_addable_types().values()
        assert set(addable_types) - set(
            epyqlib.pm.parametermodel.types) == set()


def assert_incomplete_types(name):
    assert [] == [
        cls
        for cls in epyqlib.pm.parametermodel.types.types.values()
        if not hasattr(cls, name)
    ]


def test_all_have_can_drop_on():
    assert_incomplete_types('can_drop_on')


def test_all_have_can_delete():
    assert_incomplete_types('can_delete')


def test_all_fields_in_columns():
    epyqlib.tests.test_attrsmodel.all_fields_in_columns(
        types=epyqlib.pm.parametermodel.types,
        root_type=epyqlib.pm.parametermodel.Root,
        columns=epyqlib.pm.parametermodel.columns,
    )
