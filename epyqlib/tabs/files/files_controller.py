import attr
import treq
from twisted.internet.defer import Deferred

from .graphql import API


@attr.s
class FilesController:
    api = attr.ib(factory=API)
    bucket_path = attr.ib(
        default=(
            'https://s3-us-west-2.amazonaws.com/epc-files-dev/public/firmware/'
        )
    )

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

    async def download_file(self, filename: str, destination: str):
        outf = open(destination, 'wb')

        deferred: Deferred = treq.get(self.bucket_path + filename)
        deferred.addCallback(treq.collect, outf.write)
        deferred.addBoth(lambda _: outf.close())
        return await deferred
