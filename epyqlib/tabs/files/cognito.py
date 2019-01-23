import boto3
from boto3_type_annotations.cognito_identity import Client as CognitoIdentityClient
from boto3_type_annotations.cognito_idp import Client as CognitoIdpClient


class CognitoHelper:
    _identity_pool_id = 'us-west-2:b953611b-23f3-4f76-b463-cfb6c4e75b56'
    _client_id = '416gq4mdpos55cjir1h5u8g3sl'
    _region = "us-west-2"

    def _get_client(self):
        cognito: CognitoIdentityClient = boto3.client('cognito-identity', region_name=self._region)
        id = cognito.get_id(IdentityPoolId=self._identity_pool_id)
        response = cognito.get_credentials_for_identity(IdentityId=id['IdentityId'])
        credentials = response['Credentials']

        client: CognitoIdpClient = boto3.client('cognito-idp',
                region_name=self._region,
                aws_access_key_id=credentials['AccessKeyId'],
                aws_secret_access_key=credentials['SecretKey'],
                aws_session_token=credentials['SessionToken']
            )

        return client

    def authenticate(self, username: str, password: str):
        client: CognitoIdpClient = self._get_client()

        response = client.initiate_auth(
            ClientId=self._client_id,
            AuthFlow='USER_PASSWORD_AUTH',
            AuthParameters={
                'USERNAME': username,
                'PASSWORD': password
            }
        )

        return response['AuthenticationResult']
        # auth result has the keys: AccessToken, ExpiresIn, IdToken, RefreshToken, TokenType

    def refresh(self, refresh_token: str):
        client: CognitoIdpClient = self._get_client()
        response = client.initiate_auth(
            ClientId=self._client_id,
            AuthFlow='REFRESH_TOKEN',
            AuthParameters={
                'REFRESH_TOKEN': refresh_token,
            }
        )

        return response['AuthenticationResult']
        # auth result has the keys: AccessToken, ExpiresIn, IdToken, TokenType

