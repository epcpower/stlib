import contextlib
import itertools

import attr
import graham
import marshmallow
import PyQt5.QtCore

import epyqlib.attrsmodel
import epyqlib.treenode
import epyqlib.utils.general
import epyqlib.utils.qt

# See file COPYING in this source tree
__copyright__ = 'Copyright 2017, EPC Power Corp.'
__license__ = 'GPLv2+'


@graham.schemify(tag='parameter')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Parameter(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Parameter',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )
    type_name = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_str_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )
    # TODO: CAMPid 1342975467516679768543165421
    default = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_decimal_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Decimal(allow_none=True, as_string=True),
        ),
    )
    minimum = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_decimal_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Decimal(allow_none=True, as_string=True),
        ),
    )
    maximum = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_decimal_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Decimal(allow_none=True, as_string=True),
        ),
    )
    units = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_str_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )

    enumeration_uuid = epyqlib.attrsmodel.attr_uuid(
        default=None,
        allow_none=True,
    )
    epyqlib.attrsmodel.attrib(
        attribute=enumeration_uuid,
        human_name='Enumeration',
        data_display=epyqlib.attrsmodel.name_from_uuid,
        list_selection_root='enumerations',
    )

    decimal_places = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_int_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Integer(allow_none=True),
        ),
    )
    display_hexadecimal = attr.ib(
        default=False,
        converter=epyqlib.attrsmodel.two_state_checkbox,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Boolean(),
        ),
    )
    nv_format = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_str_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True)
        ),
    )
    nv_factor = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_str_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True)
        ),
    )
    nv_cast = attr.ib(
        default=False,
        converter=epyqlib.attrsmodel.two_state_checkbox,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Boolean(),
        ),
    )
    read_only = attr.ib(
        default=False,
        converter=epyqlib.attrsmodel.two_state_checkbox,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Boolean(),
        ),
    )

    access_level_uuid = epyqlib.attrsmodel.attr_uuid(
        default=None,
        allow_none=True,
        # converter=lambda x: x if x is None else AccessLevelsAccessLevel(x),
        human_name='Access Level',
        data_display=epyqlib.attrsmodel.name_from_uuid,
        list_selection_root='access level',
    )
    parameter_uuid = epyqlib.attrsmodel.attr_uuid(
        default=None,
        allow_none=True,
    )
    comment = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_str_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )
    original_frame_name = attr.ib(
        default=None,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )
    original_multiplexer_name = attr.ib(
        default=None,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )
    original_signal_name = attr.ib(
        default=None,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )
    visibility = epyqlib.attrsmodel.attr_uuid(
        default=None,
        allow_none=True,
        # converter=lambda x: x if x is None else AccessLevelsAccessLevel(x),
        human_name='Visibility',
        data_display=epyqlib.attrsmodel.name_from_uuid,
        list_selection_root='visibility',
    )

    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self, node):
        return isinstance(node, tuple(self.addable_types().values()))

    @PyQt5.QtCore.pyqtProperty('PyQt_PyObject')
    def pyqtify_minimum(self):
        return epyqlib.utils.qt.pyqtify_get(self, 'minimum')

    @pyqtify_minimum.setter
    def pyqtify_minimum(self, value):
        epyqlib.utils.qt.pyqtify_set(self, 'minimum', value)
        if None not in (value, self.maximum):
            if value > self.maximum:
                self.maximum = value

    @PyQt5.QtCore.pyqtProperty('PyQt_PyObject')
    def pyqtify_maximum(self):
        return epyqlib.utils.qt.pyqtify_get(self, 'maximum')

    @pyqtify_maximum.setter
    def pyqtify_maximum(self, value):
        epyqlib.utils.qt.pyqtify_set(self, 'maximum', value)
        if None not in (value, self.minimum):
            if value < self.minimum:
                self.minimum = value

    can_delete = epyqlib.attrsmodel.childless_can_delete


@graham.schemify(tag='group', register=True)
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Group(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Group',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )
    type_name = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_str_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )
    children = attr.ib(
        default=attr.Factory(list),
        cmp=False,
        metadata=graham.create_metadata(
            field=graham.fields.MixedList(fields=(
                # TODO: would be nice to self reference without a name
                marshmallow.fields.Nested('Group'),
                marshmallow.fields.Nested('Array'),
                marshmallow.fields.Nested('Table'),
                marshmallow.fields.Nested(graham.schema(Parameter)),
            )),
        ),
    )
    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self, node):
        return isinstance(node, tuple(self.addable_types().values()))

    def can_delete(self, node=None):
        if node is None:
            return self.tree_parent.can_delete(node=self)

        return True


