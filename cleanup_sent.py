import imaplib
import email
import email.utils
import sys
import os
from email.header import decode_header
from datetime import datetime, timedelta

user = os.environ.get('SMTP_EMAIL') or os.environ.get('GMAIL_USER')
password = os.environ.get('SMTP_PASSWORD') or os.environ.get('GMAIL_APP_PASSWORD')

if not user or not password:
    print('Cleanup: no credentials, skipping')
    sys.exit(0)

def decode_mime(value):
    if not value:
        return ''
    parts = decode_header(value)
    result = ''
    for text, charset in parts:
        if isinstance(text, bytes):
            result += text.decode(charset or 'utf-8', 'ignore')
        else:
            result += text
    return result

try:
    M = imaplib.IMAP4_SSL('imap.gmail.com', 993)
    M.login(user, password)
except Exception as e:
    print('Cleanup IMAP login failed:', e)
    sys.exit(0)

M.select('"[Gmail]/Sent Mail"')

typ, data = M.search(None, 'SUBJECT', '"Human-Supercapacitance"')
if typ != 'OK':
    print('Cleanup: search failed')
    M.logout()
    sys.exit(0)

sent_ids = data[0].split()
deleted = 0
kept = 0
cutoff = datetime.now() - timedelta(days=2)

BS = chr(92)  # backslash

for num in sent_ids:
    try:
        typ, msg_data = M.fetch(num, '(RFC822)')
        if typ != 'OK':
            continue

        # --- Archive safety check ---
        # Fetch Gmail labels for this message; if \Sent is missing, it's been archived
        typ_lbl, lbl_data = M.fetch(num, '(X-GM-LABELS)')
        if typ_lbl == 'OK' and lbl_data and lbl_data[0]:
            labels_str = lbl_data[0].decode('utf-8', 'ignore') if isinstance(lbl_data[0], bytes) else str(lbl_data[0])
            if '\\Sent' not in labels_str and 'Sent' not in labels_str:
                # Archived – skip deletion
                kept += 1
                continue
        # ---------------------------

        msg = email.message_from_bytes(msg_data[0][1])
        subject = decode_mime(msg.get('Subject', ''))
        date_str = msg.get('Date', '')
        try:
            msg_date = email.utils.parsedate_to_datetime(date_str).replace(tzinfo=None)
        except Exception:
            msg_date = None

        if msg_date and msg_date > cutoff:
            kept += 1
            continue

        reply_subject = 'Re: ' + subject
        M2 = imaplib.IMAP4_SSL('imap.gmail.com', 993)
        M2.login(user, password)
        M2.select('"[Gmail]/All Mail"')
        typ2, data2 = M2.search(None, 'SUBJECT', '"' + reply_subject + '"')
        M2.logout()

        if typ2 == 'OK' and data2[0].split():
            kept += 1
            continue

        M.store(num, '+FLAGS', BS + 'Deleted')
        deleted += 1
    except Exception as e:
        print('Cleanup error on one email:', e)

M.expunge()
M.logout()

print('Cleanup: deleted ' + str(deleted) + ' unreplied sent emails')
print('Cleanup: kept ' + str(kept) + ' (replied or recent)')