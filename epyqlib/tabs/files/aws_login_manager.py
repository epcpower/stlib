from PyQt5.QtCore import QObject


class AwsLoginManager():
### TODO: Wire up this stub
    _instance = None
    def __init__(self):
        if self._instance is not None:
            raise Exception("Tried to create another instance of AwsLoginManager although one already exists.")
        self._logged_in = False


    @staticmethod
    def get_instance():
        if AwsLoginManager._instance is None:
            AwsLoginManager._instance = AwsLoginManager()

        return AwsLoginManager._instance

    def is_logged_in(self) -> bool:
        return self._logged_in

    def show_login_window(self, parent: QObject):
        self._logged_in = not self._logged_in

    def get_credentials(self):
        pass
