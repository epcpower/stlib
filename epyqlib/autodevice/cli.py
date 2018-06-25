import zipfile

import click

import epyqlib.autodevice.build


@click.group()
def cli():
    pass


@cli.group()
def create():
    pass


@create.command()
@click.option(
    '--zip',
    type=click.Path(dir_okay=False, resolve_path=True),
    required=True,
)
def template(zip):
    epyqlib.autodevice.build.create_template_archive(zip)
