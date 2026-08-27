import os
from datetime import datetime, timedelta, timezone

import sentry_sdk
from dotenv import load_dotenv

load_dotenv()

SENTRY_DSN = os.getenv("SENTRY_DSN")
if SENTRY_DSN:
    sentry_sdk.init(dsn=SENTRY_DSN, send_default_pii=False)

from database.database import get_active_user_ids_since, get_users_for_notifications, initialize_database
from notifications.notifier import WEBSITE_URL, send_email

initialize_database()

cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
active_user_ids = get_active_user_ids_since(cutoff)

feedback_body = (
    "You've been using YardWatch this past week - got a minute to tell us how it's going? "
    "Good, bad, confusing, missing - all of it helps.\n\n"
    f"{WEBSITE_URL}/feedback"
)

win_back_body = (
    "Haven't seen you on YardWatch this past week. Your watchlist is still running in the "
    "background, checking Jalopy Jungle and Trusty Pick-A-Part for you - log back in to see "
    "what's turned up."
)

sent_feedback_request = 0
sent_win_back = 0

for user_id, email, notify_daily_summary, notify_recently_found, notify_watchlist_matches, unsubscribe_token in get_users_for_notifications():
    if not (notify_daily_summary or notify_recently_found or notify_watchlist_matches):
        continue  # unsubscribed from everything

    unsubscribe_url = f"{WEBSITE_URL}/unsubscribe/{unsubscribe_token}"

    if user_id in active_user_ids:
        send_email(email, "How's YardWatch working for you?", feedback_body, unsubscribe_url)
        sent_feedback_request += 1
    else:
        send_email(email, "We miss you at YardWatch", win_back_body, unsubscribe_url)
        sent_win_back += 1

print(f"Weekly digest sent: {sent_feedback_request} feedback requests, {sent_win_back} win-back emails.")
