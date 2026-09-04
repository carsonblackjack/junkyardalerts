import os

import requests
from dotenv import load_dotenv

load_dotenv()

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
ALERT_EMAIL_FROM = os.getenv("ALERT_EMAIL_FROM")
ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO")

SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"
WEBSITE_URL = "https://yard-watch.com"


def send_email(to_email, subject, body, unsubscribe_url=None, include_link_footer=True, html_body=None):
    """Send an email through SendGrid - plain text only, or plain text
    plus a styled HTML version (html_body) for emails worth dressing up.
    Does nothing (just prints a warning) if the .env file isn't set up
    yet, so a missing config doesn't crash the whole scrape run."""
    if not SENDGRID_API_KEY or not ALERT_EMAIL_FROM or not to_email:
        print("Email not sent: SENDGRID_API_KEY, ALERT_EMAIL_FROM, or a recipient is missing")
        return

    full_body = body
    if include_link_footer:
        full_body += f"\n\n---\nCheck it out: {WEBSITE_URL}"
    if unsubscribe_url:
        full_body += f"\nUnsubscribe from all YardWatch emails: {unsubscribe_url}"

    content = [{"type": "text/plain", "value": full_body}]
    if html_body:
        content.append({"type": "text/html", "value": html_body})

    payload = {
        "personalizations": [{"to": [{"email": to_email}]}],
        "from": {"email": ALERT_EMAIL_FROM},
        "subject": subject,
        "content": content,
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


def render_invite_email_html(code):
    """Build the styled HTML version of the beta invite email, in
    YardWatch's brand colors. Table-based layout with inline styles and
    websafe font fallbacks throughout - email clients (especially
    Outlook) don't reliably support the CSS a normal webpage can use."""
    register_url = f"{WEBSITE_URL}/register"

    return f"""\
<!DOCTYPE html>
<html>
<body style="margin:0; padding:0; background-color:#e9e6df;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#e9e6df;">
<tr><td align="center" style="padding:48px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px; background-color:#ffffff;">

<tr><td bgcolor="#b6522a" style="height:4px; line-height:4px; font-size:0; background-color:#b6522a;">&nbsp;</td></tr>

<tr><td style="padding:40px 40px 0;">
  <p style="margin:0 0 26px; font-family:Arial,Helvetica,sans-serif; font-size:22px; font-weight:bold; letter-spacing:0.5px; color:#23262a;">YARD<span style="color:#b6522a;">WATCH</span></p>

  <p style="margin:0 0 10px; font-family:'Courier New',Courier,monospace; font-size:11px; letter-spacing:2px; text-transform:uppercase; color:#9aa0a8;">Exclusive Beta</p>
  <h1 style="margin:0 0 20px; font-family:Arial,Helvetica,sans-serif; font-size:26px; font-weight:bold; color:#23262a; line-height:1.25;">You're invited to YardWatch.</h1>

  <p style="margin:0 0 28px; font-family:Arial,Helvetica,sans-serif; font-size:15px; line-height:1.65; color:#4a4f56;">
    YardWatch checks Idaho junkyard inventory several times a day and emails you the moment a car you're after shows up, so you don't have to keep checking yourself. We're opening it to a small group before anyone else gets in.
  </p>
</td></tr>

<tr><td style="padding:0 40px 30px;">
  <p style="margin:0 0 6px; font-family:'Courier New',Courier,monospace; font-size:11px; letter-spacing:2px; text-transform:uppercase; color:#9aa0a8;">Your Invite Code</p>
  <p style="margin:0 0 10px; font-family:'Courier New',Courier,monospace; font-size:28px; font-weight:bold; letter-spacing:3px; color:#23262a; border-bottom:2px solid #b6522a; display:inline-block; padding-bottom:6px;">{code}</p>
</td></tr>

<tr><td style="padding:0 40px 36px;">
  <table role="presentation" cellpadding="0" cellspacing="0">
    <tr><td bgcolor="#b6522a" style="background-color:#b6522a; clip-path:polygon(0 0, calc(100% - 12px) 0, 100% 12px, 100% 100%, 0 100%);">
      <a href="{register_url}" style="display:inline-block; padding:14px 40px 14px 30px; font-family:Arial,Helvetica,sans-serif; font-size:14px; font-weight:bold; color:#ffffff; text-decoration:none;">Sign Up</a>
    </td></tr>
  </table>
  <p style="margin:14px 0 0; font-family:Arial,Helvetica,sans-serif; font-size:12px; color:#9aa0a8;">Enter your code above when you register.</p>
</td></tr>

<tr><td style="padding:26px 40px 40px; border-top:1px solid #e4e0d7;">
  <p style="margin:0; font-family:Arial,Helvetica,sans-serif; font-size:14px; line-height:1.65; color:#4a4f56;">
    Thanks for being part of the beta. Your feedback matters more than almost anything else right now - good, bad, or just confusing, I want to hear it.
  </p>
  <p style="margin:16px 0 0; font-family:Arial,Helvetica,sans-serif; font-size:14px; color:#23262a;">
    Carson<br><span style="color:#9aa0a8; font-size:13px;">Founder, YardWatch</span>
  </p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>
"""
