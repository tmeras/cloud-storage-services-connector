import logging
import os
import sys

# hack to allow importing modules from parent directory
sys.path.insert(0, os.path.abspath('..'))

import utils
import botocore.exceptions
import boto3

class S3:
    def __init__(self):
        # Using temporary credentials
        # self.client = temporary_authentication()

        # Using long-term credentials from my .aws/credentials file
        self.client = boto3.client('s3')

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
            utils.print_string("Could not download '{}': {}".format(
                object['Key'], e), utils.PrintStyle.ERROR)
            return False

    def download(self, localdir, bucket_name, object_name):
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

        success = False

        # Download specific object or directory
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
                    utils.print_string("Could not download object '{}': {}".format(
                        object_name, e), utils.PrintStyle.ERROR)
                    return None

            # Download directory
            else:
                success = self.download_directory(
                    localdir, bucket_name, object_name)

        # Download bucket
        else:
            success = self.download_directory(localdir, bucket_name)

        if success:
            utils.print_string("All downloads successfull!")

    def upload(self, localdir, bucket_name):
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

        # Check if bucket exists
        try:
            logging.info("Checking if bucket '{}' exists".format(bucket_name))
            self.client.head_bucket(Bucket=bucket_name)
        except botocore.exceptions.ClientError as e:
            if e.response['ResponseMetadata']['HTTPStatusCode'] == 404:
                utils.print_string("Warning: bucket '{}' doesn't exist".format(
                    bucket_name), utils.PrintStyle.WARNING)
                if utils.yesno("Do you want to create bucket '{}' and continue with the upload".format(bucket_name), True):
                    if not self.create_bucket(bucket_name):
                        return None
                else:
                    return None
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
                self.client.upload_file(localdir, bucket_name, file_name)
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
                            # Create object key in such a way that S3
                            # will automatically create required folders
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

    def delete(self, bucket_name, object_name):
        """
        Delete S3 object
        If an object is not specified, delete the bucket itself
        """

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


def temporary_authentication():
    """
    Interacts with AWS STS API to extract temporary credentials
    These are then used to authenticate the IAM user whose credentials 
    are initially extracted by Boto3 (from config file or elsewhere)
    """
    sts_client = boto3.client('sts')

    assumed_role_object = sts_client.assume_role(
        RoleArn="arn:aws:iam::825156787427:role/role_for_the_senior",
        RoleSessionName="AssumeRoleSession1"
    )

    # From the response that contains the assumed role, get the temporary
    # credentials that can be used to make subsequent API calls
    credentials = assumed_role_object['Credentials']

    # Use the temporary credentials that AssumeRole returns to make a
    # connection to Amazon S3
    client = boto3.client('s3', aws_access_key_id=credentials['AccessKeyId'],
                          aws_secret_access_key=credentials['SecretAccessKey'],
                          aws_session_token=credentials['SessionToken'])

    return client
