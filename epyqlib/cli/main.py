import click

import epyqlib.cli.audit
import epyqlib.cli.phabricator_extract
import epyqlib.pm.valueset


@click.group()
def cli():
    pass


cli.add_command(epyqlib.pm.valueset.group)
cli.add_command(epyqlib.cli.audit.create_command(), name="audit")
cli.add_command(
    epyqlib.cli.phabricator_extract.create_command(), name="phabricator_extract"
)
