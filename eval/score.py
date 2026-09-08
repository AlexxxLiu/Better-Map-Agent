"""Scorer: compare agent proposals against the injected-error answer sheet.

A proposal matches an injected error when it targets the same osm_id AND
its change_type maps to the error_type. Partial credit is tracked when the
target is right but the proposed value is wrong.

Usage: python3 eval/score.py <proposals.json>
Proposal format: [{"osm_id": ..., "change_type": ..., "proposed_value": ...}]
"""
import json
import sys
from collections import defaultdict

ANSWER_SHEET = "eval/injected_errors.json"

# proposal change_type -> injected error_type
TYPE_MAP = {
    "fix_maxspeed": "speed_limit_wrong",
    "fix_oneway": "oneway_reversed",
    "add_road": "road_missing",
    "remove_road": "road_phantom",
    "mark_closed": "closure_unmapped",
}


def main(proposals_path):
    answers = json.load(open(ANSWER_SHEET))["errors"]
    by_id = {(a["osm_id"], a["error_type"]): a for a in answers}
    proposals = json.load(open(proposals_path))

    hits, partial, false_pos = [], [], []
    for p in proposals:
        key = (p["osm_id"], TYPE_MAP.get(p["change_type"], "?"))
        a = by_id.get(key)
        if a is None:
            false_pos.append(p)
            continue
        truth_val = list(a["truth"].values())[0]
        if str(p.get("proposed_value")) == str(truth_val):
            hits.append((p, a))
        else:
            partial.append((p, a))

    found_ids = {a["error_id"] for _, a in hits} | {a["error_id"] for _, a in partial}
    missed = [a for a in answers if a["error_id"] not in found_ids]

    n_ans, n_prop = len(answers), len(proposals)
    recall = len(found_ids) / n_ans if n_ans else 0
    precision = (len(hits) + len(partial)) / n_prop if n_prop else 0

    print(f"proposals: {n_prop} | injected errors: {n_ans}")
    print(f"exact hits: {len(hits)} | partial (right target, wrong value): {len(partial)}")
    print(f"false positives: {len(false_pos)} | missed: {len(missed)}")
    print(f"RECALL: {recall:.1%} | PRECISION: {precision:.1%}")

    per_type = defaultdict(lambda: [0, 0])
    for a in answers:
        per_type[a["error_type"]][1] += 1
    counted = set()
    for _, a in hits + partial:
        if a["error_id"] not in counted:
            counted.add(a["error_id"])
            per_type[a["error_type"]][0] += 1
    print("\nby error type (found/total):")
    for t, (f, tot) in sorted(per_type.items()):
        print(f"  {t:<20} {f}/{tot}")


if __name__ == "__main__":
    main(sys.argv[1])
