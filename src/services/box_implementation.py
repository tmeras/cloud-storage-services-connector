import hashlib
import logging
import os
import sys
import webbrowser
from threading import Thread, Event
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server
import bottle
import boxsdk
from services.data_service import DataService

# hack to allow importing modules from parent directory
sys.path.insert(0, os.path.abspath('..'))
import utils

MB = 1024 * 1024

class Box(DataService):
    def __init__(self):
        # Using OAuth2
        # self.client = authenticate_OAuth2()

        # Using developer token
        auth = boxsdk.OAuth2(client_id='u5jubneda8hf7va31wdhgjv0l4poqykj',
                             client_secret='vKAy2N7rsHO99e00OOGB54AMDMKoiA0p',
                             access_token='ogZ8ohTGmk8QqZ5G0VU3nynRzwyUmsvj')
        self.client = boxsdk.Client(auth)

    def get_path(self, id, is_folder=False):
        """
        Returns absolute path of Box file or folder with the given id
        """
        if is_folder:
            info = self.client.folder(id).get()
        else:
            info = self.client.file(id).get()

        path = ''
        for item in info.path_collection['entries']:
            path += '/' + item.name
        path += '/' + info.name

        return path

    def exists(self, parent_folder, key, key_type):
        """
        If key exists inside parent_folder on Box, return its id, otherwise return None
        """
        for item in parent_folder.get_items():
            if item.name == key:
                if item.type == key_type:
                    return item.id
                
                # Item with same name but different type exists
                else:
                    return -1
        return None
    
    def traverse(self,bx_path):
        """
        Traverse Box directory structure based on given path,

        Return the id and type of the item at the end of the path
        """
        if bx_path.endswith('/'):
            key_type = 'folder'
        else:
            key_type = 'file'

        bx_path = bx_path.strip('/')
        bx_path = bx_path.removeprefix('All Files')
        bx_path = bx_path.lstrip('/')

        # Root foler requested
        if bx_path == "":
            return '0','folder'

        logging.info("Traversing '{}'".format(bx_path))

        current_folder = self.client.root_folder().get()
        names = bx_path.split('/')
        for item in names:
            # Reached final item, return its id if it exists on Box
            if item == names[-1]:
                logging.info("At final item")
                id = self.exists(current_folder, item, key_type)
                if id is not None and id != -1:
                    return id, key_type
                else:
                    utils.print_string("Invalid path: {} '{}' doesn't exist".format(key_type,item),utils.PrintStyle.ERROR)
                    sys.exit()
            else:   
                id = self.exists(current_folder, item,'folder')
                if id is not None and id != -1:
                    current_folder = self.client.folder(id)
                else:
                    utils.print_string("Invalid path: Folder '{}' doesn't exist".format(item),utils.PrintStyle.ERROR)
                    sys.exit()

    def download(self, localdir, bx_path):
        """
        Download a file or folder from Box
        """
        localdir = os.path.expanduser(localdir)
        localdir = localdir.rstrip(os.path.sep)
        if not os.path.isdir(localdir):
            utils.print_string(
                "'{}' is not a directory in your filesystem".format(localdir), utils.PrintStyle.ERROR)
            return None
        
        item_info = None

        # Get item that will be downloaded
        id, key_type = self.traverse(bx_path)
        if key_type == 'folder':
            item_info = self.client.folder(id).get()
        elif key_type == 'file':
            item_info = self.client.file(id).get()

        logging.info('Box directory:' + bx_path)
        logging.info('Local directory:' + localdir)

        try:
            # Download file
            if not item_info.type == 'folder':
                logging.info('Downloading file ' + bx_path)
                dl_path = os.path.join(localdir, item_info.name)
                with open(dl_path, 'wb') as f:
                    self.client.file(item_info.id).download_to(f)

            # Download zipped folder
            else:
                logging.info('Downloading folder ' + bx_path)
                dl_path = os.path.join(localdir, item_info.name) + '.zip'
                with open(dl_path, 'wb') as f:
                    folder = [self.client.folder(item_info.id)]
                    self.client.download_zip(item_info.name, folder, f)

        except boxsdk.BoxAPIException as e:
            utils.print_string("Could not download '{}': {}".format(
                bx_path, e), utils.PrintStyle.ERROR)
            return None

        utils.print_string("Successfully downloaded '{}'".format(
            item_info.name), utils.PrintStyle.SUCCESS)
    

    def upload_file(self, localdir, folder_id, file_id):
        """
        Upload file if it doesn't exist

        If the file already exists, update it

        Use chunked upload/update for files larger than 30 MB
        """
        file_size = os.path.getsize(localdir)

        with open(localdir, 'rb') as f:

            # Large file, upload in chunks
            if file_size > 30 * MB:
                try:
                    sha1 = hashlib.sha1()
                    parts = []

                    # Upload file if it doesn't exist, else update it
                    if file_id is None:
                        logging.info("Uploading '{}' in chunks".format(localdir))
                        uploader = self.client.folder(folder_id).create_upload_session(file_size=file_size,
                                                                                       file_name=localdir.split('/')[
                                                                                           -1])
                    else:
                        logging.info("Updating '{}' in chunks".format(localdir))
                        uploader = self.client.file(file_id).create_upload_session(file_size=file_size)

                    session_id = uploader.id
                    bytes_uploaded = 0
                    for part_num in range(uploader.total_parts):
                        chunk = f.read(uploader.part_size)
                        uploaded_part = uploader.upload_part_bytes(chunk, part_num * uploader.part_size, file_size)
                        bytes_uploaded += len(chunk)
                        logging.info("Uploaded {} MB".format(bytes_uploaded / (1024 * 1024)))
                        parts.append(uploaded_part)
                        sha1.update(chunk)

                    content_sha1 = sha1.digest()
                    logging.info("Session id: {}".format(session_id))

                    uploader.commit(content_sha1=content_sha1, parts=parts)
                    utils.print_string("Chunked upload of '{}' completed".format(localdir), utils.PrintStyle.SUCCESS)

                except boxsdk.BoxAPIException as e:
                    utils.print_string("Could not upload '{}' in chunks: {}".format(localdir, e),
                                       utils.PrintStyle.ERROR)
                    sys.exit()

            # Small file, upload in one request           
            else:
                try:
                    # Upload file it doesn't exist, else update it
                    if file_id is None:
                        logging.info("Uploading '{}' in a single request".format(localdir))
                        self.client.folder(folder_id).upload(localdir)
                    else:
                        logging.info("Updating '{}' in a single request".format(localdir))
                        self.client.file(file_id).update_contents(localdir)

                    utils.print_string("Upload of '{}' completed".format(localdir), utils.PrintStyle.SUCCESS)

                except boxsdk.BoxAPIException as e:
                    utils.print_string("Could not upload '{}': {}".format(localdir, e), utils.PrintStyle.ERROR)
                    sys.exit()

    def upload(self, localdir, bx_path):
        """
        Upload a file or folder to Box
        """
        localdir = os.path.expanduser(localdir)
        localdir = localdir.rstrip(os.path.sep)
        localdir = localdir.replace(os.path.sep, '/')
        if not os.path.exists(localdir):
            utils.print_string("'{}' does not exist in your filesystem".format(
                localdir), utils.PrintStyle.ERROR)
            return None

        folder_info = None

        if not bx_path.endswith('/'):
            utils.print_string("Error: '{}' doesn't point to a Box directory".format(bx_path),utils.PrintStyle.ERROR)
            return None

        # Get Box directory to upload to
        id, key_type = self.traverse(bx_path)
        folder_info = self.client.folder(id).get()

        logging.info("Box directory: " + bx_path)
        logging.info("Local directory: " + localdir)

        # Upload file
        if os.path.isfile(localdir):
            logging.info(localdir + ' is a local file')

            folder_id = folder_info.id
            key = localdir.split('/')[-1]
            id = self.exists(self.client.folder(folder_id), key, 'file')
            if id != -1:
                self.upload_file(localdir, folder_id, id)
            else:
                utils.print_string("Cannot upload '{}', name already in use by another item of different type".format(key),utils.PrintStyle.ERROR)
                return None
                
        # Upload folder content
        elif os.path.isdir(localdir):
            logging.info(localdir + ' is a local folder')

            # Dict mapping Box folder ids with their local absolute paths
            folders = {}

            current_folder = self.client.folder(folder_info.id)
            for dn, dirs, files in os.walk(localdir):
                subfolder = dn[len(localdir):].strip(os.path.sep)
                if subfolder != '':
                    logging.info('Descending into ' + subfolder)

                    # Get respective Box folder
                    current_folder = self.client.folder(folders[dn])

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
                        id = self.exists(current_folder, name, 'file')
                        self.upload_file(fullname, current_folder.get().id, id)

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

                        id = self.exists(current_folder, name, 'folder')

                        # If folder doesn't exist on Box, create it
                        if id is None:
                            logging.info('Creating Box subfolder ' + name)
                            id = current_folder.create_subfolder(name).get().id
                        folders[os.path.join(dn, name)] = id
                dirs[:] = keep

        utils.print_string("All uploads successfull", utils.PrintStyle.SUCCESS)

    def delete(self, bx_path):
        """
        Delete a file or folder from Box
        """
        item = None

        # Get Box item that will be deleted
        id, key_type = self.traverse(bx_path)
        if key_type == 'folder':
            item = self.client.folder(id)
        elif key_type == 'file':
            item = self.client.file(id)

        # Delete item
        if item.delete():
            utils.print_string("Successfully deleted '{}'".format(
                bx_path), utils.PrintStyle.SUCCESS)
        else:
            utils.print_string("Could not delete '{}'".format(
                bx_path), utils.PrintStyle.ERROR)


