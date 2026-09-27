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
        final_html = html_body
        if unsubscribe_url:
            unsubscribe_html = (
                f'<p style="margin:20px 40px 0; text-align:center; font-family:Arial,Helvetica,sans-serif; '
                f'font-size:11px; color:#9aa0a8;"><a href="{unsubscribe_url}" style="color:#9aa0a8;">'
                f'Unsubscribe from all YardWatch emails</a></p>'
            )
            final_html = final_html.replace("</body>", unsubscribe_html + "</body>")
        content.append({"type": "text/html", "value": final_html})

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


def _email_shell(heading, body_html, cta_text=None, cta_url=None, cta_note=None, signed=True):
    """Wraps a chunk of body HTML in the shared branded email card: the
    animated header GIF, a heading, whatever content is passed in, an
    optional CTA button, a closing hazard stripe, and a standard
    sign-off. Every YardWatch email is built from this one shell so they
    all look like they came from the same place.

    The CTA button uses a border-bottom accent instead of the site's
    cut-corner clip-path shape - clip-path isn't supported in Gmail (or
    most email clients), so it was silently rendering as a plain
    rectangle there. border-bottom is the same accent idea, but it's
    just a border, which every client renders. Matches the bold,
    full-width, uppercase treatment already used for the site's own
    login/auth buttons, so email and site read as one system."""
    cta_block = ""
    if cta_text and cta_url:
        note_html = (
            f'<p style="margin:12px 0 0; font-family:Arial,Helvetica,sans-serif; font-size:12px; '
            f'color:#9aa0a8;">{cta_note}</p>'
        ) if cta_note else ""
        cta_block = f"""
<tr><td style="padding:4px 40px 4px;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
    <tr><td bgcolor="#b6522a" style="background-color:#b6522a; border-bottom:4px solid #8a3f21;">
      <a href="{cta_url}" style="display:block; padding:16px 20px; font-family:Arial,Helvetica,sans-serif; font-size:14px; font-weight:bold; letter-spacing:0.06em; text-transform:uppercase; color:#ffffff; text-decoration:none; text-align:center;">{cta_text}</a>
    </td></tr>
  </table>
  {note_html}
</td></tr>
"""

    sign_off = ""
    if signed:
        sign_off = """
<p style="margin:20px 0 0; font-family:Arial,Helvetica,sans-serif; font-size:13px; color:#23262a;">
  Carson<br><span style="color:#9aa0a8; font-size:12px;">Founder, YardWatch</span>
</p>
"""

    return f"""\
<!DOCTYPE html>
<html>
<body style="margin:0; padding:0; background-color:#e9e6df;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#e9e6df;">
<tr><td align="center" style="padding:40px 16px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px; background-color:#ffffff;">

<tr><td><img src="{WEBSITE_URL}/static/email-header.gif" width="440" alt="YardWatch" style="display:block; width:100%; max-width:440px; height:auto;"></td></tr>

<tr><td style="padding:34px 40px 6px;">
  <h1 style="margin:0 0 16px; font-family:Arial,Helvetica,sans-serif; font-size:27px; font-weight:bold; letter-spacing:-0.01em; color:#23262a; line-height:1.15;">{heading}</h1>
  {body_html}
</td></tr>
{cta_block}
<tr><td style="padding:26px 40px 28px;">{sign_off}</td></tr>

<tr><td bgcolor="#c99236" style="height:5px; line-height:5px; font-size:0; background-color:#c99236; background-image:repeating-linear-gradient(-45deg, #c99236 0px, #c99236 10px, #23262a 10px, #23262a 20px);">&nbsp;</td></tr>

</table>
</td></tr>
</table>
</body>
</html>
"""


def _vehicle_table_html(vehicles, limit=25):
    """HTML table of vehicles for recently-found/watchlist-match emails,
    with a real column header row (mono, uppercase, letter-spaced) -
    the same treatment the site's own data tables use. Caps the list so
    a big batch doesn't make for a giant email - the full list is
    always in the plain-text version too."""
    header = """
<tr>
  <th align="left" style="padding:0 0 8px; border-bottom:2px solid #23262a; font-family:'Courier New',Courier,monospace; font-size:10px; letter-spacing:0.08em; text-transform:uppercase; color:#6e737b; font-weight:normal;">Vehicle</th>
  <th align="right" style="padding:0 0 8px; border-bottom:2px solid #23262a; font-family:'Courier New',Courier,monospace; font-size:10px; letter-spacing:0.08em; text-transform:uppercase; color:#6e737b; font-weight:normal;">Yard</th>
</tr>
"""
    rows = "".join(f"""
<tr>
  <td style="padding:9px 0; border-bottom:1px solid #e4e0d7; font-family:Arial,Helvetica,sans-serif; font-size:13px; font-weight:bold; color:#23262a;">{v['year']} {v['make']} {v['model']}</td>
  <td style="padding:9px 0; border-bottom:1px solid #e4e0d7; font-family:'Courier New',Courier,monospace; font-size:12px; color:#6e737b; text-align:right;">{v['yard']}</td>
</tr>
""" for v in vehicles[:limit])

    more_note = ""
    if len(vehicles) > limit:
        more_note = (
            f'<p style="margin:10px 0 0; font-family:Arial,Helvetica,sans-serif; font-size:12px; '
            f'color:#9aa0a8;">+ {len(vehicles) - limit} more - see the full list on the site.</p>'
        )

    return f"""\
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:18px 0 0;">
{header}
{rows}
</table>
{more_note}
"""


