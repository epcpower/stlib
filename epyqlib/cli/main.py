import click

import epyqlib.pm.valueset


@click.group()
def cli():
    pass


cli.add_command(epyqlib.pm.valueset.group)
