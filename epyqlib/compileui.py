import pathlib

import click
import PyQt5.uic


@click.command()
@click.option(
    '--ui',
    'ui_paths',
    multiple=True, type=click.Path(exists=True, dir_okay=False),
)
@click.option(
    '--directory',
    '--dir',
    'directories',
    default=['.'],
    multiple=True,
    type=click.Path(exists=True, file_okay=False),
)
@click.option('--suffix', default='_ui')
@click.option('--encoding', default='utf-8')
def cli(ui_paths, directories, suffix, encoding):
    ui_paths = [pathlib.Path(path) for path in ui_paths]

    for directory in directories:
        path = pathlib.Path(directory)
        found_paths = path.rglob('*.ui')
        ui_paths.extend(found_paths)

    for path in ui_paths:
        in_path = path
        out_path = path.with_name(f'{path.stem}{suffix}.py')

        click.echo(f'Converting: {in_path} -> {out_path}')
        with open(out_path, 'w', encoding=encoding) as out_file:
            PyQt5.uic.compileUi(in_path, out_file)
