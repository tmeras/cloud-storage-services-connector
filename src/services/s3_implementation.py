import utils
import logging
import os
import sys
import boto3
from boto3.s3.transfer import TransferConfig
import botocore.exceptions
import botocore.client
from services.data_service import DataService

# hack to allow importing modules from parent directory
sys.path.insert(0, os.path.abspath('..'))

MB = 1024 * 1024
CHUNK_SIZE = 32 * MB
THRESHOLD = 32 * MB
SEPARATOR = os.path.sep


class S3(DataService):
    def __init__(self):
        self.client = authenticate()

    def create_bucket(self, bucket_name, region=None):
        """
        Create S3 bucket in the specified region

        If a region is not specified, bucket is created in the default
        region (us-east-1)

        Returns true if bucket is successfully created, otherwise returns false
        """
        try:
            if region is None:
                self.client.create_bucket(Bucket=bucket_name)
            else:
                location = {'LocationConstraint': region}
                self.client.create_bucket(
                    Bucket=bucket_name, CreateBucketConfiguration=location)
        except botocore.exceptions.ClientError as e:
            utils.print_string("Could not create bucket '{}': {}".format(
                bucket_name, e), utils.PrintStyle.ERROR)
            return False
        return True

    def download_directory(self, localdir, bucket_name, folder_name=None):
        """
        Download a directory from S3

        If no directory is specified, download the bucket itself
        """
        try:
            result = {}

            # Get objects to download
            if folder_name is not None:
                logging.info("Downloading directory '{}'".format(folder_name))
                result = self.client.list_objects_v2(
                    Bucket=bucket_name, Prefix=folder_name)
            else:
                logging.info("Downloading bucket {}".format(bucket_name))
                result = self.client.list_objects_v2(Bucket=bucket_name)

            for object in result['Contents']:
                if folder_name is None:
                    substring = object['Key'].replace('/', SEPARATOR)
                else:
                    substring = object['Key'].split(folder_name, 1)[
                        1].replace('/', SEPARATOR)

                # Object is a file, download it
                if not object['Key'].endswith('/'):

                    # If folder that contains file doesn't exist locally, create it
                    first, delim, last = substring.rpartition(SEPARATOR)
                    if first and delim:
                        dir = os.path.join(localdir, first)
                        if not os.path.exists(dir):
                            logging.info("Creating directory '{}'".format(dir))
                            os.makedirs(dir)
                        path = os.path.join(dir, last)
                    else:
                        path = os.path.join(localdir, last)
                    
                    logging.info("path: " + path)

                    logging.info("Downloading file '{}'".format(object['Key']))
                    self.client.download_file(bucket_name, object['Key'], path)

                # Object is a folder, create it locally if it doesn't exist
                else:
                    dir = os.path.join(localdir, substring)
                    if not os.path.exists(dir):
                        logging.info(
                            "Creating local directory {}''".format(dir))
                        os.makedirs(dir)
            return True

        except botocore.exceptions.ClientError as e:
            if folder_name is None:
                utils.print_string("Error while downloading bucket '{}': {}".format(
                    bucket_name, e), utils.PrintStyle.ERROR)
            else:
                utils.print_string("Error while downloading folder '{}': {}".format(
                    folder_name, e), utils.PrintStyle.ERROR)
            return False

    def download(self, localdir, s3_path):
        """
        Download S3 content

        If object_name is empty, download the entire bucket
        """
        localdir = os.path.expanduser(localdir)
        localdir = localdir.replace('/', SEPARATOR)
        localdir = localdir.rstrip(SEPARATOR)
        if not os.path.isdir(localdir):
            utils.print_string("'{}' is not a directory in your filesystem".format(
                localdir), utils.PrintStyle.ERROR)
            return None

        # S3 identifies folders using forward slashes
        s3_path = s3_path.replace(SEPARATOR, '/')
        s3_path = s3_path.lstrip('/')
        first, delim, last = s3_path.partition('/')

        # Only bucket was specified
        if first == '':
            bucket_name = last
            object_name = ''
        else:
            bucket_name = first
            object_name = last

        logging.info("Bucket name: " + bucket_name)
        test =   localdir + '/' + object_name.split('/')[0]
        logging.info("Object name: " + test)

        success = False

        if object_name != "":

            # Download object
            if object_name[-1] != '/':
                logging.info(
                    "Downloading single object '{}'".format(object_name))
                try:
                    path = os.path.join(localdir, object_name.split('/')[-1])
                    self.client.download_file(bucket_name, object_name, path)
                    success = True
                except botocore.exceptions.ClientError as e:
                    utils.print_string("Could not download object '{}' from bucket '{}': {}".format(
                        object_name, bucket_name, e), utils.PrintStyle.ERROR)
                    return None
            # Download directory
            else:
                # Create subfolder where contents will be uploaded, if it doesn't already exist
                localdir += '/' + object_name.split('/')[0]
                if not os.path.exists(localdir):
                    logging.info( "Creating local directory {}''".format(localdir))
                    os.makedirs(localdir)

                success = self.download_directory(
                    localdir, bucket_name, object_name)
        # Download bucket
        else:
            success = self.download_directory(localdir, bucket_name)

        if success:
            utils.print_string("All downloads successfull",
                               utils.PrintStyle.SUCCESS)

    def upload(self, localdir, s3_path):
        """
        Upload file or folder to S3
        """
        localdir = os.path.expanduser(localdir)
        localdir = localdir.replace('/', SEPARATOR)
        localdir = localdir.rstrip(SEPARATOR)
        if not os.path.exists(localdir):
            utils.print_string("'{}' does not exist in your filesystem".format(
                localdir), utils.PrintStyle.ERROR)
            return None

        # S3 identifies folders using forward slashes
        s3_path = s3_path.replace(SEPARATOR, '/')
        s3_path = s3_path.lstrip('/')
        first, delim, last = s3_path.partition('/')

        # Only bucket was specified
        if first == '':
            bucket_name = last
            object_name = ''
        else:
            bucket_name = first
            if not last == '' and not last.endswith('/'):
                utils.print_string("Error: '{}' is not a directory".format(
                    last), utils.PrintStyle.ERROR)
                return
            object_name = last

        # Check if bucket exists
        try:
            logging.info("Checking if bucket '{}' exists".format(bucket_name))
            self.client.head_bucket(Bucket=bucket_name)
        except botocore.exceptions.ClientError as e:
            if e.response['ResponseMetadata']['HTTPStatusCode'] == 404:
                utils.print_string("Warning: bucket '{}' doesn't exist".format(
                    bucket_name), utils.PrintStyle.WARNING)
            else:
                utils.print_string("Error while checking if bucket '{}' exists: {}".format(
                    bucket_name, e), utils.PrintStyle.ERROR)
            return None

        logging.info("S3 bucket: {}".format(bucket_name))
        logging.info("Local directory: {}".format(localdir))

        # Configuration for chunked uploads
        config = TransferConfig(
            multipart_threshold=THRESHOLD, multipart_chunksize=CHUNK_SIZE)

        # Upload file
        if os.path.isfile(localdir):
            logging.info(localdir + ' is a local file')
            file_name = localdir.split(SEPARATOR)[-1]
            try:
                logging.info('Uploading ' + localdir)
                self.client.upload_file(
                    localdir, bucket_name, object_name + file_name, Config=config)
            except botocore.exceptions.ClientError as e:
                utils.print_string("Could not upload file '{}': {}".format(
                    localdir, e), utils.PrintStyle.ERROR)
                return None

        # Upload folder
        elif os.path.isdir(localdir):
            logging.info(localdir + ' is a local folder')

            for dn, dirs, files in os.walk(localdir):
                subfolder = dn[len(localdir):].strip(os.path.sep)
                if subfolder != '':
                    logging.info('Descending into ' + subfolder)

                # First do all the files
                for name in files:
                    fullname = os.path.join(dn, name)
                    if name.startswith('.'):
                        logging.info('Skipping dot file: ' + name)
                    elif name.startswith('@') or name.endswith('~'):
                        logging.info('Skipping temporary file: ' + name)
                    elif name.endswith('.pyc') or name.endswith('.pyo'):
                        logging.info('Skipping generated file: ' + name)
                    else:
                        try:
                            # Define object key in such a way that S3
                            # will automatically create required folders
                            key = localdir.split(SEPARATOR)[-1]
                            if not object_name == '':
                                key = os.path.join(key,
                                    object_name, subfolder, name)
                            else:
                                key = os.path.join(key,subfolder, name)
                            key = key.replace(SEPARATOR, '/')
                            logging.info('Uploading ' + fullname)
                            self.client.upload_file(
                                fullname, bucket_name, key, Config=config)
                            utils.print_string("File '{}' uploaded successfully".format(
                                fullname), utils.PrintStyle.SUCCESS)
                        except botocore.exceptions.ClientError as e:
                            utils.print_string("Could not upload file '{}': {}".format(
                                fullname, e), utils.PrintStyle.ERROR)
                            return None

                # Then choose which subdirectories to traverse
                keep = []
                for name in dirs:
                    if name.startswith('.'):
                        logging.info('Skipping dot directory: ' + name)
                    elif name.startswith('@') or name.endswith('~'):
                        logging.info('Skipping temporary directory: ' + name)
                    elif name == '__pycache__':
                        logging.info('Skipping generated directory:' + name)
                    else:
                        logging.info('Keeping directory:' + name)
                        keep.append(name)
                dirs[:] = keep

        utils.print_string("All uploads successful", utils.PrintStyle.SUCCESS)

    def empty_bucket(self, bucket_name):
        """
        Empty S3 bucket contents

        Returns true if bucket is successfully emptied, otherwise returns false
        """
        utils.print_string("Emptying bucket '{}'.".format(bucket_name))
        try:
            result = self.client.list_objects_v2(Bucket=bucket_name)
            if result['KeyCount'] == 0:
                logging.warning("Bucket '{}' is already empty".format(
                    bucket_name))
                return True

            for object in result['Contents']:
                logging.info("Deleting object '{}'".format(object['Key']))
                self.client.delete_object(
                    Bucket=bucket_name, Key=object['Key'])
                utils.print_string("Object '{}' deleted successfully".format(
                    object['Key']), utils.PrintStyle.SUCCESS)
        except botocore.exceptions.ClientError as e:
            utils.print_string("Could not empty bucket '{}': {}".format(
                bucket_name, e), utils.PrintStyle.ERROR)
            return False
        utils.print_string("Bucket '{}' emptied successfully".format(
            bucket_name), utils.PrintStyle.SUCCESS)
        return True

    def delete(self, s3_path):
        """
        Delete S3 object

        If an object is not specified, delete the bucket itself
        """
        # S3 identifies folders using forward slashes
        s3_path = s3_path.replace(SEPARATOR, '/')
        s3_path = s3_path.lstrip('/')
        first, delim, last = s3_path.partition('/')

        # Only bucket was specified
        if first == '':
            bucket_name = last
            object_name = ''
        else:
            bucket_name = first
            object_name = last

        logging.info("Object name: {}".format(object_name))

        # Delete file or folder
        if object_name != '':
            # Delete folder contents
            if object_name.endswith('/'):
                logging.info("Deleting folder '{}'".format(object_name))
                result = self.client.list_objects_v2(
                    Bucket=bucket_name, Prefix=object_name)

                if result['KeyCount'] == 0:
                    utils.print_string("Error: Folder '{}' doesn't exist".format(
                        object_name), utils.PrintStyle.ERROR)
                    return None

                for object in result['Contents']:
                    try:
                        logging.info(
                            "Deleting object '{}'".format(object['Key']))
                        self.client.delete_object(
                            Bucket=bucket_name, Key=object['Key'])
                        utils.print_string("Object '{}' successfully deleted".format(
                            object['Key']), utils.PrintStyle.SUCCESS)
                    except botocore.exceptions.ClientError as e:
                        utils.print_string("Could not delete object '{}': {}".format(
                            object['Key'], e), utils.PrintStyle.ERROR)
                        return None

            # Delete file
            else:
                try:
                    # Ensure object exists
                    self.client.head_object(
                        Bucket=bucket_name, Key=object_name)
                    logging.info("Deleting object '{}'".format(object_name))
                    self.client.delete_object(
                        Bucket=bucket_name, Key=object_name)
                except botocore.exceptions.ClientError as e:
                    utils.print_string("Could not delete object '{}': {}".format(
                        object_name, e), utils.PrintStyle.ERROR)
                    return None
        # Delete bucket
        else:
            try:
                result = self.client.list_objects_v2(Bucket=bucket_name)

                # Nonempty bucket
                if result['KeyCount'] != 0:
                    utils.print_string("Bucket '{}' needs to be emptied before deletion".format(
                        bucket_name), utils.PrintStyle.WARNING)
                    self.empty_bucket(bucket_name)
                logging.info("Deleting bucket '{}'".format(bucket_name))
                self.client.delete_bucket(Bucket=bucket_name)
            except botocore.exceptions.ClientError as e:
                utils.print_string("Could not delete bucket '{}' : {}".format(
                    bucket_name, e), utils.PrintStyle.ERROR)
                return None

        utils.print_string("All deletions successfull",
                           utils.PrintStyle.SUCCESS)

    def close(self):
        """
        Close S3 handler, cleaning up resources.
        """
        if isinstance(self.client, botocore.client.BaseClient):
            logging.info("Cleaning up S3 resources")
            self.client.close()
        else:
            logging.warning("Error when cleaning up S3 resources.")


def authenticate():
    """
    Authenticates using AWS IAM Identity Center

    Setup as described in: https://docs.aws.amazon.com/cli/latest/userguide/sso-configure-profile-token.html
    needs to first be completed
    """
    try:
        # If using a different profile from ~/.aws/config, specify it here
        session = boto3.Session(profile_name='default')

        client = session.client('s3')
        client.list_buckets()
    except botocore.exceptions.TokenRetrievalError as e:
        utils.print_string("Error while authenticating, please run the 'aws sso login' command to refresh access token",utils.PrintStyle.ERROR)
        sys.exit()
    except Exception as e:
        utils.print_string("Error whie authenticating: {}".format(e),utils.PrintStyle.ERROR)
        sys.exit()

    return client
