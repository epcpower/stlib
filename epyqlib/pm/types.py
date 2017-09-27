import enum

import attr


class Types:
    number = 0
    enumeration = 1
    string = 2


@attr.s
class CanUnsignedInteger:
    bits = attr.ib()
