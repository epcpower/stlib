import attr
import graham
import marshmallow

import epyqlib.attrsmodel
import epyqlib.pm.parametermodel
import epyqlib.treenode


def create_blank(parameter_model=None):
    value_set = ValueSet(parameter_model=parameter_model)
    _post_load(value_set)

    return value_set


def _post_load(value_set):
    if value_set.path is None:
        value_set.model = epyqlib.attrsmodel.Model(
            root=Root(),
            columns=columns,
        )
    else:
        raise NotImplementedError()

    if value_set.parameter_model is not None:
        def traverse(node, _):
            if isinstance(node, epyqlib.pm.parametermodel.Parameter):
                value_set.model.root.append_child(
                    Parameter(
                        name=node.name,
                        parameter_uuid=node.uuid,
                    ),
                )

        value_set.parameter_model.root.traverse(
            call_this=traverse,
            internal_nodes=False,
        )


def name_attrib():
    attrib = attr.ib(
        convert=str,
    )
    graham.attrib(
        attribute=attrib,
        field=marshmallow.fields.String(dump_only=True),
    )

    return attrib


def decimal_attrib(**kwargs):
    attrib = attr.ib(
        convert=epyqlib.attrsmodel.to_decimal_or_none,
        **kwargs,
    )
    graham.attrib(
        attribute=attrib,
        field=marshmallow.fields.Decimal(
            allow_none=kwargs.get('default', False) is None,
            as_string=True,
        ),
    )
    
    return attrib


@graham.schemify(tag='parameter')
@epyqlib.attrsmodel.ify()
@epyqlib.utils.qt.pyqtify()
@attr.s(hash=False)
class Parameter(epyqlib.treenode.TreeNode):
    name = name_attrib()

    value = decimal_attrib(default=None)
    user_default = decimal_attrib(default=None)
    factory_default = decimal_attrib(default=None)
    minimum = decimal_attrib(default=None)
    maximum = decimal_attrib(default=None)

    parameter_uuid = epyqlib.attrsmodel.attr_uuid(
        default=None,
        allow_none=True,
    )
    epyqlib.attrsmodel.attrib(
        attribute=parameter_uuid,
        human_name='Parameter UUID',
    )

    uuid = epyqlib.attrsmodel.attr_uuid()

    def __attrs_post_init__(self):
        super().__init__()

    def can_drop_on(self, node):
        return False

    can_delete = epyqlib.attrsmodel.childless_can_delete


Root = epyqlib.attrsmodel.Root(
    default_name='Value Set',
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
    parameter_model = attr.ib()
    model = attr.ib(default=None)
    path = attr.ib(default=None)


# TODO: CAMPid 943896754217967154269254167
def merge(name, *types):
    return tuple((x, name) for x in types)


columns = epyqlib.attrsmodel.columns(
    merge('name', *types.types.values()),
    merge('value', Parameter),
    merge('user_default', Parameter),
    merge('factory_default', Parameter),
    merge('minimum', Parameter),
    merge('maximum', Parameter),
    merge('parameter_uuid', Parameter),
    merge('uuid', *types.types.values()),
)