def authenticate_OAuth2():
    """
    Authenticate using traditional 3-legged OAuth2
    """
    CLIENT_ID = 'u5jubneda8hf7va31wdhgjv0l4poqykj'
    CLIENT_SECRET = 'vKAy2N7rsHO99e00OOGB54AMDMKoiA0p'

    class StoppableWSGIServer(bottle.ServerAdapter):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._server = None

        def run(self, app):
            server_cls = self.options.get('server_class', WSGIServer)
            handler_cls = self.options.get('handler_class', WSGIRequestHandler)
            self._server = make_server(
                self.host, self.port, app, server_cls, handler_cls)
            self._server.serve_forever()

        def stop(self):
            self._server.shutdown()

    auth_code = {}
    auth_code_is_available = Event()

    local_oauth_redirect = bottle.Bottle()

    @local_oauth_redirect.get('/')
    def get_token():
        auth_code['auth_code'] = bottle.request.query.code
        auth_code['csrf_token'] = bottle.request.query.state
        auth_code_is_available.set()

    local_server = StoppableWSGIServer(host='localhost', port=8080)
    server_thread = Thread(
        target=lambda: local_oauth_redirect.run(server=local_server))
    server_thread.start()

    oauth = boxsdk.OAuth2(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
    )
    auth_url, csrf_token = oauth.get_authorization_url('http://localhost:8080')

    # Redirect user to auth_url, where they will enter their Box credentials
    webbrowser.open(auth_url)

    # When user is redirected to localhost, exchange auth_code for access and refresh token
    auth_code_is_available.wait()
    local_server.stop()
    assert auth_code['csrf_token'] == csrf_token
    access_token, refresh_token = oauth.authenticate(auth_code['auth_code'])

    logging.info('access_token: ' + access_token)
    logging.info('refresh_token: ' + refresh_token)

    return boxsdk.Client(oauth)

if __name__ == '__main__':
    logging.basicConfig(level = logging.INFO)
    bx = Box()
    bx.upload("/Users/teomeras/Desktop/foldertest","All Files/")