@graham.schemify(tag='enumerations')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Enumerations(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Enumerations Group',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )
    children = attr.ib(
        default=attr.Factory(list),
        cmp=False,
        metadata=graham.create_metadata(
            field=graham.fields.MixedList(fields=(
                # TODO: would be nice to self reference without a name
                marshmallow.fields.Nested('Enumeration'),
                marshmallow.fields.Nested('AccessLevels'),
            )),
        ),
    )
    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self, node):
        return isinstance(node, tuple(self.addable_types().values()))

    def can_delete(self, node=None):
        if node is None:
            return self.tree_parent.can_delete(node=self)

        return True


@graham.schemify(tag='array_parameter_element')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@epyqlib.utils.qt.pyqtify_passthrough_properties(
    original='original',
    field_names=('nv_format',),
)
@attr.s(hash=False)
class ArrayParameterElement(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Array Parameter Element',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )
    # TODO: CAMPid 1342975467516679768543165421
    default = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_decimal_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Decimal(allow_none=True, as_string=True),
        ),
    )
    minimum = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_decimal_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Decimal(allow_none=True, as_string=True),
        ),
    )
    maximum = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_decimal_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Decimal(allow_none=True, as_string=True),
        ),
    )
    nv_format = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_str_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True)
        ),
    )
    uuid = epyqlib.attrsmodel.attr_uuid()
    original = attr.ib(
        default=None,
        metadata=graham.create_metadata(
            field=epyqlib.attrsmodel.Reference(),
        ),
    )
    epyqlib.attrsmodel.attrib(
        attribute=original,
        no_column=True,
    )

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self, node):
        return False

    can_delete = epyqlib.attrsmodel.childless_can_delete


@graham.schemify(tag='array_group_element')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class ArrayGroupElement(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Array Group Element',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )
    uuid = epyqlib.attrsmodel.attr_uuid()
    original = attr.ib(
        default=None,
        metadata=graham.create_metadata(
            field=epyqlib.attrsmodel.Reference(),
        ),
    )
    epyqlib.attrsmodel.attrib(
        attribute=original,
        no_column=True,
    )

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self, node):
        return False

    can_delete = epyqlib.attrsmodel.childless_can_delete


class InvalidArrayLength(Exception):
    pass


@graham.schemify(tag='array', register=True)
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Array(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Array',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )
    length = attr.ib(
        default=1,
        converter=int,
    )
    named_enumerators = attr.ib(
        default=True,
        converter=epyqlib.attrsmodel.two_state_checkbox,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Boolean(),
        ),
    )
    children = attr.ib(
        default=attr.Factory(list),
        cmp=False,
        metadata=graham.create_metadata(
            field=graham.fields.MixedList(fields=(
                marshmallow.fields.Nested(graham.schema(Parameter)),
                marshmallow.fields.Nested(graham.schema(ArrayParameterElement)),
                marshmallow.fields.Nested(graham.schema(Group)),
                marshmallow.fields.Nested(graham.schema(ArrayGroupElement)),
            )),
        ),
    )
    uuid = epyqlib.attrsmodel.attr_uuid()

    element_types = {
        Parameter: ArrayParameterElement,
        Group: ArrayGroupElement,
    }

    def __attrs_post_init__(self):
        super().__init__()

        self.length = max(1, len(self.children))

        for child in self.children[1:]:
            if self.children[0].uuid != child.original:
                raise epyqlib.attrsmodel.ConsistencyError(
                    'UUID mismatch: {} != {}'.format(
                        self.children[0].uuid,
                        child.original,
                    )
                )

            child.original = self.children[0]

    @property
    def pyqtify_length(self):
        return epyqlib.utils.qt.pyqtify_get(self, 'length')

    @pyqtify_length.setter
    def pyqtify_length(self, value):
        if value < 1:
            raise InvalidArrayLength('Length must be at least 1')

        if self.children is not None:
            if value < len(self.children):
                for row in range(len(self.children) - 1, value - 1, - 1):
                    self.remove_child(row=row)
            elif 1 <= len(self.children) < value:
                for _ in range(value - len(self.children)):
                    original = self.children[0]
                    type_ = self.element_types[type(original)]
                    self.append_child(type_(original=original))

        epyqlib.utils.qt.pyqtify_set(self, 'length', value)

    @classmethod
    def all_addable_types(cls):
        return epyqlib.attrsmodel.create_addable_types(
            [*cls.element_types.keys(), *cls.element_types.values()],
        )

    def addable_types(self):
        child_types = {type(child) for child in self.children}

        value_types = self.element_types.keys()

        if len(child_types.intersection(set(value_types))) == 0:
            types = value_types
        else:
            # types = (ArrayElement,)
            types = ()

        return epyqlib.attrsmodel.create_addable_types(types)

    def can_drop_on(self, node):
        return isinstance(node, tuple(self.addable_types().values()))

    def can_delete(self, node=None):
        if node is None:
            return self.tree_parent.can_delete(node=self)

        if node not in self.children:
            raise epyqlib.attrsmodel.ConsistencyError(
                'Specified node not found in children'
            )

        if len(self.children) > 1:
            return False

        return True


