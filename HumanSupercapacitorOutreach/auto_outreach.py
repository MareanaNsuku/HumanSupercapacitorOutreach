#!/usr/bin/env python3
import os, sys, time, sqlite3, smtplib, mimetypes, requests, re, random, urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import dotenv_values
from dns import resolver, exception
from bs4 import BeautifulSoup

# ========== CONFIG ==========
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

SENT_DB = 'data/sent_emails.db'
BATCH_SIZE = 50

cfg = dotenv_values('.env')
SMTP_EMAIL = cfg.get('SMTP_EMAIL')
SMTP_PASSWORD = cfg.get('SMTP_PASSWORD')
SMTP_HOST = cfg.get('SMTP_HOST', 'smtp.gmail.com')
SMTP_PORT = int(cfg.get('SMTP_PORT', '587'))

CC_LIST = ['Mandlenkosisindane43@gmail.com']
env_cc = cfg.get('CC_EMAIL', '').strip()
if env_cc and env_cc not in CC_LIST:
    CC_LIST.append(env_cc)

FROM_EMAIL = SMTP_EMAIL

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15',
]

# ========== DATABASE ==========
def init_db():
    os.makedirs('data', exist_ok=True)
    conn = sqlite3.connect(SENT_DB)
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS sent (email TEXT PRIMARY KEY, date TEXT, bounced INTEGER DEFAULT 0)")
    c.execute("CREATE TABLE IF NOT EXISTS scraped_domains (domain TEXT PRIMARY KEY, date TEXT, status TEXT DEFAULT 'sent')")
    conn.commit()
    conn.close()

