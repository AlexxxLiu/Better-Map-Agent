"""Scan greater Pittsburgh for recent Mapillary coverage using small sample
windows at grid-cell centers (large bboxes overload the API)."""
import os
import time
import requests
from datetime import datetime, timedelta

TOKEN = os.environ["MAPILLARY_TOKEN"]

SOUTH, WEST = 40.380, -80.060
NORTH, EAST = 40.500, -79.860
ROWS, COLS = 10, 10

cut3_ms = int((datetime.now() - timedelta(days=3 * 365)).timestamp() * 1000)
dlat_cell = (NORTH - SOUTH) / ROWS
dlon_cell = (EAST - WEST) / COLS
DLAT, DLON = 0.0014, 0.0018  # ~150m sample half-window at cell center

def query(bbox, tries=3):
    for t in range(tries):
        try:
            r = requests.get(
                "https://graph.mapillary.com/images",
                params={"access_token": TOKEN, "fields": "id,captured_at",
                        "bbox": bbox, "limit": 100},
                timeout=30,
            )
            if r.status_code == 200:
                return r.json().get("data", [])
            print(f"    HTTP {r.status_code}: {r.text[:120]}")
            time.sleep(3 * (t + 1))  # back off, esp. for rate limits
        except Exception as e:
            print(f"    EXC: {e}")
            time.sleep(3)
    return None

grid = [[0] * COLS for _ in range(ROWS)]
results = []
for i in range(ROWS):
    for j in range(COLS):
        lat = SOUTH + (i + 0.5) * dlat_cell
        lon = WEST + (j + 0.5) * dlon_cell
        bbox = f"{lon-DLON},{lat-DLAT},{lon+DLON},{lat+DLAT}"
        imgs = query(bbox)
        n3 = -1 if imgs is None else sum(
            1 for im in imgs if im.get("captured_at", 0) >= cut3_ms)
        grid[i][j] = n3
        results.append((n3, lat, lon))
        time.sleep(1)
    print(f"row {i + 1}/{ROWS} done")

print("\nRecent-imagery heatmap (<=3y image count at cell-center sample):")
print("N")
for i in range(ROWS - 1, -1, -1):
    print(" ".join(f"{v:>4}" if v >= 0 else " ERR" for v in grid[i]))
print("S   (W -> E)")

results.sort(reverse=True)
print("\nTop 10 cells (recent_count, center_lat, center_lon):")
for n3, lat, lon in results[:10]:
    print(f"  {n3:>4}  {lat:.4f}  {lon:.4f}")
