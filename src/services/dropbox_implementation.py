import datetime
import logging
import os
import sys
import time

# hack to allow importing modules from parent directory
sys.path.insert(0, os.path.abspath('..'))

import dropbox
import utils

ACCESS_TOKEN = "sl.BYQZoWR4pJA3_KLNaMvXOwsoZqMgtOtezg3BYJlktRb-u0CQLwb7n9uYCdTL_iXha0ibBQM6MB680Qf2I4rygREA8QZhVIQL6kTSu1irww4UiBLaCaundSVDMdJ95hqSldwEey4"


class Dropbox:
    def __init__(self):
        self.client = dropbox.Dropbox(ACCESS_TOKEN)

    def close_dbx(self):
        """
        Close Dropbox handler, cleaning up resources.
        """
        if isinstance(self.client, dropbox.Dropbox):
            self.client.close()
        else:
            logging.warning("Error when cleaning up Dropbox resources.")

    def download(self, local_path, dbx_path):
        """
        Download a file or folder from Dropbox
        """
        local_path = os.path.expanduser(local_path)
        local_path = local_path.replace(os.path.sep, '/')
        local_path = local_path.rstrip('/') + '/'
        if not os.path.exists(local_path):
            utils.print_string(
                "{} does not exist in your filesystem".format(local_path), utils.PrintStyle.ERROR)
            return None

        dbx_path = '/' + dbx_path.lstrip('/')
        dbx_path = dbx_path.rstrip('/')
        try:
            md = self.client.files_get_metadata(dbx_path)
        except dropbox.exceptions.ApiError as err:
            utils.print_string("Could not get metadata for path '{}': {}".format(
                dbx_path, err), utils.PrintStyle.ERROR)
            return None

        logging.info("Dropbox directory: " + dbx_path)
        logging.info("Local directory: " + local_path)

        if isinstance(md, dropbox.files.FileMetadata):
            logging.info("Dropbox path '{}' is a file".format(dbx_path))

            name = dbx_path.split('/')[-1]
            local_path += name
            with utils.stopwatch('download'):
                try:
                    md = self.client.files_download_to_file(
                        local_path, dbx_path)
                except dropbox.exceptions.ApiError as err:
                    utils.print_string(
                        "Could not download file '{}': {}".format(dbx_path, err), utils.PrintStyle.ERROR)
                    return None
            utils.print_string(
                "File '{}' downloaded successfully!".format(dbx_path.split('/')[-1]), utils.PrintStyle.SUCCESS)
        else:
            logging.info("Dropbox path '{}' is a directory".format(dbx_path))
            name = dbx_path.split('/')[-1]
            if not name.endswith('.zip'):
                name += ".zip"
            local_path += name
            with utils.stopwatch('download'):
                try:
                    self.client.files_download_zip_to_file(
                        local_path, dbx_path)
                except dropbox.exceptions.ApiError as err:
                    utils.print_string(
                        "Could not download directory '{}': {}".format(
                            dbx_path, err),
                        utils.PrintStyle.ERROR
                    )
                    return None
            utils.print_string("Folder named {} downloaded successfully!".format(
                dbx_path.split('/')[-1]), utils.PrintStyle.SUCCESS)

    def upload(self, rootdir, folder):
        """ 
        Upload a file or folder to Dropbox
        """
        folder = folder.rstrip('/')

        rootdir = os.path.expanduser(rootdir)
        rootdir = rootdir.rstrip(os.path.sep)
        rootdir = rootdir.replace(os.path.sep, '/')
        if not os.path.exists(rootdir):
            utils.print_string(
                "'{}' does not exist in your filesystem".format(rootdir), utils.PrintStyle.ERROR)
            return None

        logging.info('Dropbox folder:' + folder)
        logging.info('Local directory:' + rootdir)

        # Upload file
        if os.path.isfile(rootdir):
            logging.info(rootdir + ' is a local file')
            file_name = rootdir.split('/')[-1]
            logging.info("Uploading file '{}' ".format(rootdir))
            self.upload_file(rootdir, folder, "", file_name)

        # Upload folder content
        elif os.path.isdir(rootdir):
            logging.info(rootdir + ' is a local directory')
            for dn, dirs, files in os.walk(rootdir):
                subfolder = dn[len(rootdir):].strip(os.path.sep)
                logging.info("Descending into '{}' ...".format(subfolder))

                # First do all the files
                for name in files:
                    fullname = os.path.join(dn, name)
                    if name.startswith('.'):
                        logging.info('Skipping dot file: {}'.format(name))
                    elif name.startswith('@') or name.endswith('~'):
                        logging.info(
                            'Skipping temporary file: {}'.format(name))
                    elif name.endswith('.pyc') or name.endswith('.pyo'):
                        logging.info(
                            'Skipping generated file: {}'.format(name))
                    else:
                        logging.info(
                            "Uploading file '{}' ...".format(fullname))
                        self.upload_file(fullname, folder, subfolder, name)

                # Then choose which subdirectories to traverse
                keep = []
                for name in dirs:
                    fullname = os.path.join(dn, name)
                    if name.startswith('.'):
                        logging.info('Skipping dot directory: {}'.format(name))
                    elif name.startswith('@') or name.endswith('~'):
                        logging.info(
                            'Skipping temporary directory: {}'.format(name))
                    elif name == '__pycache__':
                        logging.info(
                            'Skipping generated directory: {}'.format(name))
                    else:
                        logging.info("Keeping directory:'{}'".format(fullname))
                        keep.append(name)
                dirs[:] = keep

        utils.print_string('All uploads successfull!',
                           utils.PrintStyle.SUCCESS)

    def delete(self, dbx_path):
        dbx_path = '/' + dbx_path.lstrip('/')
        with utils.stopwatch('delete'):
            try:
                md = self.client.files_delete(dbx_path)
            except dropbox.exceptions.ApiError as err:
                utils.print_string(
                    "Could not delete '{}': {}".format(dbx_path, err), utils.PrintStyle.ERROR)
                return None

        utils.print_string("Successfully deleted {}".format(
            md.name), utils.PrintStyle.SUCCESS)

    def download_file(self, folder, subfolder, name):
        """
        Download a file. Do not store it locally

        Return the bytes of the file, or None if it doesn't exist.
        """
        path = '/%s/%s/%s' % (folder,
                              subfolder.replace(os.path.sep, '/'), name)
        while '//' in path:
            path = path.replace('//', '/')
        with utils.stopwatch('download'):
            try:
                md, res = self.client.files_download(path)
            except dropbox.exceptions.ApiError as err:
                utils.print_string("Could not download '{}': {}".format(
                    path, err), utils.PrintStyle.ERROR)
                return None
        data = res.content
        return data

    def upload_file(self, fullname, folder, subfolder, name):
        """
        Upload a file.

        Return the request response, or None in case of error.
        """
        path = '/%s/%s/%s' % (folder,
                              subfolder.replace(os.path.sep, '/'), name)
        while '//' in path:
            path = path.replace('//', '/')
        mode = (dropbox.files.WriteMode.overwrite)
        mtime = os.path.getmtime(fullname)
        with open(fullname, 'rb') as f:
            data = f.read()
        with utils.stopwatch('upload %d bytes' % len(data)):
            try:
                res = self.client.files_upload(
                    data, path, mode,
                    client_modified=datetime.datetime(*time.gmtime(mtime)[:6]),
                    mute=True)
            except dropbox.exceptions.ApiError as err:
                utils.print_string("Could not upload file '{}': {}".format(
                    path, err), utils.PrintStyle.ERROR)
                return None
        return res


def no_redirect_OAuth2():
    """
    Goes through a basic oauth flow using the existing long-lived token type
    """
    APP_KEY = "t1uokr1i2qj9ot1"
    APP_SECRET = "yxrwv0tc5fipf8e"

    auth_flow = dropbox.DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET)
    authorize_url = auth_flow.start()
    utils.print_string("1. Go to: " + authorize_url, utils.PrintStyle.INFO)
    utils.print_string(
        "2. Click \"Allow\" (you might have to log in first).", utils.PrintStyle.INFO)
    utils.print_string("3. Copy the authorization code.",
                       utils.PrintStyle.INFO)
    auth_code = input("Enter the authorization code here: ").strip()
    try:
        oauth_result = auth_flow.finish(auth_code)
    except Exception as e:
        sys.exit('Error: ' + e)

    with dropbox.Dropbox(oauth2_access_token=oauth_result.access_token) as client:
        client.users_get_current_account()
        utils.print_string("Authentication succesfull!",
                           utils.PrintStyle.SUCCESS)
        return client  # Return the Dropbox object to later use it for requests to Dropbox API
