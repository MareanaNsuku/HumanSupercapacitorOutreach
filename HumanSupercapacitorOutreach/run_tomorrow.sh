#!/bin/bash
cd ~/Desktop/HumanSupercapacitorOutreach
source venv/bin/activate

echo "🚀 [1/2] Running daily outreach batch (max 30 emails)…"
python auto_outreach.py

echo ""
echo "📨 [2/2] Sending Google Drive link to any recent contacts who haven't received it yet…"
python -c "
import os, sqlite3, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import dotenv_values
from datetime import datetime, timedelta

cfg = dotenv_values('.env')
SMTP_EMAIL = cfg.get('SMTP_EMAIL')
SMTP_PASSWORD = cfg.get('SMTP_PASSWORD')
SMTP_HOST = cfg.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(cfg.get('SMTP_PORT', '587'))
DRIVE_LINK = cfg.get('GOOGLE_DRIVE_LINK', '#')
CC_LIST = ['Mandlenkosisindane43@gmail.com']
FROM_EMAIL = SMTP_EMAIL

DB_PATH = 'data/sent_emails.db'
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()
c.execute(\"CREATE TABLE IF NOT EXISTS follow_up_sent (email TEXT PRIMARY KEY, date TEXT)\")
two_days_ago = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')
c.execute(\"\"\"
    SELECT s.email FROM sent s
    WHERE s.date >= ? AND s.bounced = 0
      AND s.email NOT IN (SELECT f.email FROM follow_up_sent f)
\"\"\", (two_days_ago,))
recipients = [row[0] for row in c.fetchall()]
if not recipients:
    print('✅ All recent contacts already received the folder link.')
    conn.close()
    exit()
print(f'Found {len(recipients)} contacts to follow up.')
subject = 'Access to the Human-Supercapacitance Project Files'
html_body = f'''<html><body>
<p>Hello,</p>
<p>I recently shared our Human-Supercapacitance Project with you, and I wanted to make sure you have easy access to all the project resources.</p>
<p><strong>📁 <a href="{DRIVE_LINK}">Access All Project Files (presentations, design report, technical slides)</a></strong></p>
<p>If you have any questions or would like to discuss the project further, please feel free to reach out.</p>
<p>Warm regards,<br>
Mandlenkosi Sindane (Project Founder)<br>
Phone: 066 122 6886<br>
Nsuku Mareana (Collaborator)<br>
Phone: 068 078 9360</p>
</body></html>'''
sent = 0
for to_addr in recipients:
    msg = MIMEMultipart()
    msg['From'] = FROM_EMAIL
    msg['To'] = to_addr
    msg['Cc'] = ', '.join(CC_LIST)
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_EMAIL, SMTP_PASSWORD)
            s.send_message(msg)
        c.execute(\"INSERT OR IGNORE INTO follow_up_sent (email, date) VALUES (?, datetime('now'))\", (to_addr,))
        conn.commit()
        sent += 1
        print(f'✅ {to_addr}')
    except smtplib.SMTPDataError as e:
        if '5.4.5' in str(e):
            print(f'⛔ Daily limit reached. {len(recipients)-sent} remaining will be retried next time.')
            break
        else:
            print(f'❌ {to_addr}: {e}')
            c.execute(\"INSERT OR IGNORE INTO follow_up_sent (email, date) VALUES (?, datetime('now'))\", (to_addr,))
    except Exception as e:
        print(f'❌ {to_addr}: {e}')
conn.close()
print(f'Follow-up sent to {sent} contacts.')
"
echo ""
echo "✅ All tasks completed."
