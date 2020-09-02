import pathlib
import typing

import PyQt5.uic
import attr
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QLineEdit, QPushButton, QLabel, QDialogButtonBox
from epyqlib.tabs.files.cognito import CognitoException

# noinspection PyUnreachableCode
if typing.TYPE_CHECKING:
    from epyqlib.tabs.files.aws_login_manager import AwsLoginManager

Ui, UiBase = PyQt5.uic.loadUiType(
    pathlib.Path(__file__).with_suffix(".ui"),
)


@attr.s
class LoginDialog(UiBase):
    login_manager: "AwsLoginManager" = attr.ib()
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
        self._fiddle_title_label()
        self._clear_error_message()

    def _fiddle_title_label(self):
        self.ui.spacer_label.setText(self.ui.big_label.text())

        reference_font = QFont()
        reference_font.setPointSize(reference_font.pointSize() * 2)
        reference_font.setWeight(QFont.Black)

        self.ui.big_label.setFont(reference_font)

        reference_font.setPointSize(reference_font.pointSize() * 2 / 3)
        self.ui.spacer_label.setFont(reference_font)

    def _bind(self):
        # self.dialog: QDialog = self.ui.root_dialog

        self.username: QLineEdit = self.ui.username
        self.password: QLineEdit = self.ui.password

        self.error_message: QLabel = self.ui.lbl_error_message

        self.btn_cancel: QPushButton = self.ui.button_box.button(
            QDialogButtonBox.StandardButton.Cancel
        )
        self.btn_login: QPushButton = self.ui.button_box.button(
            QDialogButtonBox.StandardButton.Ok
        )
        self.btn_login.setText("Login")

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
        self.error_message.setText(f'<font color="red">{err} Please try again.</font>')

    def _text_changed(self, new_text: str):
        if self.invalid_input:
            self.invalid_input = False
            self.btn_login.setEnabled(True)
