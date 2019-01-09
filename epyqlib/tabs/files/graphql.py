
# Approach 1: Strings
# Approach 2: JSON objects
import json

import requests


class API:
    server_info = {
      "name": "EPC dev",
      "url": "https://b3oofrroujeutdd4zclqlwedhm.appsync-api.us-west-2.amazonaws.com/graphql",
      "options": {
        "headers": {
          "x-api-key": "da2-77ph5d7dlnghhnlufivpbn3cri"
        }
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
        # "operationName": "ListInverters",
        "query": listInvertersQuery,
        "variables": {}
    }

    getInverterQuery = """
        query getInverter($inverterId: ID!) { 
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

    getInverter = {
        # "operationName": "ListInverters",
        "query": getInverterQuery,
        "variables": {
            "inverterId": "d2ea61cf-50f1-4ece-9caa-8b5fd250036d"
        }
    }


    def make_request(self, json):
        return requests.post(
            self.server_info["url"],
            headers=self.server_info["options"]["headers"],
            json=json
        )

    def fetch_inverter_list(self):
        response = self.make_request(self.listInverters)

        return json.loads(response.text)['data']['listInverters']['items']


    def get_inverter(self):
        response = self.make_request(self.getInverter)

        return json.loads(response.text)
