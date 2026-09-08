"""Patrol agent v0.1 — rule-based baseline with two evidence sources.

Evidence sources:
  1. staleness  : years since the feature was last edited (from OSM metadata)
  2. osmose     : QA issues reported near the feature (Osmose public API)

No LLM yet: a transparent scoring rule turns evidence into proposals.
This run IS the ablation baseline. Proposals are written to the proposals
table AND to a JSON file for the scorer.

Usage: python3 src/run_patrol.py
"""
import json
from datetime import datetime, timezone

import psycopg2
import requests

DSN = "dbname=mapagent user=mapagent password=mapagent host=localhost port=5433"
WEST, SOUTH, EAST, NORTH = -79.960, 40.428, -79.915, 40.462
OUT = "eval/proposals_v01.json"

STALE_YEARS_SUSPECT = 6      # older than this -> suspicious
CONFIDENCE_CUTOFF = 0.5      # below this we don't even propose


def fetch_osmose_issues():
    """One bbox-wide call; returns list of (lat, lon) issue points."""
    r = requests.get(
        "https://osmose.openstreetmap.fr/api/0.3/issues",
        params={"bbox": f"{WEST},{SOUTH},{EAST},{NORTH}", "limit": 500},
        timeout=60,
    )
    r.raise_for_status()
    return [(i["lat"], i["lon"]) for i in r.json().get("issues", [])
            if i.get("lat") and i.get("lon")]


def main():
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    started = datetime.now(timezone.utc)

    # The agent sees ONLY the corrupted map (it must not peek at ground truth)
    cur.execute("""
        SELECT osm_id, name, highway, oneway,
               tags->'maxspeed' AS maxspeed,
               tags->'osm_timestamp' AS ts,
               ST_X(ST_Transform(ST_Centroid(way), 4326)) AS lon,
               ST_Y(ST_Transform(ST_Centroid(way), 4326)) AS lat
        FROM osm_corrupted
        WHERE highway IN ('primary','secondary','tertiary','residential','trunk')
    """)
    features = cur.fetchall()
    print(f"features to check: {len(features)}")

    issues = fetch_osmose_issues()
    print(f"osmose issues fetched: {len(issues)}")

    now = datetime.now(timezone.utc)
    proposals = []
    for osm_id, name, hw, oneway, maxspeed, ts, lon, lat in features:
        evidence = []
        score = 0.0

        # Evidence 1: staleness
        if ts:
            age_y = (now - datetime.fromisoformat(ts.replace("Z", "+00:00"))
                     ).days / 365.25
            if age_y >= STALE_YEARS_SUSPECT:
                score += min(0.5, 0.08 * (age_y - STALE_YEARS_SUSPECT) + 0.3)
                evidence.append({"source": "staleness",
                                 "detail": f"last edited {age_y:.1f}y ago"})

        # Evidence 2: any Osmose issue within ~100m of centroid
        near = [p for p in issues
                if abs(p[0] - lat) < 0.0009 and abs(p[1] - lon) < 0.0012]
        if near:
            score += 0.25
            evidence.append({"source": "osmose",
                             "detail": f"{len(near)} QA issue(s) nearby"})

        if score < CONFIDENCE_CUTOFF or not evidence:
            continue

        # Baseline can only say "something is off here"; it guesses the most
        # common error type for the feature kind. Crude by design.
        if maxspeed:
            ctype, pval = "fix_maxspeed", "unknown"
        elif oneway == 'yes' or oneway == '-1':
            ctype, pval = "fix_oneway", "unknown"
        else:
            ctype, pval = "mark_closed", "unknown"

        proposals.append({
            "osm_id": osm_id, "name": name, "change_type": ctype,
            "proposed_value": pval, "confidence": round(min(score, 0.95), 2),
            "evidence": evidence,
        })
        cur.execute("""
            INSERT INTO proposals (osm_id, change_type, current_value,
                                   proposed_value, confidence, evidence)
            VALUES (%s,%s,%s,%s,%s,%s)
        """, (osm_id, ctype, maxspeed or oneway or "open", pval,
              min(score, 0.95), json.dumps(evidence)))

    cur.execute("""
        INSERT INTO patrol_log (started_at, finished_at, h3_cell,
                                features_checked, api_calls, proposals_created,
                                notes)
        VALUES (%s, now(), 'full-bbox', %s, 1, %s, 'v0.1 rule baseline')
    """, (started, len(features), len(proposals)))
    conn.commit()

    with open(OUT, "w") as f:
        json.dump(proposals, f, indent=2)
    print(f"proposals: {len(proposals)} -> {OUT}")
    conn.close()


if __name__ == "__main__":
    main()
