import asyncio
import json
from enum import Enum

import treq
from epyqlib.tabs.files.activity_log import Event
from epyqlib.tabs.files.websocket_handler import WebSocketHandler
from twisted.internet import reactor
from twisted.internet.defer import ensureDeferred
from twisted.python.failure import Failure
from twisted.web.iweb import IResponse
from typing import Callable, Dict, List, Coroutine


class GraphQLException(Exception):
    pass


class InverterNotFoundException(Exception):
    pass


class API:
    _tag = "[Graphql API]"

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

    list_inverters = {"query": list_inverters_query, "variables": {}}

    _all_inverter_fields = """
                id 
                
                deploymentDate 
                manufactureDate 
                model { name partNumber id __typename } 
                notes 
                serialNumber 
                site { 
                    name 
                    id 
                    customer { name id __typename } 
                    __typename 
                } 
                testDate 
                __typename 
    """

    get_inverter_string = (
        """
        query ($inverterId: ID!) { 
            getInverter(id: $inverterId) {"""
        + _all_inverter_fields
        + """
            }
        } 
    """
    )

    def _get_inverter_query(self, inverter_id: str):
        return {
            "query": self.get_inverter_string,
            "variables": {"inverterId": inverter_id},
        }

    _get_inverter_by_sn_string = (
        """
        query ($serialNumber: String!) { 
            getInverterBySN(serialNumber: $serialNumber) {"""
        + _all_inverter_fields
        + """
            }
        } 
    """
    )

    def _get_inverter_by_sn_query(self, serial_number: str):
        return {
            "query": self._get_inverter_by_sn_string,
            "variables": {"serialNumber": serial_number},
        }

    _frag_associations_field = """
            fragment associationFields on Association {
                id
                customer { name }
                file {id, createdBy, createdAt, description, filename, hash, notes, owner, type, version}
                model {name}
                inverter {id, serialNumber}
                site {name}

                # updatedAt
            }
        """

    _get_association_str = (
        _frag_associations_field
        + """
                query ($id: ID!, $fileId: ID!) {
                    getAssociation(id: $id, fileId: $fileId) {
                       ...associationFields
                    }
                }
            """
    )

    def _get_association_query(self, association_id: str, file_id: str):
        return {
            "query": self._get_association_str,
            "variables": {"id": association_id, "fileId": file_id},
        }

    _get_associations_str = (
        _frag_associations_field
        + """
                query ($serialNumber: String) {
                    getInverterAssociations(serialNumber: $serialNumber) {
                        items {
                           ...associationFields
                        }
                    }
                }
            """
    )

    def _get_associations_query(self, serial_number: str):
        return {
            "query": self._get_associations_str,
            "variables": {"serialNumber": serial_number},
        }

    _get_associations_for_customer_str = (
        _frag_associations_field
        + """
           query {
                getAssociationsForCustomer {
                    serialNumber,
                    associations {
                        ...associationFields
                    }
                }
            }
        """
    )

    def _get_association_for_customer_query(self):
        return {"query": self._get_associations_for_customer_str, "variables": {}}

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
                  details
                  timestamp
                  type
                  
                  createdBy
            }
        }
    """

    def _get_create_activity_mutation(
        self, inverter_id: str, timestamp: str, type: str, details: dict
    ):
        return {
            "query": self._create_activity,
            "variables": {
                "details": json.dumps(details),
                "inverterId": inverter_id,
                "timestamp": timestamp,
                "type": type,
            },
        }

    _frag_files_fields = """
        fragment fileFields on File {
                id
                createdAt
                createdBy
                updatedAt
                updatedBy
                association {id}
                description
                filename
                hash
                notes
                owner
                version
                type
        }
    """

    _create_file_mutation = (
        _frag_files_fields
        + """
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
                ...fileFields
            }
        }
    """
    )

    class FileType(Enum):
        Firmware = "Firmware"
        Log = "Log"
        Other = "Other"
        Parameter = "Parameter"
        PMVS = "PMVS"

    def _get_create_file_mutation(
        self, type: FileType, filename: str, hash: str, notes: str
    ):
        return {
            "query": self._create_file_mutation,
            "variables": {
                "type": type.value,
                "filename": filename,
                "hash": hash,
                "notes": notes,
            },
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
                file { id filename notes hash createdAt }
                inverter { id, serialNumber }
            }
        }
    """

    def _get_create_association_mutation(self, inverterId: str, fileId: str):
        return {
            "query": self._create_association_mutation,
            "variables": {"fileId": fileId, "inverterId": inverterId},
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

    def _get_update_file_notes_mutation(
        self, file_id: str, description: str, notes: str
    ):
        return {
            "query": self._update_file_notes,
            "variables": {
                "description": description,
                "fileId": file_id,
                "notes": notes,
            },
        }

    urls = {
        "internal": "https://kew33ruufvh5bpocxosmuegbvq.appsync-api.us-west-2.amazonaws.com/graphql",
        "client": "https://nd6i76lygfaoxoe4xxrxnwh5ty.appsync-api.us-west-2.amazonaws.com/graphql",
    }

    def __init__(self, environment: str):
        self.ws_handler = WebSocketHandler()
        self.server_url = self.urls[environment]
        self.headers = {}

    async def _make_request(self, body):
        try:
            response: IResponse = await treq.post(
                self.server_url, headers=(self.headers), json=body
            )
            if response.code >= 400:
                raise GraphQLException(
                    [f"{response.code} {response.phrase.decode('ascii')}"]
                )
        except Exception as e:
            print(
                f"{self._tag} Error during outgoing query: {body['query']} {body['variables']}"
            )
            raise e

        # content = await treq.content(response)
        response = await treq.json_content(response)

        if response.get("errors") is not None:
            print(f"{self._tag} Errors encountered making graphQL request:")
            print(f"{self._tag} Outgoing query: {body['query']}")
            print(
                f"{self._tag} Outgoing variables: {json.dumps(body['variables'], indent=2)}"
            )
            for error in response["errors"]:
                print(f"{self._tag} Error encountered: {json.dumps(error, indent=2)}")
            messages = [
                f"{e.get('errorType') or 'Error'}: {e['message']}"
                for e in response["errors"]
            ]

            raise GraphQLException(messages)

        return response

    async def fetch_inverter_list(self):
        response = await self._make_request(self.list_inverters)

        return response["data"]["listInverters"]["items"]

    async def get_inverter(self, inverter_id: str):
        response = await self._make_request(self._get_inverter_query(inverter_id))
        return response["data"]["getInverter"]

    async def get_inverter_by_serial(self, serial_number: str):
        response = await self._make_request(
            self._get_inverter_by_sn_query(serial_number)
        )
        return response["data"]["getInverterBySN"]

    async def get_association(self, association_id: str, file_id: str):
        response = await self._make_request(
            self._get_association_query(association_id, file_id)
        )
        return response["data"]["getAssociation"]

    async def get_associations(self, serial_number: str):
        """
        :raises InverterNotFoundException
        """
        try:
            response = await self._make_request(
                self._get_associations_query(serial_number)
            )
            return response["data"]["getInverterAssociations"]["items"]
        except GraphQLException as e:
            args: List[str] = e.args
            for message in args:
                if "Unable to find inverter" in message:
                    raise InverterNotFoundException(message)
            raise e

    async def get_associations_for_customer(self) -> Dict[str, Dict]:
        """
        :return: Dict of serialNumber -> association
        """
        response = await self._make_request(self._get_association_for_customer_query())
        items = response["data"]["getAssociationsForCustomer"]
        return {item["serialNumber"]: item["associations"] for item in items}

    async def create_activity(self, event: Event):
        # details_json = json.dumps(event.details)
        request_body = self._get_create_activity_mutation(
            event.inverter_id, event.timestamp, event.type, event.details
        )
        print("[Graphql] Sending create activity request: " + json.dumps(request_body))
        response = await self._make_request(request_body)
        print(json.dumps(response))

    async def create_file(
        self, type: FileType, filename: str, hash: str, notes: str = None
    ):
        response = await self._make_request(
            self._get_create_file_mutation(type, filename, hash, notes)
        )
        return response["data"]["createFile"]

    async def create_association(self, inverterId: str, fileId: str):
        response = await self._make_request(
            self._get_create_association_mutation(inverterId, fileId)
        )
        return response["data"]["createAssociation"]

    async def test_connection(self):
        response = await self._make_request({"query": "{ __typename}"})

    async def set_file_notes(self, file_id: str, description: str, notes: str):
        response = await self._make_request(
            self._get_update_file_notes_mutation(file_id, description, notes)
        )
        return response["data"]["updateFile"]

    async def subscribe(
        self,
        customer_id: str,
        on_message: Callable[[str, dict], Coroutine],
        on_close: Callable[[], Coroutine] = None,
    ):
        print(
            f"{self._tag} Subscribing to events for public events and events for context {customer_id}"
        )

        gql = """subscription($customerId: String!) {
                    # orgFileCreated: fileCreated(owner: $customerId) { id }
                    orgFileUpdated: fileUpdated(owner: $customerId) { id }
                    orgFileDeleted: fileDeleted(owner: $customerId) { id }
                    
                    # publicFileCreated: fileCreated(owner: "public") { id }
                    publicFileUpdated: fileUpdated(owner: "public") { id }
                    publicFileDeleted: fileDeleted(owner: "public") { id }
                    
                    orgAssociationCreated: associationCreated(owner: $customerId) { id }
                    orgAssociationDeleted: associationDeleted(owner: $customerId) { id }
                    
                    publicAssociationCreated: associationCreated(owner: "public") { id }
                    publicAssociationDeleted: associationDeleted(owner: "public") { id }
                }"""

        query = {"query": gql, "variables": {"customerId": customer_id}}

        response = await self._make_request(query)
        self.ws_handler.connect(response, on_message, on_close)

    def is_subscribed(self):
        return self.ws_handler.is_subscribed()

    async def unsubscribe(self):
        if self.ws_handler.is_subscribed():
            self.ws_handler.resubscribe = False
            self.ws_handler.disconnect()

    def set_id_token(self, id_token: str):
        self.headers["Authorization"] = id_token


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
    api.set_id_token(
        "eyJraWQiOiJweldEOXl5WFdNOW82MGdLWVMxREdXZWFGc2lNcWNGM3BcL1ZTZnNuVU5ZVT0iLCJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIzZTA2OGQ4Yi01NTJmLTQ4YmYtYjVhZi1kZGViMDlhOTc3OWMiLCJjb2duaXRvOmdyb3VwcyI6WyJlcGMiXSwiZW1haWxfdmVyaWZpZWQiOnRydWUsImlzcyI6Imh0dHBzOlwvXC9jb2duaXRvLWlkcC51cy13ZXN0LTIuYW1hem9uYXdzLmNvbVwvdXMtd2VzdC0yXzhyelNSRFBHNiIsInBob25lX251bWJlcl92ZXJpZmllZCI6dHJ1ZSwiY29nbml0bzp1c2VybmFtZSI6InRlc3RlciIsImNvZ25pdG86cm9sZXMiOlsiYXJuOmF3czppYW06OjY3NDQ3NTI1NTY2Njpyb2xlXC9Db2duaXRvX2VwY0F1dGhfUm9sZSJdLCJhdWQiOiI0MTZncTRtZHBvczU1Y2ppcjFoNXU4ZzNzbCIsImV2ZW50X2lkIjoiYjE4ZDViYjUtMzZjMS0xMWU5LTk0NTItM2Q4MzQyOGExYjBjIiwidG9rZW5fdXNlIjoiaWQiLCJhdXRoX3RpbWUiOjE1NTA4NTQxMTQsInBob25lX251bWJlciI6IisxMTExMjIyMzM0NCIsImV4cCI6MTU1MTgzNDgzNSwiaWF0IjoxNTUxODMxMjM1LCJlbWFpbCI6ImJlbi5iZXJyeUBjcm9zc2NvbW0uY29tIn0.PZvs44g9BnAH5y34WSgYycZ2qvlrq2H57YSeKj2TrkTN53zJyuVET6YwSkb_Jvsq6QtQzLeAIymg5_jSr0o5cYOu9dp1rTgqQ1KdbPsPcOWPV9u7jilmPK-LeErJHP9zmlcpSvgurnJWet3tKgJhrIz2DD9nU6JINf1MvsINyIuBx8D3stivBPR3uAjO_cCwdwwmBa88txa35XLWPRMNReCnMTfxBcdT4tOBL_e1Wg9Cf5qUmxpagB9rYn3foOG5tjzRqb2XQ9v0UadPXzQYEKFs4dbThR2O5jrWQgvGRWH73TYS7L2euSlbyge9PEL6UapmhZ0Y0DyHilEEb8tZIg"
    )
    # d = ensureDeferred(api.create_file(API.FileType.Log, "testlog.log", "testhash"))
    # d = ensureDeferred(api.create_association("TestInv", "TestFile"))
    # d = ensureDeferred(api.set_file_notes("a5ef9c19-6592-47a7-ab2d-f3c7bafef51c", "Python notes"))
    # d = ensureDeferred(api.get_associations("0"))
    d = ensureDeferred(api.get)
    d.addCallback(succ)
    d.addErrback(err)
    # ensureDeferred(api.test_connection())
    reactor.run()
