from PyQt5.QtCore import QObject
from typing import Callable

from epyqlib.tabs.files.configuration import Configuration, Vars


class AwsLoginManager():
### TODO: Wire up this stub
    _instance = None

    def __init__(self):
        if self._instance is not None:
            raise Exception("Tried to create another instance of AwsLoginManager although one already exists.")
        self._logged_in = False
        self._listeners: [Callable[[bool], None]] = []


    @staticmethod
    def get_instance():
        if AwsLoginManager._instance is None:
            AwsLoginManager._instance = AwsLoginManager()

        return AwsLoginManager._instance

    def is_logged_in(self) -> bool:
        return self._logged_in

    def show_login_window(self, parent: QObject = None):
        self._logged_in = not self._logged_in
        self._notify_listeners()

        # Enable auto-sync when the user logs in
        Configuration.get_instance().set(Vars.auto_sync, True)

    def log_user_out(self):
        self._logged_in = False
        self._notify_listeners()

    def _notify_listeners(self):
        # if login was successful, notify listeners
        for listener in self._listeners:
            listener(self._logged_in)

    def get_credentials(self):
        pass

    def register_listener(self, listener: Callable[[None], None]):
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[None], None]):
        self._listeners.remove(listener)
