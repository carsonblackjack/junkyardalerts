import requests
from bs4 import BeautifulSoup

URL = "https://inventory.pickapartjalopyjungle.com/"

payload = {
	"YardId": "1020",
	"VehicleMake": "SUBARU",
	"VehicleModel": "B9 TRIBECA"
}

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
			print(
				f"Year: {cols[0]} | "
				f"Make: {cols[1]} | "
				f"Model: {cols[2]} | "
				f"Row: {cols[3]}"
			)
else:
	print("No inventory table found.")

