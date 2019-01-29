import asyncio
from twisted.web.iweb import IResponse
import treq

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

    get_inverter_string = """
        query ($inverterId: ID!) { 
            getInverter(id: $inverterId) { 
                createdAt 
                deploymentDate 
                id 
                manufactureDate 
                model { name revision partNumber codes id __typename } 
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

    get_association_str = """
        query ($inverterId: ID!) {
            getInverterAssociations(inverterId: $inverterId) {
                items {
                    id
                    customer { name }
                    file {id, filename, hash, notes, type, uploadPath, version}
                    model {name}
                    inverter {id, serialNumber}
                    site {name}
                    
                    # updatedAt
                }
            }
        }
    """

    def _get_association_query(self, inverter_id: str):
        return {
            "query": self.get_association_str,
            "variables": {
                "inverterId": inverter_id
            }
        }

    async def _make_request(self, body):
        url = self.server_info["url"]
        headers = self.server_info["headers"]
        response: IResponse = await treq.post(url, headers=headers, json=body)
        if response.code >= 400:
            raise GraphQLException(response.code)

        content = await treq.content(response)
        body = await treq.json_content(response)

        if (body.get('data') is None and body.get('errors') is not None):
            raise GraphQLException(body['errors'])

        return body


    async def fetch_inverter_list(self):
        response = await self._make_request(self.list_inverters)

        return response['data']['listInverters']['items']

    async def get_inverter_test(self):
        return await self.get_inverter("d2ea61cf-50f1-4ece-9caa-8b5fd250036d")

    async def get_inverter(self, inverter_id: str):
        response = await self._make_request(self._get_inverter_query(inverter_id))
        return response['data']['getInverter']

    async def get_associations(self, inverter_id: str):
        response = await self._make_request(self._get_association_query(inverter_id))
        message = safe_get(response, ['errors', 0, 'message']) or ''
        if ('Unable to find inverter' in message):
            raise InverterNotFoundException(message)

        return response['data']['getInverterAssociations']['items']

    def awai(self, coroutine):
        # Or `async.run(coroutine)`
        return asyncio.get_event_loop().run_until_complete(coroutine)

    def run(self, coroutine):
        from twisted.internet.defer import ensureDeferred
        deferred = ensureDeferred(coroutine)
        deferred.addCallback(succ)
        deferred.addErrback(err)
        return deferred

    def foo(self, reactor):
        return self.run(self.get_associations("TestInv"))



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

def err(error):
    print("ERROR ENCOUNTERED")
    print(error)

if __name__ == "__main__":
    from twisted.internet.task import react
    react(main)