import bottle
import os
import six
import unicodedata
from threading import Thread, Event
import webbrowser
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server
import boxsdk


class Box:
    def __init__(self):
        # Using OAuth2
        # self.client =authenticate_OAuth2()

        # Using developer token
        auth = boxsdk.OAuth2(client_id='u5jubneda8hf7va31wdhgjv0l4poqykj',
                                client_secret='vKAy2N7rsHO99e00OOGB54AMDMKoiA0p',
                                access_token='v8kYZIw7kvrbDQlHJanp6qCvLTvisu2Q')
        self.client = boxsdk.Client(auth)

    def get_path(self, id, is_folder=False):
        """Returns absolute path of Box content with the given id
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
        """If key exists inside parent_folder, return its id, otherwise return None
        """
        for item in parent_folder.get_items():
            item_info = item.get()
            if item_info.name == key and item_info.type == key_type:
                return item_info.id

        return None

    def upload(self, localdir, bxname=''):
        """Upload content of localdir to Box folder with name bxname or root folder by default
        """
        localdir = os.path.expanduser(localdir)
        localdir = localdir.rstrip(os.path.sep)
        if not os.path.exists(localdir):
            print(localdir, 'does not exist in your filesystem')
            return None

        # Search for non-root Box folder with the given name
        folder_info = None
        bxpath = None
        if bxname != '':
            search_results = self.client.search().query(query=bxname, result_type='folder')
            for item in search_results:
                folder_info = item.get()
                bxpath = self.get_path(folder_info.id, True)
                if yesno('Should content be uploaded to %s ' % bxpath, True):
                    break
            else:
                print('Cannot find Box folder with name', bxname)
                return None
        else:
            bxpath = '/All Files'
            folder_info = self.client.root_folder().get()

        print("Box Folder:", bxpath)
        print("Local Directory:", localdir)

        # Upload file
        if os.path.isfile(localdir):
            print(localdir, 'is a file in your filesystem')

            folder_id = folder_info.id
            key = localdir.split('/')[-1]
            id = self.exists(self.client.folder(folder_id), key, 'file')

            # If file doesn't already exist, upload it, otherwise update it
            try:
                if id is None:
                    print('Uploading', key, '....')
                    self.client.folder(folder_id).upload(localdir)
                    print('File upload ok')
                else:
                    print('Updating', key, '....')
                    self.client.file(id).update_contents(localdir)
                    print('File update ok')
            except boxsdk.BoxAPIException as e:
                print('*** API error', e.message)
                return None
        
        # Upload folder content
        elif os.path.isdir(localdir):
            print(localdir, 'is a folder in your filesystem')

            # Dict mapping folder ids with their names
            folders = {}

            current_folder = self.client.folder(folder_info.id)
            for dn, dirs, files in os.walk(localdir):
                subfolder = dn[len(localdir):].strip(os.path.sep)
                if subfolder != '':
                    print('Descending into', subfolder, '...')

                    # Get current folder
                    current_folder = self.client.folder(folders[dn.split('/')[-1]])

                # First do all the files
                for name in files:
                    fullname = os.path.join(dn,name)
                    if not isinstance(name, six.text_type):
                        name = name.decode('utf-8')
                    nname = unicodedata.normalize('NFC', name)
                    if name.startswith('.'):
                        print('Skipping dot file:', name)
                    elif name.startswith('@') or name.endswith('~'):
                        print('Skipping temporary file:', name)
                    elif name.endswith('.pyc') or name.endswith('.pyo'):
                        print('Skipping generated file:', name)
                    elif yesno('Upload %s' % name, True):
                        id = self.exists(current_folder, name, 'file')

                        # If file doesn't already exist, upload it, otherwise update it
                        try:
                            if id is None:
                                print('Uploading', name, '....')
                                current_folder.upload(fullname)
                                print('File upload ok')
                            else:
                                print('Updating', name, '....')
                                self.client.file(id).update_contents(fullname)
                                print('File update ok')
                        except boxsdk.BoxAPIException as e:
                            print('*** API error', e.message)
                            return None
                
                # Then choose which subdirectories to traverse
                keep = []
                for name in dirs:
                    if name.startswith('.'):
                        print('Skipping dot directory:', name)
                    elif name.startswith('@') or name.endswith('~'):
                        print('Skipping temporary directory:', name)
                    elif name == '__pycache__':
                        print('Skipping generated directory:', name)
                    elif yesno('Descend into %s' % name, True):
                        print('Keeping directory:', name)
                        keep.append(name)

                        id = self.exists(current_folder, name, 'folder')

                        # If folder doesn't exist on Box, create it
                        if id is None:
                            print('creating subfolder',name)
                            id = current_folder.create_subfolder(name).get().id
                        folders[name] = id
                    else:
                        print('OK, skipping directory:', name)

                dirs[:] = keep


def yesno(message, default):
    """Handy helper function to ask a yes/no question.
    Special answers:
    - q or quit exits the program
    - p or pdb invokes the debugger
    """
    if default:
        message += '? [Y/n] '
    else:
        message += '? [N/y] '
    while True:
        answer = input(message).strip().lower()
        if not answer:
            return default
        if answer in ('y', 'yes'):
            return True
        if answer in ('n', 'no'):
            return False
        if answer in ('q', 'quit'):
            print('Exit')
            raise SystemExit(0)
        if answer in ('p', 'pdb'):
            import pdb
            pdb.set_trace()
        print('Please answer YES or NO.')


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
    print('access_token: ' + access_token)
    print('refresh_token: ' + refresh_token)

    return boxsdk.Client(oauth)


if __name__ == '__main__':
    box = Box()
