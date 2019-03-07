import asyncio
import json
from enum import Enum
from typing import Callable, Dict

import treq
from twisted.internet import reactor
from twisted.internet.defer import ensureDeferred
from twisted.python.failure import Failure
from twisted.web.iweb import IResponse

from epyqlib.tabs.files.activity_log import Event
from epyqlib.tabs.files.websocket_handler import WebSocketHandler
from epyqlib.utils.general import safe_get


class GraphQLException(Exception):
    pass

class InverterNotFoundException(Exception):
    pass


class API:
    server_info = {
        "url": "https://b3oofrroujeutdd4zclqlwedhm.appsync-api.us-west-2.amazonaws.com/graphql",
        "headers": {
          "x-api-key": "da2-77ph5d7dlnghhnlufivpbn3cri"
        }
    }

    list_inverters_query = """
        query {
            listInverters(limit: 200) {
                items {
                    id,
                    serialNumber,
                    notes
                }
                nextToken
            }
        }
    """

    list_inverters = {
        "query": list_inverters_query,
        "variables": {}
    }

    _all_inverter_fields = """
                createdAt 
                deploymentDate 
                id 
                manufactureDate 
                model { name revision partNumber id __typename } 
                notes 
                serialNumber 
                site { 
                    name 
                    id 
                    customer { name id __typename } 
                    __typename 
                } 
                testDate 
                updatedAt 
                updatedBy 
                __typename 
    """

    get_inverter_string = """
        query ($inverterId: ID!) { 
            getInverter(id: $inverterId) {""" + \
                _all_inverter_fields + \
        """
            }
        } 
    """

    def _get_inverter_query(self, inverter_id: str):
        return {
            "query": self.get_inverter_string,
            "variables": {
                "inverterId": inverter_id
            }
        }


    _get_inverter_by_sn_string = """
        query ($serialNumber: String!) { 
            getInverterBySN(serialNumber: $serialNumber) {""" + \
                _all_inverter_fields + \
        """
            }
        } 
    """


    def _get_inverter_by_sn_query(self, serial_number: str):
        return {
            "query": self._get_inverter_by_sn_string,
            "variables": {
                "serialNumber": serial_number
            }
        }

    _frag_associations_field = """
            fragment associationFields on Association {
                id
                customer { name }
                file {id, createdBy, createdAt, description, filename, hash, notes, type, uploadPath, version}
                model {name}
                inverter {id, serialNumber}
                site {name}

                # updatedAt
            }
        """

    _get_associations_str = _frag_associations_field + \
            """
                query ($serialNumber: String) {
                    getInverterAssociations(serialNumber: $serialNumber) {
                        items {
                           ...associationFields
                        }
                    }
                }
            """

    def _get_associations_query(self, serial_number: str):
        return {
            "query": self._get_associations_str,
            "variables": {
                "serialNumber": serial_number
            }
        }

    _get_associations_for_customer_str = _frag_associations_field + \
        """
           query {
                getAssociationsForCustomer {
                    serialNumber,
                    associations {
                        ...associationFields
                    }
                }
            }
        """

    def _get_association_for_customer_query(self):
        return {
            "query": self._get_associations_for_customer_str,
            "variables": { }
        }

    _create_activity = """
        mutation Name (
            $inverterId: String!,
            $timestamp: String!,
            $type: String!,
            $details: AWSJSON
        ){
            createActivity(
                inverterId: $inverterId,
                timestamp: $timestamp,
                type: $type,
                details: $details
            ) {
                  inverterId
                  customerId
                  details
                  siteId
                  timestamp
                  type
                  
                  createdBy
            }
        }
    """

    def _get_create_activity_mutation(self, inverter_id: str, timestamp: str, type: str, details: dict):
        return {
            "query": self._create_activity,
            "variables": {
                "details": json.dumps(details),
                "inverterId": inverter_id,
                "timestamp": timestamp,
                "type": type
            }
        }

    _create_file_mutation = """
        mutation CreateFile (
            $filename: String!,
            $hash: String!,
            $notes: String,
            $type: FileType
            
        ){
            createFile(
                filename: $filename,
                hash: $hash,
                notes: $notes,
                type: $type 
            ) {
                id
                createdAt
                updatedAt
                updatedBy
                association {id}
                description
                filename
                hash
                notes
                version
                type
                uploadPath
            }
        }
    """

    class FileType(Enum):
        Firmware = "Firmware"
        Log = "Log"
        Other = "Other"
        Parameter = "Parameter"


    def _get_create_file_mutation(self, type: FileType, filename: str, hash: str, notes: str):
        return {
            "query": self._create_file_mutation,
            "variables": {
                "type": type.value,
                "filename": filename,
                "hash": hash,
                "notes": notes
            }
        }

    _create_association_mutation = """
        mutation (
            $fileId: ID!,
            $inverterId: ID
        ){
            createAssociation (
                fileId: $fileId,
                inverterId: $inverterId
            ) {
                id
                file { id filename notes createdAt }
                inverter { id, serialNumber }
            }
        }
    """

    def _get_create_association_mutation(self, inverterId: str, fileId: str):
        return {
            "query": self._create_association_mutation,
            "variables": {
                "fileId": fileId,
                "inverterId": inverterId
            }
        }

    _update_file_notes = """        
        mutation ($fileId: ID!, $description: String, $notes: String) {
            updateFile(id: $fileId, description: $description, notes: $notes) {
                id
                hash
                description
                notes
            }
        }
    """

    def _get_update_file_notes_mutation(self, file_id: str, description: str, notes: str):
        return {
            "query": self._update_file_notes,
            "variables": {
                "description": description,
                "fileId": file_id,
                "notes": notes
            }
        }


    def __init__(self):
        self.ws_handler = WebSocketHandler()

    async def _make_request(self, body):
        url = self.server_info["url"]
        headers = self.server_info["headers"]
        response: IResponse = await treq.post(url, headers=headers, json=body)
        if response.code >= 400:
            raise GraphQLException(f"{response.code} {response.phrase.decode('ascii')}")

        # content = await treq.content(response)
        body = await treq.json_content(response)

        if (body.get('data') is None and body.get('errors') is not None):
            raise GraphQLException(body['errors'])

        return body


    async def fetch_inverter_list(self):
        response = await self._make_request(self.list_inverters)

        return response['data']['listInverters']['items']


    async def get_inverter(self, inverter_id: str):
        response = await self._make_request(self._get_inverter_query(inverter_id))
        return response['data']['getInverter']

    async def get_inverter_by_serial(self, serial_number: str):
        response = await self._make_request(self._get_inverter_by_sn_query(serial_number))
        return response['data']['getInverterBySN']

    async def get_associations(self, serial_number: str):
        """
        :raises InverterNotFoundException
        """
        response = await self._make_request(self._get_associations_query(serial_number))
        message = safe_get(response, ['errors', 0, 'message']) or ''
        if ('Unable to find inverter' in message):
            raise InverterNotFoundException(message)

        return response['data']['getInverterAssociations']['items']

    async def get_associations_for_customer(self) -> Dict[str, Dict]:
        """
        :return: Dict of serialNumber -> association
        """
        response = await self._make_request(self._get_association_for_customer_query())
        items = response['data']['getAssociationsForCustomer']
        return {item['serialNumber']: item['associations'] for item in items}

    async def create_activity(self, event: Event):
        # details_json = json.dumps(event.details)
        request_body = self._get_create_activity_mutation(event.inverter_id, event.timestamp, event.type, event.details)
        print("[Graphql] Sending create activity request: " + json.dumps(request_body))
        response = await self._make_request(request_body)
        print(json.dumps(response))

    async def create_file(self, type: FileType, filename: str, hash: str, notes: str = None):
        response = await self._make_request(self._get_create_file_mutation(type, filename, hash, notes))
        return response['data']['createFile']

    async def create_association(self, inverterId: str, fileId: str):
        response = await self._make_request(self._get_create_association_mutation(inverterId, fileId))
        return response['data']['createAssociation']

    async def set_file_notes(self, file_id: str, description: str, notes: str):
        response = await self._make_request(self._get_update_file_notes_mutation(file_id, description, notes))
        return response['data']['updateFile']

    def awai(self, coroutine):
        # Or `async.run(coroutine)`
        return asyncio.get_event_loop().run_until_complete(coroutine)

    def run(self, coroutine):
        from twisted.internet.defer import ensureDeferred
        deferred = ensureDeferred(coroutine)
        deferred.addCallback(succ)
        deferred.addErrback(err)
        return deferred


    async def subscribe(self, message_handler: Callable[[str, dict], None]):
        gql = """subscription {
                    created: fileCreated { id }
                    updated: fileUpdated { id }
                    deleted: fileDeleted { id }
                }"""

        query = {
            "query": gql,
            "variables": {}
        }

        response = await self._make_request(query)
        mqttInfo = response['extensions']['subscription']['mqttConnections'][0]
        topics = response['extensions']['subscription']['newSubscriptions']
        client_id = mqttInfo['client']
        url = mqttInfo['url']
        self.ws_handler.connect(url, client_id, topics, message_handler)

    def is_subscribed(self):
        return self.ws_handler.is_subscribed()

    async def unsubscribe(self):
        if self.ws_handler.is_subscribed():
            self.ws_handler.disconnect()

    def set_id_token(self, id_token: str):
        self.server_info['headers']['Authorization'] = id_token


