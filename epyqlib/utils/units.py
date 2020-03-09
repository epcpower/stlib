import pint


registry = pint.UnitRegistry()
registry.define('percent = 0.01*count = %')


def to_unitless(value, unit):
    if isinstance(value, pint.Quantity):
        return value.to(unit).magnitude

    return value
