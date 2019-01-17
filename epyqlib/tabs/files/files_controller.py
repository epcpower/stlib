from datetime import datetime, timedelta

import treq
from twisted.internet.defer import Deferred

from .graphql import API


class FilesController:

    bucket_path = 'https://s3-us-west-2.amazonaws.com/epc-files-dev/public/firmware/'

    def __init__(self):
        self.api = API()
        self.old_notes: str = None
        self.last_sync: datetime = None

    def set_sync_time(self) -> str:
        self.last_sync = datetime.now()
        return self.get_sync_time()

    def get_sync_time(self) -> str:
        return self.last_sync.strftime('%l:%M%p %m/%d')

    def should_sync(self):
        if self.last_sync is None:
            return True

        sync_time = self.last_sync + timedelta(minutes=5)
        return sync_time < datetime.now()

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

    def set_original_notes(self, notes: str):
        self.old_notes = notes

    def notes_modified(self, new_notes):
        if self.old_notes is None:
            return False

        return (len(self.old_notes) != len(new_notes)) or self.old_notes != new_notes
