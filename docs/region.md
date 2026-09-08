# Study Area: Pittsburgh — Oakland + Shadyside

bbox (WEST, SOUTH, EAST, NORTH) = (-79.975, 40.435, -79.920, 40.460)

Why this area: diverse road network within a small extent — arterial corridors
(Forbes/Fifth Ave), university campuses (Pitt/CMU) with highly active OSM
editing, residential grids dense with one-way streets, and a hospital zone
with frequent construction. Expected good Mapillary coverage along main
corridors.

## Database
PostGIS in Docker, host port **5433** (5432 is occupied by another Postgres
instance on this machine).
Connection: postgresql://mapagent:mapagent@localhost:5433/mapagent

## Data Sources
- data/pennsylvania-260907.osm.pbf — Geofabrik extract, snapshot 2026-09-07,
  includes version + timestamp metadata
- data/oakland.osm.pbf — study-area extract produced by osmium (1.2 MB)

## Terrain Survey (2026-09-08)
- Road segments (non-null highway): 9,247; named: 1,697
- Segments with maxspeed: 515 (25 mph x402, 35 mph x92, remainder 40–60 mph)
- oneway=yes segments: 610
- Staleness: bulk of edits from 2024–2026 (fresh ground truth); 150+ segments
  last edited before 2018, oldest untouched since 2008 — real signal spread
  for the staleness evidence source
