import requests
from bs4 import BeautifulSoup

# Every make this yard's website lets you search for. Leaving "model" blank
# when searching returns every model for that make, so looping over this
# list is enough to pull the whole yard's inventory.
ALL_MAKES = [
    "ACURA", "AMC", "AUDI", "BMW", "BUICK", "CADILLAC", "CHEVROLET",
    "CHRYSLER", "DAEWOO", "DATSUN", "DODGE", "FIAT", "FORD", "GEO", "GMC",
    "HONDA", "HYUNDAI", "IBIZA", "INFINITI", "INTERNATIONAL", "ISUZU",
    "JAGUAR", "JEEP", "KIA", "LAND ROVER", "LEXUS", "LINCOLN", "MAZDA",
    "MERCEDES-BENZ", "MERCURY", "MINI", "MITSUBISHI", "NASH", "NISSAN",
    "OLDSMOBILE", "OPEL", "PACKARD", "PEUGEOT", "PLYMOUTH", "PONTIAC",
    "PORSCHE", "RAM", "SAAB", "SATURN", "SCION", "SMART", "STUDEBAKER",
    "SUBARU", "SUZUKI", "TOYOTA", "TRIUMPH", "VOLKSWAGEN", "VOLVO",
]


class JalopyScraper:
    URL = "https://inventory.pickapartjalopyjungle.com/"

    def search(self, make, model=""):
        payload = {
            "YardId": "1020",
            "VehicleMake": make,
            "VehicleModel": model
        }

        response = requests.post(self.URL, data=payload)

        if response.status_code != 200:
            raise Exception(f"Website returned {response.status_code}")

        soup = BeautifulSoup(response.text, "lxml")

        table = soup.find("table")

        vehicles = []

        if not table:
            return vehicles

        rows = table.find_all("tr")[1:]

        for row in rows:
            cols = [c.get_text(strip=True) for c in row.find_all("td")]

            if len(cols) >= 4:
                vehicles.append({
                    "year": cols[0],
                    "make": cols[1],
                    "model": cols[2],
                    "row": cols[3]
                })

        return vehicles
