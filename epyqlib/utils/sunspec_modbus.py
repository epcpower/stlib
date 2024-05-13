import contextlib
import os
import pathlib
import typing
import sunspec.core.device


@contextlib.contextmanager
def fresh_smdx_path(*paths: pathlib.Path) -> pathlib.Path:
    """
    Creates a new smdx path

    Returns:
        pathlib.Path: path from the SunSpecDevice model

    Yields:
        Iterator[pathlib.Path]: list of file path(s) from sunspec.core.device
    """
    original_pathlist = sunspec.core.device.file_pathlist
    sunspec.core.device.file_pathlist = sunspec.core.util.PathList()

    for path in paths:
        sunspec.core.device.file_pathlist.add(os.fspath(path))

    try:
        yield sunspec.core.device.file_pathlist
    finally:
        sunspec.core.device.file_pathlist = original_pathlist


def send_val(point: typing.Any, val: int) -> None:
    """
    Sets the value for a point

    Args:
        point (typing.ANy): A point in the model
        val (int): A value the point will be set to
    """
    point.value_setter(val)
    point.write()
