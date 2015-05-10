#!/usr/bin/python
import sys
import time
import re
from subprocess import call

import argparse
import httplib2

from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import run_flow, argparser
from apiclient.discovery import build
# Parse the command-line arguments (e.g. --noauth_local_webserver)
parser = argparse.ArgumentParser(parents=[argparser])
flags = parser.parse_args()

# Path to the client_secret.json file downloaded from the Developer Console
CLIENT_SECRET_FILE = 'client_secret.json'

# Check https://developers.google.com/gmail/api/auth/scopes
# for all available scopes
#OAUTH_SCOPE = 'https://www.googleapis.com/auth/gmail.readonly'
OAUTH_SCOPE = 'https://www.googleapis.com/auth/gmail.modify'

# Location of the credentials storage file
STORAGE = Storage('gmail.storage')

# Start the OAuth flow to retrieve credentials
flow = flow_from_clientsecrets(CLIENT_SECRET_FILE, scope=OAUTH_SCOPE)
http = httplib2.Http()

# Try to retrieve credentials from storage or run the flow to generate them
credentials = STORAGE.get()
if credentials is None or credentials.invalid:
    credentials = run_flow(flow, STORAGE, flags, http=http)

# Authorize the httplib2.Http object with our credentials
http = credentials.authorize(http)

# Build the Gmail service from discovery
gmail_service = build('gmail', 'v1', http=http)

###
## Actual stuff
###

clean_from_patt = re.compile(r'\s*<[^>]*>\s*')
def clean_from(from_address):
    return clean_from_patt.sub('', from_address)
clean_subject_patt = re.compile(r'\s*\[brostomp\]\s*')
def clean_subject(subject):
    return clean_subject_patt.sub('', subject)

SLEEP_TIME = 30
SCAVBASS_LABEL = 'scavbass-read'
intro = "Attention Brostompers! The following emails have been sent on the listhost:"
outro = "That is all. Thank you!"
all_labels = gmail_service.users().labels().list(userId='me').execute()['labels']
scavbasslabel_id = [l['id'] for l in all_labels if l['name'] == SCAVBASS_LABEL][0]
while True:
    threads = gmail_service.users().threads().list(userId='me', q='label:brostomp -label:'+SCAVBASS_LABEL).execute()
    if 'threads' not in threads:
        print >> sys.stderr, 'No threads found; sleeping for %d seconds.' % SLEEP_TIME
        time.sleep(SLEEP_TIME)
    else:
        threads = threads['threads']
        messages = []
        for t in threads:
            thread = gmail_service.users().threads().get(id=t['id'], userId='me').execute()
            headers = thread['messages'][0]['payload']['headers']
            thread_id = thread['id']
            subject_raw = [h['value'] for h in headers if h['name'] == 'Subject'][0]
            subject = clean_subject(subject_raw)
            from_address_raw = [h['value'] for h in headers if h['name'] == 'From'][0]
            from_address = clean_from(from_address_raw)
            req_body = {'addLabelIds': [scavbasslabel_id]}
            print >> sys.stderr, 'Updating thread: %s from %s' % (subject_raw, from_address_raw)
            gmail_service.users().threads().modify(id=thread_id, userId='me', body=req_body).execute()
            messages.append({'subject': subject, 'from': from_address})
        if messages:
            content = '\n'.join(['From %s: %s' % (m['from'], m['subject']) for m in messages])
            message = intro + '\n' + content + '\n' + outro
            print >> sys.stderr, 'Recording message:'
            print >> sys.stderr, message
            call(["/usr/bin/espeak", "-w", "wavs/message_%d.wav" % int(time.time()), message])
