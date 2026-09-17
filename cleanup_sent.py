import imaplib
import email
import email.utils
import sys
import os
import re
from datetime import datetime, timedelta

user = os.environ.get('SMTP_EMAIL') or os.environ.get('GMAIL_USER')
password = os.environ.get('SMTP_PASSWORD') or os.environ.get('GMAIL_APP_PASSWORD')

if not user or not password:
    print('Cleanup: no credentials, skipping')
    sys.exit(0)

try:
    M = imaplib.IMAP4_SSL('imap.gmail.com', 993)
    M.login(user, password)
except Exception as e:
    print('Cleanup IMAP login failed:', e)
    sys.exit(0)

BS = chr(92)

def extract_email_addr(s):
    m = re.search(r'<([^>]+)>', s)
    if m:
        return m.group(1).lower()
    m = re.search(r'[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}', s)
    if m:
        return m.group(0).lower()
    return ''

# ---- Step 1: collect reply senders from Inbox ----
M.select('INBOX')
typ, data = M.search(None, 'SUBJECT', '"Human-Supercapacitance"')
inbox_ids = data[0].split() if data[0] else []
print('Cleanup: reply emails in Inbox = ' + str(len(inbox_ids)))

replied_from = set()
for i in range(0, len(inbox_ids), 100):
    batch = inbox_ids[i:i+100]
    ids_str = ','.join(x.decode() for x in batch)
    try:
        typ, resp = M.fetch(ids_str, '(BODY.PEEK[HEADER.FIELDS (FROM)])')
        if typ != 'OK':
            continue
        for item in resp:
            if isinstance(item, tuple) and item[1]:
                header = item[1].decode('utf-8', 'ignore')
                addr = extract_email_addr(header)
                if addr:
                    replied_from.add(addr)
    except Exception as e:
        print('  inbox batch error: ' + str(e))

print('Cleanup: unique reply senders = ' + str(len(replied_from)))

# ---- Step 2: find old sent emails (older than 2 days) ----
M.select('"[Gmail]/Sent Mail"')
cutoff_date = (datetime.now() - timedelta(days=2)).strftime('%d-%b-%Y')
typ, data = M.search(None, 'SUBJECT', '"Human-Supercapacitance"', 'BEFORE', cutoff_date)
old_ids = data[0].split() if data[0] else []
print('Cleanup: old sent emails to check = ' + str(len(old_ids)))

deleted = 0
kept = 0

for i in range(0, len(old_ids), 100):
    batch = old_ids[i:i+100]
    ids_str = ','.join(x.decode() for x in batch)
    try:
        typ, resp = M.fetch(ids_str, '(BODY.PEEK[HEADER.FIELDS (TO)])')
        if typ != 'OK':
            continue
        current_num = None
        for item in resp:
            if isinstance(item, tuple) and item[0]:
                num_m = re.match(rb'(\d+)', item[0])
                if num_m:
                    current_num = num_m.group(1).decode()
            if current_num and isinstance(item, tuple) and item[1]:
                header = item[1].decode('utf-8', 'ignore')
                to_addr = extract_email_addr(header)
                if to_addr and to_addr in replied_from:
                    kept += 1
                else:
                    try:
                        M.store(current_num, '+FLAGS', BS + 'Deleted')
                        deleted += 1
                    except Exception as e:
                        print('  delete error: ' + str(e))
                current_num = None
    except Exception as e:
        print('  sent batch error: ' + str(e))

M.expunge()
M.logout()
print('Cleanup: deleted ' + str(deleted) + ' unreplied sent emails')
print('Cleanup: kept ' + str(kept) + ' (replied)')