@graham.schemify(tag='table_group_element', register=True)
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class TableGroupElement(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Table Group Element',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )

    children = attr.ib(
        default=attr.Factory(list),
        cmp=False,
        metadata=graham.create_metadata(
            field=graham.fields.MixedList(fields=(
                marshmallow.fields.Nested('TableGroupElement'),
            )),
        ),
    )

    uuid = epyqlib.attrsmodel.attr_uuid()

    ref = attr.ib(factory=list)
    graham.attrib(
        attribute=ref,
        field=marshmallow.fields.Nested(
            'TableGroupElement',
            allow_none=True,
        ),
    )
    epyqlib.attrsmodel.attrib(
        attribute=ref,
        no_column=True,
    )

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self, node):
        return False

    can_delete = epyqlib.attrsmodel.childless_can_delete


@graham.schemify(tag='table_enumeration_reference')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class TableEnumerationReference(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Enumeration Reference',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )

    uuid = epyqlib.attrsmodel.attr_uuid()

    enumeration_uuid = epyqlib.attrsmodel.attr_uuid(
        default=None,
        allow_none=True,
        human_name='Enumeration',
        data_display=epyqlib.attrsmodel.name_from_uuid,
        list_selection_root='enumerations',
    )

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self, node):
        return False
    
    can_delete = epyqlib.attrsmodel.childless_can_delete

    def link(self, enumeration):
        self.enumeration_uuid = enumeration.uuid


@graham.schemify(tag='table', register=True)
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Table(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Table',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )

    children = attr.ib(
        default=attr.Factory(list),
        cmp=False,
        metadata=graham.create_metadata(
            field=graham.fields.MixedList(
                fields=(
                    marshmallow.fields.Nested(graham.schema(Array)),
                    marshmallow.fields.Nested(graham.schema(
                        TableEnumerationReference,
                    )),
                    marshmallow.fields.Nested(graham.schema(TableGroupElement)),
                ),
                exclude=(TableGroupElement,),
            ),
        ),
    )
    uuid = epyqlib.attrsmodel.attr_uuid()

    group = attr.ib(default=None)
    epyqlib.attrsmodel.attrib(
        attribute=group,
        no_column=True,
    )

    def __attrs_post_init__(self):
        super().__init__()

        self._monitor_children = True
        self.pyqt_signals.child_added_complete.connect(self.update)
        self.pyqt_signals.child_removed_complete.connect(self.update)

    @contextlib.contextmanager
    def _ignore_children(self):
        self._monitor_children = False
        yield
        self._monitor_children = True

    def update(self, changed=None):
        if not self._monitor_children:
            return

        old_groups = [
            child
            for child in self.children
            if isinstance(child, TableGroupElement)
        ]

        root = self.find_root()

        enumerations = []

        for child in self.children:
            if not isinstance(child, TableEnumerationReference):
                continue

            if child.enumeration_uuid is None:
                continue

            enumeration, = root.nodes_by_attribute(
                attribute_value=child.enumeration_uuid,
                attribute_name='uuid',
            )

            enumerations.append(enumeration.children)

        arrays = [
            child
            for child in self.children
            if isinstance(child, Array)
        ]

        with self._ignore_children():
            for group in old_groups:
                self.remove_child(child=group)

            self.group = TableGroupElement(
                name='Tree',
            )
            self.append_child(self.group)

        product = list(itertools.product(*enumerations))

        for combination in product:
            present = self.group

            for layer in combination:
                upcoming = present.children_by_attribute(layer, 'ref')
                if len(upcoming) == 1:
                    present, = upcoming
                else:
                    new = TableGroupElement(name=layer.name, ref=layer)
                    present.append_child(new)
                    present = new

            for array in arrays:
                present.append_child(array)

    def addable_types(self):
        return epyqlib.attrsmodel.create_addable_types((
            TableEnumerationReference,
            Array,
        ))

    @classmethod
    def all_addable_types(cls):
        return epyqlib.attrsmodel.create_addable_types((
            TableEnumerationReference,
            Array,
            TableGroupElement,
        ))

    def can_drop_on(self, node):
        return isinstance(node, tuple(self.addable_types().values()))

    def can_delete(self, node=None):
        if node is None:
            return self.tree_parent.can_delete(node=self)

        if node not in self.children:
            raise epyqlib.attrsmodel.ConsistencyError(
                'Specified node not found in children'
            )

        return not isinstance(node, TableGroupElement)


@graham.schemify(tag='enumerator')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Enumerator(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Enumerator',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )
    value = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_decimal_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Integer(allow_none=True),
        ),
    )
    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self):
        return False

    can_delete = epyqlib.attrsmodel.childless_can_delete