def render_invite_email_html(code):
    """Beta invite email: exclusive-access framing, the code, and a
    sign-up button."""
    body = f"""\
<p style="margin:0 0 24px; font-family:Arial,Helvetica,sans-serif; font-size:15px; line-height:1.65; color:#4a4f56;">
  YardWatch checks Idaho junkyard inventory several times a day and emails you the moment a car you're after shows up, so you don't have to keep checking yourself. We're opening it to a small group before anyone else gets in.
</p>
<p style="margin:0 0 6px; font-family:'Courier New',Courier,monospace; font-size:11px; letter-spacing:2px; text-transform:uppercase; color:#9aa0a8;">Your Invite Code</p>
<p style="margin:0; font-family:'Courier New',Courier,monospace; font-size:28px; font-weight:bold; letter-spacing:3px; color:#23262a; border-bottom:2px solid #b6522a; display:inline-block; padding-bottom:6px;">{code}</p>
<p style="margin:24px 0 0; font-family:Arial,Helvetica,sans-serif; font-size:14px; line-height:1.65; color:#4a4f56;">
  Thanks for being part of the beta. Your feedback matters more than almost anything else right now - good, bad, or just confusing, I want to hear it.
</p>
"""
    return _email_shell(
        "You're Invited to YardWatch", body,
        "Sign Up", f"{WEBSITE_URL}/register", cta_note="Enter your code above when you register.",
    )


def render_recently_found_html(vehicles):
    """New-inventory alert email: a list of everything new across every
    yard the user is watching."""
    body = f"""\
<p style="margin:0; font-family:Arial,Helvetica,sans-serif; font-size:14px; line-height:1.6; color:#4a4f56;">
  {len(vehicles)} new vehicle{'s' if len(vehicles) != 1 else ''} showed up in the yards you're tracking.
</p>
{_vehicle_table_html(vehicles)}
"""
    return _email_shell(f"{len(vehicles)} New Vehicle{'s' if len(vehicles) != 1 else ''} Found", body, "Browse Inventory", f"{WEBSITE_URL}/dashboard", signed=False)


def render_watchlist_matches_html(vehicles):
    """Watchlist match alert email: only the new vehicles matching this
    user's own watchlist."""
    body = f"""\
<p style="margin:0; font-family:Arial,Helvetica,sans-serif; font-size:14px; line-height:1.6; color:#4a4f56;">
  Something on your watchlist just showed up.
</p>
{_vehicle_table_html(vehicles)}
"""
    return _email_shell(f"{len(vehicles)} Match{'es' if len(vehicles) != 1 else ''} On Your Watchlist", body, "View Your Watchlist", f"{WEBSITE_URL}/dashboard", signed=False)


def render_daily_summary_html(counts_by_yard, total_count, new_count):
    """Daily summary email: today's scrape totals plus current inventory
    counts per yard."""
    rows = "".join(f"""
<tr>
  <td style="padding:7px 0; border-bottom:1px solid #e4e0d7; font-family:Arial,Helvetica,sans-serif; font-size:13px; color:#23262a;">{yard}</td>
  <td style="padding:7px 0; border-bottom:1px solid #e4e0d7; font-family:'Courier New',Courier,monospace; font-size:13px; color:#6e737b; text-align:right;">{count:,}</td>
</tr>
""" for yard, count in counts_by_yard)

    body = f"""\
<p style="margin:0 0 14px; font-family:Arial,Helvetica,sans-serif; font-size:14px; line-height:1.6; color:#4a4f56;">
  Checked {total_count:,} vehicles today, {new_count} new.
</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0">
{rows}
</table>
"""
    return _email_shell("Today's Inventory", body, "Browse Inventory", f"{WEBSITE_URL}/dashboard", signed=False)


def render_password_reset_html(reset_url):
    """Password reset email - no sign-off, since it's a security
    notice, not a personal note."""
    body = """\
<p style="margin:0; font-family:Arial,Helvetica,sans-serif; font-size:14px; line-height:1.65; color:#4a4f56;">
  Someone (hopefully you) asked to reset the password on your YardWatch account. This link works once and expires in an hour. If you didn't request this, you can safely ignore this email.
</p>
"""
    return _email_shell("Reset Your Password", body, "Reset Password", reset_url, signed=False)


def render_feedback_request_html():
    """Weekly digest email for active users: a nudge to leave beta
    feedback."""
    body = """\
<p style="margin:0; font-family:Arial,Helvetica,sans-serif; font-size:14px; line-height:1.65; color:#4a4f56;">
  You've been using YardWatch this past week - got a minute to tell us how it's going? Good, bad, confusing, missing - all of it helps.
</p>
"""
    return _email_shell("How's YardWatch Working For You?", body, "Leave Feedback", f"{WEBSITE_URL}/feedback", signed=False)


def render_win_back_html():
    """Weekly digest email for inactive users: a nudge to come back."""
    body = """\
<p style="margin:0; font-family:Arial,Helvetica,sans-serif; font-size:14px; line-height:1.65; color:#4a4f56;">
  Haven't seen you on YardWatch this past week. Your watchlist is still running in the background, checking every yard for you - log back in to see what's turned up.
</p>
"""
    return _email_shell("Come See What's New", body, "Log Back In", f"{WEBSITE_URL}/login", signed=False)
