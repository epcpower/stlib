import json
import os

from epyqlib.tabs.files.files_utils import ensure_dir

class Vars:
    auto_sync = "auto_sync"
    offline_mode = "offline_mode"
    provided_serial_number = "provided_serial_number"
    refresh_token = "refresh_token"
    server_url = "server_url"

class SyncConfig:
    _instance = None
    _tag = f'[{__name__}]'

    _dev_url = "https://u62ugr52vbfcliv4x5tvjlo5dq.appsync-api.us-west-2.amazonaws.com/graphql"
    _beta_url = "https://sayn4ej53bbxbjfbtrnoeda5ia.appsync-api.us-west-2.amazonaws.com/graphql"

    default_values = {
        Vars.auto_sync: True,
        Vars.server_url: _dev_url,
        Vars.offline_mode: False
    }

    def __init__(self, directory=None, filename='epyq-config.json'):
        self.required_keys = [key for key in Vars.__dict__.keys() if not key.startswith("__")]

        self.directory = directory or os.path.join(os.getcwd(), 'sync')
        ensure_dir(self.directory)

        self.filename = os.path.join(self.directory, filename)
        self.file_error = False
        if os.path.exists(self.filename):
            self._read_file()
        else:
            self.config = dict()
            for key in self.required_keys:
                self.config[key] = self.default_values.get(key)

        self._write_file()

    @staticmethod
    def get_instance():
        if SyncConfig._instance is None:
            SyncConfig._instance = SyncConfig()

        return SyncConfig._instance

    def _read_file(self):
        with open(self.filename, 'r') as infile:
            contents = json.load(infile)
        if type(contents) is not dict:
            self.file_error = True
            raise ConfigurationError('Configuration file is not a valid configuration JSON object.')
        for key in self.required_keys:
            if key not in contents.keys() or contents[key] is None:
                contents[key] = self.default_values.get(key)
        self.config = contents

    def _write_file(self):
        if not self.file_error:
            with open(self.filename, 'w') as outfile:
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


