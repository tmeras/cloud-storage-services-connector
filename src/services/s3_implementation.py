import logging
import os
import sys

# hack to allow importing modules from parent directory
sys.path.insert(0, os.path.abspath('..'))

import boto3
import botocore.exceptions
import utils

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

    def upload(self, bucket_name, localdir):
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

        # Search if bucket exists
        for bucket in self.client.list_buckets()['Buckets']:
            if bucket['Name'] == bucket_name:
                break
        else:
            utils.print_string("Warning: bucket '{}' doesn't exist".format(
                bucket_name), utils.PrintStyle.WARNING)
            if utils.yesno("Do you want to create bucket '{}' and continue with the upload".format(bucket_name), True):
                if not self.create_bucket(bucket_name):
                    return None
            else:
                return None

        logging.info("S3 bucket: {}".format(bucket_name))
        logging.info("Local directory: {}".format(localdir))

        # Upload file
        if os.path.isfile(localdir):
            logging.info(localdir + ' is a local file')
            file_name = localdir.split('/')[-1]
            try:
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
                print("SUBFOLDER:", subfolder)
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    s3 = S3()
    s3.upload('mm0x', '/Users/teomeras/Desktop/test')
