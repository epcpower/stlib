import collections
import inspect
import itertools
import json
import pathlib
import uuid

import attr
import graham
import pytest
from PyQt5 import QtCore

import epyqlib.attrsmodel
import epyqlib.pm.parametermodel
import epyqlib.tests.test_attrsmodel


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
                name='Letters',
                uuid='d80162ea-bd8c-4936-bca1-732b11205423',
                enumeration_uuid=self.letters_enumeration.uuid,
            ),
        )
        self.table.append_child(
            epyqlib.pm.parametermodel.TableEnumerationReference(
                name='Numbers',
                uuid='3d98c907-0b81-4e29-be9b-2620ef44ce26',
                enumeration_uuid=self.numbers_enumeration.uuid,
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
        array_a.children[1].uuid = uuid.UUID(
            '9d642888-b7f0-4d04-8ebf-10887249b179',
        )
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
        array_b.children[1].uuid = uuid.UUID(
            '32666885-2934-481f-88fd-7e3157f702b1',
        )
        self.table.append_child(array_b)

        table_group_root = epyqlib.pm.parametermodel.TableGroupElement(
            name='Tree',
            uuid='428124a2-6fe3-4b40-9e23-f78e19c7aa7a',
        )

        table_group_root_a = epyqlib.pm.parametermodel.TableGroupElement(
            original=self.letters_enumerators['a'],
            uuid='904d287d-2cdd-487e-ada9-ed0f8a552078',
            path=(self.letters_enumerators['a'].uuid,),
        )
        table_group_root_a_1 = epyqlib.pm.parametermodel.TableGroupElement(
            original=self.numbers_enumerators['1'],
            uuid='9d37bb7f-2618-4ce8-b9f9-214c19851361',
            path=table_group_root_a.path + (self.numbers_enumerators['1'].uuid,),
        )
        table_group_root_a_1_a = epyqlib.pm.parametermodel.TableGroupElement(
            original=array_a,
            uuid='993ededd-6083-4c1e-aa72-bf08ee3ea61c',
            path=table_group_root_a_1.path + (array_a.uuid,),
        )
        self.add_array_elements(
            array=array_a,
            group=table_group_root_a_1_a,
            uuids=[
                '403b3a2c-f94a-490c-b112-87cdd3551e55',
                '3fd1f0e6-09e7-413e-b169-3fafff126bbc',
            ],
        )
        table_group_root_a_1.append_child(table_group_root_a_1_a)

        table_group_root_a_1_b = epyqlib.pm.parametermodel.TableGroupElement(
            original=array_b,
            uuid='72ce1cf9-0c90-48e9-a37c-aee1b36fca80',
            path=table_group_root_a_1.path + (array_b.uuid,),
        )
        self.add_array_elements(
            array=array_b,
            group=table_group_root_a_1_b,
            uuids=[
                '106cc983-0321-4ced-9e72-ab56d6bf1e7f',
                '80fd2eb7-6c89-4b65-ad35-05d63522f991',
            ],
        )
        table_group_root_a_1.append_child(table_group_root_a_1_b)
        table_group_root_a.append_child(table_group_root_a_1)
        table_group_root_a_2 = epyqlib.pm.parametermodel.TableGroupElement(
            original=self.numbers_enumerators['2'],
            uuid='b748bc78-0267-477e-95ec-e64a6686e010',
            path=table_group_root_a.path + (self.numbers_enumerators['2'].uuid,),
        )
        table_group_root_a_2_a = epyqlib.pm.parametermodel.TableGroupElement(
            original=array_a,
            uuid='712cda8a-4744-4da2-a1d1-1573625bbf14',
            path=table_group_root_a_2.path + (array_a.uuid,),
        )
        self.add_array_elements(
            array=array_a,
            group=table_group_root_a_2_a,
            uuids=[
                '290b2762-61c7-4666-8f99-af3c0113d4a3',
                'aee3a1de-b35a-4e7b-b274-1ef6766d5889',
            ],
        )
        table_group_root_a_2.append_child(table_group_root_a_2_a)
        table_group_root_a_2_b = epyqlib.pm.parametermodel.TableGroupElement(
            original=array_b,
            uuid='e74d9047-1635-43f3-825b-6844fab96a00',
            path=table_group_root_a_2.path + (array_b.uuid,),
        )
        self.add_array_elements(
            array=array_b,
            group=table_group_root_a_2_b,
            uuids=[
                '99a1be09-c4e0-41f1-bda4-d0f139038cbf',
                'fa79e1aa-647d-4783-8b16-fe752ac8e8c4',
            ],
        )
        table_group_root_a_2.append_child(table_group_root_a_2_b)
        table_group_root_a.append_child(table_group_root_a_2)
        table_group_root.append_child(table_group_root_a)

        table_group_root_b = epyqlib.pm.parametermodel.TableGroupElement(
            original=self.letters_enumerators['b'],
            uuid='104d1901-524e-412b-84e7-98707dce362d',
            path=(self.letters_enumerators['b'].uuid,),
        )
        table_group_root_b_1 = epyqlib.pm.parametermodel.TableGroupElement(
            original=self.numbers_enumerators['1'],
            uuid='9dc75463-f6a9-411f-b0a7-5c311086ff69',
            path=table_group_root_b.path + (self.numbers_enumerators['1'].uuid,),
        )
        table_group_root_b_1_a = epyqlib.pm.parametermodel.TableGroupElement(
            original=array_a,
            uuid='f0989f09-4066-4047-8d61-c134c6e1e55c',
            path=table_group_root_b_1.path + (array_a.uuid,),
        )
        self.add_array_elements(
            array=array_a,
            group=table_group_root_b_1_a,
            uuids=[
                'c076b3e1-a287-468c-80e4-43523a021feb',
                '937be4d7-b578-4daa-aef0-4065198a613d',
            ],
        )
        table_group_root_b_1.append_child(table_group_root_b_1_a)
        table_group_root_b_1_b = epyqlib.pm.parametermodel.TableGroupElement(
            original=array_b,
            uuid='18e84e98-e8ad-4d4a-9180-951350f6590c',
            path=table_group_root_b_1.path + (array_b.uuid,),
        )
        self.add_array_elements(
            array=array_b,
            group=table_group_root_b_1_b,
            uuids=[
                '286079b0-6028-4959-8396-78c626cdab46',
                'de30995a-ba26-49cf-abd0-84d3dc62b3eb',
            ],
        )
        table_group_root_b_1.append_child(table_group_root_b_1_b)
        table_group_root_b.append_child(table_group_root_b_1)
        table_group_root_b_2 = epyqlib.pm.parametermodel.TableGroupElement(
            original=self.numbers_enumerators['2'],
            uuid='1178e67b-ddda-43f3-a26a-30d0e10a2bd3',
            path=table_group_root_b.path + (self.numbers_enumerators['2'].uuid,),
        )
        table_group_root_b_2_a = epyqlib.pm.parametermodel.TableGroupElement(
            original=array_a,
            uuid='1134bc2e-93d9-4b33-8164-dca0520f3910',
            path=table_group_root_b_2.path + (array_a.uuid,),
        )
        self.add_array_elements(
            array=array_a,
            group=table_group_root_b_2_a,
            uuids=[
                '6a151510-c6e5-4673-9198-d3d9fb0dfcdc',
                'dd3887db-df84-4f5f-ae6f-98201403c1d2',
            ],
        )
        table_group_root_b_2.append_child(table_group_root_b_2_a)
        table_group_root_b_2_b = epyqlib.pm.parametermodel.TableGroupElement(
            original=array_b,
            uuid='d84963e3-164e-4df8-9f5e-cf6717e20b0d',
            path=table_group_root_b_2.path + (array_b.uuid,),
        )
        self.add_array_elements(
            array=array_b,
            group=table_group_root_b_2_b,
            uuids=[
                'd01008cc-cef0-4c95-b642-71e974690416',
                '2b16a382-2fa2-41b4-a0dc-161c7496d13a',
            ],
        )
        table_group_root_b_2.append_child(table_group_root_b_2_b)
        table_group_root_b.append_child(table_group_root_b_2)
        table_group_root.append_child(table_group_root_b)

        automatic_table_root, = [
            child
            for child in self.table.children
            if isinstance(child, epyqlib.pm.parametermodel.TableGroupElement)
        ]

        with self.table._ignore_children():
            self.table.remove_child(child=automatic_table_root)

            self.table.append_child(table_group_root)

        self.model.update_nodes()

    def add_array_elements(self, array, group, uuids):
        assert len(array.children) == len(uuids)

        for child, a_uuid in zip(array.children, uuids):
            element = epyqlib.pm.parametermodel.TableArrayElement(
                original=child,
                uuid=a_uuid,
                path=group.path + (child.uuid,),
            )
            group.append_child(element)


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
    sample.root.model = None

    assert loaded.data == sample.root


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


def test_table_update_same_uuid(qapp):
    root = graham.schema(epyqlib.pm.parametermodel.Root).loads(
        serialized_sample,
    ).data
    model = epyqlib.attrsmodel.Model(
        root=root,
        columns=epyqlib.pm.parametermodel.columns,
    )
    root.model = model

    table_a, = root.nodes_by_attribute(
        attribute_value='Table A',
        attribute_name='name',
    )

    # TODO: CAMPid 9784566547216435136479765479163496731
    def collect(node):
        def collect(node, payload):
            payload[node.uuid] = node.name

        results = {}

        node.traverse(
            call_this=collect,
            internal_nodes=True,
            payload=results,
        )

        return results

    table_a.update()

    original = collect(table_a)

    table_a.update()

    after_update = collect(table_a)

    assert after_update == original


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


def test_move_enumeration_in_table(sample):
    uuids_before = {
        node.uuid
        for node in sample.table.nodes_by_filter(lambda node: True)
    }

    table_index = sample.model.index_from_node(sample.table)
    names_before = epyqlib.utils.qt.child_text_list_from_index(
        model=sample.model.model,
        index=table_index,
        recurse=False,
    )

    sample.table.update()
    uuids_after = {
        node.uuid
        for node in sample.table.nodes_by_filter(lambda node: True)
    }

    assert len(uuids_after) == len(uuids_before)
    assert uuids_after == uuids_before

    node_to_move = sample.table.children[1]

    mime_data = sample.model.mimeData(
        (sample.model.index_from_node(node_to_move),),
    )

    sample.model.dropMimeData(
        data=mime_data,
        action=QtCore.Qt.MoveAction,
        row=-1,
        column=0,
        parent=sample.model.index_from_node(sample.table),
    )

    sample.table.update()
    uuids_after = {
        node.uuid
        for node in sample.table.nodes_by_filter(lambda node: True)
    }

    assert len(uuids_after) == len(uuids_before)
    assert uuids_after == uuids_before

    names_after = epyqlib.utils.qt.child_text_list_from_index(
        model=sample.model.model,
        index=table_index,
        recurse=False,
    )

    assert set(names_before) == set(names_after)
    assert len(names_before) == len(names_after)
    assert names_before != names_after


TestAttrsModel = epyqlib.attrsmodel.build_tests(
    types=epyqlib.pm.parametermodel.types,
    root_type=epyqlib.pm.parametermodel.Root,
    columns=epyqlib.pm.parametermodel.columns,
)
