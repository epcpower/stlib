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
    _client_id = '416gq4mdpos55cjir1h5u8g3sl'
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
        client: CognitoIdpClient = self.get_anonymous_client('cognito-idp')

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

    def get_anonymous_client(self, type: str):
        return boto3.client(
            type,
            region_name=self._region,
            aws_access_key_id = "",
            aws_secret_access_key = "",
            aws_session_token = ""
        )

    def get_s3_resource(self):
        if not self._is_session_valid():
            self._refresh()

        return self._s3_resource


    def _create_resources(self):
        self._s3_resource = self._session.resource('s3')


    def _get_client(self, type: str):
        return self._session.client(type)

    def _get_resource(self, service_name: str):
        return self._session.resource(service_name)

    def _is_session_valid(self):
        return datetime.now() < self._expires_time

    def _get_refresh_token_pref(self):
        return self._sync_config.get(Vars.refresh_token)

    def is_user_logged_in(self) -> bool:
        token = self._get_refresh_token_pref()
        return token is not None and token != ""

    def _refresh(self, refresh_token: str = None):
        if self._is_session_valid():
            # If have credentials that haven't expired yet, bail out
            return

        refresh_token = refresh_token or self._get_refresh_token_pref()
        client: CognitoIdpClient = self.get_anonymous_client('cognito-idp')

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
    refresh_token = "eyJjdHkiOiJKV1QiLCJlbmMiOiJBMjU2R0NNIiwiYWxnIjoiUlNBLU9BRVAifQ.VEjQ-DcDlH1qBjKJofIT7MV1iPom5kQN0WvEMSrYOOs2ZW8OImaLuKRIhf-4IvxP4pzXKrcl1dTcF-nlmNcdwbWuFQ8b1R8YoW_wf-RO37gQTiMLSVS0p9EADUl6tf-R6AN6tGG51D8g7ec6DQvDxPdQpZUPSX250OZtczM9kD1H_it3Y9FbFtYXc5TqQoviDa8Rq06MCnr0WAq0Ea_rGNU2EvnWsX5xWO17l4uOEziKJB68khm75UgeRJ0jCWVw1yviUf8A4ZP2ZPQuUpAHj_V-Bohltn8RyfeJZbHybAcf-6FkcSLrMoicz5ZrjzDMv1HHqFcGi7KoI9-BVLFzOg.c5k8d5nTvsIiIiKi.SmS9u8q5CClnW47Zi2r3ShrTJPLYX77FUfRPatvJYSx-0PnjgzyeGXK8SLFMttbCd2cU8IQZ_-b0040l30aqaiLqoEni7AbtlxRu6wBoPDpjORRYA3UW630nPPbZwQh2F9FfIt1FEONx3GucQMS0tBYUoU3w3lEACmmJPTUcLoxI1RgJZveom2u8jYGKLIcL6Szj9fZCIRX4OmD1-Z6Q9Nz4m22vAYqlqarhW7BuHMSDecNIk2Vt0Zk9Yn0W3H7IXqErp-k1C_0TbYhrsuUqS23owl3ZHei_ootbEkw3lhGleFQx7g8f8BCW4Bfw4R8Mkt3SE0cRAuDM9-mm9ZofjvFwrv-YiIZrRMgwRt_bQtTDZgjKh4kcX2Zlp81cCfTNaCjfn0Sm1EyI4po2lS9bjHiY49VjJETcoFm-nkqLlAD5Hq5iySSC5vtGg_cezXTc1GQvgDKc7tUa0CxJirgMQrkJifShWeY1k6Mk5L821L9gbBEdKFBDfPBczSrzUt3yP6LzzvCQljQWovO96Ou34j07ac-nnVTT5mpIcDRux_gZxZ5gjGEHTsR3MhdgSjK2waMnPPZWeXzv1WlpxU9zCULNy6gcRHHp7jzunsDdShxJPy0o46NXEOuQq-CEVNV_xzMt0UE9Tz_34bR-niI795H14kFzTXMXbrZQxgT3roKlbFf7IDb2jF2IOxwZTFDIDnj5-CFD2M_L3D-HyYWfiOUMJkIIKTvtW_NiF6mjm16kzTZE_iaVSzt8cvxm2mX2VCapVdSVWLWcHFahRrJMHmpVb-XgX9v6uyOCvfIZQCC5KZYB1XMFfw3rONhPDlhL4O7HlliJilFXK_xts1FmlIlMRQ1-zWqM1Y8yMoEd9JWL8qaYGuAMxy-7X6EjnhLgZvHjFs0G8CV3WWinRzYMkaRxj3J1hg5THJ7Suu8x2XsCKE9036HpMwZ69nYzJV-SAlKfyAuIdSOE_Le_tW6bvxiCybFQvFEGcp6InyJINQhUq-kdcioQoel2V7YaiwWT-SIfes2ZXOPHljIvUGxmrHAebR5SgFwBYrCAY84Fc5Rx-zBAK66jCFxl4P9NMjIssLliF83eCOVTuVrEeHCxSBUMcYTKEeetWfFEbhw9tEtbfuOtH9T4CQk5Cthtqid2sXNm84MKT82QOyq0OlBlR6ni2ismcyeQibJTtW6KBFCSRQaAMeb5Aj4sxP7BfK0WS22GqU-pfbDisN6A6MNiaBJTGLNCthyOLRrZRpIbZprc8gVWR1Tut5zaILjkotbgF9YR.0wiNQMzyTEBG5EB7KqR9iQ"
    helper = CognitoHelper()
    helper._refresh(refresh_token)
    print(helper._expires_in)
