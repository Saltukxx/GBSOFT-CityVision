"""Kartal (Istanbul) map in an Apple-Maps-like style, from OpenStreetMap data.

Input : public/maps/kartal.json  (Overpass export, © OpenStreetMap contributors, ODbL)
Output: public/maps/kartal-light.svg, kartal-navy.svg  (baked to PNG by scripts/bake-maps.mjs)
        src/howto/map.json  — real street routes (shortest paths on the OSM road graph),
                              pins and their real coordinates, all in map pixels.
    python3 scripts/howto_map.py
"""
import heapq
import json
import math
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = json.loads((ROOT / "public/maps/kartal.json").read_text())

LON0, LON1, LAT0, LAT1 = 29.172, 29.196, 40.879, 40.897
W = 3000
H = round(W * (LAT1 - LAT0) * 111195 / ((LON1 - LON0) * 111195 * math.cos(math.radians(40.888))))


def px(lat, lon):
    return ((lon - LON0) / (LON1 - LON0) * W, (LAT1 - lat) / (LAT1 - LAT0) * H)


def unpx(x, y):
    return LAT1 - y / H * (LAT1 - LAT0), LON0 + x / W * (LON1 - LON0)


STYLE = {
    "light": {
        "land": "#F3F1EC", "building": "#E4E0D8", "bstroke": "#D6D0C5", "park": "#CFE8C1", "water": "#A9D3F1",
        "label": "#6B6760", "halo": "#F7F6F2", "sea_label": "#5E99C9",
        "roads": {  # class: (width, fill, casing)
            "trunk": (30, "#FFD27F", "#E2AC4E"), "primary": (24, "#FFE6A6", "#E3C47C"),
            "secondary": (20, "#FFFFFF", "#D3CDC2"), "tertiary": (17, "#FFFFFF", "#D3CDC2"),
            "residential": (12, "#FFFFFF", "#D9D4CA"), "minor": (8, "#FFFFFF", "#DDD8CF"),
        },
    },
    "navy": {
        "land": "#10244F", "building": "#16295B", "bstroke": "#1C3268", "park": "#123B52", "water": "#091733",
        "label": "#8EA4D6", "halo": "#10244F", "sea_label": "#3D5D9C",
        "roads": {
            "trunk": (30, "#4566B5", "#2D4A8E"), "primary": (24, "#3A5AA3", "#284282"),
            "secondary": (20, "#2C4886", "#22396F"), "tertiary": (17, "#2A4581", "#21386C"),
            "residential": (12, "#233D76", "#1C3366"), "minor": (8, "#203970", "#1B3163"),
        },
    },
}
ROAD_CLASS = {
    "motorway": "trunk", "trunk": "trunk", "trunk_link": "primary", "primary": "primary", "primary_link": "primary",
    "secondary": "secondary", "secondary_link": "secondary", "tertiary": "tertiary", "tertiary_link": "tertiary",
    "residential": "residential", "unclassified": "residential", "living_street": "minor", "service": "minor",
}
DRAW_ORDER = ["minor", "residential", "tertiary", "secondary", "primary", "trunk"]

roads, buildings, parks, coast = [], [], [], []
for e in D["elements"]:
    t, g = e.get("tags", {}), e.get("geometry")
    if not g:
        continue
    pts = [px(p["lat"], p["lon"]) for p in g]
    if "highway" in t and t["highway"] in ROAD_CLASS:
        roads.append((ROAD_CLASS[t["highway"]], pts, t.get("name"), [(p["lat"], p["lon"]) for p in g]))
    elif "building" in t:
        buildings.append(pts)
    elif t.get("leisure") in ("park", "garden", "pitch", "playground") or t.get("landuse") in (
        "grass", "park", "forest", "recreation_ground", "cemetery") or t.get("natural") == "wood":
        parks.append(pts)
    elif t.get("natural") == "coastline":
        coast.append(pts)


def path_d(pts, close=False):
    s = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return s + (" Z" if close else "")


# sea: coastline runs NW → SE with the water on its right (south); close it below the map
sea = []
for c in coast:
    sea.append(path_d(c + [(c[-1][0] + 400, H + 600), (c[0][0] - 400, H + 600)], close=True))

# ── road graph (for real-street routes) ──
graph = defaultdict(list)
node_xy = {}
for cls, pts, name, ll in roads:
    if cls == "minor":
        continue
    for (a, b) in zip(pts, pts[1:]):
        ka, kb = (round(a[0], 1), round(a[1], 1)), (round(b[0], 1), round(b[1], 1))
        node_xy[ka], node_xy[kb] = a, b
        d = math.hypot(a[0] - b[0], a[1] - b[1])
        graph[ka].append((kb, d))
        graph[kb].append((ka, d))


def nearest(x, y):
    return min(node_xy, key=lambda k: (k[0] - x) ** 2 + (k[1] - y) ** 2)


def route(a, b):
    s, t = nearest(*a), nearest(*b)
    dist, prev, pq = {s: 0}, {}, [(0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == t:
            break
        if d > dist[u]:
            continue
        for v, w in graph[u]:
            nd = d + w
            if nd < dist.get(v, 1e18):
                dist[v], prev[v] = nd, u
                heapq.heappush(pq, (nd, v))
    out, u = [t], t
    while u != s:
        u = prev[u]
        out.append(u)
    out = [node_xy[k] for k in reversed(out)]
    # drop near-duplicate points
    clean = [out[0]]
    for p in out[1:]:
        if math.hypot(p[0] - clean[-1][0], p[1] - clean[-1][1]) > 3:
            clean.append(p)
    return clean


def length(pts):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))


