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


@click.command()
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
