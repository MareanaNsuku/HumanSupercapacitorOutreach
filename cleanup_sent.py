import imaplib
import sys
import os
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

# ---- Step 1: reply thread IDs (Gmail native search) ----
M.select('INBOX', readonly=True)
typ, data = M.search(None, 'X-GM-RAW', 'subject:Human-Supercapacitance -label:sent')
reply_threads = set()
if typ == 'OK' and data[0]:
    ids = data[0].split()
    print('Cleanup: reply emails in Inbox = ' + str(len(ids)))
    for i in range(0, len(ids), 500):
        batch = ids[i:i+500]
        try:
            typ, resp = M.fetch(','.join(x.decode() for x in batch), '(X-GM-THRID)')
            if typ == 'OK':
                for item in resp:
                    if isinstance(item, tuple) and item[0]:
                        line = item[0].decode('utf-8', 'ignore')
                        if 'X-GM-THRID' in line:
                            try:
                                t = line.split('X-GM-THRID')[1].strip().split()[0].rstrip(')')
                                reply_threads.add(t)
                            except:
                                pass
        except Exception as e:
            print('  reply batch error: ' + str(e))
print('Cleanup: unique reply threads = ' + str(len(reply_threads)))

# ---- Step 2: old sent emails (Gmail native search, older than 2 days) ----
M.select('"[Gmail]/Sent Mail"')
typ, data = M.search(None, 'X-GM-RAW', 'subject:Human-Supercapacitance older_than:2d')
old_ids = data[0].split() if data[0] else []
print('Cleanup: old sent emails to check = ' + str(len(old_ids)))

deleted = 0
kept = 0

for i in range(0, len(old_ids), 500):
    batch = old_ids[i:i+500]
    try:
        typ, resp = M.fetch(','.join(x.decode() for x in batch), '(X-GM-THRID)')
        if typ != 'OK':
            continue
        for item in resp:
            if not (isinstance(item, tuple) and item[0]):
                continue
            line = item[0].decode('utf-8', 'ignore')
            num = line.split(' ', 1)[0]
            thrid = ''
            if 'X-GM-THRID' in line:
                try:
                    thrid = line.split('X-GM-THRID')[1].strip().split()[0].rstrip(')')
                except:
                    pass
            if thrid and thrid in reply_threads:
                kept += 1
            else:
                try:
                    M.store(num, '+FLAGS', BS + 'Deleted')
                    deleted += 1
                except Exception as e:
                    print('  delete error: ' + str(e))
    except Exception as e:
        print('  sent batch error: ' + str(e))

M.expunge()
M.logout()
print('Cleanup: deleted ' + str(deleted) + ' unreplied sent emails')
print('Cleanup: kept ' + str(kept) + ' (replied)')