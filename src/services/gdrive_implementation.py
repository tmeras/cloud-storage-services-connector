import logging
import os
import sys
import os.path

# hack to allow importing modules from parent directory
sys.path.insert(0, os.path.abspath('..'))

import utils
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

class Gdrive:
    def __init__(self):
        self.client = authenticate_OAuth2()

    def get_path(self,id):
        """
        Return absolute path of Google Drive file or folder with the given id
        """
        try:
            object = self.client.files().get(fileId = id,fields='id, name, parents').execute()
            parent = object.get('parents')
            path = object.get('name')
            while parent is not None:
                folder = self.client.files().get(fileId = parent[0],fields='id, name, parents').execute()
                path = folder.get('name') + '/' + path
                parent = folder.get('parents')
            return path
        except HttpError as e:
            utils.print_string("Could not get absolute path for object with id '{}':{}".format(id,e),utils.PrintStyle.ERROR)


    
    def exists(self,folder_id,key,key_is_folder = False):
        """
        If key exists inside specified folder, return its id, otherwise return None
        """
        try:
            files = []
            page_token = None
            while True:
                response = self.client.files().list(q="'" + folder_id + "' in parents and trashed = false",spaces='drive',fields='nextPageToken, files(id, name, mimeType)',pageToken = page_token).execute()
                files.extend(response.get('files')) 
                page_token = response.get('nextPageToken')
                if page_token is None:
                    break
        except HttpError as e:
            utils.print_string("Error while listing contents of '{}'".format(folder_id),utils.PrintStyle.ERROR)
            sys.exit()
        
        for item in files:
            if item.get('name') == key:
                if (key_is_folder and item.get('mimeType') == 'application/vnd.google-apps.folder') or ((not key_is_folder) and item.get('mimeType') != 'application/vnd.google-apps.folder'):
                    logging.info("Found '{}', id: {}".format(key,item.get('id')))
                    return item.get('id')
        else:
            logging.info("Not found '{}'".format(key))
            return None


        
    def upload_file(self,localdir,request = None):
        """
        Upload file using resumable upload
        """
        if request is None:
            logging.info("Initiating resumable upload of '{}'".format(localdir))
            metadata = {'name':localdir.split('/')[-1]}
            media = MediaFileUpload(localdir,resumable=True)
            request = self.client.files().create(body = metadata,media_body = media)     
        else:
            logging.info("Resuming upload of '{}'".format(localdir))
 
        response = None
        try:
            while response is None:
                status, response = request.next_chunk()
                if status:
                    utils.print_string("Uploaded %d%%." % int(status.progress() * 100),utils.PrintStyle.INFO)
            utils.print_string ("Upload Complete!",utils.PrintStyle.SUCCESS)
        except HttpError as e:
            if e.resp.status in [404]:
                # Restart the upload
                self.upload_file(localdir)
            elif e.resp.status in [500,502,503,504]:
                # Resume upload
                self.upload_file(localdir,request)
            else:
                utils.print_string("Could not upload file '{}': {}".format(localdir,e),utils.PrintStyle.ERROR)


# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive']

def authenticate_OAuth2():
    """
    Authenticate using traditional 3-legged OAuth2
    """
    creds = None

    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server()
        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    logging.info("Client ID: " + creds.client_id)
    logging.info("Client secret: " + creds.client_secret)
    logging.info("Refresh token: " + creds.refresh_token)

    # Create and return client
    client = build('drive', 'v3', credentials=creds)
    return client


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    gd = Gdrive()
    gd.exists('root','test.txt')
