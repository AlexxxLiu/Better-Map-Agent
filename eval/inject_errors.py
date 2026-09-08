"""Error injector v0.2 — all five error types.

Two-world model:
  planet_osm_line + reality_overrides = ground truth ("the real world")
  osm_corrupted                       = the stale map under test

Error types:
  speed_limit_wrong  : corrupted has wrong maxspeed          (corrupt the copy)
  oneway_reversed    : corrupted has oneway direction flipped (corrupt the copy)
  road_missing       : road exists in reality, absent from map (delete from copy)
  road_phantom       : map has a road that reality demolished  (mark in overrides)
  closure_unmapped   : road closed in reality, map unaware     (mark in overrides)

Deterministic under SEED. Answer sheet -> eval/injected_errors.json
"""
import json
import random
import psycopg2

SEED = 42
QUOTA = {
    "speed_limit_wrong": 20,
    "oneway_reversed": 10,
    "road_missing": 8,
    "road_phantom": 7,
    "closure_unmapped": 5,
}
ANSWER_SHEET = "eval/injected_errors.json"
SPEED_SWAPS = {
    "25 mph": ["35 mph", "30 mph"],
    "35 mph": ["25 mph", "45 mph"],
    "55 mph": ["45 mph", "65 mph"],
}
DRIVABLE = ('primary', 'secondary', 'tertiary', 'residential', 'trunk')
DSN = "dbname=mapagent user=mapagent password=mapagent host=localhost port=5433"


def rebuild_tables(cur):
    """Fresh start: rebuild corrupted copy and reality overrides."""
    cur.execute("DROP TABLE IF EXISTS osm_corrupted")
    cur.execute("""
        CREATE TABLE osm_corrupted AS
        SELECT osm_id, name, highway, oneway, tags, way
        FROM planet_osm_line WHERE highway IS NOT NULL
    """)
    cur.execute("CREATE INDEX ON osm_corrupted (osm_id)")
    cur.execute("DROP TABLE IF EXISTS reality_overrides")
    cur.execute("""
        CREATE TABLE reality_overrides (
            osm_id BIGINT PRIMARY KEY,
            override_type TEXT NOT NULL
        )
    """)


def pick(cur, sql, params, n, rng):
    cur.execute(sql, params)
    return rng.sample(cur.fetchall(), n)


def main():
    rng = random.Random(SEED)
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    rebuild_tables(cur)
    answers = []
    used_ids = set()

    def record(etype, osm_id, name, highway, truth, corrupted):
        used_ids.add(osm_id)
        answers.append({
            "error_id": f"{etype}_{sum(1 for a in answers if a['error_type']==etype)+1:03d}",
            "error_type": etype, "osm_id": osm_id, "name": name,
            "highway": highway, "truth": truth, "corrupted": corrupted,
        })

    base_filter = """FROM osm_corrupted
        WHERE highway = ANY(%s) AND name IS NOT NULL
          AND NOT (osm_id = ANY(%s))"""
    no_ids = [0]  # placeholder; used_ids grows as we go

    # 1) speed_limit_wrong
    rows = pick(cur, f"""SELECT osm_id, name, highway, tags->'maxspeed'
        {base_filter} AND tags->'maxspeed' = ANY(%s) ORDER BY osm_id""",
        (list(DRIVABLE), list(used_ids) or no_ids, list(SPEED_SWAPS)),
        QUOTA["speed_limit_wrong"], rng)
    for osm_id, name, hw, true_speed in rows:
        wrong = rng.choice(SPEED_SWAPS[true_speed])
        cur.execute("""UPDATE osm_corrupted
            SET tags = tags || hstore('maxspeed', %s) WHERE osm_id=%s""",
            (wrong, osm_id))
        record("speed_limit_wrong", osm_id, name, hw,
               {"maxspeed": true_speed}, {"maxspeed": wrong})

    # 2) oneway_reversed
    rows = pick(cur, f"""SELECT osm_id, name, highway
        {base_filter} AND oneway = 'yes' ORDER BY osm_id""",
        (list(DRIVABLE), list(used_ids) or no_ids),
        QUOTA["oneway_reversed"], rng)
    for osm_id, name, hw in rows:
        cur.execute("UPDATE osm_corrupted SET oneway='-1' WHERE osm_id=%s",
                    (osm_id,))
        record("oneway_reversed", osm_id, name, hw,
               {"oneway": "yes"}, {"oneway": "-1 (reversed)"})

    # 3) road_missing: reality has it, map lost it -> delete from corrupted
    rows = pick(cur, f"""SELECT osm_id, name, highway
        {base_filter} ORDER BY osm_id""",
        (list(DRIVABLE), list(used_ids) or no_ids),
        QUOTA["road_missing"], rng)
    for osm_id, name, hw in rows:
        cur.execute("DELETE FROM osm_corrupted WHERE osm_id=%s", (osm_id,))
        record("road_missing", osm_id, name, hw,
               {"exists": True}, {"exists": False})

    # 4) road_phantom: reality demolished it, map still shows it
    rows = pick(cur, f"""SELECT osm_id, name, highway
        {base_filter} ORDER BY osm_id""",
        (list(DRIVABLE), list(used_ids) or no_ids),
        QUOTA["road_phantom"], rng)
    for osm_id, name, hw in rows:
        cur.execute("""INSERT INTO reality_overrides VALUES (%s,'demolished')""",
                    (osm_id,))
        record("road_phantom", osm_id, name, hw,
               {"exists": False, "note": "demolished in reality"},
               {"exists": True})

    # 5) closure_unmapped: closed in reality, map unaware
    rows = pick(cur, f"""SELECT osm_id, name, highway
        {base_filter} ORDER BY osm_id""",
        (list(DRIVABLE), list(used_ids) or no_ids),
        QUOTA["closure_unmapped"], rng)
    for osm_id, name, hw in rows:
        cur.execute("""INSERT INTO reality_overrides VALUES (%s,'closed')""",
                    (osm_id,))
        record("closure_unmapped", osm_id, name, hw,
               {"status": "closed"}, {"status": "open (unaware)"})

    conn.commit()
    with open(ANSWER_SHEET, "w") as f:
        json.dump({"seed": SEED, "quota": QUOTA, "errors": answers}, f, indent=2)

    # Self-checks
    cur.execute("""SELECT count(*) FROM osm_corrupted c
        JOIN planet_osm_line g USING (osm_id)
        WHERE c.tags->'maxspeed' IS DISTINCT FROM g.tags->'maxspeed'
           OR c.oneway IS DISTINCT FROM g.oneway""")
    tag_diffs = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM reality_overrides")
    overrides = cur.fetchone()[0]
    print(f"answer sheet: {len(answers)} errors -> {ANSWER_SHEET}")
    print(f"self-check: {tag_diffs} tag/oneway diffs "
          f"(expect {QUOTA['speed_limit_wrong'] + QUOTA['oneway_reversed']})")
    print(f"self-check: {overrides} reality overrides "
          f"(expect {QUOTA['road_phantom'] + QUOTA['closure_unmapped']})")
    print(f"self-check: unique osm_ids = {len(used_ids)} (expect 50)")
    conn.close()


if __name__ == "__main__":
    main()
