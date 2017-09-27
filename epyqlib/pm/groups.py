import uuid

import attr

import epyqlib.pm.access


def overlay(layers, cls=None):
    if cls is None:
        cls = type(layers[0])

    fields = {field.name: None for field in attr.fields(cls)}

    for name in fields:
        for layer in layers:
            value = getattr(layer, name)
            if value is not None:
                fields[name] = value
                break

    return cls(**fields)


@attr.s
class Limits:
    minimum = attr.ib()
    maximum = attr.ib()
    enabled = attr.ib()
    type = attr.ib()

    def complete(self):
        return self.minimum is not None and self.maximum is not None

    def __contains__(self, value):
        return (
            self.complete()
            and self.minimum <= value <= self.maximum
        )

    def validate(self):
        if None in (self.maximum, self.minimum):
            return

        if self.minimum >= self.maximum:
            raise Exception('Minimum must be less than or equal to maximum.')


to_all = object()


# TODO: using object.__hash__ is a bit evil
@attr.s(hash=False)
class Parameter:
    name = attr.ib()
    type = attr.ib()
    value = attr.ib()
    id = attr.ib(default=attr.Factory(uuid.uuid4))
    applicability = attr.ib(default=to_all)
    comment = attr.ib(default=None)
    access = attr.ib(default=epyqlib.pm.access.all)
    # TODO: maybe default should go away and it should instead be a
    #       value set exclusively
    default = attr.ib(default=0)
    # # hardware_limits = attr.ib(default=None)
    # # TODO: below as list?
    # factory_limits = attr.ib(default=None)
    # customer_limits = attr.ib(default=None)
    limits = attr.ib(default=None)

    @value.default
    def value(self):
        return self.default

    def valid(self):
        for attribute in attr.astuple(self):
            attribute.validate()

        # if self.value is not None:

reactive_current_command = Parameter()
reactive_current_max = Parameter()
reactive_current_min = Parameter()
reactive_current_command.relate_to(_min, _max)
