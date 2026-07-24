import time
from datetime import date

from database.database import initialize_database, save_vehicle
from scraper.jalopy import ALL_MAKES, JalopyScraper

initialize_database()
scraper = JalopyScraper()

total_count = 0
new_count = 0

for make in ALL_MAKES:
    print(f"Checking {make}...")

    try:
        vehicles = scraper.search(make)
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
            yard="Jalopy Jungle",
            date_found=str(date.today())
        )

        if is_new:
            new_count += 1
            print(
                f"  [NEW] {vehicle['year']} {vehicle['make']} "
                f"{vehicle['model']} - Row {vehicle['row']}"
            )

    time.sleep(1)  # wait a bit between checks so we don't hammer their site

print(f"\nDone. Checked {total_count} vehicles, found {new_count} new.")
