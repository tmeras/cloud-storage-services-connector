import datetime
import os
import six
import sys
import time
import unicodedata
import contextlib
import re
import dropbox

ACCESS_TOKEN = "sl.BYC9VluRNp4UpLl7HDlO86kLtEHg2AinAeZ8BvZCJqJ5mdhIxp0Y1MxVLvuZie-byzYiWUdxGkwAPTP2J1-mcE3v7lkKkyFarj24k1WQqhr38R8ukzDcbUf9ft3SdiMWbQGS6oE"


class Dropbox:
    def __init__(self):
        self.dbx = dropbox.Dropbox(ACCESS_TOKEN)

    def close_dbx(self):
        if isinstance(self.dbx, dropbox.Dropbox):
            self.dbx.close()
        else:
            print("Error when cleaning up resources")

    def download(self, name, local_path, dbx_path):
        """ Download file or folder, as requested by user, from Dropbox
        """
        local_path = os.path.expanduser(local_path)
        if not dbx_path.startswith("/"):
            dbx_path = "/" + dbx_path
        if not os.path.exists(local_path):
            print(local_path, 'does not exist in your filesystem')
            return None
        print('Dropbox folder: ', dbx_path)
        print('Local directory: ', local_path)
        print('File/folder name: ', name)
        local_path = local_path.replace(os.path.sep, "/")
        if not local_path.endswith("/"):
            local_path = local_path + "/"

        # If dbx_path points to file
        if re.search(r'\.[a-zA-Z0-9]+$', dbx_path) is not None:
            print(dbx_path, 'points to file')
            name = name.strip("/")
            local_path += name
            with stopwatch('download'):
                try:
                    md = self.dbx.files_download_to_file(local_path, dbx_path)
                except dropbox.exceptions.ApiError as err:
                    print('*** API error', err)
                    return None
            print(md.name, "downloaded succesfully")

        # If dbx_path points to folder
        else:
            print(dbx_path, 'points to folder')
            name = name.strip("/")
            if not name.endswith(".zip"):
                name += ".zip"
            local_path += name
            with stopwatch('download'):
                try:
                    self.dbx.files_download_zip_to_file(local_path, dbx_path)
                except dropbox.exceptions.ApiError as err:
                    print('*** API error', err)
                    return None
            print("Folder named", dbx_path.split(
                "/")[-1], "downloaded successful")

    def delete(self, dbx_path):
        if not dbx_path.startswith("/"):
            dbx_path = "/" + dbx_path
        with stopwatch('delete'):
            try:
                md = self.dbx.files_delete(dbx_path)
            except dropbox.exceptions.ApiError as err:
                print('*** API error', err)
                return None
        print("Successfully deleted", md.name)

    def upload(self, rootdir, folder):
        """ Upload file or folder, as requested by user, to Dropbox
        """
        rootdir = os.path.expanduser(rootdir)
        rootdir = rootdir.rstrip(os.path.sep)
        print('Dropbox folder:', folder)
        print('Local directory:', rootdir)
        if not os.path.exists(rootdir):
            print(rootdir, 'does not exist in your filesystem')
            return None

        # Upload file
        elif os.path.isfile(rootdir):
            print(rootdir, 'is a file in your filesystem')
            rootdir = rootdir.replace(os.path.sep, "/")
            file_name = rootdir.split('/')[-1]
            if not isinstance(file_name, six.text_type):
                file_name = file_name.decode('utf-8')
            nname = unicodedata.normalize('NFC', file_name)
            if yesno('Upload %s' % file_name, True):
                self.upload_file(rootdir, folder, "", file_name)

        # Upload folder content
        elif os.path.isdir(rootdir):
            print(rootdir, 'is a folder in your filesystem')
            for dn, dirs, files in os.walk(rootdir):
                subfolder = dn[len(rootdir):].strip(os.path.sep)
                #listing = self.list_folder(folder, subfolder)
                print('Descending into', subfolder, '...')

                # First do all the files
                for name in files:
                    fullname = os.path.join(dn, name)
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
                        self.upload_file(fullname, folder, subfolder, name)

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
                    else:
                        print('OK, skipping directory:', name)
                dirs[:] = keep

    def list_folder(self, folder, subfolder):
        """List a folder.
        Return a dict mapping unicode filenames to
        FileMetadata|FolderMetadata entries.
        """
        path = '/%s/%s' % (folder, subfolder.replace(os.path.sep, '/'))
        while '//' in path:
            path = path.replace('//', '/')
        path = path.rstrip('/')
        try:
            with stopwatch('list_folder'):
                res = self.dbx.files_list_folder(path)
        except dropbox.exceptions.ApiError as err:
            print('Folder listing failed for', path, '-- assumed empty:', err)
            return {}
        else:
            rv = {}
            for entry in res.entries:
                rv[entry.name] = entry
            return rv

    def download_file(self, folder, subfolder, name):
        """Download a file. Do not store it locally
        Return the bytes of the file, or None if it doesn't exist.
        """
        path = '/%s/%s/%s' % (folder,
                              subfolder.replace(os.path.sep, '/'), name)
        while '//' in path:
            path = path.replace('//', '/')
        with stopwatch('download'):
            try:
                md, res = self.dbx.files_download(path)
            except dropbox.exceptions.ApiError as err:
                print('*** API error', err)
                return None
        data = res.content
        print(len(data), 'bytes; md:', md)
        return data

    def upload_file(self, fullname, folder, subfolder, name):
        """Upload a file.
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
        with stopwatch('upload %d bytes' % len(data)):
            try:
                res = self.dbx.files_upload(
                    data, path, mode,
                    client_modified=datetime.datetime(*time.gmtime(mtime)[:6]),
                    mute=True)
            except dropbox.exceptions.ApiError as err:
                print('*** API error', err)
                return None
        print('uploaded as', res.name)
        return res


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


@contextlib.contextmanager
def stopwatch(message):
    """Context manager to print how long a block of code took."""
    t0 = time.time()
    try:
        yield
    finally:
        t1 = time.time()
        print('Total elapsed time for %s: %.3f seconds' % (message, t1 - t0))


def no_redirect_OAuth2():
    """Goes through a basic oauth flow using the existing long-lived token type
    """
    APP_KEY = "t1uokr1i2qj9ot1"
    APP_SECRET = "yxrwv0tc5fipf8e"

    auth_flow = DropboxOAuth2FlowNoRedirect(APP_KEY, APP_SECRET)
    authorize_url = auth_flow.start()
    print("1. Go to: " + authorize_url)
    print("2. Click \"Allow\" (you might have to log in first).")
    print("3. Copy the authorization code.")
    auth_code = input("Enter the authorization code here: ").strip()
    try:
        oauth_result = auth_flow.finish(auth_code)
    except Exception as e:
        sys.exit('Error: ' + e)

    with dropbox.Dropbox(oauth2_access_token=oauth_result.access_token) as dbx:
        dbx.users_get_current_account()
        print("Successfully set up client!")
        return dbx  # Return the Dropbox object to later use it for requests to Dropbox API
