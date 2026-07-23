import requests
from bs4 import BeautifulSoup
from datetime import date
from database.database import initialize_database, save_vehicle

URL = "https://inventory.pickapartjalopyjungle.com/"

payload = {
    "YardId": "1020",
    "VehicleMake": "SUBARU",
    "VehicleModel": "B9 TRIBECA"
}

initialize_database()

print("Searching inventory...")

response = requests.post(URL, data=payload)

print(f"Status Code: {response.status_code}")

soup = BeautifulSoup(response.text, "lxml")

table = soup.find("table")

if table:
    print("\nInventory Found:\n")

    rows = table.find_all("tr")[1:]

    for row in rows:
        cols = [c.get_text(strip=True) for c in row.find_all("td")]

        if len(cols) >= 4:
            year = cols[0]
            make = cols[1]
            model = cols[2]
            row_location = cols[3]

            print(
                f"Year: {year} | "
                f"Make: {make} | "
                f"Model: {model} | "
                f"Row: {row_location}"
            )

            save_vehicle(
                year=year,
                make=make,
                model=model,
                row_location=row_location,
                yard="Jalopy Jungle",
                date_found=str(date.today())
            )
else:
    print("No inventory table found.")