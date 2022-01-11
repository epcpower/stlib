.venv/bin/genbuildinfo epyqlib/_build.py
.venv/bin/pytest -vvvv -s --no-qt-log --run-factory epyqlib.tests --pyargs
