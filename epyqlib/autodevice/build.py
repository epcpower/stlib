import collections
import json
import os
import pathlib
import shutil
import subprocess
import tempfile

import attr
import canmatrix.formats

import epyqlib.device


class InvalidAutoParametersDeviceError(Exception):
    pass


class MultipleFoundError(Exception):
    pass


@attr.s
class AccessInput:
    node = attr.ib()
    description = attr.ib()
    secret = attr.ib()
    value = attr.ib(default=None)


@attr.s
class Builder:
    template = attr.ib(default=None)
    template_path = attr.ib(default=None)
    value_set = attr.ib(default=None)
    target = attr.ib(default=None)
    access_parameters = attr.ib(default=None)
    archive_code = attr.ib()

    @archive_code.default
    def _(self):
        code = epyqlib.utils.qt.get_code()
        if code is not None:
            code = code.decode('ascii')

        return code

    def set_access_level_names(self, password_name, access_level_name):
        self.access_parameters = (
            AccessInput(
                node=password_name,
                description='Elevated Access Code',
                secret=True,
            ),
            AccessInput(
                node=access_level_name,
                description='Elevated Access Level',
                secret=False,
            ),
        )

    def set_template(self, path):
        self.template_path = pathlib.Path(path)

        self.template = epyqlib.device.Device(
            file=os.fspath(self.template_path),
            only_for_files=True,
        )

        auto_value_set_key = 'auto_value_set'
        if auto_value_set_key not in self.template.raw_dict:
            raise InvalidAutoParametersDeviceError(
                'Key {} not found'.format(auto_value_set_key)
            )

    def load_pmvs(self, path):
        self.value_set = epyqlib.pm.valuesetmodel.loadp(path)

    def load_epp(self, parameter_path, can_path):
        matrix = canmatrix.formats.loadp(can_path).values()
        neo = epyqlib.canneo.Neo(matrix=matrix)
        nvs = epyqlib.nv.Nvs(neo=neo)
        with open(parameter_path) as f:
            parameters = json.load(f)
        nvs.from_dict(parameters)
        self.value_set = nvs.to_value_set(include_secrets=True)

    def get_or_create_parameter(self, name):
        try:
            nodes = self.value_set.model.root.nodes_by_attribute(
                attribute_value=name,
                attribute_name='name',
            )
        except epyqlib.treenode.NotFoundError:
            node = epyqlib.pm.valuesetmodel.Parameter(
                name=name,
            )
            self.value_set.model.root.append_child(node)
        else:
            try:
                node, = nodes
            except ValueError as e:
                raise MultipleFoundError(
                    'Found multiple nodes but expected only one when '
                    'searching for {}'.format(repr(name))
                )

        return node

    def set_target(self, path):
        self.target = pathlib.Path(path)

    def create(self, original_raw_dict, can_contents):
        for access_input in self.access_parameters:
            access_input.node = self.get_or_create_parameter(access_input.node)

        # def node_path(node):
        #     return [
        #         node.frame.name,
        #         node.frame.mux_name,
        #         node.name,
        #     ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_directory = pathlib.Path(temporary_directory)
            directory_path = temporary_directory / self.target.stem
            directory_path.mkdir()

            for access_input in self.access_parameters:
                # name = ':'.join(node_path(access_input.node)[1:])

                node = self.get_or_create_parameter(name=access_input.node)

                node.value = access_input.value

            self.value_set.path = directory_path / self.template.raw_dict[
                'auto_value_set'
            ]
            self.value_set.save()

            can_path = self.template.raw_dict['can_path']

            for file_name in self.template.referenced_files:
                if file_name in (can_path, self.template.raw_dict['auto_value_set']):
                    continue

                file_path = pathlib.Path(file_name)

                shutil.copy(
                    self.template_path.parent/file_path.name,
                    directory_path,
                )

            with open(self.template_path) as f:
                raw_dict = json.load(
                    f,
                    object_pairs_hook=collections.OrderedDict,
                )

            keys_to_copy = (
                'can_configuration',
                'nv_configuration',
                'node_id_type',
                'access_level_path',
                'access_password_path',
                'nv_meta_enum',
            )
            for key in keys_to_copy:
                raw_dict[key] = original_raw_dict[key]

            target_epc_name = (
                directory_path / 'auto_parameters.epc'
            )
            with open(target_epc_name, 'w') as f:
                json.dump(raw_dict, f, indent=4)

            with open(directory_path / can_path, 'wb') as f:
                f.write(can_contents)

            backup_path = None
            if self.target.exists():
                backup_path = temporary_directory / self.target.name
                shutil.move(self.target, backup_path)

            try:
                password_option = []
                if len(self.archive_code) > 0:
                    password_option = ['-p{}'.format(self.archive_code)]

                paths = (
                    pathlib.Path('7z'),
                    pathlib.Path('C:') / os.sep / 'Program Files' / '7-Zip' / '7z.exe',
                    (
                        pathlib.Path('C:') / os.sep
                        / 'Program Files (x86)' / '7-Zip' / '7z.exe',
                    ),
                )
                for path in paths:
                    try:
                        subprocess.run(
                            [
                                str(path),
                                'a',
                                '-tzip',
                                str(self.target),
                                str(directory_path),
                                *password_option,
                            ],
                            check=True,
                        )
                    except FileNotFoundError:
                        continue
                    else:
                        break
                else:
                    raise Exception(
                        'Unable to find 7z binary as any of: {}'.format(
                            paths,
                        )
                    )
            except Exception as e:
                if backup_path is not None:
                    shutil.move(backup_path, self.target)

                raise e
