from __future__ import print_function

import argparse
import os
import subprocess
from datetime import datetime

import httplib2
from apiclient import discovery
from oauth2client import client, tools
from oauth2client.file import Storage

parser = argparse.ArgumentParser(parents=[tools.argparser])
parser.add_argument("event", choices=["copy", "copied", "swapped"])
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


def tmutil(*args):
    return subprocess.check_output(['/usr/bin/tmutil'] + list(args)).strip()


def latest_timemachine_backup():
    line = tmutil('latestbackup')
    # Like "/Volumes/Time Machine 4TB 1/Backups.backupdb/MBP/2017-02-17-031920"
    return datetime.strptime(line.split('/')[-1], '%Y-%m-%d-%H%M%S')


spreadsheetId = '11X3adqmCRztAaNjY0dKbeyds7J_yu6HgkyyGtgNZR-0'


def spreadsheets():
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                    'version=v4')

    return discovery.build('sheets', 'v4',
                           http=http,
                           discoveryServiceUrl=discoveryUrl
                           ).spreadsheets().values()


def spreadsheet_values():
    rangeName = 'A1:D5'
    result = spreadsheets().get(spreadsheetId=spreadsheetId,
                                range=rangeName).execute()

    values = result.get('values', [])
    if not values:
        raise Exception('No data found.')

    for rownum, (disk, data, where, copied) in enumerate(values):
        yield rownum + 1, disk, data, where, copied


def on_copied():
    for rownum, disk, data, where, copied in spreadsheet_values():
        if data.lower() == flags.data.lower() and where == "home":
            print("%s last copied to \"%s\" on %s." % (
                data.title(), disk, copied))

            break
    else:
        raise Exception("Couldn't find last copy of \"%s\"" % flags.data)

    if flags.data == 'system':
        latest_backup = latest_timemachine_backup().strftime('%Y/%m/%d')
    else:
        latest_backup = datetime.now().strftime('%Y/%m/%d')

    body = {"values": [[latest_backup]]}
    spreadsheets().update(
        spreadsheetId=spreadsheetId,
        range="D%d" % rownum,
        valueInputOption="USER_ENTERED",
        body=body
    ).execute()

    print("Updated: %s." % latest_backup)


def main():
    if flags.event == 'copy':
        if flags.data == 'system':
            print('Copying....')
            print(tmutil('startbackup', '--auto', '--block'))
        else:
            assert False, "Don't know how to copy \"%s\"" % flags.data

        on_copied()
    elif flags.event == 'copied':
        on_copied()
    elif flags.event == "swapped":
        home_disk = None
        office_disk = None
        for rownum, disk, data, where, copied in spreadsheet_values():
            if data.lower() == flags.data.lower():
                if where == "home":
                    home_disk = rownum
                    home_disk_name = disk
                elif where == "office":
                    office_disk = rownum
                    office_disk_name = disk

        if not home_disk:
            raise Exception("Couldn't find home disk for \"%s\"", flags.data)

        if not office_disk:
            raise Exception("Couldn't find office disk for \"%s\"", flags.data)

        print('"%s" is now home, "%s" at office' % (
            office_disk_name, home_disk_name))

        # Swap home and office.
        data = [{
            "range": "C%d" % home_disk,
            "values": [["office"]]
        }, {
            "range": "C%d" % office_disk,
            "values": [["home"]]
        }]

        body = {"data": data, "valueInputOption": "USER_ENTERED"}
        spreadsheets().batchUpdate(
            spreadsheetId=spreadsheetId, body=body).execute()
    else:
        raise argparse.ArgumentError(
            argument="event", message='Unknown event: "%s"' % flags.event)


if __name__ == '__main__':
    main()
