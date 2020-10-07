import click

import epyqlib.cli.audit
import epyqlib.pm.valueset


@click.group()
def cli():
    pass


cli.add_command(epyqlib.pm.valueset.group)
cli.add_command(epyqlib.cli.audit.create_command(), name="audit")
