import time
from datetime import date

from database.database import get_inventory_counts_by_yard, initialize_database, save_vehicle
from notifications.notifier import send_email
from scraper.jalopy import ALL_MAKES as JALOPY_MAKES, JalopyScraper
from scraper.trusty_pap import ALL_MAKES as TRUSTY_MAKES, TrustyPapScraper

# Each yard we check: its name, its scraper, and the list of makes to search.
YARDS = [
    {"name": "Jalopy Jungle", "scraper": JalopyScraper(), "makes": JALOPY_MAKES},
    {"name": "Trusty Pick-A-Part", "scraper": TrustyPapScraper(), "makes": TRUSTY_MAKES},
]

initialize_database()

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
                new_vehicles.append(
                    f"{vehicle['year']} {vehicle['make']} {vehicle['model']} "
                    f"- Row {vehicle['row']} - {yard['name']}"
                )
                print(
                    f"  [NEW] {vehicle['year']} {vehicle['make']} "
                    f"{vehicle['model']} - Row {vehicle['row']}"
                )

        time.sleep(1)  # wait a bit between checks so we don't hammer their site

print(f"\nDone. Checked {total_count} vehicles, found {new_count} new.")

if new_vehicles:
    subject = f"YardWatch: {new_count} new vehicle(s) found"
    body = "\n".join(new_vehicles)
    send_email(subject, body)
    print("Sent email alert.")

# Daily summary, sent every run regardless of whether anything new turned up.
counts_by_yard = get_inventory_counts_by_yard()
summary_lines = [f"{yard}: {count} vehicles" for yard, count in counts_by_yard]
summary_body = (
    f"Checked {total_count} vehicles today, {new_count} new.\n\n"
    "Current inventory:\n" + "\n".join(summary_lines)
)
send_email("YardWatch Daily Summary", summary_body)
print("Sent daily summary email.")