def already_scraped_domain(domain):
    conn = sqlite3.connect(SENT_DB)
    c = conn.cursor()
    c.execute('SELECT 1 FROM scraped_domains WHERE domain=?', (domain,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def mark_domain_scraped(domain):
    conn = sqlite3.connect(SENT_DB)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO scraped_domains (domain, date, status) VALUES (?, datetime("now"), "sent")', (domain,))
    conn.commit()
    conn.close()

def is_sent_or_bounced(email):
    conn = sqlite3.connect(SENT_DB)
    c = conn.cursor()
    c.execute('SELECT bounced FROM sent WHERE email=?', (email,))
    row = c.fetchone()
    conn.close()
    return row is not None

def mark_sent(email):
    conn = sqlite3.connect(SENT_DB)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO sent (email, date, bounced) VALUES (?, datetime("now"), 0)', (email,))
    conn.commit()
    conn.close()

def mark_bounced(email):
    conn = sqlite3.connect(SENT_DB)
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO sent (email, date, bounced) VALUES (?, datetime("now"), 1)', (email,))
    conn.commit()
    conn.close()

def has_mx(domain):
    try:
        answers = resolver.resolve(domain, 'MX')
        return len(answers) > 0
    except: return False

def mailbox_exists(email, timeout=10):
    try:
        from validate_email_address import validate_email
        return validate_email(email, verify=True, timeout=timeout)
    except ImportError:
        domain = email.split('@')[1]
        try:
            mx_records = resolver.resolve(domain, 'MX')
            mx_host = sorted([(r.preference, str(r.exchange).rstrip('.')) for r in mx_records])[0][1]
        except:
            return False
        try:
            server = smtplib.SMTP(mx_host, 25, timeout=timeout)
            server.helo()
            server.mail('test@example.com')
            code, message = server.rcpt(email)
            server.quit()
            return code == 250 or code == 251
        except:
            return False

# ========== EMAIL SCRAPER ==========
def scrape_emails(url, max_pages=30):
    found = set()
    visited = set()
    to_visit = [url]
    headers = {'User-Agent': random.choice(USER_AGENTS)}
    domain = urllib.parse.urlparse(url).netloc
    while to_visit and len(visited) < max_pages:
        current = to_visit.pop(0)
        if current in visited: continue
        visited.add(current)
        try:
            resp = requests.get(current, headers=headers, timeout=10)
            if resp.status_code != 200: continue
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resp.text)
            found.update(emails)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('/') or domain in href:
                    full = urllib.parse.urljoin(current, href)
                    if domain in full and full not in visited:
                        to_visit.append(full)
        except:
            continue
    return ', '.join(found) if found else ''

# ========== EMAIL SENDER ==========
def send_email(to_addr, company_name):
    subject = 'Powering the Future with Human Motion: The Human-Supercapacitance Project'
    drive_link = cfg.get('GOOGLE_DRIVE_LINK', '#')
    html_body = f"""<html><body>
<p>Dear {company_name},</p>
<p>The project was founded by <strong>Mandlenkosi Sindane</strong>, a Mechanical &amp; Mechatronics Engineering student at the Cape Peninsula University of Technology. I, <strong>Nsuku Mareana</strong>, a Mechanical &amp; Mechatronics Engineering student at the University of Cape Town, am collaborating with him. Together, we have developed the <strong>Human-Supercapacitance Project</strong> – a groundbreaking clean-energy device that turns human pedalling into instant electrical power for the CPUT STEM Club Expo Competition.</p>
<h3>About the Project:</h3>
<p>Our device captures mechanical energy from pedalling – similar to a stationary bike – and converts it instantly into electrical energy stored in supercapacitors. Unlike conventional batteries, supercapacitors charge in seconds, deliver high bursts of power, and last for hundreds of thousands of cycles without degradation. The system uses an AC generator, a rectifier to convert AC to DC, an Arduino microcontroller to manage power flow, and an LCD display to show real‑time energy metrics. A current sensor monitors the electricity flowing from the generator to the supercapacitor bank, ensuring safe and efficient energy transfer.</p>
<h3>Why This Matters:</h3>
<p>In emergency situations (load‑shedding, natural disasters, rural clinics), reliable power is critical. Our charger can be rapidly deployed to power defibrillators, oxygen concentrators, communication devices, LED lights, or charge mobile phones – all without relying on the electrical grid. It also works perfectly in gyms, off‑grid communities, and outdoor settings where human motion is abundant.</p>
<h3>Competition &amp; Vision:</h3>
<p>We are presenting this prototype at the CPUT STEM Club Expo Competition and plan to publish our findings openly to inspire further innovation in human‑powered clean energy. Our goal is to demonstrate a scalable, sustainable alternative to traditional battery banks that reduces e‑waste and provides instant, on‑demand power.</p>
<h3>How You Can Help:</h3>
<p>We are looking for:
<br>- Expert advice on energy‑harvesting gym equipment or human‑powered generators
<br>- Information on supercapacitor integration and mechanical‑electrical conversion
<br>- Potential sponsorship (materials, testing equipment, fabrication support) to finalise the prototype
<br>- Industry connections that could help us test the device in a real‑world environment</p>
<p>The design report is attached.</p>
<p><strong>📁 <a href="{drive_link}">Access All Project Files (presentations, technical slides, poster)</a></strong><br>
Please feel free to download and review the full documentation.</p>
<p>We are available at the following times for a call or meeting:<br>
- Monday: 07:00–08:30 and 10:00–11:00<br>
- Tuesday: 14:00–18:00<br>
- Wednesday: 14:00–18:00<br>
- Thursday: 12:00–14:00<br>
- Friday: 12:00–14:00<br>
- Saturday: 08:00–17:00<br>
- Sunday: 12:00–17:00</p>
<p>Additionally, I will be in <strong>Johannesburg (Randburg)</strong> during the upcoming holidays and would be happy to arrange an in‑person meeting or meetup with any companies or branches in the Johannesburg area.</p>
<p>Additionally, I will be in <strong>Johannesburg (Randburg)</strong> during the upcoming holidays and would be happy to arrange an in‑person meeting or meetup with any companies or branches in the Johannesburg area.</p>
<p>Thank you for supporting student innovation and clean energy.</p>
<p>Warm regards,<br>
<strong>Mandlenkosi Sindane (Project Founder)</strong><br>
Phone: 066 122 6886<br>
LinkedIn: <a href="https://www.linkedin.com/in/mandlenkosi-sindane-4b780530b/">https://www.linkedin.com/in/mandlenkosi-sindane-4b780530b/</a></p>
<p><strong>Nsuku Mareana (Collaborator)</strong><br>
Phone: 068 078 9360<br>
LinkedIn: <a href="https://www.linkedin.com/in/nsukumareana/">https://www.linkedin.com/in/nsukumareana/</a></p>
</body></html>"""

    msg = MIMEMultipart()
    msg['From'] = FROM_EMAIL
    msg['To'] = to_addr
    msg['Cc'] = ', '.join(CC_LIST)
    msg['Subject'] = subject
    msg['X-Priority'] = '1'
    msg['Importance'] = 'High'
    msg['X-No-Archive'] = 'yes'
    msg['X-Unsent'] = '1'
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    # Attach design report
    docx_path = "/Users/nsukumareana/Downloads/Human SuperCapacitance/Human_Supercapacitor_Project_Design_Report.docx"
    if os.path.isfile(docx_path):
        ctype, encoding = mimetypes.guess_type(docx_path)
        if ctype is None or encoding is not None:
            ctype = 'application/octet-stream'
        maintype, subtype = ctype.split('/', 1)
        with open(docx_path, 'rb') as fp:
            part = MIMEBase(maintype, subtype)
            part.set_payload(fp.read())
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(docx_path)}"')
        msg.attach(part)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_EMAIL, SMTP_PASSWORD)
            s.send_message(msg)
        return True, 'sent'
    except smtplib.SMTPRecipientsRefused:
        return False, 'bounce'
    except smtplib.SMTPDataError:
        return False, 'bounce'
    except Exception as e:
        return False, str(e)

