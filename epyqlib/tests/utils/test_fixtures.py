import os
import shutil
import tempfile
from os import path

import pytest


@pytest.fixture
def temp_dir(request):
    dir = tempfile.mkdtemp()

    def cleanup():
        shutil.rmtree(dir)

    request.addfinalizer(cleanup)

    return dir
