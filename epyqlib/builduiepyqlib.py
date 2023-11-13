# import alqtendpy.compileui
import io
import pathlib

import PyQt5.uic


def _do_nothing(*args, **kwargs):
    pass


def compile_ui(
    file_paths=(),
    directory_paths=(),
    extension=".ui",
    suffix="_ui",
    encoding="utf-8",
    output=_do_nothing,
    qtpy=False,
):
    paths = collect_paths(
        file_paths=file_paths,
        directory_paths=directory_paths,
        extension=extension,
    )

    compile_paths(
        ui_paths=paths,
        suffix=suffix,
        encoding=encoding,
        output=output,
        qtpy=qtpy,
    )


def collect_paths(file_paths=(), directory_paths=(), extension=".ui"):
    file_paths = [pathlib.Path(path) for path in file_paths]

    for directory in directory_paths:
        path = pathlib.Path(directory)
        found_paths = path.rglob("*" + extension)
        file_paths.extend(found_paths)

    return file_paths


def compile_paths(
    ui_paths,
    suffix="_ui",
    encoding="utf-8",
    output=_do_nothing,
    qtpy=False,
):
    for path in ui_paths:
        in_path = path
        out_path = path.with_name(f"{path.stem}{suffix}.py")

        output(f"Converting: {in_path} -> {out_path}")
        intermediate = io.StringIO()
        PyQt5.uic.compileUi(in_path, intermediate)
        intermediate = intermediate.getvalue()
        if qtpy:
            intermediate = intermediate.replace("PyQt5", "qtpy")
        with open(out_path, "w", encoding=encoding) as out_file:
            out_file.write(intermediate)


def compile_ui():
    print("epyqlib::compile_ui building UI in epyqlib")
    compile_ui(
        directory_paths=[pathlib.Path(__file__).parent],
    )
