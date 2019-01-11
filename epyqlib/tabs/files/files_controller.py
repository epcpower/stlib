from tabs.files import graphql


class FilesController:

    def __init__(self):
        self.api = graphql.API()

    def get_inverter_associations(self, inverter_id: str):
        return self.api.get_associations(inverter_id)
