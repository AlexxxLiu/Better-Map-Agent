import os
import time
import requests
from datetime import datetime, timedelta

TOKEN = os.environ["MAPILLARY_TOKEN"]

# Candidate study area v2: shifted east to Shadyside / Squirrel Hill N / East Liberty
SOUTH, WEST = 40.435, -79.950
NORTH, EAST = 40.465, -79.895

now = datetime.now()
cut3_ms = int((now - timedelta(days=3 * 365)).timestamp() * 1000)
cut5_ms = int((now - timedelta(days=5 * 365)).timestamp() * 1000)

rows, cols = 4, 5
points = []
for i in range(rows):
    for j in range(cols):
        lat = SOUTH + (NORTH - SOUTH) * (i + 0.5) / rows
        lon = WEST + (EAST - WEST) * (j + 0.5) / cols
        points.append((lat, lon))

DLAT, DLON = 0.0009, 0.0012

cov3 = cov5 = 0
print(f"{'#':>3} {'lat':>9} {'lon':>10} {'total':>6} {'<=3y':>5} {'<=5y':>5}")
for idx, (lat, lon) in enumerate(points, 1):
    bbox = f"{lon-DLON},{lat-DLAT},{lon+DLON},{lat+DLAT}"
    r = requests.get(
        "https://graph.mapillary.com/images",
        params={"access_token": TOKEN, "fields": "id,captured_at",
                "bbox": bbox, "limit": 100},
        timeout=30,
    )
    r.raise_for_status()
    imgs = r.json().get("data", [])
    n3 = sum(1 for im in imgs if im.get("captured_at", 0) >= cut3_ms)
    n5 = sum(1 for im in imgs if im.get("captured_at", 0) >= cut5_ms)
    cov3 += 1 if n3 else 0
    cov5 += 1 if n5 else 0
    print(f"{idx:>3} {lat:>9.4f} {lon:>10.4f} {len(imgs):>6} {n3:>5} {n5:>5}")
    time.sleep(1)

print(f"\nCoverage: {cov3}/20 points with <=3y imagery, {cov5}/20 with <=5y")
if cov3 >= 14:
    print("Verdict: PASS on 3-year window - lock in this bbox")
elif cov5 >= 14:
    print("Verdict: PASS on relaxed 5-year window - lock in bbox, document the relaxation")
else:
    print("Verdict: FAIL - report back for next move")
