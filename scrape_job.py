import time
from datetime import date, datetime, timedelta, timezone

from database.database import (
    SPOTTED_EXPIRY_DAYS,
    delete_expired_spotted,
    get_inventory_counts_by_yard,
    get_users_for_notifications,
    get_watchlist,
    initialize_database,
    save_vehicle,
    update_yard_sync,
)
from notifications.notifier import (
    WEBSITE_URL,
    render_daily_summary_html,
    render_recently_found_html,
    render_watchlist_matches_html,
    send_email,
)
from scraper.jalopy import ALL_MAKES as JALOPY_MAKES, YARD_LOCATIONS as JALOPY_LOCATIONS, JalopyScraper
from scraper.trusty_pap import ALL_MAKES as TRUSTY_MAKES, TrustyPapScraper


def build_yards():
    """Each yard we check: its name, its scraper, and the list of makes to
    search. Jalopy Jungle has 5 physical locations, so that's one entry
    per location."""
    return [
        {"name": f"Jalopy Jungle {location}", "scraper": JalopyScraper(yard_id), "makes": JALOPY_MAKES}
        for location, yard_id in JALOPY_LOCATIONS.items()
    ] + [
        {"name": "Trusty Pick-A-Part", "scraper": TrustyPapScraper(), "makes": TRUSTY_MAKES},
    ]


def get_yard_names():
    """Every yard the scraper checks, in order - used for the admin
    panel's resync yard picker."""
    return [yard["name"] for yard in build_yards()]


def vehicle_matches_watchlist_item(vehicle, make, model, year_from, year_to):
    """Check a newly found vehicle against one watchlist entry (make
    always, model/year range only if specified)."""
    if vehicle["make"].upper() != make.upper():
        return False
    if model and vehicle["model"].upper() != model.upper():
        return False
    if year_from and vehicle["year"] < year_from:
        return False
    if year_to and vehicle["year"] > year_to:
        return False
    return True


def run_scrape(send_summary=False, yards=None):
    """Check every yard, save what's new, and email each user whatever
    they've opted into. Used by both the scheduled cron job and the admin
    panel's Resync button, so they behave identically - important, since
    a vehicle saved here never counts as "new" again, so skipping the user
    alerts on a manual run would silently lose them.

    Returns a dict of stats about the run, for the admin report email."""
    started = time.time()
    yards = yards if yards is not None else build_yards()

    initialize_database()

    spotted_cutoff = (datetime.now(timezone.utc) - timedelta(days=SPOTTED_EXPIRY_DAYS)).isoformat()
    delete_expired_spotted(spotted_cutoff)

    total_count = 0
    new_count = 0
    skipped_makes = 0
    new_vehicles = []

    for yard in yards:
        print(f"\n=== {yard['name']} ===")

        for make in yard["makes"]:
            print(f"Checking {make}...")

            try:
                vehicles = yard["scraper"].search(make)
            except Exception as e:
                print(f"  Skipped {make}, something went wrong: {e}")
                skipped_makes += 1
                continue

            for vehicle in vehicles:
                total_count += 1

                is_new = save_vehicle(
                    year=vehicle["year"],
                    make=vehicle["make"],
                    model=vehicle["model"],
                    row_location=vehicle["row"],
                    yard=yard["name"],
                    date_found=str(date.today())
                )

                if is_new:
                    new_count += 1
                    new_vehicles.append({
                        "year": vehicle["year"],
                        "make": vehicle["make"],
                        "model": vehicle["model"],
                        "row": vehicle["row"],
                        "yard": yard["name"],
                        "date_found": str(date.today()),
                    })
                    print(
                        f"  [NEW] {vehicle['year']} {vehicle['make']} "
                        f"{vehicle['model']} - Row {vehicle['row']}"
                    )

            time.sleep(1)  # wait a bit between checks so we don't hammer their site

        update_yard_sync(yard["name"], datetime.now(timezone.utc).isoformat())

    print(f"\nDone. Checked {total_count} vehicles, found {new_count} new.")

    new_vehicles.sort(key=lambda v: (v["make"], v["model"], v["year"]))

    # Only send the full daily summary once a day (the scheduled 8am run passes
    # --summary). The other runs during the day still alert on new finds, they
    # just skip this repetitive email.
    if send_summary:
        counts_by_yard = get_inventory_counts_by_yard()
        summary_lines = [f"{yard}: {count} vehicles" for yard, count in counts_by_yard]
        summary_body = (
            f"Checked {total_count} vehicles today, {new_count} new.\n\n"
            "Current inventory:\n" + "\n".join(summary_lines)
        )

    emails_sent = 0

    # Every registered user gets exactly the emails they've opted into, in
    # their own settings - not one broadcast address for everyone.
    for user_id, email, notify_daily_summary, notify_recently_found, notify_watchlist_matches, unsubscribe_token, preferred_yards in get_users_for_notifications():
        unsubscribe_url = f"{WEBSITE_URL}/unsubscribe/{unsubscribe_token}"

        # Blank preferred_yards means "every yard" - only narrow the list
        # down when the user actually picked specific ones.
        yard_filter = set(preferred_yards.split(",")) if preferred_yards else None
        user_vehicles = (
            [v for v in new_vehicles if v["yard"] in yard_filter] if yard_filter else new_vehicles
        )

        if notify_recently_found and user_vehicles:
            lines = [
                f"{v['year']} {v['make']} {v['model']} - Yard: {v['yard']} - Row: {v['row']}"
                for v in user_vehicles
            ]
            send_email(
                email, f"YardWatch: {len(user_vehicles)} new vehicle(s) found", "\n".join(lines), unsubscribe_url,
                html_body=render_recently_found_html(user_vehicles),
            )
            emails_sent += 1
            print(f"Sent 'recently found' email to {email}.")

        if notify_watchlist_matches and user_vehicles:
            watchlist = get_watchlist(user_id)
            personal_matches = [
                v for v in user_vehicles
                if any(
                    vehicle_matches_watchlist_item(v, make, model, year_from, year_to)
                    for _, make, model, year_from, year_to in watchlist
                )
            ]
            if personal_matches:
                lines = [
                    f"{v['year']} {v['make']} {v['model']} - Yard: {v['yard']} "
                    f"- Row: {v['row']} - Found: {date.fromisoformat(v['date_found']).strftime('%m-%d-%Y')}"
                    for v in personal_matches
                ]
                send_email(
                    email,
                    f"YardWatch: {len(personal_matches)} watchlist match(es) found",
                    "\n".join(lines),
                    unsubscribe_url,
                    html_body=render_watchlist_matches_html(personal_matches),
                )
                emails_sent += 1
                print(f"Sent watchlist match email to {email}.")

        if notify_daily_summary and send_summary:
            send_email(
                email, "YardWatch Daily Summary", summary_body, unsubscribe_url,
                html_body=render_daily_summary_html(counts_by_yard, total_count, new_count),
            )
            emails_sent += 1
            print(f"Sent daily summary email to {email}.")

    new_by_yard = {}
    for v in new_vehicles:
        new_by_yard[v["yard"]] = new_by_yard.get(v["yard"], 0) + 1

    return {
        "total_count": total_count,
        "new_count": new_count,
        "skipped_makes": skipped_makes,
        "new_by_yard": new_by_yard,
        "emails_sent": emails_sent,
        "yards_checked": len(yards),
        "yard_names": [yard["name"] for yard in yards],
        "seconds": time.time() - started,
    }
