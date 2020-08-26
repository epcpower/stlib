import os
import shutil
import tempfile
from os import path

import pytest


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as dir:
        yield dir
