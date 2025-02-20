import pathlib

import attr
import graham
import marshmallow

import epyqlib.attrsmodel
import epyqlib.nv
import epyqlib.pm.parametermodel
import epyqlib.treenode


class SaveCancelled(Exception):
    pass


def create_blank(parameter_model=None):
    value_set = ValueSet(parameter_model=parameter_model)
    _post_load(value_set)

    return value_set


def loads(s, path=None):
    root = graham.schema(Root).loads(s).data
    value_set = ValueSet(path=path)

    if path is not None:
        value_set.path = pathlib.Path(path).absolute()

    _post_load(value_set, root=root)

    return value_set


def load(f):
    value_set = loads(f.read(), path=f.name)

    return value_set


def loadp(path):
    with open(path) as f:
        return load(f)


def _post_load(value_set, root=None):
    if root is None:
        root = Root()

    if value_set.model is None:
        value_set.model = epyqlib.attrsmodel.Model(
            root=root,
            columns=columns,
        )


def copy_parameter_data(
    value_set,
    human_names=True,
    base_node=None,
    calculate_unspecified_min_max=False,
    can_root=None,
):
    def traverse(node, _):
        if isinstance(node, epyqlib.pm.parametermodel.Parameter):
            if human_names:
                name = node.name
            else:
                name = ":".join(
                    (
                        node.original_multiplexer_name,
                        node.original_signal_name,
                    )
                )

            minimum = node.minimum
            maximum = node.maximum

            if calculate_unspecified_min_max and None in (minimum, maximum):
                (query_multiplexed_message,) = can_root.nodes_by_attribute(
                    attribute_value="Parameter Query",
                    attribute_name="name",
                )
                (signal,) = query_multiplexed_message.nodes_by_attribute(
                    attribute_value=node.uuid,
                    attribute_name="parameter_uuid",
                )

                calculated_minimum, calculated_maximum = signal.calculated_min_max()

                if minimum is None:
                    minimum = calculated_minimum

                if maximum is None:
                    maximum = calculated_maximum

            value_set.model.root.append_child(
                Parameter(
                    name=name,
                    parameter_uuid=node.uuid,
                    factory_default=node.default,
                    minimum=minimum,
                    maximum=maximum,
                ),
            )

            value_set.model.root.children.sort()

    if base_node is None:
        base_node = value_set.parameter_model.root

    base_node.traverse(
        call_this=traverse,
        internal_nodes=False,
    )


def decimal_attrib(load_only=False, **kwargs):
    attrib = attr.ib(
        converter=epyqlib.attrsmodel.to_decimal_or_none,
        **kwargs,
    )
    graham.attrib(
        attribute=attrib,
        field=marshmallow.fields.Decimal(
            allow_none=kwargs.get("default", False) is None,
            as_string=True,
            load_only=load_only,
        ),
    )

    return attrib


@graham.schemify(tag="parameter")
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Parameter(epyqlib.treenode.TreeNode):
    name = attr.ib(
        default="New Parameter",
        converter=str,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )

    value = decimal_attrib(default=None)
    user_default = decimal_attrib(default=None, load_only=True)
    factory_default = decimal_attrib(default=None, load_only=True)
    minimum = decimal_attrib(default=None, load_only=True)
    maximum = decimal_attrib(default=None, load_only=True)

    parameter_uuid = epyqlib.attrsmodel.attr_uuid(
        default=None,
        allow_none=True,
    )

    epyqlib.attrsmodel.attrib(
        attribute=parameter_uuid,
        human_name="Parameter UUID",
    )

    readable = attr.ib(
        default=None,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Boolean(allow_none=True),
        ),
    )
    writable = attr.ib(
        default=None,
        metadata=graham.create_metadata(
            field=marshmallow.fields.Boolean(allow_none=True),
        ),
    )

    uuid = epyqlib.attrsmodel.attr_uuid(load_only=True)

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self, node):
        return False

    can_delete = epyqlib.attrsmodel.childless_can_delete
    remove_old_on_drop = epyqlib.attrsmodel.default_remove_old_on_drop
    child_from = epyqlib.attrsmodel.default_child_from
    internal_move = epyqlib.attrsmodel.default_internal_move
    check = epyqlib.attrsmodel.check_just_children


Root = epyqlib.attrsmodel.Root(
    default_name="Value Set",
    valid_types=(Parameter,),
)

types = epyqlib.attrsmodel.Types(
    types=(
        Root,
        Parameter,
    ),
)


@attr.s
class ValueSet:
    parameter_model = attr.ib(default=None)
    model = attr.ib(default=None)
    path = attr.ib(default=None)
    filters = attr.ib(
        default=(
            ("Parameter Value Set", ["pmvs"]),
            ("All Files", ["*"]),
        )
    )

    def save(self, path=None, parent=None):
        if path is None:
            path = self.path

        if path is None:
            path = epyqlib.utils.qt.file_dialog(
                filters=self.filters,
                parent=parent,
                save=True,
                caption="Save Value Set As",
            )

            if path is None:
                raise SaveCancelled()

            self.path = pathlib.Path(path)

        sorted_children = sorted(self.model.root.children)

        sorted_root = attr.evolve(self.model.root, children=sorted_children)

        s = graham.dumps(sorted_root, indent=4).data

        with open(path, "w") as f:
            f.write(s)

            if not s.endswith("\n"):
                f.write("\n")

    def overlay(self, overlay):
        attribute_names = [
            "value",
            "minimum",
            "maximum",
        ]

        parameter_from_parameter_uuid = {
            parameter.parameter_uuid: parameter
            for parameter in self.model.root.children
        }

        for overlay_parameter in overlay.model.root.children:
            base_parameter = parameter_from_parameter_uuid.get(
                overlay_parameter.parameter_uuid,
            )
            if base_parameter is None:
                self.model.root.append_child(attr.evolve(overlay_parameter))
                continue

            for name in attribute_names:
                value = getattr(overlay_parameter, name)
                if value is not None:
                    setattr(base_parameter, name, value)

    def strip_common(self, reference):
        reference_parameter_by_uuid = {
            parameter.parameter_uuid: parameter
            for parameter in reference.model.root.children
        }

        drop_list = []

        for output_parameter in self.model.root.children:
            reference_parameter = reference_parameter_by_uuid.get(
                output_parameter.parameter_uuid,
            )
            if reference_parameter is None:
                continue

            if not output_parameter.writable:
                drop_list.append(output_parameter)
                continue

            if output_parameter.value is None:
                drop_list.append(output_parameter)
                continue

            for meta in epyqlib.nv.MetaEnum.non_value:
                setattr(output_parameter, meta.name, None)

            if reference_parameter.value == output_parameter.value:
                drop_list.append(output_parameter)

        for parameter in drop_list:
            self.model.root.remove_child(child=parameter)


# TODO: CAMPid 943896754217967154269254167
def merge(name, *types):
    return tuple((x, name) for x in types)


columns = epyqlib.attrsmodel.columns(
    merge("name", *types.types.values()),
    merge("value", Parameter),
    merge("minimum", Parameter),
    merge("maximum", Parameter),
    merge("readable", Parameter),
    merge("writable", Parameter),
    merge("parameter_uuid", Parameter),
    merge("uuid", *types.types.values()),
)
