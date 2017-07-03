################################################
#
#    This is a tool intended to be used by Splunk Ops to read the contents of the "Retention_Request_form"
#
###############################################

#  To execute this script, run "python ./read_google_sheet.py --noauth_local_webserver"

#  THE FOLLOWING NEED TO BE CUSTOMIZED DEPENDING UPON THE THE TARHETED GOOGLE SHEET
credential_name = "BreakMainSheet_credentials.json"
spreadsheetId = '1dFk-bzmM6j8AXpG6-eslQn3l8tZ2VFAEK7a5E5-iXxk'
rangeName1 = 'Retention Request Form v1!B:B'  #  The sourcetype column
rangeName2 = 'Retention Request Form v1!F:F'  #  The new_index  column
scopes = 'https://www.googleapis.com/auth/spreadsheets.readonly'
#CLIENT_SECRET_FILE = 'client_secret.json'
application_name = 'Google Sheets API Python Break Main'

import argparse
import os
import httplib2

#  sudo pip install --upgrade google-api-python-client
from apiclient import discovery
from apiclient.discovery import build
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage


def get_credentials():

	cwd = os.getcwd()
        flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()

	client_secret_file = cwd+"/"+credential_name
        if not os.path.exists(client_secret_file):
                print "ERROR.  The Google Sheet secret file "+client_secret_file+" does not exist. Not ablwe to get sourcetype <-> index mapping"
                exit()

    	home_dir = os.path.expanduser('~')
    	credential_dir = os.path.join(home_dir, '.credentials')
    	if not os.path.exists(credential_dir):
        	os.makedirs(credential_dir)
    	credential_path = os.path.join(credential_dir, 'sheets.googleapis.com-break-main.json')

    	store = Storage(credential_path)
    	credentials = store.get()
    	if not credentials or credentials.invalid:
        	flow = client.flow_from_clientsecrets(client_secret_file, scopes)
        	flow.user_agent = application_name
            	credentials = tools.run_flow(flow, store, flags)
		#credentials = tools.run_flow(flow, store)
    	return credentials

	

if __name__ == "__main__":


        credentials=get_credentials()
        http = credentials.authorize(httplib2.Http())
        discoveryUrl = ('https://sheets.googleapis.com/$discovery/rest?'
                    'version=v4')
        service = discovery.build('sheets', 'v4', http=http,
                              discoveryServiceUrl=discoveryUrl)

	#  Get sourcetype column
        result = service.spreadsheets().values().get(spreadsheetId=spreadsheetId, range=rangeName1).execute()
        values = result.get('values', [])
	print "values="+str(values)

	#  Get new_index column
	result = service.spreadsheets().values().get(spreadsheetId=spreadsheetId, range=rangeName2).execute()
	values = result.get('values', [])
	print "values="+str(values)

        exit()


