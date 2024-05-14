import contextlib
import os
import pathlib
import typing
import sunspec.core.device


@contextlib.contextmanager
def fresh_smdx_path(
    *paths: pathlib.Path,
) -> typing.Generator[sunspec.core.device.file_pathlist]:
    """
    Creates a new smdx path using a path to the model

    Returns:
        typing.Generator[sunspec.core.device.file_pathlist]: A new smdx path

    Yields:
        Iterator[typing.Generator[sunspec.core.device.file_pathlist]]: A new smdx path
    """
    original_pathlist = sunspec.core.device.file_pathlist
    sunspec.core.device.file_pathlist = sunspec.core.util.PathList()

    for path in paths:
        sunspec.core.device.file_pathlist.add(os.fspath(path))

    try:
        yield sunspec.core.device.file_pathlist
    finally:
        sunspec.core.device.file_pathlist = original_pathlist


def send_val(
    point: sunspec.core.device.Point, val: typing.Union[int, bool, float, str]
) -> None:
    """
    Sets a value for a point in the model

    Args:
        point (sunspec.core.device.Point): A point in the SunSpec model
        val (typing.Union[int, bool, float, str]): A new value the point will be set to
    """
    point.value_setter(val)
    point.write()
