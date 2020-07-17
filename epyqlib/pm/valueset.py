import collections
import os
import pathlib

import attr
import click
import epyqlib.pm.valuesetmodel
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
def cli(configuration_path_string):
    configuration_path = pathlib.Path(configuration_path_string)
    reference_path = configuration_path.parent

    schema = graham.schema(OverlayConfiguration)

    configuration_text = configuration_path.read_text(encoding='utf-8')
    configuration = schema.loads(configuration_text).data

    for recipe in configuration.recipes:
        output_path = reference_path / configuration.output_path / recipe.output_path
        click.echo(f'Creating: {os.fspath(output_path)}')

        base_pmvs_path = reference_path / recipe.base_pmvs_path

        overlay_pmvs_paths = [
            reference_path / path
            for path in recipe.overlay_pmvs_paths
        ]

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
