import enum
import itertools

import attr

import epyqlib.pm.groups


# names = {
#     cls: {
#         attribute.name for attribute in attr.fields(cls)
#     }
#     for cls, names in {
#         epyqlib.pm.groups.Limits: {
#         },
#         epyqlib.pm.groups.Parameter: {
#             # TODO: automate this?  but still with manual override, and
#             #       maybe just leave it manual to avoid unexpected changes in
#             #       c code.  though sparse like this still lets surprises
#             #       through for name, type, etc
#             'hardware_limits': 'hardwareLimits',
#             'factory_limits': 'factoryLimits',
#             'customer_limits': 'customerLimits',
#         },
#     }.items()
# }


# TODO: CAMPid 978597542154245264521645215421964521
def snake_case_to_lower_camel(name):
    segments = name.split('_')
    segments = itertools.chain(
        segments[0].lower(),
        *(''.join(itertools.chain(
            c[0].upper(), c[1:].lower(),
        )) for c in segments[1:]),
    )
    return ''.join(segments)


def automatic_names(cls):
    return {
        field.name: snake_case_to_lower_camel(field.name)
        for field in attr.fields(cls)
    }


@attr.s
class Member:
    name = attr.ib()
    ctype = attr.ib()


limits = epyqlib.pm.groups.Limits(
    # **automatic_names(epyqlib.pm.groups.Limits),
    # type='Limits',
    minimum=Member(name='minimum', ctype=),
    minimum=Member(name='maximum', ctype=),
    type=
)

names = {
    epyqlib.pm.groups.Limits: limits,
    epyqlib.pm.groups.Parameter: epyqlib.pm.groups.Parameter(
        name='',
        type='type',
        # value='value',
        id='id',
        applicability='applicability',
        comment='comment',
        access='access',
        default='default',
        hardware_limits='hardwareLimits',
        factory_limits='factoryLimits',
        customer_limits='customerLimits',
        # customer_limits=Value(name='customerLimits', type=)
    ),
}


@attr.s
class CType:
    name = attr.ib()
    short = attr.ib()


class Types(enum.Enum):
    uint16_t = CType(name='uint16_t', short='u16')
    sint16_t = CType(name='sint16_t', short='s16')


# def typedef_lines(parameter):
#     cls = type(parameter)
#
#     parameters_struct_typedef = [
#         'typedef struct',
#         '{',
#         *[
#             '{type} {name}'.format(
#                 type=
#             )
#             for field in attr.fields(cls)
#             if getattr(names[cls], field.name).struct_member
#         ],
#         '}} {};'.format(names[cls].name.name),
#     ]


def limits_typedef_lines(c_type):
    cls = epyqlib.pm.groups.Limits

    lines = [
        'typedef struct',
        '{',
        *[
            '{type} {name}'.format(
                type=c_type.name,
                name=field.name,
            )
            for field in attr.fields(cls)
            if getattr(names[cls], field.name).struct_member
        ],
        '}} {}{};'.format(names[cls].name.name),
    ]


limits_typedefs_lines = list(itertools.chain(
    limits_typedef_lines(c_type)
    for c_type in Types
))




# def parameter_typedef_lines(parameter):
#     cls = type(parameter)
#
#     lines = [
#         'typedef struct',
#         '{',
#         *[
#             '{type} {name}'.format(
#                 type=
#             )
#             for field in attr.fields(cls)
#             if getattr(names[cls], field.name).struct_member
#         ],
#         '}} {};'.format(names[cls].name.name),
#     ]

# names = {
#     epyqlib.pm.groups.Limits: {
#     },
#     epyqlib.pm.groups.Parameter: {
#         # TODO: automate this?  but still with manual override, and
#         #       maybe just leave it manual to avoid unexpected changes in
#         #       c code.  though sparse like this still lets surprises
#         #       through for name, type, etc
#         'hardware_limits': 'hardwareLimits',
#         'factory_limits': 'factoryLimits',
#         'customer_limits': 'customerLimits',
#     },
# }
