import epyqlib.pm.generate.c
import epyqlib.pm.groups
import epyqlib.pm.protocols
import epyqlib.pm.types
import epyqlib.pm.values


def test_exploration():
    frequency_reference = epyqlib.pm.groups.Parameter(
        name='Frequency Reference',
        comment='Desired output frequency while in grid forming mode.',
        type=epyqlib.pm.types.Types.number,
        default=60,
        customer_limits=epyqlib.pm.groups.Limits(
            minimum=45,
            maximum=65,
        ),
    )


    overmodulation_limit = epyqlib.pm.groups.Parameter(
        name='Overmodulation Limit',
        type=epyqlib.pm.types.Types.number,
    )


    map_to_can = {
        frequency_reference: epyqlib.pm.protocols.Type(
            name='FrequencyReference',
            type=epyqlib.pm.types.CanUnsignedInteger(bits=16),
            scaling=10,
        ),
        overmodulation_limit: epyqlib.pm.protocols.Type(
            name='OvermodulationLimit',
            type=epyqlib.pm.types.CanUnsignedInteger(bits=16),
        ),
    }


    map_to_c = {
        overmodulation_limit: epyqlib.pm.protocols.Type(
            name='overmodulationLimit',
            type=epyqlib.pm.types.C.uint16_t,
        ),
    }


def test_overlay():
    layers = (
        epyqlib.pm.groups.Limits(
            minimum=None,
            maximum=100,
        ),
        epyqlib.pm.groups.Limits(
            minimum=None,
            maximum=200,
        ),
        epyqlib.pm.groups.Limits(
            minimum=-10,
            maximum=300,
        ),
        epyqlib.pm.groups.Limits(
            minimum=-20,
            maximum=400,
        ),
    )

    expected = epyqlib.pm.groups.Limits(
        minimum=-10,
        maximum=100,
    )

    assert epyqlib.pm.groups.overlay(layers) == expected


def test_limits_complete():
    assert not epyqlib.pm.groups.Limits(
        minimum=None,
        maximum=0,
    ).complete()

    assert not epyqlib.pm.groups.Limits(
        minimum=0,
        maximum=None,
    ).complete()

    assert epyqlib.pm.groups.Limits(
        minimum=0,
        maximum=0,
    ).complete()


def test_c_name_conversion():
    examples = (
        ('abc', 'abc'),
        ('a_bc', 'aBc'),
        ('a_b_c', 'aBC'),
    )

    for pre, post in examples:
        assert epyqlib.pm.generate.c.snake_case_to_lower_camel(pre) == post


def test_c_names():
    examples = (
        (epyqlib.pm.groups.Limits, 'minimum', 'minimum'),
        (epyqlib.pm.groups.Parameter, 'name', 'name'),
        (epyqlib.pm.groups.Parameter, 'customer_limits', 'customerLimits'),
    )

    for cls, pre, post in examples:
        assert getattr(
            epyqlib.pm.generate.c.names[cls],
            pre
        ) == post
