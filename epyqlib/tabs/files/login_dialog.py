import pathlib
import attr
import PyQt5
import PyQt5.uic


from PyQt5.QtWidgets import QDialog, QLineEdit, QPushButton, QLabel

# noinspection PyUnreachableCode
from epyqlib.tabs.files.cognito import CognitoException

if False:  # Tell the editor about the type, but don't invoke a cyclic depedency
    from epyqlib.tabs.files.aws_login_manager import AwsLoginManager

Ui, UiBase = PyQt5.uic.loadUiType(
   pathlib.Path(__file__).with_suffix('.ui'),
)

@attr.s
class LoginDialog(UiBase):
    login_manager: 'AwsLoginManager' = attr.ib()
    ui = attr.ib(factory=Ui)

    invalid_input = False

    def __attrs_post_init__(self):
        super().__init__()
        self.setup_ui()

    @classmethod
    def build(cls):
        instance = cls()
        instance.setup_ui()

        return instance

    # noinspection PyAttributeOutsideInit
    def setup_ui(self):
        self.ui.setupUi(self)

        self._bind()
        self._clear_error_message()

    def _bind(self):
        # self.dialog: QDialog = self.ui.root_dialog

        self.username: QLineEdit = self.ui.username
        self.password: QLineEdit = self.ui.password

        self.error_message: QLabel = self.ui.lbl_error_message

        self.btn_cancel: QPushButton = self.ui.btn_cancel
        self.btn_login: QPushButton = self.ui.btn_login

        self.username.textChanged.connect(self._text_changed)
        self.password.textChanged.connect(self._text_changed)

        self.btn_cancel.clicked.connect(self._cancel_clicked)
        self.btn_login.clicked.connect(self._login_clicked)


    def _cancel_clicked(self):
        self.reject()

    def _login_clicked(self):
        self._clear_error_message()


        username = self.username.text()
        password = self.password.text()
        try:
            self.login_manager.authenticate(username, password)
        except CognitoException as e:
            self._show_error_message(e.message)
            self.invalid_input = True
            self.btn_login.setDisabled(True)
            return

        self.accept()

    def _clear_error_message(self):
        self.error_message.setText(None)

    def _show_error_message(self, err: str):
        self.error_message.setText(f"<font color=\"red\">{err} Please try again.</font>")

    def _text_changed(self, new_text: str):
        if self.invalid_input:
            self.invalid_input = False
            self.btn_login.setEnabled(True)



