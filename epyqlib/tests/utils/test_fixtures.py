import os
import tempfile
from os import path

import pytest


@pytest.fixture
def temp_dir(request):
    dir = tempfile.mkdtemp()

    def cleanup():
        for file in os.listdir(dir):
            os.remove(path.join(dir, file))
        os.rmdir(dir)

    request.addfinalizer(cleanup)

    return dir
