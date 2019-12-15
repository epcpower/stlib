import struct

import attr
import siphash


struct_format = '<I16sHq'


def high_32(value):
    return (value >> 32) & 0xffffffff


def low_32(value):
    return value & 0xffffffff


@attr.s(frozen=True)
class Uint64:
    value = attr.ib()

    @classmethod
    def ensure(cls, value):
        if isinstance(value, cls):
            return value

        return cls(value=value)

    def low_32(self):
        return low_32(self.value)

    def high_32(self):
        return high_32(self.value)

    def to_bytes(self, byteorder='little'):
        return self.value.to_bytes(8, byteorder)

    def evolve_low(self, low):
        return attr.evolve(
            self,
            value=(self.high_32() << 32) | low_32(low),
        )

    def evolve_high(self, high):
        return attr.evolve(
            self,
            value=(low_32(high) << 32) | self.low_32(),
        )


@attr.s(frozen=True)
class Tag64:
    value = attr.ib(converter=Uint64.ensure)


@attr.s(frozen=True)
class Key64:
    value = attr.ib(converter=Uint64.ensure)
    level = attr.ib()


# TODO: make it do something
# def generate_key():
#     pass


def pack(serial_number, parameter_uuid, meta_index, value):
    return struct.pack(
        struct_format,
        int(serial_number),  # TODO: make sure it doesn't lose info?
        parameter_uuid.bytes,
        meta_index,
        value,
    )


def build_tag(key, message):
    output_bytes = siphash.half_siphash_64(
        key=key.to_bytes(byteorder='little'),
        data=message,
    )

    tag = int.from_bytes(output_bytes, byteorder='little')

    return tag


def create_tag(key_value, serial_number, parameter_uuid, meta_index, value):
    message = pack(
        serial_number=serial_number,
        parameter_uuid=parameter_uuid,
        meta_index=meta_index,
        value=value,
    )

    tag_value = build_tag(key=key_value, message=message)

    return Tag64(value=tag_value)
