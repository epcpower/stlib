import os


def ensure_dir(dir_name):
    if os.path.exists(dir_name):
        if os.path.isdir(dir_name):
            return
        else:
            raise NotADirectoryError(f"Files cache dir {dir_name} already exists but is not a directory")

    os.mkdir(dir_name)
