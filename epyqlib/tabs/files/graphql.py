import asyncio
import aiohttp


class GraphQLException(Exception):
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

    def get_inverter_query(self, inverter_id: str):
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
                    file {filename, uploadPath}
                    model {name}
                    inverter {id, serialNumber}
                    site {name}
                }
            }
        }
    """

    def get_association_query(self, inverter_id: str):
        return {
            "query": self.get_association_str,
            "variables": {
                "inverterId": inverter_id
            }
        }


    async def make_request(self, json):
        url = self.server_info["url"]
        headers = self.server_info["headers"]

        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(url, json=json) as response:
                body = await response.json()
                errors = body.get('errors')
                if errors is not None:
                    raise GraphQLException(errors)
                return body


    async def fetch_inverter_list(self):
        response = await self.make_request(self.list_inverters)

        return response['data']['listInverters']['items']

    async def get_inverter_test(self):
        return await self.get_inverter("d2ea61cf-50f1-4ece-9caa-8b5fd250036d")

    async def get_associations_test(self):
        return await self.get_associations("TestInv")

    async def get_inverter(self, inverter_id: str):
        response = await self.make_request(self.get_inverter_query(inverter_id))
        return response['data']['getInverter']

    async def get_associations(self, inverter_id: str):
        response = await self.make_request(self.get_association_query(inverter_id))
        return response['data']['getInverterAssociations']['items']

    def awai(self, coroutine):
        return asyncio.get_event_loop().run_until_complete(coroutine)
