import imaplib
import email
import email.utils
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

# ---- Step 1: one search for ALL reply threads ----
M.select('"[Gmail]/All Mail"', readonly=True)
typ, data = M.search(None, 'SUBJECT', '"Re: Human-Supercapacitance"')
reply_threads = set()
if typ == 'OK' and data[0]:
    ids = data[0].split()
    print('Cleanup: reply emails found: ' + str(len(ids)))
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
                                thrid = line.split('X-GM-THRID')[1].strip().split()[0].rstrip(')')
                                reply_threads.add(thrid)
                            except:
                                pass
        except Exception as e:
            print('  reply batch error: ' + str(e))
print('Cleanup: unique reply threads = ' + str(len(reply_threads)))

# ---- Step 2: one search for ALL sent emails ----
M.select('"[Gmail]/Sent Mail"')
typ, data = M.search(None, 'SUBJECT', '"Human-Supercapacitance"')
sent_ids = data[0].split() if data[0] else []
print('Cleanup: sent emails to check = ' + str(len(sent_ids)))

cutoff = datetime.now() - timedelta(days=2)
BS = chr(92)
deleted = 0
kept = 0

for i in range(0, len(sent_ids), 200):
    batch = sent_ids[i:i+200]
    ids_str = ','.join(x.decode() for x in batch)
    sent_info = {}
    try:
        typ, resp = M.fetch(ids_str, '(X-GM-THRID INTERNALDATE)')
        if typ == 'OK':
            for item in resp:
                if isinstance(item, tuple) and item[0]:
                    line = item[0].decode('utf-8', 'ignore')
                    parts = line.split(' ', 1)
                    if len(parts) == 2:
                        num = parts[0]
                        rest = parts[1]
                        thrid = ''
                        date_str = ''
                        if 'X-GM-THRID' in rest:
                            try:
                                thrid = rest.split('X-GM-THRID')[1].strip().split()[0].rstrip(')')
                            except:
                                pass
                        if 'INTERNALDATE' in rest:
                            try:
                                ds = rest.split('INTERNALDATE')[1].strip()
                                if ds.startswith('"'):
                                    ds = ds[1:].split('"')[0]
                                date_str = ds
                            except:
                                pass
                        sent_info[num] = (thrid, date_str)
    except Exception as e:
        print('  sent batch error: ' + str(e))
        continue

    for num_str, (thrid, date_str) in sent_info.items():
        if thrid and thrid in reply_threads:
            kept += 1
            continue
        try:
            msg_date = email.utils.parsedate_to_datetime(date_str).replace(tzinfo=None)
        except Exception:
            msg_date = None
        if msg_date and msg_date > cutoff:
            kept += 1
            continue
        try:
            M.store(num_str, '+FLAGS', BS + 'Deleted')
            deleted += 1
        except Exception as e:
            print('  delete error: ' + str(e))

M.expunge()
M.logout()
print('Cleanup: deleted ' + str(deleted) + ' unreplied sent emails')
print('Cleanup: kept ' + str(kept) + ' (replied or recent)')