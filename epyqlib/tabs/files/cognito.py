import logging
from datetime import datetime, timedelta

import botocore
from boto3 import Session
from boto3_type_annotations.s3 import ServiceResource as S3Resource
import attr

import boto3
from boto3_type_annotations.cognito_identity import Client as CognitoIdentityClient
from boto3_type_annotations.cognito_idp import Client as CognitoIdpClient

from epyqlib.tabs.files.sync_config import SyncConfig, Vars

logger = logging.getLogger("CognitoHelper")


@attr.s(slots=True, auto_attribs=True)
class CognitoException(Exception):
    message: str

class CognitoHelper:

    _tag = '[CognitoHelper]'
    _identity_pool_id = 'us-west-2:b953611b-23f3-4f76-b463-cfb6c4e75b56'
    _client_id = '544t83vhj0ubcqcroo9sf77i04'
    _region = "us-west-2"

    _user_pool_id = 'cognito-idp.us-west-2.amazonaws.com/us-west-2_8rzSRDPG6'

    def __init__(self):
        self._access_token = ""
        self._expires_in = 0
        self._expires_time = datetime.min
        self._id_token = ""
        self._refresh_token = ""
        self._token_type = ""

        self._s3_resource: S3Resource = None

        self._session: Session = boto3.session.Session(region_name=self._region,
                                                       aws_access_key_id="",
                                                       aws_secret_access_key="",
                                                       aws_session_token=""
                                                       )

        self._sync_config = SyncConfig.get_instance()

    def authenticate(self, username: str, password: str):
        """
        :raises botocore.errorfactory.UserNotFoundException If username is wrong
        :raises botocore.errorfactory.NotAuthorizedException If password is wrong
        """
        print(f"{self._tag} Beginning authentication for user {username}")
        client: CognitoIdpClient = self._get_anonymous_client('cognito-idp')

        try:
            response = client.initiate_auth(
                ClientId=self._client_id,
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    'USERNAME': username,
                    'PASSWORD': password
                }
            )
        except Exception:
            raise CognitoException("Invalid credentials.")

        result = response['AuthenticationResult']
        self._access_token = result['AccessToken']
        self._expires_in = result['ExpiresIn']
        self._expires_time = datetime.now() + timedelta(seconds=self._expires_in)
        self._id_token = result['IdToken']
        self._refresh_token = result['RefreshToken']
        self._token_type = result['TokenType']

        self._sync_config.set(Vars.refresh_token, self._refresh_token)
        # auth result has the keys: AccessToken, ExpiresIn, IdToken, RefreshToken, TokenType

        self._init_auth_session()

        print(f"{self._tag} Authentication successful")
        self._create_resources()


    def _init_auth_session(self):
        cognito: CognitoIdentityClient = boto3.client('cognito-identity', region_name=self._region)

        id = cognito.get_id(
            AccountId="674475255666",
            IdentityPoolId=self._identity_pool_id,
            Logins={self._user_pool_id: self._id_token}
        )

        response = cognito.get_credentials_for_identity(
            IdentityId=id['IdentityId'],
            Logins={self._user_pool_id: self._id_token}
        )
        credentials = response['Credentials']

        self._session = boto3.session.Session(region_name=self._region,
                                              aws_access_key_id=credentials['AccessKeyId'],
                                              aws_secret_access_key=credentials['SecretKey'],
                                              aws_session_token=credentials['SessionToken'])


    def _init_unauth_session(self):
        ### DEPRECATED: Should not be needed anymore
        cognito: CognitoIdentityClient = boto3.client('cognito-identity', region_name=self._region)

        id = cognito.get_id(IdentityPoolId=self._identity_pool_id)

        response = cognito.get_credentials_for_identity(IdentityId=id['IdentityId'])
        credentials = response['Credentials']

        self._session = boto3.session.Session(region_name=self._region,
                                              aws_access_key_id=credentials['AccessKeyId'],
                                              aws_secret_access_key=credentials['SecretKey'],
                                              aws_session_token=credentials['SessionToken'])

    def _get_anonymous_client(self, type: str):
        return boto3.client(
            type,
            region_name=self._region,
            aws_access_key_id = "",
            aws_secret_access_key = "",
            aws_session_token = ""
        )

    def get_s3_resource(self):
        if not self.is_session_valid():
            self._refresh()

        return self._s3_resource


    def _create_resources(self):
        self._s3_resource = self._session.resource('s3')


    def _get_client(self, type: str):
        return self._session.client(type)

    def _get_resource(self, service_name: str):
        return self._session.resource(service_name)

    def is_session_valid(self):
        return datetime.now() < self._expires_time

    def _get_refresh_token_pref(self):
        return self._sync_config.get(Vars.refresh_token)

    def is_user_logged_in(self) -> bool:
        token = self._get_refresh_token_pref()
        return token is not None and token != ""

    def _refresh(self, refresh_token: str = None, force=False):
        if self.is_session_valid() and not force:
            # If we have credentials that haven't expired yet, bail out
            return

        refresh_token = refresh_token or self._get_refresh_token_pref()
        client: CognitoIdpClient = self._get_anonymous_client('cognito-idp')

        response = client.initiate_auth(
            ClientId=self._client_id,
            AuthFlow='REFRESH_TOKEN',
            AuthParameters={
                'REFRESH_TOKEN': refresh_token,
            }
        )

        # auth result has the keys: AccessToken, ExpiresIn, IdToken, TokenType
        result = response['AuthenticationResult']
        self._access_token = result['AccessToken']
        self._expires_in = result['ExpiresIn']
        self._expires_time = datetime.now() + timedelta(seconds=self._expires_in)
        self._id_token = result['IdToken']
        self._token_type = result['TokenType']

        self._init_auth_session()
        self._create_resources()

    def log_out(self):
        self._access_token = ""
        self._expires_in = ""
        self._expires_time = datetime.min
        self._id_token = ""
        self._token_type = ""

        self._s3_resource = None
        self._sync_config.set(Vars.refresh_token, None)


if __name__ == '__main__':
    # refresh_token = "..."
    config = SyncConfig.get_instance()
    helper = CognitoHelper()
    helper._refresh(config.get(Vars.refresh_token))
    print(helper._id_token)
