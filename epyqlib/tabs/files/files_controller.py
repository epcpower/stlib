import treq
from twisted.internet.defer import Deferred

from .graphql import API


class FilesController:

    bucket_path = 'https://s3-us-west-2.amazonaws.com/epc-files-dev/public/firmware/'

    def __init__(self):
        self.api = API()

    async def get_inverter_associations(self, inverter_id: str):
        groups = {
            'params': [],
            'firmware': [],
            'fault_logs': [],
            'other': []
        }

        associations = await self.api.get_associations(inverter_id)
        for association in associations:
            type = association['file']['type'].lower()
            if groups.get(type) is None:
                groups[type] = []
            groups[type].append(association)

        return groups

    async def download_file(self, filename: str, destination: str):
        outf = open(destination, 'wb')

        deferred: Deferred = treq.get(self.bucket_path + filename)
        deferred.addCallback(treq.collect, outf.write)
        deferred.addBoth(lambda _: outf.close())
        return await deferred
