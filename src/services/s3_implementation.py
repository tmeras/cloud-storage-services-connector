import logging
import os
import sys
import boto3
import botocore.exceptions
import botocore.client
from services.data_service import DataService

# hack to allow importing modules from parent directory
sys.path.insert(0, os.path.abspath('..'))
import utils


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
                    substring = object['Key']
                else:
                    substring = object['Key'].split(folder_name, 1)[1]

                # Object is a file, download it
                if not object['Key'].endswith('/'):

                    # If folder that contains file doesn't exist locally, create it
                    first, delim, last = substring.rpartition('/')
                    if first and delim:
                        dir = os.path.join(localdir, first)
                        if not os.path.exists(dir):
                            logging.info("Creating directory '{}'".format(dir))
                            os.makedirs(dir)
                        path = os.path.join(dir, last)
                    else:
                        path = os.path.join(localdir, last)

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
        localdir = localdir.rstrip(os.path.sep)
        localdir = localdir.replace(os.path.sep, '/')
        if not os.path.isdir(localdir):
            utils.print_string("'{}' is not a directory in your filesystem".format(
                localdir), utils.PrintStyle.ERROR)
            return None
        
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
        logging.info("Object name: " + object_name)

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
                        object_name,bucket_name, e), utils.PrintStyle.ERROR)
                    return None

            # Download directory
            else:
                success = self.download_directory(
                    localdir, bucket_name, object_name)

        # Download bucket
        else:
            success = self.download_directory(localdir, bucket_name)

        if success:
            utils.print_string("All downloads successfull",utils.PrintStyle.SUCCESS)

    def upload(self, localdir, s3_path):
        """
        Upload file or folder to S3
        """
        localdir = os.path.expanduser(localdir)
        localdir = localdir.rstrip(os.path.sep)
        localdir = localdir.replace(os.path.sep, '/')
        if not os.path.exists(localdir):
            utils.print_string("'{}' does not exist in your filesystem".format(
                localdir), utils.PrintStyle.ERROR)
            return None

        s3_path = s3_path.lstrip('/')
        first, delim, last = s3_path.partition('/')

        # Only bucket was specified
        if first == '':
            bucket_name = last
            object_name = ''
        else:
            bucket_name = first
            if not last == '' and not last.endswith('/'):
                utils.print_string("Error: '{}' is not a directory".format(last),utils.PrintStyle.ERROR)
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

        # Upload file
        if os.path.isfile(localdir):
            logging.info(localdir + ' is a local file')
            file_name = localdir.split('/')[-1]
            try:
                logging.info('Uploading ' + localdir)
                self.client.upload_file(localdir, bucket_name, object_name + file_name)
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
                            if not object_name == '':
                                key = os.path.join(object_name,subfolder, name)
                            else:
                                 key = os.path.join(subfolder, name)
                            logging.info('Uploading ' + fullname)
                            self.client.upload_file(fullname, bucket_name, key)
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

        utils.print_string("All uploads ok!", utils.PrintStyle.SUCCESS)

    def empty_bucket(self, bucket_name):
        """
        Empty S3 bucket contents

        Returns true if bucket is successfully emptied, otherwise returns false
        """
        logging.info("Emptying bucket '{}'.".format(bucket_name))
        try:
            result = self.client.list_objects_v2(Bucket=bucket_name)
            if result['KeyCount'] == 0:
                utils.print_string("Bucket '{}' is already empty".format(
                    bucket_name), utils.PrintStyle.SUCCESS)
                return True

            for object in result['Contents']:
                logging.info("Deleting object '{}'".format(object['Key']))
                self.client.delete_object(
                    Bucket=bucket_name, Key=object['Key'])
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

        s3_path = s3_path.lstrip('/')
        first, delim, last = s3_path.partition('/')

        # Only bucket was specified
        if first == '':
            bucket_name = last
            object_name = ''
        else:
            bucket_name = first
            object_name = last
        
        logging.info("S3 path: {}".format(bucket_name))


        # Delete object
        if object_name != '':
            try:
                logging.info("Deleting object '{}'".format(object_name))
                self.client.delete_object(Bucket=bucket_name, Key=object_name)
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
                    if utils.yesno("Empty bucket and proceed with deletion?", True):
                        self.empty_bucket(bucket_name)
                    else:
                        return None
                logging.info("Deleting bucket '{}'".format(bucket_name))
                self.client.delete_bucket(Bucket=bucket_name)
            except botocore.exceptions.ClientError as e:
                utils.print_string("Could not delete bucket '{}' : {}".format(
                    bucket_name, e), utils.PrintStyle.ERROR)
                return None

        utils.print_string("Deletion successfull!", utils.PrintStyle.SUCCESS)

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
    # If using a different profile from ~/.aws/config, specify it here
    session = boto3.Session(profile_name='default')

    client = session.client('s3')
    return client
    