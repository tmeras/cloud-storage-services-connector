import json
import datetime
import logging
import os
import sys
import webbrowser
import time
import dropbox
import requests
import utils
from .data_service import DataService

# hack to allow importing modules from parent directory
sys.path.insert(0, os.path.abspath('..'))

MB = 1024 * 1024
CHUNK_SIZE = 32 * MB
THRESHOLD = 32 * MB
SEPARATOR = os.path.sep


class Dropbox(DataService):
    def __init__(self):
        self.client = authenticate()

    @utils.timeit
    def download(self, local_path, dbx_path):
        """
        Download a file or folder from Dropbox
        """
        local_path = os.path.expanduser(local_path)
        local_path = local_path.replace('/', SEPARATOR)
        local_path = local_path.rstrip(SEPARATOR) + SEPARATOR
        if not os.path.exists(local_path):
            utils.print_string(
                "{} does not exist in your filesystem".format(local_path), utils.PrintStyle.ERROR)
            return None

        dbx_path = dbx_path.replace('\\', '/')
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

    def upload_file(self, fullname, dbx_path, subfolder, name):
        """
        Upload a file
        """
        path = '/%s/%s/%s' % (dbx_path,
                              subfolder.replace(os.path.sep, '/'), name)
        while '//' in path:
            path = path.replace('//', '/')

        mode = dropbox.files.WriteMode.overwrite
        mtime = os.path.getmtime(fullname)

        with open(fullname, 'rb') as f:
            file_size = os.path.getsize(fullname)

            # Small file, upload in a single request
            if file_size <= THRESHOLD:
                try:
                    logging.info(
                        "Uploading '{}' in a single request ".format(fullname))
                    self.client.files_upload(
                        f.read(), path, mode,
                        client_modified=datetime.datetime(
                            *time.gmtime(mtime)[:6]),
                        mute=True)
                except dropbox.exceptions.ApiError as e:
                    utils.print_string("Could not upload file '{}': {}".format(
                        path, e), utils.PrintStyle.ERROR)
                    sys.exit()

            # Use chunked upload
            else:
                try:
                    logging.info(
                        "Uploading '{}' in chunks ".format(fullname))
                    uploader = self.client.files_upload_session_start(
                        f.read(CHUNK_SIZE))
                    cursor = dropbox.files.UploadSessionCursor(
                        session_id=uploader.session_id, offset=f.tell())
                    commit = dropbox.files.CommitInfo(path=path)
                    while f.tell() < file_size:
                        try:
                            current_offset = f.tell()
                            if (file_size - f.tell()) <= CHUNK_SIZE:
                                self.client.files_upload_session_finish(
                                    f.read(CHUNK_SIZE), cursor, commit)
                            else:
                                self.client.files_upload_session_append_v2(
                                    f.read(CHUNK_SIZE), cursor)
                                cursor.offset = f.tell()

                        # Attempt to resume failed upload session
                        except requests.exceptions.ConnectionError as e:
                            f.seek(current_offset)
                            cursor.offset = current_offset
                except dropbox.exceptions.ApiError as e:
                    utils.print_string("Could not upload file '{}' in chunks: {}".format(
                        path, e), utils.PrintStyle.ERROR)
                    sys.exit()

        utils.print_string("Successfully uploaded '{}'".format(
            fullname), utils.PrintStyle.SUCCESS)

    @utils.timeit
    def upload(self, rootdir, dbx_path):
        """ 
        Upload a file or folder to Dropbox
        """
        rootdir = os.path.expanduser(rootdir)
        rootdir = rootdir.replace('/', SEPARATOR)
        rootdir = rootdir.rstrip(SEPARATOR)
        if not os.path.exists(rootdir):
            utils.print_string(
                "'{}' does not exist in your filesystem".format(rootdir), utils.PrintStyle.ERROR)
            return None

        dbx_path = dbx_path.replace('\\', '/')
        dbx_path = dbx_path.rstrip('/')

        logging.info('Dropbox folder:' + dbx_path)
        logging.info('Local directory:' + rootdir)

        # Upload file
        if os.path.isfile(rootdir):
            logging.info(rootdir + ' is a local file')
            file_name = rootdir.split(SEPARATOR)[-1]
            logging.info("Uploading file '{}' ".format(rootdir))
            self.upload_file(rootdir, dbx_path, "", file_name)

        # Upload folder content
        elif os.path.isdir(rootdir):
            logging.info(rootdir + ' is a local directory')
            for dn, dirs, files in os.walk(rootdir):
                subfolder = dn[len(rootdir):].strip(SEPARATOR)
                if subfolder != '':
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
                        self.upload_file(fullname, dbx_path, subfolder, name)

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

        utils.print_string('All uploads successfull', utils.PrintStyle.SUCCESS)

    @utils.timeit
    def delete(self, dbx_path):
        dbx_path = dbx_path.replace('\\', '/')
        dbx_path = '/' + dbx_path.lstrip('/')
        try:
            md = self.client.files_delete(dbx_path)
        except dropbox.exceptions.ApiError as err:
            utils.print_string(
                "Could not delete '{}': {}".format(dbx_path, err), utils.PrintStyle.ERROR)
            return None

        utils.print_string("Successfully deleted {}".format(
            md.name), utils.PrintStyle.SUCCESS)

    def close(self):
        """
        Close Dropbox handler, cleaning up resources.
        """
        if isinstance(self.client, dropbox.Dropbox):
            logging.info("Cleaning up Dropbox resources")
            self.client.close()
        else:
            logging.warning("Error when cleaning up Dropbox resources.")


