import collections
import os
import math
import pathlib

import attr
import click
import epyqlib.pm.valuesetmodel
import epyqlib.attrsmodel
import graham
import marshmallow


def create_path_attribute():
    return attr.ib(
        converter=pathlib.Path,
        metadata=graham.create_metadata(
            field=marshmallow.fields.String(),
        ),
    )


def to_list_of_pathlib(l):
    return [pathlib.Path(path) for path in l]


@graham.schemify(tag='valueset_overlay_recipe')
@attr.s
class OverlayRecipe:
    output_path = create_path_attribute()
    base_pmvs_path = create_path_attribute()
    overlay_pmvs_paths = attr.ib(
        converter=to_list_of_pathlib,
        metadata=graham.create_metadata(
            field=marshmallow.fields.List(marshmallow.fields.String()),
        ),
    )


@graham.schemify(tag='valueset_overlay_configuration')
@attr.s
class OverlayConfiguration:
    output_path = create_path_attribute()
    recipes = attr.ib(
        metadata=graham.create_metadata(
            field=marshmallow.fields.List(marshmallow.fields.Nested(graham.schema(OverlayRecipe))),
        ),
    )
    reference_path = attr.ib(
        default=None,
        converter=epyqlib.attrsmodel.to_pathlib_or_none,
    )
    path = attr.ib(default=None)

    @classmethod
    def load(cls, path):
        schema = graham.schema(cls)

        configuration_text = path.read_text(encoding='utf-8')
        configuration = schema.loads(configuration_text).data

        configuration.path = path
        if configuration.reference_path is None:
            configuration.reference_path = path.parent

        return configuration

    def recipe_output_path(self, recipe):
        return self.reference_path / self.output_path / recipe.output_path

    def recipe_base_pmvs_path(self, recipe):
        return self.reference_path / recipe.base_pmvs_path

    def recipe_overlay_pmvs_paths(self, recipe):
        return [
            self.reference_path / path
            for path in recipe.overlay_pmvs_paths
        ]

    def raw(self, echo=lambda *args, **kwargs: None):
        input_modification_times = []
        output_modification_times = []

        input_modification_times.append(self.path.stat().st_mtime)

        for recipe in self.recipes:
            output_path = self.recipe_output_path(recipe=recipe)
            echo(f'Checking: {os.fspath(output_path)}')

            try:
                stat = recipe.output_path.stat()
            except FileNotFoundError:
                output_modification_time = math.inf
            else:
                output_modification_time = stat.st_mtime
            output_modification_times.append(output_modification_time)

            overlay_pmvs_paths = self.recipe_overlay_pmvs_paths(recipe=recipe)

            for overlay_pmvs_path in overlay_pmvs_paths:
                input_modification_times.append(
                    overlay_pmvs_path.stat().st_mtime,
                )

        return min(output_modification_times) < max(input_modification_times)


@click.group(name='value-sets')
def group():
    pass


@group.group()
def recipes():
    pass


@recipes.command(name='generate')
@click.option(
    '--input',
    'value_set_path_strings',
    type=click.Path(dir_okay=False, readable=True, resolve_path=True),
    multiple=True,
    required=True,
)
@click.option(
    '--common-output',
    'common_output_path_string',
    type=click.Path(dir_okay=False, readable=True, resolve_path=True),
    required=True,
)
def generate_recipes(value_set_path_strings, common_output_path_string):
    value_set_paths = [
        pathlib.Path(path_string)
        for path_string in value_set_path_strings
    ]
    common_output_path = pathlib.Path(common_output_path_string)

    common_value_set = epyqlib.pm.valuesetmodel.create_blank()

    value_sets = [
        epyqlib.pm.valuesetmodel.loadp(value_set_path)
        for value_set_path in value_set_paths
    ]

    all_parameters_by_uuid = collections.defaultdict(list)
    for value_set in value_sets:
        for parameter in value_set.model.root.children:
            all_parameters_by_uuid[parameter.parameter_uuid].append(parameter)

    common_uuids = [
        uuid_
        for uuid_, parameters in all_parameters_by_uuid.items()
        if len(parameters) == len(value_sets)
    ]

    common_and_equal_uuids = [
        uuid_
        for uuid_ in common_uuids
        if 1 == len({
            parameter.value for parameter in all_parameters_by_uuid[uuid_]
        })
    ]

    for uuid_ in common_and_equal_uuids:
        reference_parameter = all_parameters_by_uuid[uuid_][0]

        new_parameter = epyqlib.pm.valuesetmodel.Parameter(
            name=reference_parameter.name,
            value=reference_parameter.value,
            parameter_uuid=reference_parameter.parameter_uuid,
            readable=reference_parameter.readable,
            writable=reference_parameter.writable,
        )

        common_value_set.model.root.append_child(new_parameter)

    for value_set in value_sets:
        value_set.strip_common(reference=common_value_set)

    common_value_set.save(path=common_output_path)
    for value_set in value_sets:
        new_name = common_output_path.stem + '-' + value_set.path.name
        path = common_output_path.parent / new_name
        value_set.save(path=path)


@recipes.command(name='cook')
@click.option(
    '--configuration',
    'configuration_path_string',
    type=click.Path(dir_okay=False, readable=True, resolve_path=True),
)
@click.option(
    '--if-raw/--assume-raw',
    'only_if_raw',
    default=False,
)
def cli(configuration_path_string, only_if_raw):
    configuration_path = pathlib.Path(configuration_path_string)

    configuration = OverlayConfiguration.load(configuration_path)

    if only_if_raw:
        if not configuration.raw(echo=click.echo):
            click.echo(
                'Generated files appear to be up to date, skipping cooking',
            )

            return

        click.echo(
            'Generated files appear to be out of date, starting cooking'
        )

    for recipe in configuration.recipes:
        output_path = configuration.recipe_output_path(recipe=recipe)
        click.echo(f'Creating: {os.fspath(output_path)}')

        base_pmvs_path = configuration.recipe_base_pmvs_path(recipe=recipe)

        overlay_pmvs_paths = configuration.recipe_overlay_pmvs_paths(
            recipe=recipe,
        )

        all_pmvs_paths = [base_pmvs_path, *overlay_pmvs_paths]

        click.echo(
            '\n'.join(f'    {os.fspath(path)}' for path in all_pmvs_paths),
        )

        result_value_set = epyqlib.pm.valuesetmodel.loadp(base_pmvs_path)

        for path in overlay_pmvs_paths:
            overlay_value_set = epyqlib.pm.valuesetmodel.loadp(path)
            result_value_set.overlay(overlay_value_set)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        result_value_set.save(path=output_path)
