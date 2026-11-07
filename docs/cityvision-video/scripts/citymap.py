"""District maps in an Apple-Maps-like style, from OpenStreetMap data (© OpenStreetMap contributors, ODbL).

    python3 scripts/citymap.py kadikoy        → public/maps/kadikoy-{light,navy}.svg + src/mayor/map.json
    node scripts/bake-maps.mjs kadikoy src/mayor/map.json    (SVG → PNG)

Routes are shortest paths on the real road graph. The sea is built from OSM coastline ways
(water is always on the right of a coastline), clipped to the map and closed along its edge.
"""
import heapq
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DISTRICTS = {
    "kadikoy": {
        "data": "public/maps/kadikoy.json",
        "bbox": (29.017, 29.041, 40.979, 40.997),  # lon0, lon1, lat0, lat1
        "label": "KADIKÖY",
        "sea": "Marmara Denizi",
        "fly": ((40.9912, 29.0262), (40.9842, 29.0352)),
        "fix_from": (40.9868, 29.0265),
        "meta": "src/mayor/map.json",
    },
}

NAME = sys.argv[1] if len(sys.argv) > 1 else "kadikoy"
C = DISTRICTS[NAME]
D = json.loads((ROOT / C["data"]).read_text())
LON0, LON1, LAT0, LAT1 = C["bbox"]
LATC = (LAT0 + LAT1) / 2
W = 3000
H = round(W * (LAT1 - LAT0) / ((LON1 - LON0) * math.cos(math.radians(LATC))))


def px(lat, lon):
    return ((lon - LON0) / (LON1 - LON0) * W, (LAT1 - lat) / (LAT1 - LAT0) * H)


def unpx(x, y):
    return LAT1 - y / H * (LAT1 - LAT0), LON0 + x / W * (LON1 - LON0)


STYLE = {
    "light": {
        "land": "#F3F1EC", "building": "#E4E0D8", "bstroke": "#D6D0C5", "park": "#CFE8C1", "water": "#A9D3F1",
        "label": "#6B6760", "halo": "#F7F6F2", "sea_label": "#5E99C9",
        "roads": {"trunk": (30, "#FFD27F", "#E2AC4E"), "primary": (24, "#FFE6A6", "#E3C47C"),
                  "secondary": (20, "#FFFFFF", "#D3CDC2"), "tertiary": (17, "#FFFFFF", "#D3CDC2"),
                  "residential": (12, "#FFFFFF", "#D9D4CA"), "minor": (8, "#FFFFFF", "#DDD8CF")},
    },
    "navy": {
        "land": "#10244F", "building": "#16295B", "bstroke": "#1C3268", "park": "#123B52", "water": "#091733",
        "label": "#8EA4D6", "halo": "#10244F", "sea_label": "#3D5D9C",
        "roads": {"trunk": (30, "#4566B5", "#2D4A8E"), "primary": (24, "#3A5AA3", "#284282"),
                  "secondary": (20, "#2C4886", "#22396F"), "tertiary": (17, "#2A4581", "#21386C"),
                  "residential": (12, "#233D76", "#1C3366"), "minor": (8, "#203970", "#1B3163")},
    },
}
ROAD_CLASS = {
    "motorway": "trunk", "trunk": "trunk", "trunk_link": "primary", "primary": "primary", "primary_link": "primary",
    "secondary": "secondary", "secondary_link": "secondary", "tertiary": "tertiary", "tertiary_link": "tertiary",
    "residential": "residential", "unclassified": "residential", "living_street": "minor", "service": "minor",
}
DRAW_ORDER = ["minor", "residential", "tertiary", "secondary", "primary", "trunk"]

