"""Error injector v0.1 — speed-limit corruption only.

Copies of the map: planet_osm_line = ground truth, osm_corrupted = the map
under test. This script picks target ways, corrupts maxspeed in
osm_corrupted, and records every change in the answer sheet JSON.
Deterministic under a fixed seed.
"""
import json
import random
import psycopg2

SEED = 42
N_SPEED_ERRORS = 20
ANSWER_SHEET = "eval/injected_errors.json"

# Plausible wrong values: what a stale map would realistically say
SPEED_SWAPS = {
    "25 mph": ["35 mph", "30 mph"],
    "35 mph": ["25 mph", "45 mph"],
    "55 mph": ["45 mph", "65 mph"],
}

DSN = "dbname=mapagent user=mapagent password=mapagent host=localhost port=5433"


def main():
    rng = random.Random(SEED)
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()

    # Candidates: drivable roads with a swappable speed value and a name
    # (named roads are easier to sanity-check by eye)
    cur.execute("""
        SELECT osm_id, name, highway, tags->'maxspeed'
        FROM osm_corrupted
        WHERE tags->'maxspeed' = ANY(%s)
          AND highway IN ('primary','secondary','tertiary','residential','trunk')
          AND name IS NOT NULL
        ORDER BY osm_id
    """, (list(SPEED_SWAPS.keys()),))
    candidates = cur.fetchall()
    print(f"eligible candidates: {len(candidates)}")

    targets = rng.sample(candidates, N_SPEED_ERRORS)
    answers = []
    for osm_id, name, highway, true_speed in targets:
        wrong_speed = rng.choice(SPEED_SWAPS[true_speed])
        cur.execute("""
            UPDATE osm_corrupted
            SET tags = tags || hstore('maxspeed', %s)
            WHERE osm_id = %s
        """, (wrong_speed, osm_id))
        answers.append({
            "error_id": f"speed_{len(answers)+1:03d}",
            "error_type": "speed_limit_wrong",
            "osm_id": osm_id,
            "name": name,
            "highway": highway,
            "truth": {"maxspeed": true_speed},
            "corrupted": {"maxspeed": wrong_speed},
        })
        print(f"  {name} ({highway}, way {osm_id}): {true_speed} -> {wrong_speed}")

    conn.commit()
    with open(ANSWER_SHEET, "w") as f:
        json.dump({"seed": SEED, "errors": answers}, f, indent=2)
    print(f"\n{len(answers)} errors injected; answer sheet -> {ANSWER_SHEET}")

    # Self-check: corrupted table must now disagree with ground truth
    cur.execute("""
        SELECT count(*) FROM osm_corrupted c
        JOIN planet_osm_line g USING (osm_id)
        WHERE c.tags->'maxspeed' IS DISTINCT FROM g.tags->'maxspeed'
    """)
    print(f"self-check: {cur.fetchone()[0]} ways now differ from ground truth "
          f"(expect {N_SPEED_ERRORS})")
    conn.close()


if __name__ == "__main__":
    main()
