import treq
from twisted.internet.defer import Deferred


class BucketManager():
    _bucket_path = 'https://s3-us-west-2.amazonaws.com/epc-files-dev/files/'

    async def download_file(self, hash: str, filename: str):
        destination = open(filename, "wb")

        deferred: Deferred = treq.get(self._bucket_path + hash)
        deferred.addCallback(treq.collect, destination.write)
        deferred.addCallback(self.foo, hash)
        # deferred.addBoth(lambda _: destination.close())
        return deferred

    def foo(self, result, hash):
        print(f"[Bucket Manager] Finished downloading {hash} ")