def no_redirect_oauth2():
    """
    Goes through a basic OAuth flow using a short-lived token type
    """
    # Read credentials file
    with open("../data/dropbox_credentials.json") as f:
        data = json.load(f)

    auth_flow = dropbox.DropboxOAuth2FlowNoRedirect(
        data.get("app_key"), use_pkce=True, token_access_type='offline')
    authorize_url = auth_flow.start()

    # Redirect user to auth_url, where they will enter their Dropbox credentials
    webbrowser.open(authorize_url)

    utils.print_string("1. Go to: " + authorize_url, utils.PrintStyle.INFO)
    utils.print_string(
        "2. Click \"Allow\" (you might have to log in first).", utils.PrintStyle.INFO)
    utils.print_string("3. Copy the authorization code.",
                       utils.PrintStyle.INFO)
    auth_code = input("Enter the authorization code here: ").strip()

    try:
        oauth_result = auth_flow.finish(auth_code)
    except Exception as e:
        utils.print_string("Error during OAuth flow: {}" .format(
            e), utils.PrintStyle.ERROR)
        sys.exit()

    # Update crdentials file with tokens
    tokens = {
        "access_token": oauth_result.access_token,
        "refresh_token": oauth_result.refresh_token
    }
    with open('../data/dropbox_credentials.json') as file:
        data = json.load(file)
    data.update(tokens)
    with open('../data/dropbox_credentials.json', 'w') as file:
        json.dump(data, file)

    with dropbox.Dropbox(oauth2_access_token=oauth_result.access_token, oauth2_refresh_token=oauth_result.refresh_token, app_key=data.get("app_key")) as client:
        client.users_get_current_account()
        utils.print_string("Authentication successful!",
                           utils.PrintStyle.SUCCESS)
        return client  # Return the Dropbox client object to later use it for requests to Dropbox API


def authenticate():
    """
    Authenticate user using access and refresh token.

    If there are no (valid) tokens avaialble, initiate new OAuth flow
    """
    # Read credentials file
    with open("../data/dropbox_credentials.json") as f:
        data = json.load(f)

    if "access_token" in data and "refresh_token" in data:
        try:
            client = dropbox.Dropbox(oauth2_access_token=data.get(
                "access_token"), oauth2_refresh_token=data.get("refresh_token"), app_key=data.get("app_key"))
            client.users_get_current_account()
        except dropbox.exceptions.AuthError as e:
            utils.print_string(
                "Could authenticate with access/refresh token: {}".format(e), utils.PrintStyle.WARNING)
            client = no_redirect_oauth2()
        except Exception as e:
            utils.print_string("Unexpected error during authentication: {}".format(
                e), utils.PrintStyle.ERROR)
            sys.exit()
    else:
        logging.info("Tokens not found, initating OAuth flow")
        client = no_redirect_oauth2()

    return client
