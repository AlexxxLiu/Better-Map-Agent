"""Probe Osmose QA API for issues inside the study area."""
import requests

# Study area v3 bbox
WEST, SOUTH, EAST, NORTH = -79.960, 40.428, -79.915, 40.462

r = requests.get(
    "https://osmose.openstreetmap.fr/api/0.3/issues",
    params={"bbox": f"{WEST},{SOUTH},{EAST},{NORTH}", "limit": 500},
    timeout=60,
)
r.raise_for_status()
issues = r.json().get("issues", [])
print(f"Osmose issues in study area: {len(issues)}")
for i in issues[:5]:
    print(f"  item={i.get('item')} class={i.get('class')} "
          f"lat={i.get('lat')} lon={i.get('lon')} title={i.get('title')}")
