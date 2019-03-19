import contextlib
import itertools
import uuid

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


def create_abbreviation_attribute():
    return attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_str_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )


def create_read_only_attribute():
    return attr.ib(
        default=False,
        converter=epyqlib.attrsmodel.two_state_checkbox,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Boolean(),
        ),
    )


create_notes_attribute = epyqlib.attrsmodel.create_str_or_none_attribute


@graham.schemify(tag='parameter')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Parameter(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Parameter',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )
    abbreviation = create_abbreviation_attribute()
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
        delegate=epyqlib.attrsmodel.RootDelegateCache(
            list_selection_root='enumerations',
        )
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

    embedded_getter = epyqlib.attrsmodel.create_str_or_none_attribute()
    embedded_setter = epyqlib.attrsmodel.create_str_or_none_attribute()

    read_only = create_read_only_attribute()

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
    notes = create_notes_attribute()
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
    visibility = epyqlib.attrsmodel.attr_uuid_list(
        default=None,
        allow_none=True,
    )
    epyqlib.attrsmodel.attrib(
        attribute=visibility,
        human_name='Visibility',
        data_display=epyqlib.attrsmodel.names_from_uuid_list,
        delegate=epyqlib.attrsmodel.RootDelegateCache(
            list_selection_root='visibility',
            multi_select=True,
        )
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
    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


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
        repr=False,
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

    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


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
        repr=False,
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

    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


@graham.schemify(tag='array_parameter_element')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@epyqlib.utils.qt.pyqtify_passthrough_properties(
    original='original',
    field_names=(
        'nv_format',
        'nv_factor',
        'nv_cast',
        'access_level_uuid',
        'comment',
        'decimal_places',
        'display_hexadecimal',
        'enumeration_uuid',
        'units',
        'visibility',
    ),
)
@attr.s(hash=False)
class ArrayParameterElement(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Array Parameter Element',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )

    abbreviation = create_abbreviation_attribute()
    notes = create_notes_attribute()
    read_only = create_read_only_attribute()

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
    uuid = epyqlib.attrsmodel.attr_uuid()
    access_level_uuid = epyqlib.attrsmodel.attr_uuid(
        default=None,
        allow_none=True,
        # converter=lambda x: x if x is None else AccessLevelsAccessLevel(x),
        human_name='Access Level',
        data_display=epyqlib.attrsmodel.name_from_uuid,
        list_selection_root='access level',
    )
    enumeration_uuid = epyqlib.attrsmodel.attr_uuid(
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
    units = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_str_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )
    visibility = epyqlib.attrsmodel.attr_uuid_list(
        default=None,
        allow_none=True,
    )
    epyqlib.attrsmodel.attrib(
        attribute=visibility,
        human_name='Visibility',
        data_display=epyqlib.attrsmodel.names_from_uuid_list,
        delegate=epyqlib.attrsmodel.RootDelegateCache(
            list_selection_root='visibility',
            multi_select=True,
        )
    )
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
    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


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
    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


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
        repr=False,
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

    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


@graham.schemify(tag='table_array_element', register=True)
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@epyqlib.utils.qt.pyqtify_passthrough_properties(
    original='original',
    field_names=(
        'name',
        'abbreviation',
        'notes',
        'read_only',
        'access_level_uuid',
        'enumeration_uuid',
        'minimum',
        'maximum',
        'nv_format',
        'nv_factor',
        'nv_cast',
        'comment',
        'units',
        'visibility',
        'display_hexadecimal',
        'default',
        'decimal_places',
    ),
)
@attr.s(hash=False)
class TableArrayElement(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default=None,
        convert=epyqlib.attrsmodel.to_str_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True)
        ),
    )

    abbreviation = create_abbreviation_attribute()
    notes = create_notes_attribute()
    read_only = create_read_only_attribute()

    path = attr.ib(
        factory=tuple,
    )
    epyqlib.attrsmodel.attrib(
        attribute=path,
        no_column=True,
    )
    graham.attrib(
        attribute=path,
        field=graham.fields.Tuple(marshmallow.fields.UUID()),
    )

    access_level_uuid = epyqlib.attrsmodel.attr_uuid(
        default=None,
        allow_none=True,
        # converter=lambda x: x if x is None else AccessLevelsAccessLevel(x),
        human_name='Access Level',
        data_display=epyqlib.attrsmodel.name_from_uuid,
        list_selection_root='access level',
        no_graham=True,
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
    comment = attr.ib(
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
    units = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_str_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )
    visibility = epyqlib.attrsmodel.attr_uuid_list(
        default=None,
        allow_none=True,
    )
    epyqlib.attrsmodel.attrib(
        attribute=visibility,
        human_name='Visibility',
        data_display=epyqlib.attrsmodel.names_from_uuid_list,
        delegate=epyqlib.attrsmodel.RootDelegateCache(
            list_selection_root='visibility',
            multi_select=True,
        )
    )
    display_hexadecimal = attr.ib(
        default=False,
        converter=epyqlib.attrsmodel.two_state_checkbox,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Boolean(),
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
    decimal_places = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_int_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Integer(allow_none=True),
        ),
    )

    index = attr.ib(
        default=None,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Integer(allow_none=False),
        )
    )
    epyqlib.attrsmodel.attrib(
        attribute=index,
        editable=False,
        no_column=True,
    )

    uuid = epyqlib.attrsmodel.attr_uuid()

    original = attr.ib(
        default=None,
        repr=False,
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
    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


@graham.schemify(tag='table_group_element', register=True)
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@epyqlib.utils.qt.pyqtify_passthrough_properties(
    original='original',
    field_names=('name',),
)
@attr.s(hash=False)
class TableGroupElement(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default=None,
        convert=epyqlib.attrsmodel.to_str_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True)
        ),
    )

    path = attr.ib(
        factory=tuple,
    )
    epyqlib.attrsmodel.attrib(
        attribute=path,
        no_column=True,
    )
    graham.attrib(
        attribute=path,
        field=graham.fields.Tuple(marshmallow.fields.UUID()),
    )

    children = attr.ib(
        default=attr.Factory(list),
        cmp=False,
        repr=False,
        metadata=graham.create_metadata(
            field=graham.fields.MixedList(fields=(
                marshmallow.fields.Nested('TableGroupElement'),
                marshmallow.fields.Nested(graham.schema(TableArrayElement)),
            )),
        ),
    )

    axis = attr.ib(
        default=None,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        )
    )
    epyqlib.attrsmodel.attrib(
        attribute=axis,
        editable=False,
        no_column=True,
    )

    curve_index = attr.ib(
        default=None,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Integer(allow_none=True),
        )
    )
    epyqlib.attrsmodel.attrib(
        attribute=curve_index,
        editable=False,
        no_column=True,
    )

    uuid = epyqlib.attrsmodel.attr_uuid()

    original = attr.ib(default=None)
    epyqlib.attrsmodel.attrib(
        attribute=original,
        no_column=True,
    )

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self, node):
        return False

    def can_delete(self, node=None):
        return False

    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


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

    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


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

    embedded_getter = attr.ib(
        default=None,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )

    embedded_setter = attr.ib(
        default=None,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )

    active_curve_getter = attr.ib(
        default=None,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )

    active_curve_setter = attr.ib(
        default=None,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )

    children = attr.ib(
        default=attr.Factory(list),
        cmp=False,
        repr=False,
        metadata=graham.create_metadata(
            field=graham.fields.MixedList(
                fields=(
                    marshmallow.fields.Nested(graham.schema(Array)),
                    marshmallow.fields.Nested(graham.schema(Group)),
                    marshmallow.fields.Nested(graham.schema(
                        TableEnumerationReference,
                    )),
                    marshmallow.fields.Nested(graham.schema(TableGroupElement)),
                ),
            ),
        ),
    )
    uuid = epyqlib.attrsmodel.attr_uuid()

    group = attr.ib(default=None)
    epyqlib.attrsmodel.attrib(
        attribute=group,
        no_column=True,
    )

    combinations = attr.ib(default=None)
    epyqlib.attrsmodel.attrib(
        attribute=combinations,
        no_column=True,
    )

    arrays = attr.ib(default=None)
    epyqlib.attrsmodel.attrib(
        attribute=arrays,
        no_column=True,
    )

    arrays_and_groups = attr.ib(default=None)
    epyqlib.attrsmodel.attrib(
        attribute=arrays_and_groups,
        no_column=True,
    )

    curve_group_combinations = attr.ib(default=None)
    epyqlib.attrsmodel.attrib(
        attribute=curve_group_combinations,
        no_column=True,
    )

    def __attrs_post_init__(self):
        super().__init__()

        self._monitor_children = True
        self.pyqt_signals.child_added_complete.connect(self.update)
        self.pyqt_signals.child_removed_complete.connect(self.update)

        self.pyqt_signals.child_added_complete.connect(self.array_added)
        self.pyqt_signals.child_removed_complete.connect(self.array_removed)

        self.array_connections = {}

    @contextlib.contextmanager
    def _ignore_children(self):
        self._monitor_children = False
        yield
        self._monitor_children = True

    def array_added(self, array):
        if not isinstance(array, Array):
            return

        self.array_connections[array] = epyqlib.utils.qt.Connections(
            signal=epyqlib.utils.qt.pyqtify_signals(array).length,
            slot=self.update,
        )


    def array_removed(self, array):
        if not isinstance(array, Array):
            return

        connections = self.array_connections.pop(array)
        connections.disconnect()

    def update_array_connections(self):
        for array in list(self.array_connections.keys()):
            self.array_removed(array)

        arrays = [
            child
            for child in self.children
            if isinstance(child, Array)
        ]

        for array in arrays:
            self.array_added(array)

    def update(self, changed=None):
        if not self._monitor_children:
            return

        self.update_array_connections()

        old_groups = [
            child
            for child in self.children
            if isinstance(child, TableGroupElement)
        ]

        if len(old_groups) == 1:
            old_group, = old_groups
        elif len(old_groups) < 1:
            old_group = None
        else:
            raise Exception('Too many old groups found while updating ')

        root = self.find_root()

        enumerations = []

        for child in self.children:
            if not isinstance(child, TableEnumerationReference):
                continue

            if child.enumeration_uuid is None:
                continue

            enumeration = root.model.node_from_uuid(child.enumeration_uuid)

            enumerations.append(enumeration.children)

        arrays = [
            child
            for child in self.children
            if isinstance(child, (Array, Group))
        ]
        self.arrays_and_groups = arrays
        self.arrays = [
            child
            for child in self.children
            if isinstance(child, Array)
        ]
        self.groups = [
            child
            for child in self.children
            if isinstance(child, Group)
        ]

        with self._ignore_children():
            if old_group is None:
                old_group = TableGroupElement(
                    name='Tree',
                )
                self.append_child(old_group)

            self.group = old_group

            nodes = old_group.recursively_remove_children()

            old_by_path = {
                node.path: node
                for node in nodes
            }

        product = list(itertools.product(*enumerations))

        self.combinations = product

        self.curve_group_combinations = tuple(
            epyqlib.utils.general.ordered_unique(
                tuple(
                    x
                    for x in itertools.takewhile(
                        lambda y: y.tree_parent.name != 'Curves',
                        combination,
                    )
                )
                for combination in self.combinations
            )
        )

        model = self.find_root().model

        for combination in product:
            present = old_group

            path = ()

            for layer in combination:
                path += (layer.uuid,)

                previous = old_by_path.get(path)
                if previous is None:
                    current = TableGroupElement(
                        original=layer,
                        path=path,
                    )
                    old_by_path[path] = current
                else:
                    current = previous
                    if current.original is None:
                        current.original = current.path[-1]
                    if isinstance(current.original, uuid.UUID):
                        current.original = model.node_from_uuid(current.original)

                if layer.tree_parent.name == 'Curves':
                    current.curve_index = int(layer.value)

                if current.tree_parent is None:
                    present.append_child(current)

                present = current

            axes = ['x', 'y', 'z']
            axes_iterator = iter(axes)
            for array in arrays:
                if isinstance(array, Array):
                    try:
                        axis = next(axes_iterator)
                    except StopIteration:
                        raise
                else:
                    axis = None
                array_path = path + (array.uuid,)
                previous = old_by_path.get(array_path)
                if previous is None:
                    current = TableGroupElement(
                        original=array,
                        path=array_path,
                    )
                    old_by_path[array_path] = current
                else:
                    current = previous
                    if current.original is None:
                        current.original = current.path[-1]
                    if isinstance(current.original, uuid.UUID):
                        current.original = model.node_from_uuid(
                            current.original
                        )

                current.axis = axis

                if current.tree_parent is None:
                    present.append_child(current)

                for index, element in enumerate(array.children):
                    element_path = array_path + (element.uuid,)
                    previous_element = old_by_path.get(element_path)
                    if previous_element is None:
                        current_element = TableArrayElement(
                            original=element,
                            path=element_path,
                        )
                        old_by_path[element_path] = current_element
                    else:
                        current_element = previous_element
                        if current_element.original is None:
                            current_element.original = current_element.path[-1]
                        if isinstance(current_element.original, uuid.UUID):
                            current_element.original = model.node_from_uuid(
                                current_element.original
                            )

                    current_element.index = index

                    if current_element.tree_parent is None:
                        current.append_child(current_element)

    def addable_types(self):
        return epyqlib.attrsmodel.create_addable_types((
            TableEnumerationReference,
            Array,
            Group,
        ))

    @classmethod
    def all_addable_types(cls):
        return epyqlib.attrsmodel.create_addable_types((
            TableEnumerationReference,
            Array,
            Group,
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

    def internal_move(self, node, node_to_insert_before):
        with self._ignore_children():
            self.remove_child(child=node)
            if node_to_insert_before is None:
                self.append_child(node)
            else:
                self.insert_child(
                    i=self.children.index(node_to_insert_before),
                    child=node,
                )

        return True

    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    check = epyqlib.attrsmodel.check_just_children


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

    def can_drop_on(self, node):
        return False

    can_delete = epyqlib.attrsmodel.childless_can_delete
    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


@graham.schemify(tag='sunspec_enumerator')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class SunSpecEnumerator(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default='New Sunspec Enumerator',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )
    label = attr.ib(
        default='',
        convert=epyqlib.attrsmodel.to_str_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(allow_none=True),
        ),
    )
    description = attr.ib(
        default='',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )
    notes = create_notes_attribute()
    value = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_decimal_or_none,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Integer(allow_none=True),
        ),
    )
    type = attr.ib(
        default='',
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )
    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self, node):
        return False

    can_delete = epyqlib.attrsmodel.childless_can_delete
    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


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
        repr=False,
        metadata=graham.create_metadata(
            field=graham.fields.MixedList(fields=(
                marshmallow.fields.Nested(graham.schema(Enumerator)),
                marshmallow.fields.Nested(graham.schema(SunSpecEnumerator)),
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

    def can_drop_on(self, node):
        return isinstance(node, Enumerator)

    def can_delete(self, node=None):
        if node is None:
            return self.tree_parent.can_delete(node=self)

        return True

    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


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

    def can_drop_on(self, node):
        return False

    can_delete = epyqlib.attrsmodel.childless_can_delete
    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


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
        repr=False,
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

    def can_drop_on(self, node):
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

    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


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
        SunSpecEnumerator,
        Enumerations,
        AccessLevel,
        AccessLevels,
        Table,
        TableEnumerationReference,
        TableArrayElement,
        TableGroupElement,
    ),
    external_list_selection_roots={'sunspec types'},
)


# TODO: CAMPid 943896754217967154269254167
def merge(name, *types):
    return tuple((x, name) for x in types)


columns = epyqlib.attrsmodel.columns(
    merge('name', *types.types.values()),
    merge('abbreviation', Parameter, ArrayParameterElement, TableArrayElement),
    (
        merge('type_name', Parameter, Group)
        + merge('type', SunSpecEnumerator)
    ),
    merge('length', Array),
    merge('named_enumerators', Array),
    merge(
        'units',
        Parameter,
        ArrayParameterElement,
        TableArrayElement,
    ),
    merge(
        'enumeration_uuid',
        Parameter,
        TableEnumerationReference,
        ArrayParameterElement,
        TableArrayElement,
    ),

    merge('value', Enumerator, SunSpecEnumerator, AccessLevel),
    merge(
        'default',
        Parameter,
        ArrayParameterElement,
        TableArrayElement,
    ),
    merge(
        'minimum',
        Parameter,
        ArrayParameterElement,
        TableArrayElement,
    ),
    merge(
        'maximum',
        Parameter,
        ArrayParameterElement,
        TableArrayElement,
    ),

    merge('label', SunSpecEnumerator),

    merge('embedded_getter', Table, Parameter),
    merge('embedded_setter', Table, Parameter),
    merge('active_curve_getter', Table),
    merge('active_curve_setter', Table),
    merge(
        'nv_format',
        Parameter,
        ArrayParameterElement,
        TableArrayElement,
    ),
    merge(
        'nv_factor',
        Parameter,
        TableArrayElement,
        ArrayParameterElement,
    ),
    merge(
        'nv_cast',
        Parameter,
        TableArrayElement,
        ArrayParameterElement,
    ),
    merge('read_only', Parameter, ArrayParameterElement, TableArrayElement),
    merge(
        'access_level_uuid',
        Parameter,
        TableArrayElement,
        ArrayParameterElement,
    ),
    merge(
        'visibility',
        Parameter,
        ArrayParameterElement,
        TableArrayElement,
    ),

    merge(
        'display_hexadecimal',
        Parameter,
        ArrayParameterElement,
        TableArrayElement,
    ),
    merge(
        'decimal_places',
        Parameter,
        ArrayParameterElement,
        TableArrayElement,
    ),

    (
        merge(
            'comment',
            Parameter,
            ArrayParameterElement,
            TableArrayElement,
        )
        +
        merge('description', SunSpecEnumerator)
    ),

    merge(
        'notes',
        Parameter,
        SunSpecEnumerator,
        ArrayParameterElement,
        TableArrayElement,
    ),

    merge('original_frame_name', Parameter),
    merge('original_multiplexer_name', Parameter),
    merge('original_signal_name', Parameter),

    merge('parameter_uuid', Parameter),
    merge('uuid', *types.types.values()),

)