# ========== DUCKDUCKGO HTML LIVE SEARCH ==========
def search_duckduckgo(query, max_results=60):
    """Fetch links using the ddgs library (reliable, no blocking)."""
    links = []
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            for r in ddgs.text(query, region='wt-wt', max_results=max_results):
                href = r.get('href', '')
                if href.startswith('http'):
                    links.append(href)
    except Exception as e:
        print(f'   Search error: {e}')
    return links[:max_results]
def search_companies(queries, total_wanted=50):
    found = []
    domains_seen = set()
    excluded = [
        'facebook.com','twitter.com','linkedin.com','instagram.com','youtube.com',
        'google.com','yelp.com','tripadvisor.com','yellowpages.com','bizcommunity.com','cylex.co.za','tuugo.co.za','hotfrog.co.za','africanadvice.com','sayellow.co.za','brabys.co.za','zafroms.co.za','infobel.co.za','southafricaonline.co.za','findit.co.za','sabusiness.co.za','localbusiness.co.za','southafrica.com','travelground.com','sa-venues.com','roomsforafrica.com','property24.com','privateproperty.co.za','autotrader.co.za','cars.co.za','gumtree.co.za','olx.co.za','junkmail.co.za',
        'wikipedia.org','southafrica.info','showme.co.za',
        'yellowpages.co.za','yellowpages.net.za','yellowpages.com',
        'indeed.com','pnet.co.za','careerjet.co.za','adzuna.co.za','recruit.net',
        'careers24.com','zajob.com','jobmail.co.za','bestjobs.co.za','glassdoor.co.za',
        'simplyhired.co.za','jobvine.co.za','myjobmag.co.za','jobspace.co.za',
        'careerjunction.co.za','gumtree.co.za','junkmail.co.za','olx.co.za'
    ]
    for q in queries:
        print(f'🔎 Searching: {q}')
        results = search_duckduckgo(q, max_results=20)
        time.sleep(random.uniform(3, 6))
        for url in results:
            domain = url.split('/')[2].replace('www.', '')
            # ----- ONLY South African domains -----
            if not domain.endswith('.za'):
                continue
            # ----- Exclude educational institutions -----
            if domain.endswith('.ac.za') or domain.endswith('.edu.za') or domain.endswith('.school.za') or domain.endswith('.college.za'):
                continue
            # -----------------------------------------
            if any(ex in domain for ex in excluded):
                continue
            if domain in domains_seen or already_scraped_domain(domain):
                continue
            domains_seen.add(domain)
            company_name = domain.split('.')[0].capitalize()
            found.append((company_name, url))
            if len(found) >= total_wanted:
                break
        if len(found) >= total_wanted:
            break
    print(f'✅ Live search found {len(found)} companies.')
    return found


