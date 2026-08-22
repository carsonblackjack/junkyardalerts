import os

import requests
from dotenv import load_dotenv

load_dotenv()

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM")

SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"
WEBSITE_URL = "https://yard-watch.com"


def send_email(to_email, subject, body, unsubscribe_url=None):
    """Send a plain-text email through SendGrid. Does nothing (just prints
    a warning) if the .env file isn't set up yet, so a missing config
    doesn't crash the whole scrape run."""
    if not SENDGRID_API_KEY or not ALERT_EMAIL_FROM or not to_email:
        print("Email not sent: SENDGRID_API_KEY, ALERT_EMAIL_FROM, or a recipient is missing")
        return

    full_body = f"{body}\n\n---\nCheck it out: {WEBSITE_URL}"
    if unsubscribe_url:
        full_body += f"\nUnsubscribe from all YardWatch emails: {unsubscribe_url}"

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": ALERT_EMAIL_FROM},
        "subject": subject,
        "content": [{"type": "text/plain", "value": full_body}],
        # Otherwise SendGrid rewrites every link into a long tracking
        # redirect URL instead of leaving it as a plain, readable link.
        "tracking_settings": {"click_tracking": {"enable": False}}
    }

    headers = {
        "Authorization": f"Bearer {SENDGRID_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(SENDGRID_URL, json=payload, headers=headers)

    if response.status_code >= 300:
        raise Exception(f"SendGrid returned {response.status_code}: {response.text}")
