import inspect

from PyQt5.QtCore import QObject
from typing import Callable, Coroutine

from twisted.internet.defer import ensureDeferred

from epyqlib.tabs.files.cognito import CognitoHelper
from epyqlib.tabs.files.sync_config import SyncConfig, Vars
from boto3_type_annotations.s3 import ServiceResource as S3Resource


## Async function that takes a bool whether or not the user was just logged in
LoginListener = Callable[[bool], Coroutine]

class AwsLoginManager():
    _instance = None

    def __init__(self):
        if self._instance is not None:
            raise Exception("Tried to create another instance of AwsLoginManager although one already exists.")
        self._listeners: [LoginListener] = []
        self._cognito_helper = CognitoHelper()

    @staticmethod
    def get_instance():
        if AwsLoginManager._instance is None:
            AwsLoginManager._instance = AwsLoginManager()

        return AwsLoginManager._instance

    def is_logged_in(self) -> bool:
        return self._cognito_helper.is_user_logged_in()

    def show_login_window(self, parent: QObject = None):

        self._cognito_helper.authenticate("tester", "...")

        self._notify_listeners()

        # Enable auto-sync when the user logs in
        SyncConfig.get_instance().set(Vars.auto_sync, True)


    def log_user_out(self):
        self._cognito_helper.log_out()
        self._notify_listeners()


    ## Get Resources
    def get_s3_resource(self) -> S3Resource:
        return self._cognito_helper.get_s3_resource()

    def refresh(self):
        self._cognito_helper._refresh()

    ## Manage Listeners
    def _notify_listeners(self):
        # if login was successful, notify listeners
        for listener in self._listeners:
            result = listener(self._cognito_helper.is_user_logged_in())
            if inspect.iscoroutine(result):
                ensureDeferred(result)


    def register_listener(self, listener: LoginListener):
        self._listeners.append(listener)

    def remove_listener(self, listener: LoginListener):
        self._listeners.remove(listener)
