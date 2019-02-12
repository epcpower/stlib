import json
import os


class SyncConfig:
    _instance = None

    def __init__(self, directory=None, filename='epyq-config.json'):
        self.required_keys = [key for key in Vars.__dict__.keys() if not key.startswith("__")]

        self.directory = directory or os.path.join(os.getcwd(), 'sync')
        if not os.path.lexists(self.directory):
            os.mkdir(self.directory)

        self.filename = os.path.join(self.directory, filename)
        self.file_error = False
        if os.path.exists(self.filename):
            self._read_file()
        else:
            self.config = dict()
            for key in self.required_keys:
                self.config[key] = None

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
            if key not in contents.keys():
                self.file_error = True
                raise ConfigurationError(f'Required key {key} is missing from configuration file.')
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

    def log_serial_number(self, serial_number: str):
        if self.config[Vars.unique_inverters] is None:
            self.set(Vars.unique_inverters, [serial_number])
        elif serial_number not in self.config[Vars.unique_inverters]:
            self.set(Vars.unique_inverters, self.config[Vars.unique_inverters] + [serial_number])


class ConfigurationError(Exception):
    pass


class Vars:
    auto_sync = "auto_sync"
    offline_mode = "offline_mode"
    provided_serial_number = "provided_serial_number"
    refresh_token = "refresh_token"
    unique_inverters = "unique_inverters"
    username = "username"
