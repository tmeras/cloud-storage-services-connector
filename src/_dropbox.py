import os
import sys
import dropbox
from dropbox import DropboxOAuth2FlowNoRedirect
from dropbox.files import WriteMode
from dropbox.exceptions import ApiError, AuthError

def no_redirect_OAuth2():
    #Goes through a basic oauth flow using the existing long-lived token type

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
        return dbx #return the Dropbox object to later use it for requests to Dropbox API

LOCALFILE = 'test.txt'
UPLOADPATH = '/test.txt'

def backup(dbx):
    #Uploads contents of LOCALFILE to Dropbox  
    with open(LOCALFILE, 'rb') as f:
        # We use WriteMode=overwrite to make sure that the settings in the file
        # are changed on upload
        print("Uploading " + LOCALFILE + " to Dropbox as " + UPLOADPATH + "...")
        try:
            dbx.files_upload(f.read(), UPLOADPATH, mode=WriteMode('overwrite'))
        except ApiError as err:
            # This checks for the specific error where a user doesn't have
            # enough Dropbox space quota to upload this file
            if (err.error.is_path() and
                    err.error.get_path().reason.is_insufficient_space()):
                sys.exit("ERROR: Cannot back up; insufficient space.")
            elif err.user_message_text:
                print(err.user_message_text)
                sys.exit()
            else:
                print(err)
                sys.exit()


if __name__ == "__main__":
    print()
    print(os.getcwd())
    dbx = no_redirect_OAuth2() #authorize user
    try:
        dbx.users_get_current_account()
    except AuthError:
         sys.exit("ERROR: Something went wrong while accessing Dropbox object")

    backup(dbx)

    dbx.close() #clean up all resources

    
    