def at(pts, f):
    target, acc = length(pts) * f, 0
    for a, b in zip(pts, pts[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if acc + seg >= target:
            k = (target - acc) / seg if seg else 0
            return (a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k)
        acc += seg
    return pts[-1]


fly = route(px(40.8858, 29.1787), px(40.8921, 29.1903))
pins = [at(fly, f) for f in (0.24, 0.52, 0.8)]
fix = route(px(40.8893, 29.1938), pins[1])
m_per_px = (LON1 - LON0) * 111195 * math.cos(math.radians(40.888)) / W


def bbox(pts, pad):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad]


meta = {
    "w": W, "h": H,
    "fly": [[round(x, 1), round(y, 1)] for x, y in fly],
    "fix": [[round(x, 1), round(y, 1)] for x, y in fix],
    "pins": [{"x": round(x, 1), "y": round(y, 1), "lat": round(unpx(x, y)[0], 5), "lon": round(unpx(x, y)[1], 5)} for x, y in pins],
    "flyBox": bbox(fly, 160), "fixBox": bbox(fix + [pins[1]], 300), "pinBox": bbox(pins, 260),
    "flyMeters": round(length(fly) * m_per_px), "fixMeters": round(length(fix) * m_per_px),
    "attribution": "© OpenStreetMap contributors",
}
(ROOT / "src/howto/map.json").write_text(json.dumps(meta))
print(f"fly route {meta['flyMeters']} m, {len(fly)} pts · fix route {meta['fixMeters']} m · pins", meta["pins"])

# ── labels: one per named major road, on its longest way, left-to-right ──
best = {}
for cls, pts, name, ll in roads:
    if not name or cls in ("minor",):
        continue
    L = length(pts)
    if L > best.get(name, (0,))[0]:
        best[name] = (L, pts, cls)
labels = []
for i, (name, (L, pts, cls)) in enumerate(sorted(best.items(), key=lambda x: -x[1][0])[:14]):
    if L < 420:
        continue
    if pts[-1][0] < pts[0][0]:
        pts = pts[::-1]
    labels.append((f"lbl{i}", name, pts, cls))

FONT = "-apple-system, 'SF Pro Text', 'Helvetica Neue', Helvetica, Arial, sans-serif"
for theme, S in STYLE.items():
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    o.append(f'<rect width="{W}" height="{H}" fill="{S["land"]}"/>')
    for p in parks:
        o.append(f'<path d="{path_d(p, True)}" fill="{S["park"]}"/>')
    for d in sea:
        o.append(f'<path d="{d}" fill="{S["water"]}"/>')
    for b in buildings:
        o.append(f'<path d="{path_d(b, True)}" fill="{S["building"]}" stroke="{S["bstroke"]}" stroke-width="1.2"/>')
    for layer in ("casing", "fill"):
        for cls in DRAW_ORDER:
            wdt, fill, casing = S["roads"][cls]
            for c, pts, _, _ in roads:
                if c != cls:
                    continue
                if layer == "casing":
                    o.append(f'<path d="{path_d(pts)}" fill="none" stroke="{casing}" stroke-width="{wdt + 5}" stroke-linecap="round" stroke-linejoin="round"/>')
                else:
                    o.append(f'<path d="{path_d(pts)}" fill="none" stroke="{fill}" stroke-width="{wdt}" stroke-linecap="round" stroke-linejoin="round"/>')
    o.append("<defs>" + "".join(f'<path id="{k}" d="{path_d(p)}"/>' for k, _, p, _ in labels) + "</defs>")
    for k, name, p, cls in labels:
        size = 30 if cls in ("trunk", "primary") else 26
        for halo in (True, False):
            st = f'stroke="{S["halo"]}" stroke-width="7" stroke-linejoin="round"' if halo else ""
            o.append(
                f'<text font-family="{FONT}" font-size="{size}" font-weight="600" fill="{S["label"]}" {st} dy="9">'
                f'<textPath href="#{k}" startOffset="50%" text-anchor="middle">{name}</textPath></text>'
            )
    o.append(
        f'<text x="{W * 0.3:.0f}" y="{H * 0.93:.0f}" font-family="{FONT}" font-size="44" font-style="italic" '
        f'letter-spacing="6" fill="{S["sea_label"]}">Marmara Denizi</text>'
    )
    o.append(
        f'<text x="{W * 0.56:.0f}" y="{H * 0.47:.0f}" font-family="{FONT}" font-size="64" font-weight="700" '
        f'letter-spacing="18" fill="{S["label"]}" opacity="0.55" stroke="{S["halo"]}" stroke-width="10" paint-order="stroke">KARTAL</text>'
    )
    o.append("</svg>")
    (ROOT / f"public/maps/kartal-{theme}.svg").write_text("\n".join(o))
    print("wrote", f"public/maps/kartal-{theme}.svg")

# ── street network for the "every street" coverage effect (game video) ──
def decimate(pts, tol=6):
    out = [pts[0]]
    for p in pts[1:-1]:
        if math.hypot(p[0] - out[-1][0], p[1] - out[-1][1]) >= tol:
            out.append(p)
    out.append(pts[-1])
    return out


net = [
    [[round(x), round(y)] for x, y in decimate(pts)]
    for cls, pts, _, _ in roads
    if cls in ("trunk", "primary", "secondary", "tertiary", "residential")
]
(ROOT / "src/game").mkdir(exist_ok=True)
(ROOT / "src/game/roads.json").write_text(json.dumps(net, separators=(",", ":")))
print("wrote src/game/roads.json:", len(net), "streets")
