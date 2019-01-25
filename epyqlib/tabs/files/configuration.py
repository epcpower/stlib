import json
import os


class Configuration:
    required_keys = ["username"]
    def __init__(self, directory=os.getcwd(), filename='epyq-config.json'):
        self.filename = os.path.join(directory, filename)
        self.file_error = False
        if os.path.exists(self.filename):
            self.read_file()
        else:
            self.config = dict()
            for key in self.required_keys:
                self.config[key] = None

    def read_file(self):
        with open(self.filename, 'r') as infile:
            contents = json.load(infile)
        if type(contents) is not dict:
            self.file_error = True
            raise ConfigurationError('Configuration file is not a valid configuration JSON object.')
        for key in self.required_keys:
            if contents.get(key) is None:
                self.file_error = True
                raise ConfigurationError(f'Required key ${key} is missing from configuration file.')
        self.config = contents

    def write_file(self):
        if not self.file_error:
            with open(self.filename, 'w') as outfile:
                json.dump(self.config, outfile)

    def get(self, key):
        return self.config.get(key)

    def set(self, key, value):
        self.config[key] = value
        self.write_file()


class ConfigurationError(Exception):
    pass