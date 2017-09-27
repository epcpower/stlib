import attr


@attr.s
class Type:
    name = attr.ib()
    type = attr.ib()
    scaling = attr.ib(default=1)
    offset = attr.ib(default=0)
