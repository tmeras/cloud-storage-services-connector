import io
import logging
import os
import sys
from services.data_service import DataService
import utils
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.discovery import Resource
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

# hack to allow importing modules from parent directory
sys.path.insert(0, os.path.abspath('..'))

MB = 1024 * 1024
CHUNK_SIZE = 32 * MB
THRESHOLD = 32 * MB
SEPARATOR = os.path.sep


class Gdrive(DataService):
    def __init__(self):
        self.client = authenticate_OAuth2()

    def get_path(self, id):
        """
        Return absolute path of Google Drive file or folder with the given id
        """
        try:
            object = self.client.files().get(fileId=id, fields='id, name, parents').execute()
            parent = object.get('parents')
            path = object.get('name')
            while parent is not None:
                folder = self.client.files().get(
                    fileId=parent[0], fields='id, name, parents').execute()
                path = folder.get('name') + SEPARATOR + path
                parent = folder.get('parents')
            return path
        except HttpError as e:
            utils.print_string("Could not get absolute path for object with id '{}':{}".format(
                id, e), utils.PrintStyle.ERROR)

    def exists(self, folder_id, key, key_is_folder=False):
        """
        If key exists inside specified folder, return its id, otherwise return None
        """
        try:
            files = []
            page_token = None
            while True:
                response = self.client.files().list(q="'" + folder_id + "' in parents and trashed = false",
                                                    spaces='drive', fields='nextPageToken, files(id, name, mimeType)',
                                                    pageToken=page_token).execute()
                files.extend(response.get('files', []))
                page_token = response.get('nextPageToken', None)
                if page_token is None:
                    break
        except HttpError as e:
            utils.print_string("Error while listing contents of '{}' : {}".format(
                folder_id, e), utils.PrintStyle.ERROR)
            sys.exit()

        for item in files:
            if item.get('name') == key:
                if (key_is_folder and item.get('mimeType') == 'application/vnd.google-apps.folder') or (
                        (not key_is_folder) and item.get('mimeType') != 'application/vnd.google-apps.folder'):
                    return item.get('id')
        else:
            logging.info("Not found '{}'".format(key))
            return None

    def traverse(self, gd_path):
        """
        Traverse Google Drive directory structure based on given path,

        Return the id and type of the item at the end of the path
        """
        gd_path = gd_path.replace('/', SEPARATOR)
        if gd_path.endswith(SEPARATOR):
            is_folder = True
            key_type = 'folder'
        else:
            is_folder = False
            key_type = 'file'

        gd_path = gd_path.strip(SEPARATOR)
        gd_path = gd_path.removeprefix('My Drive')
        gd_path = gd_path.lstrip(SEPARATOR)

        # Root folder requested
        if gd_path == "":
            return 'root', 'folder'

        logging.info("Traversing '{}'".format(gd_path))

        current_folder_id = 'root'
        names = gd_path.split(SEPARATOR)
        for item in names:
            # Reached final item, return its id if it exists on Google Drive
            if item == names[-1]:
                logging.info("At final item")
                id = self.exists(current_folder_id, item, is_folder)
                if id is not None:
                    return id, is_folder
                else:
                    utils.print_string("Invalid path: {} '{}' doesn't exist".format(
                        key_type, item), utils.PrintStyle.ERROR)
                    sys.exit()
            else:
                id = self.exists(current_folder_id, item, True)
                if id is not None:
                    current_folder_id = id
                else:
                    utils.print_string("Invalid path: Folder '{}' doesn't exist".format(
                        item), utils.PrintStyle.ERROR)
                    sys.exit()

    def download_file(self, localdir, file_id, old_downloader=None):
        """
        Download Google Drive file
        """
        try:
            if old_downloader is None:
                file = self.client.files().get(fileId=file_id, fields='id, name, mimeType').execute()
                file_name = file.get('name')
                file_mimeType = file.get('mimeType')

                # Download Google Workspace document as PDF
                if file_mimeType.startswith("application/vnd.google-apps") and not file_mimeType.endswith(
                        "script+json"):
                    logging.info(
                        "Initiating resumable download of Google Workspace Document '{}'".format(file_name))
                    request = self.client.files().export_media(
                        fileId=file_id, mimeType='application/pdf')
                    file_name += ".pdf"

                # Download Blob (text or binary) files
                else:
                    logging.info(
                        "Initiating resumable download of Blob '{}'".format(file_name))
                    request = self.client.files().get_media(fileId=file_id)

                file_path = os.path.join(localdir, file_name)
                f = io.FileIO(file_path, mode='wb')
                logging.info("Downloading to {}".format(file_path))
                downloader = MediaIoBaseDownload(f, request)
            else:
                logging.info("Resuming download of '{}'".format(file_name))
                downloader = old_downloader

            done = False
            while done is False:
                status, done = downloader.next_chunk()
                if status:
                    utils.print_string("Downloaded %d%%." % int(
                        status.progress() * 100), utils.PrintStyle.INFO)

            utils.print_string("File '{}' downloaded successfully".format(
                file_name), utils.PrintStyle.SUCCESS)
        except HttpError as e:
            if e.resp.status in [404]:
                # Restart the download
                self.download_file(localdir, file_id=file_id)
            elif e.resp.status in [500, 502, 503, 504]:
                # Resume download
                self.download_file(localdir, file_id=file_id,
                                   old_downloader=downloader)
            else:
                utils.print_string("Could not download file '{}': {}".format(
                    file_name, e), utils.PrintStyle.ERROR)
                sys.exit()

    def download_directory(self, localdir, folder_id):
        """
        Download contents of Google Drive directory
        """
        try:
            items = []
            page_token = None
            while True:
                response = self.client.files().list(q="'" + folder_id + "' in parents and trashed = false",
                                                    spaces='drive', fields='nextPageToken, files(id, name, mimeType)',
                                                    pageToken=page_token).execute()
                items.extend(response.get('files', []))
                page_token = response.get('nextPageToken', None)
                if page_token is None:
                    break
        except HttpError as e:
            utils.print_string("Error while listing contents of '{}' : {}".format(
                folder_id, e), utils.PrintStyle.ERROR)
            sys.exit()

        current_folder_name = self.client.files().get(
            fileId=folder_id, fields='id, name').execute().get('name')

        logging.info("Downloading contents of directory '{}'".format(
            current_folder_name))

        for item in items:
            # Create directory locally, if it doesn't exist
            path = os.path.join(localdir, current_folder_name)
            if not os.path.isdir(path):
                os.makedirs(path)

            # Item is a directory
            if item.get('mimeType') == "application/vnd.google-apps.folder":
                self.download_directory(path, item.get('id'))

            # Item is a file
            else:
                name = item.get('name')
                if name.startswith('.'):
                    logging.info('Skipping dot file: ' + name)
                elif name.startswith('@') or name.endswith('~'):
                    logging.info('Skipping temporary file: ' + name)
                elif name.endswith('.pyc') or name.endswith('.pyo'):
                    logging.info('Skipping generated file: ' + name)
                else:
                    self.download_file(path, item.get('id'))

    def download(self, localdir, gd_path):
        """
        Download Google Drive file or directory
        """
        localdir = os.path.expanduser(localdir)
        localdir = localdir.replace('/', SEPARATOR)
        localdir = localdir.rstrip(SEPARATOR)
        if not os.path.isdir(localdir):
            utils.print_string("'{}' is not a directory in your filesystem".format(
                localdir), utils.PrintStyle.ERROR)
            return None

        # Get item that will be downloaded
        id, is_folder = self.traverse(gd_path)
        item = self.client.files().get(fileId=id).execute()

        logging.info("Local directory: " + localdir)
        logging.info("Google Drive path: " + gd_path)

        try:
            # Download directory
            if item.get('mimeType') == "application/vnd.google-apps.folder":
                self.download_directory(localdir, item.get('id'))
            else:
                self.download_file(localdir, item.get('id'))
        except HttpError as e:
            utils.print_string("Could not download '{}' : {}".format(
                gd_path, e), utils.PrintStyle.ERROR)
            return None

        utils.print_string("All downloads ok", utils.PrintStyle.SUCCESS)

    def upload_file(self, localdir, folder_id='root', file_id=None, old_request=None):
        """
        Upload file if it doesn't exist

        If the file already exists, update it

        Use resumable upload for large files
        """
        file_size = os.path.getsize(localdir)
        if file_size > THRESHOLD:
            logging.info(
                "Initiating resumable upload of '{}'".format(localdir))
            resumable = True
        else:
            logging.info("Uploading '{}' in a single request".format(localdir))
            resumable = False

        try:
            if old_request is None:
                metadata = {'name': localdir.split(SEPARATOR)[-1]}
                media = MediaFileUpload(
                    localdir,  chunksize=CHUNK_SIZE, resumable=resumable)

                # Upload new file, otherwise update existing file
                if file_id is None:
                    logging.info("Uploading new file '{}'".format(
                        localdir.split(SEPARATOR)[-1]))
                    metadata['parents'] = [folder_id]
                    request = self.client.files().create(body=metadata, media_body=media)
                else:
                    logging.info("Updating file '{}'".format(
                        localdir.split(SEPARATOR)[-1]))
                    request = self.client.files().update(
                        fileId=file_id, body=metadata, media_body=media)
            else:
                request = old_request
                logging.info("Resuming upload/update of '{}'".format(localdir))

            if resumable:
                response = None
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        utils.print_string("Uploaded %d%%." % int(
                            status.progress() * 100), utils.PrintStyle.INFO)
            else:
                request.execute()

            utils.print_string("File '{}' uploaded successfully".format(
                localdir), utils.PrintStyle.SUCCESS)
        except HttpError as e:
            if e.resp.status in [404]:
                # Restart the upload
                self.upload_file(
                    localdir, folder_id=folder_id, file_id=file_id)
            elif e.resp.status in [500, 502, 503, 504]:
                # Resume upload
                if resumable:
                    self.upload_file(localdir, folder_id=folder_id,
                                     file_id=file_id, old_request=request)
                else:
                    sys.exit()
            else:
                utils.print_string("Could not upload file '{}': {}".format(
                    localdir, e), utils.PrintStyle.ERROR)
                sys.exit()

    def upload(self, localdir, gd_path):
        """
        Upload file or directory to Google Drive
        """
        localdir = os.path.expanduser(localdir)
        localdir = localdir.replace('/', SEPARATOR)
        localdir = localdir.rstrip(SEPARATOR)
        if not os.path.exists(localdir):
            utils.print_string("'{}' does not exist in your filesystem".format(
                localdir), utils.PrintStyle.ERROR)
            return None

        gfolder = None

        # Get Google Drive directory to upload to
        gd_path = gd_path.replace('/', SEPARATOR)
        id, is_folder = self.traverse(gd_path)
        gfolder = self.client.files().get(fileId=id).execute()

        logging.info("Local directory: " + localdir)
        logging.info("Google Drive path: " + gd_path)

        # Upload file
        if os.path.isfile(localdir):
            logging.info(localdir + " is a local file")
            key = localdir.split(SEPARATOR)[-1]
            file_id = self.exists(gfolder.get('id'), key)
            self.upload_file(
                localdir, folder_id=gfolder.get('id'), file_id=file_id)

        # Upload folder content
        elif os.path.isdir(localdir):
            logging.info(localdir + " is a local directory")
            name = localdir.split(SEPARATOR)[-1]

            # Create subfolder where contents will be uploaded, if it doesn't already exist
            folder_id = self.exists(gfolder.get('id'), name, True)
            if folder_id is None:
                logging.info(
                    "Creating Google Drive subdirectory '{}'".format(name))
                try:
                    metadata = {
                        'name': name,
                        'mimeType': 'application/vnd.google-apps.folder',
                        'parents': [gfolder.get('id')]
                    }
                    current_folder = self.client.files().create(
                        body=metadata, fields='id').execute()
                except HttpError as e:
                    utils.print_string("Could not create folder '{}' on Google Drive: {}".format(
                    name, e), utils.PrintStyle.ERROR)
            else:
                current_folder = self.client.files().get(fileId=folder_id).execute()

            # Dict mapping Google Drive folders with their local absolute paths
            folders = {}

            for dn, dirs, files in os.walk(localdir):
                subfolder = dn[len(localdir):].strip(os.path.sep)
                if subfolder != '':
                    logging.info('Descending into ' + subfolder)

                    # Get respective Google Drive folder
                    current_folder = self.client.files().get(
                        fileId=folders[dn], fields='id, name').execute()

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
                        file_id = self.exists(current_folder.get('id'), name)
                        self.upload_file(
                            fullname, folder_id=current_folder.get('id'), file_id=file_id)

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

                        folder_id = self.exists(
                            current_folder.get('id'), name, True)

                        # If folder doesn't exist on Google Drive, create it
                        if folder_id is None:
                            logging.info(
                                "Creating Google Drive subdirectory '{}'".format(name))
                            try:
                                metadata = {
                                    'name': name,
                                    'mimeType': 'application/vnd.google-apps.folder',
                                    'parents': [current_folder.get('id')]
                                }
                                folder_id = self.client.files().create(
                                    body=metadata, fields='id').execute().get('id')
                            except HttpError as e:
                                utils.print_string("Could not create folder '{}' on Google Drive: {}".format(
                                    os.path.join(dn, name), e), utils.PrintStyle.ERROR)
                        folders[os.path.join(dn, name)] = folder_id
                dirs[:] = keep
        utils.print_string("All uploads successful", utils.PrintStyle.SUCCESS)

    def delete(self, gd_path):
        """
        Delete Google Drive file or directory
        """
        # Get id of Google Drive item that will be deleted
        id, is_folder = self.traverse(gd_path)

        # Delete specified content
        try:
            self.client.files().delete(fileId=id).execute()
            utils.print_string("Successfully deleted '{}'".format(
                gd_path), utils.PrintStyle.SUCCESS)
        except HttpError as e:
            utils.print_string("Could not delete '{}': {}".format(
                gd_path, e), utils.PrintStyle.ERROR)

    def close(self):
        """
        Close Google Drive handler, cleaning up resources.
        """
        if isinstance(self.client, Resource):
            logging.info("Cleaning up Drive resources")
            self.client.close()
        else:
            logging.warning("Error when cleaning up Drive resources.")


# If modifying these scopes, delete the file token.json
SCOPES = ['https://www.googleapis.com/auth/drive']


def authenticate_OAuth2():
    """
    Authenticate using traditional 3-legged OAuth2
    """
    creds = None

    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time
    if os.path.exists('../data/drive_token.json'):
        creds = Credentials.from_authorized_user_file(
            '../data/drive_token.json', SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                '../data/drive_credentials.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('../data/drive_token.json', 'w') as token:
            token.write(creds.to_json())

    logging.info("Client ID: " + creds.client_id)
    logging.info("Client secret: " + creds.client_secret)
    logging.info("Refresh token: " + creds.refresh_token)

    # Create and return client
    client = build('drive', 'v3', credentials=creds)
    return client
