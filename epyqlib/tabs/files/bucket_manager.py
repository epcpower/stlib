from epyqlib.tabs.files.aws_login_manager import AwsLoginManager

class BucketManager():
    _bucket_name = 'epc-files-dev'
    _bucket_url = 'https://s3-us-west-2.amazonaws.com/' + _bucket_name + '/'
    _files_url = _bucket_url + 'files/'
    _logs_path = 'logs/'
    _tag = "[Bucket Manager]"

    def __init__(self):
        self._aws = AwsLoginManager.get_instance()
        self._uploaded_logs: set[str] = None

    async def download_file(self, hash: str, filename: str):
        bucket = self._aws.get_s3_resource().Bucket(self._bucket_name)
        bucket.download_file(Filename=filename, Key='files/' + hash)
        print(f"{self._tag} Finished downloading {hash}")

    async def upload_log(self, source_path: str, dest_filename: str):
        print(f"{self._tag} Starting to upload log {dest_filename}")

        with open(source_path, "rb") as source_file:
            s3_resource = self._aws.get_s3_resource()
            bucket = s3_resource.Bucket(self._bucket_name)
            bucket.put_object(Key=self._logs_path + dest_filename, Body=source_file)

        print(f"{self._tag} Finished upload of log {dest_filename}")
        self._uploaded_logs.add(dest_filename) # Assuming dest_filename is the file's hash

    def fetch_uploaded_log_names(self):
        if self._uploaded_logs is None:
            s3_resource = self._aws.get_s3_resource()
            bucket = s3_resource.Bucket(self._bucket_name)

            # Get list of all paths and trim the leading "logs/" from each
            self._uploaded_logs = set([o.key[5:] for o in bucket.objects.filter(Prefix='logs/')])

        return self._uploaded_logs

if __name__ == '__main__':
    bucket_manager = BucketManager()
    bucket_manager.fetch_uploaded_log_names()
    print(bucket_manager._uploaded_logs)
