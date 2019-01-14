from .graphql import API


class FilesController:

    def __init__(self):
        self.api = API()

    async def get_inverter_associations(self, inverter_id: str):
        groups = {
            'model': [],
            'customer': [],
            'site': [],
            'inverter': []
        }

        associations = await self.api.get_associations(inverter_id)
        for association in associations:
            if association['customer'] is not None:
                associations['customer'].append(association)
            elif association['site'] is not None:
                associations['site'].append(association)
            elif association['model'] is not None:
                associations['model'].append(association)
            else:
                associations['inverter'].append(association)

        return associations