roads, buildings, parks, water_areas, coast_ways = [], [], [], [], []
for e in D["elements"]:
    t, g = e.get("tags", {}), e.get("geometry")
    if not g:
        continue
    pts = [px(p["lat"], p["lon"]) for p in g]
    if "highway" in t and t["highway"] in ROAD_CLASS:
        roads.append((ROAD_CLASS[t["highway"]], pts, t.get("name")))
    elif "building" in t:
        buildings.append(pts)
    elif t.get("natural") == "coastline":
        coast_ways.append([(p["lat"], p["lon"]) for p in g])
    elif t.get("natural") == "water":
        water_areas.append(pts)
    elif t.get("leisure") in ("park", "garden", "pitch", "playground") or t.get("landuse") in (
        "grass", "park", "forest", "recreation_ground", "cemetery") or t.get("natural") == "wood":
        parks.append(pts)


def path_d(pts, close=False):
    return "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + (" Z" if close else "")


# ───────── sea from coastline ─────────
def chain(ways):
    """Join coastline ways end-to-start into longer lines (and closed rings)."""
    ways = [list(w) for w in ways]
    out = []
    while ways:
        cur = ways.pop()
        grown = True
        while grown:
            grown = False
            for i, w in enumerate(ways):
                if w[0] == cur[-1]:
                    cur += w[1:]
                elif w[-1] == cur[0]:
                    cur = w[:-1] + cur
                else:
                    continue
                ways.pop(i)
                grown = True
                break
        out.append(cur)
    return out


M = 120  # clip rectangle = map + margin, in px
RX0, RY0, RX1, RY1 = -M, -M, W + M, H + M
PER = 2 * ((RX1 - RX0) + (RY1 - RY0))


def inside(p):
    return RX0 <= p[0] <= RX1 and RY0 <= p[1] <= RY1


