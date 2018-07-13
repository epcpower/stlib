import pathlib

import pytest

import epyqlib.cmemoryparser


here = pathlib.Path(__file__).parent

outs = tuple(sorted((here/'outs').glob('*.out')))


@pytest.mark.parametrize(
    argnames='path',
    argvalues=outs,
    ids=[out.name for out in outs],
)
def test_load(path):
    epyqlib.cmemoryparser.process_file(filename=path)
