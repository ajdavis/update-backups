from __future__ import print_function

# Adapted from Google's "Python spreadsheets quick start".

import argparse
import httplib2
import os

from apiclient import discovery
from datetime import datetime
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

parser = argparse.ArgumentParser(parents=[tools.argparser])
parser.add_argument("event", choices=["copied", "swapped"])
parser.add_argument("data", choices=["system", "photos"])
flags = parser.parse_args()

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/update_backups.json
SCOPES = 'https://www.googleapis.com/auth/spreadsheets'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'update_backups'


def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, 'update_backups.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        credentials = tools.run_flow(flow, store, flags)
        print('Storing credentials to ' + credential_path)
    return credentials


def main():
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                    'version=v4')
    service = discovery.build('sheets', 'v4', http=http,
                              discoveryServiceUrl=discoveryUrl)

    spreadsheetId = '11X3adqmCRztAaNjY0dKbeyds7J_yu6HgkyyGtgNZR-0'
    rangeName = 'A1:D5'
    result = service.spreadsheets().values().get(
        spreadsheetId=spreadsheetId, range=rangeName).execute()
    values = result.get('values', [])

    if not values:
        raise Exception('No data found.')
    elif flags.event == 'copied':
        for rownum, (disk, data, where, copied) in enumerate(values):
            if data.lower() == flags.data.lower() and where == "home":
                print("%s last copied to \"%s\" on %s." % (
                    data.title(), disk, copied))

                break
        else:
            raise Exception("Couldn't find last copy of \"%s\"" % flags.data)

        body = {"values": [[datetime.now().strftime('%Y/%m/%d')]]}
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheetId,
            range="D%d" % (rownum + 1),
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()

        print("Updated.")

if __name__ == '__main__':
    main()
