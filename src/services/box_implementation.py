import bottle
import logging
import os
import sys
import unicodedata
from threading import Thread, Event
import webbrowser
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

import boxsdk
import utils

# hack to allow importing modules from parent directory
sys.path.insert(0, os.path.abspath('..'))


class Box:
    def __init__(self):
        # Using OAuth2
        # self.client = authenticate_OAuth2()

        # Using developer token
        auth = boxsdk.OAuth2(client_id='u5jubneda8hf7va31wdhgjv0l4poqykj',
                             client_secret='vKAy2N7rsHO99e00OOGB54AMDMKoiA0p',
                             access_token='4fwp1VQhawgttGTns6uMSrdvuqQ5lBia')
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
            item_info = item.get()
            if item_info.name == key and item_info.type == key_type:
                return item_info.id

        return None

    def download(self, localdir, bxname):
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
        bxpath = None

        # Search for Box content named bxname
        search_results = self.client.search().query(query=bxname)
        for item in search_results:
            item_info = item.get()
            is_folder = (item_info.type == 'folder')
            bxpath = self.get_path(item_info.id, is_folder)
            if utils.yesno('Download %s ' % bxpath, True):
                break
        else:
            utils.print_string('Cannot find Box content with name {}'.format(
                bxname), utils.PrintStyle.ERROR)
            return None

        logging.info('Box directory:' + bxpath)
        logging.info('Local directory:' + localdir)

        try:
            # Download file
            if not item_info.type == 'folder':
                logging.info('Downloading file ' + bxpath)
                dl_path = os.path.join(localdir, item_info.name)
                with open(dl_path, 'wb') as f:
                    self.client.file(item_info.id).download_to(f)

            # Download zipped folder
            else:
                logging.info('Downloading folder ' + bxpath)
                dl_path = os.path.join(localdir, item_info.name) + '.zip'
                with open(dl_path, 'wb') as f:
                    folder = [self.client.folder(item_info.id)]
                    self.client.download_zip(item_info.name, folder, f)
        except boxsdk.BoxAPIException as e:
            utils.print_string("Could not download '{}': {}".format(
                bxpath, e), utils.PrintStyle.ERROR)
            return None

        utils.print_string("Successfully downloaded '{}'".format(
            item_info.name), utils.PrintStyle.SUCCESS)

    def upload(self, localdir, bxname):
        """
        Upload a file or folder to Box
        """
        localdir = os.path.expanduser(localdir)
        localdir = localdir.rstrip(os.path.sep)
        if not os.path.exists(localdir):
            utils.print_string("'{}' does not exist in your filesystem".format(
                localdir), utils.PrintStyle.ERROR)
            return None

        folder_info = None
        bxpath = None

        # Search for non-root Box folder with the given name
        if bxname != '':
            search_results = self.client.search().query(query=bxname, result_type='folder')
            for item in search_results:
                folder_info = item.get()
                bxpath = self.get_path(folder_info.id, True)
                if utils.yesno('Should content be uploaded to %s ' % bxpath, True):
                    break
            else:
                utils.print_string('Cannot find Box folder with name: {}'.format(
                    bxname), utils.PrintStyle.ERROR)
                return None

        # Otherwise upload to root Box folder
        else:
            bxpath = '/All Files'
            folder_info = self.client.root_folder().get()

        logging.info("Local directory: " + localdir)
        logging.info("Box directory: " + bxpath)

        # Upload file
        if os.path.isfile(localdir):
            logging.info(localdir + ' is a local file')

            folder_id = folder_info.id
            key = localdir.split('/')[-1]
            id = self.exists(self.client.folder(folder_id), key, 'file')

            # If file doesn't already exist, upload it, otherwise update it
            try:
                if id is None:
                    logging.info('Uploading ' + localdir)
                    self.client.folder(folder_id).upload(localdir)
                else:
                    logging.info('Updating ' + localdir)
                    self.client.file(id).update_contents(localdir)
            except boxsdk.BoxAPIException as e:
                utils.print_string("Could not upload file '{}': {}".format(
                    localdir, e), utils.PrintStyle.ERROR)
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

                        # If file doesn't already exist, upload it, otherwise update it
                        try:
                            if id is None:
                                logging.info('Uploading ' + name)
                                current_folder.upload(fullname)
                            else:
                                logging.info('Updating ' + name)
                                self.client.file(id).update_contents(fullname)
                        except boxsdk.BoxAPIException as e:
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

                        id = self.exists(current_folder, name, 'folder')

                        # If folder doesn't exist on Box, create it
                        if id is None:
                            logging.info('Creating Box subfolder ' + name)
                            id = current_folder.create_subfolder(name).get().id
                        folders[os.path.join(dn, name)] = id
                dirs[:] = keep

        utils.print_string("All uploads ok!", utils.PrintStyle.SUCCESS)

    def delete(self, bxname):
        """
        Delete a file or folder from Box
        """
        item = None
        item_info = None
        bxpath = ''

        # Search for Box content with the name bxname
        search_results = self.client.search().query(query=bxname)
        for item in search_results:
            item_info = item.get()
            is_folder = (item_info.type == 'folder')
            bxpath = self.get_path(item_info.id, is_folder)
            if utils.yesno('Delete %s ' % bxpath, True):
                break
        else:
            utils.print_string('Cannot find Box content with name: {}'.format(
                bxname), utils.PrintStyle.ERROR)
            return None

        if item.delete():
            utils.print_string("Sucesfully deleted '{}'".format(
                bxpath), utils.PrintStyle.SUCCESS)
        else:
            utils.print_string("Could not delete '{}'".format(
                bxpath), utils.PrintStyle.ERROR)


def authenticate_OAuth2():
    """Authenticate using traditional 3-legged OAuth2
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

    # Redirect user to auth_url, where they will enter thei Box credentials
    webbrowser.open(auth_url)

    # When user is redirected to localhost, exchange auth_code for access and refresh token
    auth_code_is_available.wait()
    local_server.stop()
    assert auth_code['csrf_token'] == csrf_token
    access_token, refresh_token = oauth.authenticate(auth_code['auth_code'])

    logging.info('access_token: ' + access_token)
    logging.info('refresh_token: ' + refresh_token)

    return boxsdk.Client(oauth)
