import threading
from datetime import datetime, timezone

import sentry_sdk

from notifications.notifier import render_resync_report_html, send_email
from scrape_job import build_yards, run_scrape

# A full scrape takes minutes (it pauses between every make so it doesn't
# hammer the yards' sites), far longer than a web request is allowed to
# run, so the admin button kicks it off in a background thread and the
# result arrives by email. The lock keeps it to one resync at a time.
_lock = threading.Lock()
_state = {"started_at": None, "started_by": None, "scope": None}


def get_resync_status():
    """Return (running, started_at_iso, started_by_email, scope) where
    scope is a yard name or "all yards"."""
    if not _lock.locked():
        return False, None, None, None
    return True, _state["started_at"], _state["started_by"], _state["scope"]


def start_resync(admin_email, yard_name=None):
    """Start a resync in the background - of one yard if yard_name is
    given, otherwise every yard. Returns False if one is already running
    (or the yard name isn't one we check), True if it was started."""
    yards = None
    if yard_name:
        yards = [yard for yard in build_yards() if yard["name"] == yard_name]
        if not yards:
            return False

    if not _lock.acquire(blocking=False):
        return False

    _state["started_at"] = datetime.now(timezone.utc).isoformat()
    _state["started_by"] = admin_email
    _state["scope"] = yard_name or "all yards"

    threading.Thread(target=_run, args=(admin_email, yards, yard_name or "all yards"), daemon=True).start()
    return True


def _run(admin_email, yards, scope):
    try:
        stats = run_scrape(yards=yards)
        body = (
            f"Resync of {scope} finished. Checked {stats['total_count']:,} vehicles "
            f"in {stats['seconds'] / 60:.1f} minutes. {stats['new_count']:,} new, "
            f"{stats['emails_sent']} alert email(s) sent to users."
        )
        if stats["skipped_makes"]:
            body += f"\n{stats['skipped_makes']} make search(es) failed and were skipped - worth checking the logs."
        send_email(
            admin_email, f"YardWatch resync complete: {scope}", body,
            include_link_footer=False, html_body=render_resync_report_html(stats),
        )
    except Exception as e:
        sentry_sdk.capture_exception(e)
        send_email(
            admin_email, f"YardWatch resync failed: {scope}",
            f"The resync of {scope} stopped with an error:\n\n{e}", include_link_footer=False,
        )
    finally:
        _lock.release()
