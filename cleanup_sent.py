import imaplib
import re
import sys
import os

user = os.environ.get('SMTP_EMAIL') or os.environ.get('GMAIL_USER')
password = os.environ.get('SMTP_PASSWORD') or os.environ.get('GMAIL_APP_PASSWORD')

if not user or not password:
    print('Cleanup: no credentials, skipping')
    sys.exit(0)

try:
    M = imaplib.IMAP4_SSL('imap.gmail.com', 993)
    M.login(user, password)
except Exception as e:
    print('Cleanup IMAP login failed: ' + str(e))
    sys.exit(0)

BS = chr(92)

def extract_addr(s):
    m = re.search(r'<([^>]+)>', s)
    if m:
        return m.group(1).lower().strip()
    m = re.search(r'[\w._%+-]+@[\w.-]+\.[A-Za-z]{2,}', s)
    if m:
        return m.group(0).lower().strip()
    return ''

def domain_of(addr):
    if '@' in addr:
        return addr.split('@', 1)[1]
    return ''

# Step 1: reply senders from Inbox
M.select('INBOX', readonly=True)
typ, data = M.search(None, 'X-GM-RAW', '"subject:Human-Supercapacitance -label:sent"')
inbox_ids = data[0].split() if data[0] else []
print('Cleanup: reply emails in Inbox = ' + str(len(inbox_ids)))

reply_addrs = set()
reply_domains = set()
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
                addr = extract_addr(header)
                if addr:
                    reply_addrs.add(addr)
                    d = domain_of(addr)
                    if d:
                        reply_domains.add(d)
    except Exception as e:
        print('  inbox fetch error: ' + str(e))

print('Cleanup: unique reply senders = ' + str(len(reply_addrs)))
print('Cleanup: unique reply domains = ' + str(len(reply_domains)))

# Step 2: process old sent emails
M.select('"[Gmail]/Sent Mail"')
typ, data = M.search(None, 'X-GM-RAW', '"subject:Human-Supercapacitance older_than:2d"')
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
                m = re.match(rb'(\d+)', item[0])
                if m:
                    current_num = m.group(1).decode()
            if current_num and isinstance(item, tuple) and item[1]:
                header = item[1].decode('utf-8', 'ignore')
                to_addr = extract_addr(header)
                d = domain_of(to_addr)
                if to_addr in reply_addrs or (d and d in reply_domains):
                    kept += 1
                else:
                    try:
                        M.store(current_num, '+FLAGS', BS + 'Deleted')
                        deleted += 1
                    except Exception as e:
                        print('  delete error: ' + str(e))
                current_num = None
    except Exception as e:
        print('  sent fetch error: ' + str(e))

M.expunge()
M.logout()
print('Cleanup: deleted ' + str(deleted) + ' unreplied sent emails')
print('Cleanup: kept ' + str(kept) + ' (replied)')