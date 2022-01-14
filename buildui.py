import alqtendpy.compileui
import pathlib


def compile_ui():
    print("epyqlib::compile_ui building UI in epyq")
    alqtendpy.compileui.compile_ui(
        directory_paths=[pathlib.Path(__file__).parent / "epyqlib"],
    )
