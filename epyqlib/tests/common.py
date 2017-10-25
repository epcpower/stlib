import os

import attr


library_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..',
))

project_path = os.path.abspath(os.path.join(
    os.path.dirname(__file__), '..', '..',
))

scripts_path = os.path.join(project_path, 'venv', 'Scripts')

device_path = os.path.join(library_path, 'examples', 'devices')

devices = {
    'customer': os.path.join('customer', 'distributed_generation.epc'),
    'factory': os.path.join('factory', 'distributed_generation_factory.epc'),
}

devices = {
    k: os.path.normpath(os.path.join(device_path, v))
    for k, v in devices.items()
}

symbol_files = {
    'customer': os.path.join('customer', 'EPC_DG_ID247.sym'),
    'factory': os.path.join('factory', 'EPC_DG_ID247_FACTORY.sym'),
}

symbol_files = {
    k: os.path.normpath(os.path.join(device_path, v))
    for k, v in symbol_files.items()
}


@attr.s
class Values:
    initial = attr.ib()
    input = attr.ib()
    expected = attr.ib()
    collected = attr.ib(default=attr.Factory(list))

    def collect(self, value):
        self.collected.append(value)

    def check(self):
        return all(x == y for x, y in zip(self.expected, self.collected))
