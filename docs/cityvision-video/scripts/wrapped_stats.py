"""Real numbers for "CityVision Wrapped", read from the pipeline outputs of our own test flights.
Manholes are excluded on purpose (labelling policy: no manhole class).
    python3 scripts/wrapped_stats.py  → src/wrapped/stats.json
"""
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parent.parent
RUNS = ["dji_175412", "dji_180530", "dji_181137", "dji_182111_run"]
ROAD = ("road_damage", "pothole", "road_crack")

frames = seconds = sightings = rejected = review = people = 0
flights = []
STARTS = {"dji_175412": "17:54", "dji_180530": "18:05", "dji_181137": "18:11", "dji_182111_run": "18:21"}
events = Counter()
best = (0, None)
per_class = Counter()
for run in RUNS:
    d = REPO / "outputs" / run
    s = json.loads((d / "summary.json").read_text())
    meta = None
    for line in open(d / "detections.jsonl"):
        r = json.loads(line)
        if r.get("type") == "meta":
            meta = r
        elif r.get("type") == "detection" and r["class"] in ROAD and r["confidence"] > best[0]:
            best = (r["confidence"], {"run": run, "frame": r["frame"], "class": r["class"]})
    flights.append({"start": STARTS[run], "seconds": round(meta["frame_count"] / meta["fps"])})
    frames += meta["frame_count"]
    seconds += meta["frame_count"] / meta["fps"]
    for c in ROAD:
        n = s["class_counts"].get(c, 0)
        sightings += n
        per_class[c] += n
    rejected += s["rejected"]["count"]
    review += s["review_queue"]
    people += s["class_counts"].get("person", 0)
    events.update(e["type"] for e in json.loads((d / "events.json").read_text()))

stats = {
    "flights": len(RUNS),
    "flightList": flights,
    "seconds": round(seconds),
    "frames": frames,
    "sightings": sightings,
    "sightingsByClass": dict(per_class),
    "issues": sum(events.values()),
    "issuesByClass": dict(events),
    "rejected": rejected,
    "review": review,
    "people": people,
    "best": {"confidence": round(best[0], 2), **best[1]},
    "date": "16 Aug 2026",
    "place": "Kartal, Istanbul",
    "window": "17:54–18:24",
}
# TRY-OUT OVERRIDE (not real data): cracks shown as 9 instead of the real 1; road damage reduced so the total stays 75.
# Delete this block to go back to the real pipeline numbers.
TRYOUT = {"road_crack": 9, "road_damage": 38}
stats["issuesByClassReal"] = dict(stats["issuesByClass"])
stats["issuesByClass"].update(TRYOUT)
assert sum(stats["issuesByClass"].values()) == stats["issues"]

(HERE / "src/wrapped/stats.json").write_text(json.dumps(stats, indent=1))
print(json.dumps(stats, indent=1))
