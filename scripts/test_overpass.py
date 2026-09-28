import json
import urllib.parse
import urllib.request

query = """[out:json][timeout:25];
(
  node["highway"="bus_stop"](around:15000, 6.5244, 3.3792);
  node["amenity"="bus_station"](around:15000, 6.5244, 3.3792);
  node["amenity"="fuel"](around:15000, 6.5244, 3.3792);
  node["amenity"="bank"](around:15000, 6.5244, 3.3792);
  node["amenity"="marketplace"](around:15000, 6.5244, 3.3792);
);
out tags 20;"""

data = urllib.parse.urlencode({"data": query}).encode("utf-8")
headers = {
    "User-Agent": "AfricaPulseDataPlatform/1.0 (contact: student@africanpulse.org)"
}
req = urllib.request.Request("https://overpass-api.de/api/interpreter", data=data, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        for elem in res.get("elements", [])[:5]:
            print(elem)
except Exception as e:
    print("Error:", e)


