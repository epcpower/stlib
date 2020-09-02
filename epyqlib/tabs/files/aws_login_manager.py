import inspect
from typing import Callable, Coroutine

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QDialog
from boto3_type_annotations.s3 import ServiceResource as S3Resource
from twisted.internet.defer import ensureDeferred

from epyqlib.tabs.files.cognito import CognitoHelper
from epyqlib.tabs.files.login_dialog import LoginDialog
from epyqlib.tabs.files.sync_config import SyncConfig, Vars

## Async function that takes a bool whether or not the user was just logged in
LoginListener = Callable[[bool], Coroutine]


class AwsLoginManager:
    _instance = None

    def __init__(self):
        if self._instance is not None:
            raise Exception(
                "Tried to create another instance of AwsLoginManager although one already exists."
            )
        self._listeners: [LoginListener] = []
        self._cognito_helper = CognitoHelper(SyncConfig.get_env())

    @staticmethod
    def get_instance():
        if AwsLoginManager._instance is None:
            AwsLoginManager._instance = AwsLoginManager()

        return AwsLoginManager._instance

    def is_logged_in(self) -> bool:
        return self._cognito_helper.is_user_logged_in()

    def show_login_window(self, parent: QObject = None):

        dialog: QDialog = LoginDialog(self)

        code = dialog.exec()

        if code == QDialog.Accepted:
            self._notify_listeners()

            # Enable auto-sync when the user logs in
            SyncConfig.get_instance().set(Vars.auto_sync, True)

    def authenticate(self, username: str, password: str):
        self._cognito_helper.authenticate(username, password)

    def log_user_out(self):
        self._cognito_helper.log_out()
        self._notify_listeners()

    def get_id_token(self) -> str:
        return self._cognito_helper._id_token

    def get_valid_id_token(self) -> str:
        if not self._cognito_helper.is_session_valid():
            self.refresh()

        return self.get_id_token()

    def get_s3_resource(self) -> S3Resource:
        return self._cognito_helper.get_s3_resource()

    def get_username(self):
        return self._cognito_helper.get_username()

    def get_user_customer(self):
        return self._cognito_helper.get_user_customer()

    def is_session_valid(self) -> bool:
        return self._cognito_helper.is_session_valid()

    def refresh(self, force=False):
        self._cognito_helper._refresh(force=force)

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
