# Study Area (v3, FINAL): Pittsburgh — Oakland corridor + east

bbox (WEST, SOUTH, EAST, NORTH) = (-79.960, 40.428, -79.915, 40.462)

Selection was data-driven: two rounds of Mapillary coverage probing showed
recent (<=3y) imagery concentrates along the Fifth/Forbes corridor in
central-east Oakland; the bbox was shifted to capture all confirmed hotspots
while keeping CMU/Pitt campuses, the hospital zone, and one-way-dense
residential grids. Street-view coverage is corridor-shaped, which is treated
as a normal branch: speed-limit errors will preferentially be injected on
segments with imagery.

## Database
PostGIS in Docker, host port 5433 (5432 occupied by another local Postgres).
Connection: postgresql://mapagent:mapagent@localhost:5433/mapagent

## Terrain Survey (2026-09-08, v3)
- Road segments (non-null highway): 9,461; named: 1,680
- maxspeed segments: 597 (25mph x485, 35mph x73, 55mph x32, others minor)
- oneway=yes segments: 587
- Staleness: bulk 2024-2026; 180+ segments last edited pre-2018 (oldest 2008)
- 23 segments tagged highway=construction (live roadwork inside study area)

## Roadwork Announcement Sources
- Primary (study-area coverage): PennDOT RCRS via 511PA — application pending
- WZDx format dev: PA Turnpike feed (key requested; no study-area coverage)
- USDOT WZ Archive: empty for our needs; will self-archive RCRS snapshots
