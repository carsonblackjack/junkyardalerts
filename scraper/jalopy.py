import requests
from bs4 import BeautifulSoup


class JalopyScraper:
    URL = "https://inventory.pickapartjalopyjungle.com/"

    def search(self, make, model):
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
