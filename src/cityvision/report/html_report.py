from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def write_html_report(
    path: str | Path,
    meta: Dict[str, Any],
    summary: Dict[str, Any],
    events: Sequence[Dict[str, Any]],
    traffic: Optional[Dict[str, Any]] = None,
) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    markers = []
    for ev in events:
        if ev.get("lat") is None or ev.get("lon") is None:
            continue
        if ev.get("confidence_band") == "discard":
            continue
        markers.append(
            {
                "id": ev.get("event_id"),
                "type": ev.get("type"),
                "lat": ev.get("lat"),
                "lon": ev.get("lon"),
                "confidence": ev.get("confidence"),
                "severity": ev.get("severity"),
                "band": ev.get("confidence_band"),
            }
        )

    center = {"lat": 39.92, "lon": 41.27}
    if markers:
        center = {
            "lat": sum(m["lat"] for m in markers) / len(markers),
            "lon": sum(m["lon"] for m in markers) / len(markers),
        }

    rows = []
    for ev in events:
        rows.append(
            "<tr>"
            f"<td>{html.escape(str(ev.get('event_id')))}</td>"
            f"<td>{html.escape(str(ev.get('type')))}</td>"
            f"<td>{html.escape(str(ev.get('severity')))}</td>"
            f"<td>{ev.get('confidence')}</td>"
            f"<td>{html.escape(str(ev.get('confidence_band')))}</td>"
            f"<td>{ev.get('observations')}</td>"
            f"<td>{ev.get('lat')}, {ev.get('lon')}</td>"
            f"<td>{html.escape(str(ev.get('status')))}</td>"
            "</tr>"
        )

    traffic_html = ""
    if traffic:
        traffic_html = f"<pre>{html.escape(json.dumps(traffic, indent=2))}</pre>"

    doc = f"""<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>City Vision Report</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>
    :root {{
      --bg: #0f1419;
      --panel: #1a222d;
      --text: #e8eef5;
      --muted: #9aabbd;
      --accent: #3d8bfd;
      --line: #2a3544;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0; font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
      background: radial-gradient(1200px 600px at 10% -10%, #1c2a3d, var(--bg));
      color: var(--text);
    }}
    header {{ padding: 28px 32px 8px; }}
    h1 {{ margin: 0 0 6px; font-size: 28px; letter-spacing: -0.02em; }}
    .sub {{ color: var(--muted); margin-bottom: 18px; }}
    .grid {{ display: grid; grid-template-columns: 1.2fr 1fr; gap: 16px; padding: 0 32px 32px; }}
    .card {{
      background: color-mix(in srgb, var(--panel) 92%, black);
      border: 1px solid var(--line); border-radius: 14px; padding: 16px;
    }}
    #map {{ height: 420px; border-radius: 10px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 8px 6px; text-align: left; }}
    th {{ color: var(--muted); font-weight: 600; }}
    .kpis {{ display: flex; gap: 12px; flex-wrap: wrap; margin: 12px 0 0; }}
    .kpi {{
      background: #121820; border: 1px solid var(--line); border-radius: 10px;
      padding: 10px 12px; min-width: 120px;
    }}
    .kpi b {{ display: block; font-size: 20px; }}
    .kpi span {{ color: var(--muted); font-size: 12px; }}
    pre {{ white-space: pre-wrap; color: var(--muted); font-size: 12px; }}
    @media (max-width: 960px) {{ .grid {{ grid-template-columns: 1fr; }} }}
  </style>
</head>
<body>
  <header>
    <h1>GBSoft City Vision</h1>
    <div class="sub">Run report · {html.escape(str(meta.get('source', '')))}</div>
    <div class="kpis">
      <div class="kpi"><b>{summary.get('detections', 0)}</b><span>detections</span></div>
      <div class="kpi"><b>{summary.get('events', 0)}</b><span>events</span></div>
      <div class="kpi"><b>{summary.get('unique_tracks', 0)}</b><span>unique tracks</span></div>
      <div class="kpi"><b>{summary.get('review_queue', 0)}</b><span>review queue</span></div>
    </div>
  </header>
  <div class="grid">
    <section class="card">
      <h2>City Event Map</h2>
      <div id="map"></div>
    </section>
    <section class="card">
      <h2>Traffic</h2>
      {traffic_html or "<p class='sub'>No traffic stats</p>"}
      <h2>Summary</h2>
      <pre>{html.escape(json.dumps(summary, indent=2, ensure_ascii=False))}</pre>
    </section>
    <section class="card" style="grid-column: 1 / -1;">
      <h2>Events</h2>
      <table>
        <thead>
          <tr>
            <th>ID</th><th>Type</th><th>Severity</th><th>Conf</th>
            <th>Band</th><th>Obs</th><th>GPS</th><th>Status</th>
          </tr>
        </thead>
        <tbody>
          {''.join(rows) if rows else '<tr><td colspan="8">No events</td></tr>'}
        </tbody>
      </table>
    </section>
  </div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const markers = {json.dumps(markers)};
    const center = {json.dumps(center)};
    const map = L.map('map').setView([center.lat, center.lon], 15);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap'
    }}).addTo(map);
    const color = {{
      high: '#e74c3c', probable: '#e67e22', manual_review: '#f1c40f', discard: '#7f8c8d'
    }};
    markers.forEach(m => {{
      L.circleMarker([m.lat, m.lon], {{
        radius: 8,
        color: color[m.band] || '#3d8bfd',
        fillColor: color[m.band] || '#3d8bfd',
        fillOpacity: 0.85
      }}).addTo(map).bindPopup(
        `<b>${{m.id}}</b><br/>${{m.type}}<br/>conf ${{m.confidence}} · ${{m.severity}}`
      );
    }});
  </script>
</body>
</html>
"""
    path.write_text(doc, encoding="utf-8")
    return path
