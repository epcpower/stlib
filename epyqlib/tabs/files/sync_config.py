import json
import os

import appdirs
from epyqlib.tabs.files.files_utils import ensure_dir


class Vars:
    auto_sync = "auto_sync"
    offline_mode = "offline_mode"
    refresh_token = "refresh_token"


class SyncConfig:
    _instance = None
    _tag = f"[{__name__}]"

    default_values = {Vars.auto_sync: True, Vars.offline_mode: False}

    def __init__(self, directory=None, filename="epyq-config.json"):
        self.required_keys = [
            key for key in Vars.__dict__.keys() if not key.startswith("__")
        ]

        self.config_dir = directory or appdirs.user_config_dir("Epyq", "EPC Power")
        self.cache_dir = directory or os.path.join(os.getcwd(), "sync")

        print(f"{self._tag} Using config dir: {self.config_dir}")
        print(f"{self._tag} Using cache dir: {self.cache_dir}")

        for dir in (self.config_dir, self.cache_dir):
            ensure_dir(dir)

        self.filename = os.path.join(self.config_dir, filename)
        self.file_error = False
        if os.path.exists(self.filename):
            self._read_file()
        else:
            self.config = dict()
            for key in self.required_keys:
                self.config[key] = self.default_values.get(key)

        self._write_file()

    @staticmethod
    def get_env() -> str:
        # return "client"
        return "internal"

    @staticmethod
    def get_instance():
        if SyncConfig._instance is None:
            SyncConfig._instance = SyncConfig()

        return SyncConfig._instance

    def _read_file(self):
        with open(self.filename, "r") as infile:
            contents = json.load(infile)
        if type(contents) is not dict:
            self.file_error = True
            raise ConfigurationError(
                "Configuration file is not a valid configuration JSON object."
            )
        for key in self.required_keys:
            if key not in contents.keys() or contents[key] is None:
                contents[key] = self.default_values.get(key)
        self.config = contents

    def _write_file(self):
        if not self.file_error:
            with open(self.filename, "w") as outfile:
                json.dump(self.config, outfile, indent=2)

    def get(self, key):
        return self.config.get(key)

    def get_bool(self, key):
        return self.get(key) or False

    def set(self, key, value):
        self.config[key] = value
        self._write_file()


class ConfigurationError(Exception):
    pass