def main():
    init_db()
    print('🚀 Human Supercapacitance Outreach – live DuckDuckGo HTML scraper…')

    queries = [
        # Gym / fitness – by city
        'gym equipment Cape Town',
        'gym equipment Johannesburg',
        'gym equipment Durban',
        'gym equipment Pretoria',
        'fitness equipment supplier Gauteng',
        'fitness accessories store Western Cape',
        'commercial gym equipment KwaZulu-Natal',
        'exercise bike dealer South Africa',
        'gym machine manufacturer South Africa',
        # Cycling – by city
        'bicycle shop Cape Town',
        'bicycle shop Johannesburg',
        'bicycle shop Durban',
        'cycling equipment supplier South Africa',
        'mountain bike dealer Western Cape',
        # Energy / renewables – by city
        'solar energy company Cape Town',
        'solar energy company Johannesburg',
        'energy storage manufacturer South Africa',
        'battery supplier South Africa',
        'supercapacitor distributor South Africa',
        'off-grid power company Western Cape',
        'generator supplier Gauteng',
        # Mechanical / fitness manufacturing
        'gym treadmill manufacturer South Africa',
        'exercise bike manufacturer South Africa',
        'fitness equipment factory South Africa',
        # Software / fitness tech
        'gym management software South Africa',
        'fitness app developer South Africa',
        'wearable fitness technology South Africa',
        # Electronics / prototyping
        'electronics component supplier South Africa',
        'prototype manufacturer South Africa',
        'mechanical engineering workshop Cape Town',
        'embedded systems developer South Africa',
        # Medical / emergency
        'medical device supplier South Africa',
        'defibrillator distributor South Africa',
        'hospital equipment supplier South Africa',
        # Innovation / co‑working
        'startup incubator South Africa',
        'maker space South Africa',
        'tech hub Cape Town',
        'coworking space South Africa',
        # Additional broad location terms
        'engineering companies Gauteng',
        'energy companies Western Cape',
        'fitness businesses KwaZulu-Natal',
        'electronics manufacturers South Africa',
        'battery dealers South Africa',
        'cycling shops Eastern Cape',
        'renewable energy installers South Africa',
        # Deep‑dig queries (list‑style pages often ignored by Google)
        'list of energy companies in South Africa',
        'top gym equipment suppliers South Africa',
        'best cycling shops South Africa',
        'renewable energy directory South Africa',
        'fitness equipment wholesale South Africa',
    ]
    random.shuffle(queries)

    companies = search_companies(queries, total_wanted=BATCH_SIZE)
    if not companies:
        print('❌ No companies found today. Try again tomorrow.')
        return
    print(f'📊 Processing {len(companies)} companies today.')

    total_sent = 0
    for idx, (company_name, website) in enumerate(companies, 1):
        print(f'\n📌 [{idx}/{len(companies)}] {company_name} ({website})')
        try:
            # Check website alive
            try:
                resp = requests.head(website, headers={'User-Agent': random.choice(USER_AGENTS)}, timeout=10, allow_redirects=True)
                if resp.status_code >= 400:
                    resp = requests.get(website, headers={'User-Agent': random.choice(USER_AGENTS)}, timeout=10)
                    if resp.status_code >= 400:
                        print('   ❌ website unreachable')
                        mark_domain_scraped(website.split('/')[2].replace('www.', ''))
                        continue
            except:
                print('   ❌ website timeout')
                mark_domain_scraped(website.split('/')[2].replace('www.', ''))
                continue


            # Scrape emails
            try:
                emails = scrape_emails(website)
            except Exception as e:
                print(f'   ⚠️ scraping error: {e}')
                continue

            if not emails:
                print('   📭 no emails found')
                mark_domain_scraped(website.split('/')[2].replace('www.', ''))
                continue

            addresses = set()
            for addr in emails.split(','):
                addr = addr.strip()
                if '@' in addr:
                    addresses.add(addr)

            valid = [a for a in addresses if has_mx(a.split('@')[1]) and mailbox_exists(a)]
            new_emails = [e for e in valid if not is_sent_or_bounced(e)]
            print(f'   {len(valid)} valid mailboxes, {len(new_emails)} new')

            for email_addr in new_emails:
                success, status = send_email(email_addr, company_name)
                if success:
                    print(f'   ✅ {email_addr}')
                    mark_sent(email_addr)
                    total_sent += 1
                else:
                    print(f'   ❌ {email_addr}: {status}')
                    if 'bounce' in status:
                        mark_bounced(email_addr)
                time.sleep(random.uniform(4, 8))  # slightly longer pause

            domain = website.split('/')[2].replace('www.', '')
            mark_domain_scraped(domain)

        except Exception as e:
            print(f'   💥 Unexpected error: {e}')
            domain = website.split('/')[2].replace('www.', '')
            mark_domain_scraped(domain)
            continue

    print(f'\n🎉 Done! Sent {total_sent} new emails today.')

if __name__ == '__main__':
    main()
