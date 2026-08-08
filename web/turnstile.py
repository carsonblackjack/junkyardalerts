import os

import requests

TURNSTILE_SITE_KEY = os.getenv("TURNSTILE_SITE_KEY")
TURNSTILE_SECRET_KEY = os.getenv("TURNSTILE_SECRET_KEY")

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile(token, remote_ip=None):
    """Check a Turnstile response token with Cloudflare. Returns True if
    the visitor passed the bot check, False otherwise."""
    if not token:
        return False

    payload = {"secret": TURNSTILE_SECRET_KEY, "response": token}
    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        response = requests.post(VERIFY_URL, data=payload, timeout=10)
        return response.json().get("success", False)
    except requests.RequestException:
        return False
