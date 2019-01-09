import json
import requests


class API:
    server_info = {
        "url": "https://b3oofrroujeutdd4zclqlwedhm.appsync-api.us-west-2.amazonaws.com/graphql",
        "headers": {
          "x-api-key": "da2-77ph5d7dlnghhnlufivpbn3cri"
        }
    }

    listInvertersQuery = """
        query {
            listInverters(limit: 2) {
                items {
                    id,
                    serialNumber,
                    notes
                }
                nextToken
            }
        }
    """

    listInverters = {
        "query": listInvertersQuery,
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

    def getInverterQuery(self, inverter_id):
        return {
            "query": self.get_inverter_string,
            "variables": {
                "inverterId": inverter_id
            }
        }

    get_association_str = """
        query ($inverterId: ID!) {
            getAssociations(inverterId: $inverterId) {
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

    def getAssociationQuery(self, inverter_id):
        return {
            "query": self.get_association_str,
            "variables": {
                "inverterId": inverter_id
            }
        }


    def make_request(self, json):
        return requests.post(
            self.server_info["url"],
            headers=self.server_info["headers"],
            json=json
        )

    def fetch_inverter_list(self):
        response = self.make_request(self.listInverters)

        return json.loads(response.text)['data']['listInverters']['items']

    def get_inverter_test(self):
        return self.get_inverter("d2ea61cf-50f1-4ece-9caa-8b5fd250036d")

    def get_associations_test(self):
        return self.get_associations("1e4aabcc-d470-4dac-abf5-b9b4f6b8841e")

    def get_inverter(self, inverter_id):
        response = self.make_request(self.getInverterQuery(inverter_id))
        return json.loads(response.text)['data']['getInverter']

    def get_associations(self, inverter_id):
        response = self.make_request(self.getAssociationQuery(inverter_id))
        return json.loads(response.text)['data']['getAssociations']['items']
