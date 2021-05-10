import click

import epyqlib.cli.audit
import epyqlib.pm.valueset


@click.group()
def cli():
    pass


cli.add_command(epyqlib.pm.valueset.group)
cli.add_command(epyqlib.cli.audit.create_command(), name="audit")
try:
    import epyqlib.cli.phabricator_extract

    cli.add_command(
        epyqlib.cli.phabricator_extract.create_command(), name="phabricator_extract"
    )
except ModuleNotFoundError as mnfe:
    click.echo(
        f"Phabricator extract functionality is unavailable due to missing module: {mnfe.name}"
    )