def main(reactor):
    from twisted.internet.defer import ensureDeferred

    api = API()
    deferred = ensureDeferred(api.get_associations("TestInv"))
    deferred.addCallback(succ)
    deferred.addErrback(err)
    return deferred

def succ(body):
    print("SUCCESS")
    print(body)

def err(error: Failure):
    print("ERROR ENCOUNTERED")
    print(error.type)
    print(error.value)
    print(error.getBriefTraceback())
    reactor.stop()


if __name__ == "__main__":
    # from twisted.internet.task import react
    # react(main)

    api = API()
    # d = ensureDeferred(api.subscribe())
    api.set_id_token("eyJraWQiOiJweldEOXl5WFdNOW82MGdLWVMxREdXZWFGc2lNcWNGM3BcL1ZTZnNuVU5ZVT0iLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIzZTA2OGQ4Yi01NTJmLTQ4YmYtYjVhZi1kZGViMDlhOTc3OWMiLCJjb2duaXRvOmdyb3VwcyI6WyJlcGMiXSwiZW1haWxfdmVyaWZpZWQiOnRydWUsImlzcyI6Imh0dHBzOlwvXC9jb2duaXRvLWlkcC51cy13ZXN0LTIuYW1hem9uYXdzLmNvbVwvdXMtd2VzdC0yXzhyelNSRFBHNiIsInBob25lX251bWJlcl92ZXJpZmllZCI6dHJ1ZSwiY29nbml0bzp1c2VybmFtZSI6InRlc3RlciIsImNvZ25pdG86cm9sZXMiOlsiYXJuOmF3czppYW06OjY3NDQ3NTI1NTY2Njpyb2xlXC9Db2duaXRvX2VwY0F1dGhfUm9sZSJdLCJhdWQiOiI0MTZncTRtZHBvczU1Y2ppcjFoNXU4ZzNzbCIsImV2ZW50X2lkIjoiYjE4ZDViYjUtMzZjMS0xMWU5LTk0NTItM2Q4MzQyOGExYjBjIiwidG9rZW5fdXNlIjoiaWQiLCJhdXRoX3RpbWUiOjE1NTA4NTQxMTQsInBob25lX251bWJlciI6IisxMTExMjIyMzM0NCIsImV4cCI6MTU1MTgzNDgzNSwiaWF0IjoxNTUxODMxMjM1LCJlbWFpbCI6ImJlbi5iZXJyeUBjcm9zc2NvbW0uY29tIn0.PZvs44g9BnAH5y34WSgYycZ2qvlrq2H57YSeKj2TrkTN53zJyuVET6YwSkb_Jvsq6QtQzLeAIymg5_jSr0o5cYOu9dp1rTgqQ1KdbPsPcOWPV9u7jilmPK-LeErJHP9zmlcpSvgurnJWet3tKgJhrIz2DD9nU6JINf1MvsINyIuBx8D3stivBPR3uAjO_cCwdwwmBa88txa35XLWPRMNReCnMTfxBcdT4tOBL_e1Wg9Cf5qUmxpagB9rYn3foOG5tjzRqb2XQ9v0UadPXzQYEKFs4dbThR2O5jrWQgvGRWH73TYS7L2euSlbyge9PEL6UapmhZ0Y0DyHilEEb8tZIg")
    # d = ensureDeferred(api.create_file(API.FileType.Log, "testlog.log", "testhash"))
    # d = ensureDeferred(api.create_association("TestInv", "TestFile"))
    # d = ensureDeferred(api.set_file_notes("a5ef9c19-6592-47a7-ab2d-f3c7bafef51c", "Python notes"))
    # d = ensureDeferred(api.get_associations("0"))
    d = ensureDeferred(api.get)
    d.addCallback(succ)
    d.addErrback(err)
    # ensureDeferred(api.test_connection())
    reactor.run()