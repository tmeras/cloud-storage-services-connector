import datetime
import os
import six
import sys
import time
import unicodedata
import contextlib
import dropbox


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


def close_dbx():
    if isinstance(dbx, dropbox.Dropbox):
        dbx.close()
    else:
        print("Error when cleaning up resources")


def download(is_file, name, local_path, dbx_path):
    """
    Download file or folder, as requested by user, from Dropbox
    """
    local_path = os.path.expanduser(local_path)
    print('Dropbox folder name:', dbx_path)
    print('Local directory:', local_path)
    print('File/folder name: ', name)

    if is_file:
        if not dbx_path.startswith("/"):
            dbx_path = "/" + dbx_path
        if not os.path.exists(local_path):
            print(local_path, 'does not exist in your filesystem')
            return None
        local_path = local_path.replace(os.path.sep, "/")
        if not local_path.endswith("/"):
            local_path = local_path + "/"
        name = name.strip("/")
        local_path += name
        with stopwatch('download'):
            try:
                md = dbx.files_download_to_file(local_path, dbx_path)
            except dropbox.exceptions.ApiError as err:
                print('*** API error', err)
                return None
        print(md.name, "downloaded succesfully")
    else:
        if not dbx_path.startswith("/"):
            dbx_path = "/" + dbx_path
        if not os.path.exists(local_path):
            print(local_path, 'does not exist in your filesystem')
            return None
        local_path = local_path.replace(os.path.sep, "/")
        if not local_path.endswith("/"):
            local_path = local_path + "/"
        name = name.strip("/")
        if not name.endswith(".zip"):
            name += ".zip"
        local_path += name
        with stopwatch('download'):
            try:
                dbx.files_download_zip_to_file(local_path, dbx_path)
            except dropbox.exceptions.ApiError as err:
                print('*** API error', err)
                return None
        print("Folder named", dbx_path.split("/")[-1], "downloaded successful")


def delete(dbx_path):
    if not dbx_path.startswith("/"):
        dbx_path = "/" + dbx_path
    with stopwatch('delete'):
        try:
            md = dbx.files_delete(dbx_path)
        except dropbox.exceptions.ApiError as err:
            print('*** API error', err)
            return None
    print("Successfully deleted", md.name)


def upload(rootdir, folder):
    """
     Upload file or folder, as requested by user, to Dropbox
    If a file is already uploaded and hasn't changed since last upload, do not reupload it
    """
    rootdir = os.path.expanduser(rootdir)
    rootdir = rootdir.rstrip(os.path.sep)
    print('Dropbox folder name:', folder)
    print('Local directory:', rootdir)
    if not os.path.exists(rootdir):
        print(rootdir, 'does not exist in your filesystem')
        return None

    # Upload file
    elif os.path.isfile(rootdir):
        print(rootdir, 'is a file in your filesystem')
        rootdir = rootdir.replace(os.path.sep, "/")
        file_name = rootdir.split("/")[-1]
        if not isinstance(file_name, six.text_type):
            file_name = file_name.decode('utf-8')
        nname = unicodedata.normalize('NFC', file_name)
        listing = list_folder(dbx, folder, file_name)
        if nname in listing:
            md = listing[nname]
            mtime = os.path.getmtime(rootdir)
            mtime_dt = datetime.datetime(*time.gmtime(mtime)[:6])
            size = os.path.getsize(rootdir)
            # Compare file modification times
            if (isinstance(md, dropbox.files.FileMetadata) and
                    mtime_dt == md.client_modified and size == md.size):
                print(file_name, 'is already synced [times match]')
            else:
                print(name, 'exists with different stats, downloading')
                res = download_file(dbx, folder, subfolder, name)
                # Compare file contents
                with open(rootdir) as f:
                    data = f.read()
                if res == data:
                    print(file_name, 'is already synced [content match]')
                else:
                    print(file_name, 'has changed since last sync')
                    if yesno('Refresh %s' % file_name, False):
                        upload_file(dbx, rootdir, folder, "", file_name,
                                    overwrite=True)
        elif yesno('Upload %s' % file_name, True):
            upload_file(dbx, rootdir, folder, "", file_name)

    # Upload folder content
    elif os.path.isdir(rootdir):
        print(rootdir, 'is a folder in your filesystem')
        for dn, dirs, files in os.walk(rootdir):
            subfolder = dn[len(rootdir):].strip(os.path.sep)
            listing = list_folder(dbx, folder, subfolder)
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
                elif nname in listing:
                    md = listing[nname]
                    mtime = os.path.getmtime(fullname)
                    mtime_dt = datetime.datetime(*time.gmtime(mtime)[:6])
                    size = os.path.getsize(fullname)
                    # Compare file modification times
                    if (isinstance(md, dropbox.files.FileMetadata) and
                            mtime_dt == md.client_modified and size == md.size):
                        print(name, 'is already synced [times match]')
                    else:
                        print(name, 'exists with different stats, downloading')
                        res = download_file(dbx, folder, subfolder, name)
                        # Compare file contents
                        with open(fullname) as f:
                            data = f.read()
                        if res == data:
                            print(name, 'is already synced [content match]')
                        else:
                            print(name, 'has changed since last sync')
                            if yesno('Refresh %s' % name, False):
                                upload_file(dbx, fullname, folder, subfolder, name,
                                            overwrite=True)
                elif yesno('Upload %s' % name, True):
                    upload_file(dbx, fullname, folder, subfolder, name)

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

    dbx.close()


def list_folder(dbx, folder, subfolder):
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
            res = dbx.files_list_folder(path)
    except dropbox.exceptions.ApiError as err:
        print('Folder listing failed for', path, '-- assumed empty:', err)
        return {}
    else:
        rv = {}
        for entry in res.entries:
            rv[entry.name] = entry
        return rv


def download_file(dbx, folder, subfolder, name):
    """Download a file.
    Return the bytes of the file, or None if it doesn't exist.
    """
    path = '/%s/%s/%s' % (folder, subfolder.replace(os.path.sep, '/'), name)
    while '//' in path:
        path = path.replace('//', '/')
    with stopwatch('download'):
        try:
            md, res = dbx.files_download(path)
        except dropbox.exceptions.ApiError as err:
            print('*** API error', err)
            return None
    data = res.content
    print(len(data), 'bytes; md:', md)
    return data


def upload_file(dbx, fullname, folder, subfolder, name, overwrite=False):
    """Upload a file.
    Return the request response, or None in case of error.
    """
    path = '/%s/%s/%s' % (folder, subfolder.replace(os.path.sep, '/'), name)
    while '//' in path:
        path = path.replace('//', '/')
    mode = (dropbox.files.WriteMode.overwrite
            if overwrite
            else dropbox.files.WriteMode.add)
    mtime = os.path.getmtime(fullname)
    with open(fullname, 'rb') as f:
        data = f.read()
    with stopwatch('upload %d bytes' % len(data)):
        try:
            res = dbx.files_upload(
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


ACCESS_TOKEN = "sl.BWiweo3ioG_406obuOWVGvEoI3OxniQVITO0sUi7t3LwN9Jnv1QKEEBQ6drjkRzhwGArFi_UWD7EZEUC5jBQS0LDkoRpbuTJMpnAFvzZe1BvzQsXxMN5_yNjQejKXm-6hR23QeM"

if __name__ == "__main__":
    dbx = dropbox.Dropbox(ACCESS_TOKEN)
    dbx.close()
else:
    dbx = dropbox.Dropbox(ACCESS_TOKEN)