def seg_clip(a, b):
    """Liang–Barsky: part of segment a→b inside the rectangle as (t0, t1) or None."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - RX0), (dx, RX1 - a[0]), (-dy, a[1] - RY0), (dy, RY1 - a[1])):
        if p == 0:
            if q < 0:
                return None
        else:
            r = q / p
            if p < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
    return (t0, t1) if t0 <= t1 else None


def perim(p):
    """Clockwise (on screen) position along the clip rectangle, starting top-left."""
    x, y = p
    w, h = RX1 - RX0, RY1 - RY0
    if abs(y - RY0) < 1e-6:
        return x - RX0
    if abs(x - RX1) < 1e-6:
        return w + (y - RY0)
    if abs(y - RY1) < 1e-6:
        return w + h + (RX1 - x)
    return 2 * w + h + (RY1 - y)


CORNERS = [(0.0, (RX0, RY0)), (RX1 - RX0, (RX1, RY0)), ((RX1 - RX0) + (RY1 - RY0), (RX1, RY1)),
           (2 * (RX1 - RX0) + (RY1 - RY0), (RX0, RY1))]

pieces, islands = [], []
for line in chain(coast_ways):
    pts = [px(*p) for p in line]
    if line[0] == line[-1] and all(inside(p) for p in pts):
        islands.append(pts)
        continue
    cur = []
    for a, b in zip(pts, pts[1:]):
        c = seg_clip(a, b)
        if c is None:
            continue
        t0, t1 = c
        pa = (a[0] + (b[0] - a[0]) * t0, a[1] + (b[1] - a[1]) * t0)
        pb = (a[0] + (b[0] - a[0]) * t1, a[1] + (b[1] - a[1]) * t1)
        if not cur:
            cur = [pa]
        cur.append(pb)
        if t1 < 1:  # leaves the rectangle
            pieces.append(cur)
            cur = []
    if cur:
        pieces.append(cur)
ok_pieces = []
for p in pieces:
    on_edge = lambda q: min(abs(q[0] - RX0), abs(q[0] - RX1), abs(q[1] - RY0), abs(q[1] - RY1)) < 1e-3
    if on_edge(p[0]) and on_edge(p[-1]):
        ok_pieces.append(p)
    else:
        print("  ! skipped a coastline piece that ends inside the map (data cut)")

sea_polys = []
used = [False] * len(ok_pieces)
for i in range(len(ok_pieces)):
    if used[i]:
        continue
    poly, j = [], i
    while True:
        used[j] = True
        poly += ok_pieces[j]
        tx = perim(ok_pieces[j][-1])
        # next entry clockwise from this exit
        cands = sorted(range(len(ok_pieces)), key=lambda k: (perim(ok_pieces[k][0]) - tx) % PER)
        nxt = cands[0]
        te = perim(ok_pieces[nxt][0])
        span = (te - tx) % PER
        for cp, cxy in sorted(CORNERS, key=lambda c: (c[0] - tx) % PER):
            if 0 < (cp - tx) % PER < span:
                poly.append(cxy)
        if nxt == i or used[nxt]:
            break
        j = nxt
    sea_polys.append(poly)
print(f"  coastline: {len(ok_pieces)} piece(s) → {len(sea_polys)} sea polygon(s), {len(islands)} island(s)")

# ───────── road graph + routes ─────────
graph, node_xy = defaultdict(list), {}
for cls, pts, _ in roads:
    if cls == "minor":
        continue
    for a, b in zip(pts, pts[1:]):
        ka, kb = (round(a[0], 1), round(a[1], 1)), (round(b[0], 1), round(b[1], 1))
        node_xy[ka], node_xy[kb] = a, b
        d = math.hypot(a[0] - b[0], a[1] - b[1])
        graph[ka].append((kb, d))
        graph[kb].append((ka, d))


def route(a, b):
    s = min(node_xy, key=lambda k: (k[0] - a[0]) ** 2 + (k[1] - a[1]) ** 2)
    t = min(node_xy, key=lambda k: (k[0] - b[0]) ** 2 + (k[1] - b[1]) ** 2)
    dist, prev, pq = {s: 0}, {}, [(0, s)]
    while pq:
        d, u = heapq.heappop(pq)
        if u == t:
            break
        if d > dist[u]:
            continue
        for v, wgt in graph[u]:
            nd = d + wgt
            if nd < dist.get(v, 1e18):
                dist[v], prev[v] = nd, u
                heapq.heappush(pq, (nd, v))
    out, u = [t], t
    while u != s:
        u = prev[u]
        out.append(u)
    out = [node_xy[k] for k in reversed(out)]
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


def bbox(pts, pad):
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad]


fly = route(px(*C["fly"][0]), px(*C["fly"][1]))
pins = [at(fly, f) for f in (0.24, 0.52, 0.8)]
fix = route(px(*C["fix_from"]), pins[1])
m_per_px = (LON1 - LON0) * 111195 * math.cos(math.radians(LATC)) / W
meta = {
    "district": NAME, "w": W, "h": H,
    "fly": [[round(x, 1), round(y, 1)] for x, y in fly],
    "fix": [[round(x, 1), round(y, 1)] for x, y in fix],
    "pins": [{"x": round(x, 1), "y": round(y, 1), "lat": round(unpx(x, y)[0], 5), "lon": round(unpx(x, y)[1], 5)} for x, y in pins],
    "flyBox": bbox(fly, 160), "fixBox": bbox(fix + [pins[1]], 300), "pinBox": bbox(pins, 260),
    "flyMeters": round(length(fly) * m_per_px), "fixMeters": round(length(fix) * m_per_px),
    "light": f"maps/{NAME}-light.png", "navy": f"maps/{NAME}-navy.png",
    "attribution": "© OpenStreetMap contributors",
}
(ROOT / C["meta"]).write_text(json.dumps(meta))
print(f"  fly {meta['flyMeters']} m · fix {meta['fixMeters']} m · pins {[(p['lat'], p['lon']) for p in meta['pins']]}")

# ───────── labels ─────────
best = {}
for cls, pts, name in roads:
    if not name or cls == "minor":
        continue
    L = length(pts)
    if L > best.get(name, (0,))[0]:
        best[name] = (L, pts, cls)
labels = []
for i, (name, (L, pts, cls)) in enumerate(sorted(best.items(), key=lambda x: -x[1][0])[:16]):
    if L < 380:
        continue
    if pts[-1][0] < pts[0][0]:
        pts = pts[::-1]
    labels.append((f"lbl{i}", name, pts, cls))


def in_poly(p, poly):
    x, y, c = p[0], p[1], False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            c = not c
    return c


# sea label: the open-water point (on the map) farthest from the coast
sea_pt = None
if sea_polys:
    coast_pts = [q for p in ok_pieces for q in p[:: max(1, len(p) // 200)]]
    best_d = -1
    for gx in range(150, W - 150, 60):
        for gy in range(150, H - 150, 60):
            if any(in_poly((gx, gy), sp) for sp in sea_polys):
                d = min(math.hypot(gx - q[0], gy - q[1]) for q in coast_pts)
                if d > best_d:
                    best_d, sea_pt = d, (gx, gy)
# district label: land point between the routes, nudged off them
lbl_pt = (sum(p[0] for p in fly) / len(fly) + 260, sum(p[1] for p in fly) / len(fly) - 220)

FONT = "-apple-system, 'SF Pro Text', 'Helvetica Neue', Helvetica, Arial, sans-serif"
for theme, S in STYLE.items():
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         f'<rect width="{W}" height="{H}" fill="{S["land"]}"/>']
    for p in parks:
        o.append(f'<path d="{path_d(p, True)}" fill="{S["park"]}"/>')
    for p in sea_polys:
        o.append(f'<path d="{path_d(p, True)}" fill="{S["water"]}"/>')
    for p in water_areas:
        o.append(f'<path d="{path_d(p, True)}" fill="{S["water"]}"/>')
    for p in islands:
        o.append(f'<path d="{path_d(p, True)}" fill="{S["land"]}"/>')
    for b in buildings:
        o.append(f'<path d="{path_d(b, True)}" fill="{S["building"]}" stroke="{S["bstroke"]}" stroke-width="1.2"/>')
    for layer in ("casing", "fill"):
        for cls in DRAW_ORDER:
            wdt, fill, casing = S["roads"][cls]
            for c, pts, _ in roads:
                if c != cls:
                    continue
                col, wd = (casing, wdt + 5) if layer == "casing" else (fill, wdt)
                o.append(f'<path d="{path_d(pts)}" fill="none" stroke="{col}" stroke-width="{wd}" stroke-linecap="round" stroke-linejoin="round"/>')
    o.append("<defs>" + "".join(f'<path id="{k}" d="{path_d(p)}"/>' for k, _, p, _ in labels) + "</defs>")
    for k, name, p, cls in labels:
        size = 30 if cls in ("trunk", "primary") else 26
        for halo in (True, False):
            st = f'stroke="{S["halo"]}" stroke-width="7" stroke-linejoin="round"' if halo else ""
            o.append(f'<text font-family="{FONT}" font-size="{size}" font-weight="600" fill="{S["label"]}" {st} dy="9">'
                     f'<textPath href="#{k}" startOffset="50%" text-anchor="middle">{name}</textPath></text>')
    if sea_pt:
        o.append(f'<text x="{sea_pt[0]:.0f}" y="{sea_pt[1]:.0f}" text-anchor="middle" font-family="{FONT}" font-size="44" '
                 f'font-style="italic" letter-spacing="6" fill="{S["sea_label"]}">{C["sea"]}</text>')
    o.append(f'<text x="{lbl_pt[0]:.0f}" y="{lbl_pt[1]:.0f}" text-anchor="middle" font-family="{FONT}" font-size="64" font-weight="700" '
             f'letter-spacing="18" fill="{S["label"]}" opacity="0.55" stroke="{S["halo"]}" stroke-width="10" paint-order="stroke">{C["label"]}</text>')
    o.append("</svg>")
    (ROOT / f"public/maps/{NAME}-{theme}.svg").write_text("\n".join(o))
    print("  wrote", f"public/maps/{NAME}-{theme}.svg")
