import logging
from datetime import datetime, timedelta

import attr
import boto3
from boto3 import Session
from boto3_type_annotations.cognito_identity import Client as CognitoIdentityClient
from boto3_type_annotations.cognito_idp import Client as CognitoIdpClient
from boto3_type_annotations.s3 import ServiceResource as S3Resource
from epyqlib.tabs.files.files_utils import decode_jwt
from epyqlib.tabs.files.sync_config import SyncConfig, Vars
from epyqlib.utils.general import safe_get

logger = logging.getLogger("CognitoHelper")


@attr.s(slots=True, auto_attribs=True)
class CognitoException(Exception):
    message: str


class CognitoHelper:

    _tag = "[CognitoHelper]"

    configs = {
        "internal": {
            "identity_pool_id": "us-west-2:2e8a787f-e6b3-4fc0-b24f-2f7855b9bcf3",
            "client_id": "6ald2becsbriio982480bjacgq",
            "region": "us-west-2",
            "user_pool_id": "cognito-idp.us-west-2.amazonaws.com/us-west-2_wIVmyFHI5",
        },
        "client": {
            "identity_pool_id": "us-west-2:92cfea99-64ff-4c20-9202-b752d9e0db61",
            "client_id": "2jof2obe6dtofat1eml8kqjssv",
            "region": "us-west-2",
            "user_pool_id": "cognito-idp.us-west-2.amazonaws.com/us-west-2_DdfcP6fUX",
        },
    }

    def __init__(self, environment: str):
        self._access_token = ""
        self._expires_in = 0
        self._expires_time = datetime.min
        self._id_token = ""
        self._decoded_id_token: dict = {}
        self._refresh_token = ""
        self._token_type = ""
        self.config = self.configs[environment]

        self._s3_resource: S3Resource = None

        self._session: Session = boto3.session.Session(
            region_name=self.config["region"],
            aws_access_key_id="",
            aws_secret_access_key="",
            aws_session_token="",
        )

        self._sync_config = SyncConfig.get_instance()

    def authenticate(self, username: str, password: str):
        """
        :raises botocore.errorfactory.UserNotFoundException If username is wrong
        :raises botocore.errorfactory.NotAuthorizedException If password is wrong
        """
        print(f"{self._tag} Beginning authentication for user {username}")
        client: CognitoIdpClient = self._get_anonymous_client("cognito-idp")

        try:
            response = client.initiate_auth(
                ClientId=self.config["client_id"],
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters={"USERNAME": username, "PASSWORD": password},
            )
        except Exception:
            raise CognitoException("Invalid credentials.")

        result = response["AuthenticationResult"]
        self._access_token = result["AccessToken"]
        self._expires_in = result["ExpiresIn"]
        self._expires_time = datetime.now() + timedelta(seconds=self._expires_in)
        self._id_token = result["IdToken"]
        self._decoded_id_token = decode_jwt(self._id_token)["payload"]
        self._refresh_token = result["RefreshToken"]
        self._token_type = result["TokenType"]

        self._sync_config.set(Vars.refresh_token, self._refresh_token)
        # auth result has the keys: AccessToken, ExpiresIn, IdToken, RefreshToken, TokenType

        self._init_auth_session()

        print(f"{self._tag} Authentication successful")
        self._create_resources()

    def _init_auth_session(self):
        cognito: CognitoIdentityClient = boto3.client(
            "cognito-identity", region_name=self.config["region"]
        )

        id = cognito.get_id(
            AccountId="203222013089",
            IdentityPoolId=self.config["identity_pool_id"],
            Logins={self.config["user_pool_id"]: self._id_token},
        )

        response = cognito.get_credentials_for_identity(
            IdentityId=id["IdentityId"],
            Logins={self.config["user_pool_id"]: self._id_token},
        )
        credentials = response["Credentials"]

        self._session = boto3.session.Session(
            region_name=self.config["region"],
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretKey"],
            aws_session_token=credentials["SessionToken"],
        )

    def _get_anonymous_client(self, type: str):
        return boto3.client(
            type,
            region_name=self.config["region"],
            aws_access_key_id="",
            aws_secret_access_key="",
            aws_session_token="",
        )

    def get_s3_resource(self):
        if not self.is_session_valid():
            self._refresh()

        return self._s3_resource

    def _create_resources(self):
        self._s3_resource = self._session.resource("s3")

    def _get_client(self, type: str):
        return self._session.client(type)

    def _get_resource(self, service_name: str):
        return self._session.resource(service_name)

    def is_session_valid(self):
        return datetime.now() < self._expires_time

    def _get_refresh_token_pref(self):
        return self._sync_config.get(Vars.refresh_token)

    def _clear_refresh_token_pref(self):
        self._sync_config.set(Vars.refresh_token, None)

    def is_user_logged_in(self) -> bool:
        token = self._get_refresh_token_pref()
        return token is not None and token != ""

    def get_user_customer(self) -> str:
        return self._decoded_id_token.get("custom:customer")

    def get_username(self) -> str:
        return self._decoded_id_token.get("cognito:username")

    def is_user_epc(self) -> bool:
        return self.get_user_customer() == "epc"

    def _refresh(self, refresh_token: str = None, force=False):
        if self.is_session_valid() and not force:
            # If we have credentials that haven't expired yet, bail out
            return

        refresh_token = refresh_token or self._get_refresh_token_pref()
        client: CognitoIdpClient = self._get_anonymous_client("cognito-idp")

        try:
            response = client.initiate_auth(
                ClientId=self.config["client_id"],
                AuthFlow="REFRESH_TOKEN",
                AuthParameters={
                    "REFRESH_TOKEN": refresh_token,
                },
            )
        except client.exceptions.NotAuthorizedException:
            print(
                f"{self._tag} Previous refresh token invalid. Clearing and forcing user to log in again."
            )
            self._clear_refresh_token_pref()
            return

        # auth result has the keys: AccessToken, ExpiresIn, IdToken, TokenType
        result = response["AuthenticationResult"]
        self._access_token = result["AccessToken"]
        self._expires_in = result["ExpiresIn"]
        self._expires_time = datetime.now() + timedelta(seconds=self._expires_in)
        self._id_token = result["IdToken"]
        self._decoded_id_token = decode_jwt(self._id_token)["payload"]
        self._token_type = result["TokenType"]

        self._init_auth_session()
        self._create_resources()

    def log_out(self):
        self._access_token = ""
        self._expires_in = ""
        self._expires_time = datetime.min
        self._id_token = ""
        self._decoded_id_token = ""
        self._token_type = ""

        self._s3_resource = None
        self._sync_config.set(Vars.refresh_token, None)


if __name__ == "__main__":
    # refresh_token = "..."
    # config = SyncConfig.get_instance()

    import sys

    env = sys.argv[1]
    username = sys.argv[2]
    password = sys.argv[3]

    helper = CognitoHelper(env)
    helper.authenticate(username, password)
    print(helper._id_token)