@graham.schemify(tag='enumeration', register=True)
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Enumeration(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Enumeration',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )
    children = attr.ib(
        default=attr.Factory(list),
        metadata=graham.create_metadata(
            field=graham.fields.MixedList(fields=(
                marshmallow.fields.Nested(graham.schema(Enumerator)),
            )),
        ),
    )
    # children = attr.ib(
    #     default=attr.Factory(list),
    #     metadata=graham.create_metadata(
    #         field=marshmallow.fields.List(
    #             marshmallow.fields.Nested(graham.schema(Enumerator)),
    #         ),
    #     ),
    # )

    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()

    def items(self):
        for child in self.children:
            yield (child.name, child.value)

    def values(self):
        for child in self.children:
            yield child.value

    def can_drop_on(self):
        return False

    def can_delete(self, node=None):
        if node is None:
            return self.tree_parent.can_delete(node=self)

        return True


@graham.schemify(tag='access_level')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class AccessLevel(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Access Level',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )
    value = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_decimal_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Integer(allow_none=True),
        ),
    )
    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self):
        return False

    can_delete = epyqlib.attrsmodel.childless_can_delete


@graham.schemify(tag='access_levels', register=True)
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class AccessLevels(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Access Levels',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )
    children = attr.ib(
        default=attr.Factory(list),
        metadata=graham.create_metadata(
            field=graham.fields.MixedList(fields=(
                marshmallow.fields.Nested(graham.schema(AccessLevel)),
            )),
        ),
    )

    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()

    def items(self):
        for child in self.children:
            yield (child.name, child.value)

    def values(self):
        for child in self.children:
            yield child.value

    def can_drop_on(self):
        return False

    def can_delete(self, node=None):
        if node is None:
            return self.tree_parent.can_delete(node=self)

        return True

    def by_name(self, name):
        level, = (
            level
            for level in self.children
            if level.name.casefold() == name.casefold()
        )

        return level

    def default(self):
        return min(self.children, key=lambda x: x.value)


Root = epyqlib.attrsmodel.Root(
    default_name='Parameters',
    valid_types=(Parameter, Group, Enumerations)
)

types = epyqlib.attrsmodel.Types(
    types=(
        Root,
        Parameter,
        Group,
        Array,
        ArrayGroupElement,
        ArrayParameterElement,
        Enumeration,
        Enumerator,
        Enumerations,
        AccessLevel,
        AccessLevels,
        Table,
        TableEnumerationReference,
        TableGroupElement,
    ),
)


# TODO: CAMPid 943896754217967154269254167
def merge(name, *types):
    return tuple((x, name) for x in types)


columns = epyqlib.attrsmodel.columns(
    merge('name', *types.types.values()),
    merge('type_name', Parameter, Group),
    merge('length', Array),
    merge('named_enumerators', Array),
    merge('units', Parameter),
    merge('enumeration_uuid', Parameter, TableEnumerationReference),

    merge('value', Enumerator, AccessLevel),
    merge('default', Parameter, ArrayParameterElement),
    merge('minimum', Parameter, ArrayParameterElement),
    merge('maximum', Parameter, ArrayParameterElement),

    merge('nv_format', Parameter, ArrayParameterElement),
    merge('nv_factor', Parameter),
    merge('nv_cast', Parameter),
    merge('read_only', Parameter),
    merge('access_level_uuid', Parameter),
    merge('visibility', Parameter),

    merge('display_hexadecimal', Parameter),
    merge('decimal_places', Parameter),

    merge('comment', Parameter),

    merge('original_frame_name', Parameter),
    merge('original_multiplexer_name', Parameter),
    merge('original_signal_name', Parameter),

    merge('parameter_uuid', Parameter),
    merge('uuid', *types.types.values()),

)
