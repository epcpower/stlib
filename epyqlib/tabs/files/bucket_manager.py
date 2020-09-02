from epyqlib.tabs.files.aws_login_manager import AwsLoginManager
from epyqlib.tabs.files.sync_config import SyncConfig


class BucketManager:
    _bucket_names = {
        "internal": "epc-files-internal-203222013089",
        "client": "epc-files-client-203222013089",
    }
    _bucket_name = _bucket_names[SyncConfig.get_env()]
    _logs_path = "logs/"
    _tag = "[Bucket Manager]"

    def __init__(self):
        self._aws = AwsLoginManager.get_instance()
        self._uploaded_logs: set[str] = None

    async def download_file(self, hash: str, filename: str):
        return await self._download(filename, "files/" + hash)

    async def download_log(self, hash: str, filename: str):
        # Is it really worth it to have logs in a separate folder...?
        return await self._download(filename, "logs/" + hash)

    async def _download(self, filename: str, key: str):
        try:
            bucket = self._aws.get_s3_resource().Bucket(self._bucket_name)
            bucket.download_file(Filename=filename, Key=key)
            print(f"{self._tag} Finished downloading {key}")
        except Exception as ex:
            import sys

            error_message = (
                f"{self._tag} Error downloading Key: {key} from Bucket: {self._bucket_name}.\n"
                + f"{str(ex)}\n"
            )
            sys.stderr.write(error_message)
            raise Exception(error_message)

    async def upload_log(self, source_path: str, dest_filename: str):
        print(f"{self._tag} Starting to upload log {dest_filename}")

        # TODO: Figure out if logs should really be uploaded to their own folder
        with open(source_path, "rb") as source_file:
            s3_resource = self._aws.get_s3_resource()
            bucket = s3_resource.Bucket(self._bucket_name)
            bucket.put_object(Key=self._logs_path + dest_filename, Body=source_file)

        print(f"{self._tag} Finished upload of log {dest_filename}")
        if self._uploaded_logs is not None:
            self._uploaded_logs.add(
                dest_filename
            )  # Assuming dest_filename is the file's hash

    def fetch_uploaded_log_names(self):
        if self._uploaded_logs is None:
            s3_resource = self._aws.get_s3_resource()
            bucket = s3_resource.Bucket(self._bucket_name)

            # Get list of all paths and trim the leading "logs/" from each
            self._uploaded_logs = set(
                [o.key[5:] for o in bucket.objects.filter(Prefix="logs/")]
            )

        return self._uploaded_logs


if __name__ == "__main__":
    bucket_manager = BucketManager()
    bucket_manager.fetch_uploaded_log_names()
    print(bucket_manager._uploaded_logs)
