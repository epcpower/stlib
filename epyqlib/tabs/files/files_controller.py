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
                groups['customer'].append(association)
            elif association['site'] is not None:
                groups['site'].append(association)
            elif association['model'] is not None:
                groups['model'].append(association)
            else:
                groups['inverter'].append(association)

        return groups

