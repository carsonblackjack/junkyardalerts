import sys
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
)
from notifications.notifier import send_email
from scraper.jalopy import ALL_MAKES as JALOPY_MAKES, YARD_LOCATIONS as JALOPY_LOCATIONS, JalopyScraper
from scraper.trusty_pap import ALL_MAKES as TRUSTY_MAKES, TrustyPapScraper

# Each yard we check: its name, its scraper, and the list of makes to search.
# Jalopy Jungle has 5 physical locations, so that's one entry per location.
YARDS = [
    {"name": f"Jalopy Jungle {location}", "scraper": JalopyScraper(yard_id), "makes": JALOPY_MAKES}
    for location, yard_id in JALOPY_LOCATIONS.items()
] + [
    {"name": "Trusty Pick-A-Part", "scraper": TrustyPapScraper(), "makes": TRUSTY_MAKES},
]


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


initialize_database()

spotted_cutoff = (datetime.now(timezone.utc) - timedelta(days=SPOTTED_EXPIRY_DAYS)).isoformat()
delete_expired_spotted(spotted_cutoff)

total_count = 0
new_count = 0
new_vehicles = []

for yard in YARDS:
    print(f"\n=== {yard['name']} ===")

    for make in yard["makes"]:
        print(f"Checking {make}...")

        try:
            vehicles = yard["scraper"].search(make)
        except Exception as e:
            print(f"  Skipped {make}, something went wrong: {e}")
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

print(f"\nDone. Checked {total_count} vehicles, found {new_count} new.")

new_vehicles.sort(key=lambda v: (v["make"], v["model"], v["year"]))
recently_found_lines = [
    f"{v['year']} {v['make']} {v['model']} - Yard: {v['yard']} - Row: {v['row']}"
    for v in new_vehicles
]
recently_found_subject = f"YardWatch: {new_count} new vehicle(s) found"

# Only send the full daily summary once a day (the scheduled 8am run passes
# --summary). The other runs during the day still alert on new finds, they
# just skip this repetitive email.
send_summary = "--summary" in sys.argv
if send_summary:
    counts_by_yard = get_inventory_counts_by_yard()
    summary_lines = [f"{yard}: {count} vehicles" for yard, count in counts_by_yard]
    summary_body = (
        f"Checked {total_count} vehicles today, {new_count} new.\n\n"
        "Current inventory:\n" + "\n".join(summary_lines)
    )

# Every registered user gets exactly the emails they've opted into, in
# their own settings - not one broadcast address for everyone.
for user_id, email, notify_daily_summary, notify_recently_found, notify_watchlist_matches in get_users_for_notifications():
    if notify_recently_found and new_vehicles:
        send_email(email, recently_found_subject, "\n".join(recently_found_lines))
        print(f"Sent 'recently found' email to {email}.")

    if notify_watchlist_matches and new_vehicles:
        watchlist = get_watchlist(user_id)
        personal_matches = [
            v for v in new_vehicles
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
                "\n".join(lines)
            )
            print(f"Sent watchlist match email to {email}.")

    if notify_daily_summary and send_summary:
        send_email(email, "YardWatch Daily Summary", summary_body)
        print(f"Sent daily summary email to {email}.")
