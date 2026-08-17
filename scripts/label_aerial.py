#!/usr/bin/env python3
"""Local aerial box labeler — no Docker / CVAT.

  .venv/bin/python scripts/label_aerial.py
  # browser → http://127.0.0.1:8765

Draw boxes on DJI frames. Saves YOLO txt. Then:

  .venv/bin/python scripts/label_aerial.py --export
"""

from __future__ import annotations

import argparse
import json
import shutil
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
DS = ROOT / "data" / "datasets" / "model_b_aerial"
FRAMES = DS / "raw_frames"
LABELS = DS / "labels_hand"
NAMES = {0: "pothole", 1: "road_crack", 2: "manhole", 3: "road_damage"}
EXTS = {".jpg", ".jpeg", ".png", ".webp"}

HTML = r"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8"/>
<title>City Vision — aerial label</title>
<style>
  :root { --bg:#111; --fg:#eee; --muted:#888; --bar:#1c1c1c; }
  * { box-sizing: border-box; }
  html, body { margin:0; height:100%; background:var(--bg); color:var(--fg);
    font: 14px/1.4 system-ui, sans-serif; overflow:hidden; }
  #bar { display:flex; gap:8px; align-items:center; flex-wrap:wrap;
    padding:8px 12px; background:var(--bar); border-bottom:1px solid #333; }
  button, select { background:#2a2a2a; color:#fff; border:1px solid #444;
    border-radius:6px; padding:8px 12px; cursor:pointer; font:inherit; }
  button:hover { background:#3a3a3a; }
  button.active { outline:2px solid currentColor; }
  #stage { position:relative; height:calc(100% - 92px); background:#000;
    display:flex; align-items:center; justify-content:center; }
  #wrap { position:relative; display:inline-block; max-width:100%; max-height:100%; }
  #img { max-width:100%; max-height:calc(100vh - 92px); display:block; user-select:none; }
  #cv { position:absolute; left:0; top:0; cursor:crosshair; }
  #hint { padding:6px 12px; color:var(--muted); font-size:12px; }
  #status { margin-left:auto; color:#aaa; }
</style>
</head>
<body>
<div id="bar">
  <button id="prev">← Prev</button>
  <button id="next">Next →</button>
  <button data-cls="0" style="color:#ff4d4d">1 Çukur</button>
  <button data-cls="1" style="color:#3dff6e">2 Çatlak</button>
  <button data-cls="2" style="color:#ffa64d">3 Rögar</button>
  <button data-cls="3" style="color:#d24dff">4 Hasar</button>
  <button id="undo">Undo</button>
  <button id="clear">Clear</button>
  <label style="color:#aaa"><input type="checkbox" id="only"/> unlabeled only</label>
  <span id="status"></span>
</div>
<div id="stage"><div id="wrap"><img id="img" alt="frame"/><canvas id="cv"></canvas></div></div>
<div id="hint">
  Drag to draw. 1–4 class · ←/→ frame · Backspace last box · Del selected.
  Rögar kapağı = Rögar, çukur değil. Islak leke / kişi / araç işaretleme.
</div>
<script>
const COLORS = {0:"#ff4d4d",1:"#3dff6e",2:"#ffa64d",3:"#d24dff"};
const NAMES = {0:"pothole",1:"road_crack",2:"manhole",3:"road_damage"};
let files=[], view=[], idx=0, boxes=[], cls=0, drag=null, sel=-1, natW=1, natH=1;

const $ = id => document.getElementById(id);
const img = $("img"), cv = $("cv"), ctx = cv.getContext("2d");

function clsBtns() {
  document.querySelectorAll("[data-cls]").forEach(b => {
    b.classList.toggle("active", Number(b.dataset.cls)===cls);
  });
}
async function loadList() {
  files = await (await fetch("/api/list")).json();
  if (!files.length) { $("status").textContent = "No frames in raw_frames/"; return; }
  await show(0);
}
function rebuildView() {
  view = $("only").checked ? files.filter(f => !f.labeled) : files.slice();
  if (!view.length) view = files.slice();
}
async function show(i) {
  rebuildView();
  idx = Math.max(0, Math.min(i, view.length-1));
  const rec = view[idx];
  const data = await (await fetch("/api/labels/"+encodeURIComponent(rec.name))).json();
  boxes = data.boxes || [];
  sel = -1;
  img.onload = fit;
  img.src = "/img/"+encodeURIComponent(rec.name)+"?t="+Date.now();
  if (img.complete) fit();
  $("status").textContent = `${idx+1}/${view.length}  ${rec.name}  boxes=${boxes.length}  labeled=${files.filter(f=>f.labeled).length}`;
}
function fit() {
  natW = img.naturalWidth; natH = img.naturalHeight;
  cv.width = img.clientWidth; cv.height = img.clientHeight;
  draw();
}
function toNorm(px, py) {
  return [px / cv.width, py / cv.height];
}
function draw() {
  ctx.clearRect(0,0,cv.width,cv.height);
  boxes.forEach((b,i) => {
    const x = b.xc*cv.width - b.w*cv.width/2;
    const y = b.yc*cv.height - b.h*cv.height/2;
    const w = b.w*cv.width, h = b.h*cv.height;
    ctx.strokeStyle = COLORS[b.cls];
    ctx.lineWidth = i===sel ? 4 : 2;
    ctx.strokeRect(x,y,w,h);
    ctx.fillStyle = COLORS[b.cls];
    ctx.font = "13px sans-serif";
    ctx.fillText(NAMES[b.cls], x, Math.max(14, y-4));
  });
  if (drag) {
    ctx.strokeStyle = COLORS[cls];
    ctx.setLineDash([6,4]);
    ctx.strokeRect(drag.x0, drag.y0, drag.x1-drag.x0, drag.y1-drag.y0);
    ctx.setLineDash([]);
  }
}
async function save() {
  const rec = view[idx];
  if (!rec) return;
  await fetch("/api/labels/"+encodeURIComponent(rec.name), {
    method:"PUT", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({boxes})
  });
  rec.labeled = boxes.length > 0;
  rec.n = boxes.length;
  const src = files.find(f => f.name === rec.name);
  if (src) { src.labeled = rec.labeled; src.n = rec.n; }
  $("status").textContent = `${idx+1}/${view.length}  ${rec.name}  boxes=${boxes.length}  labeled=${files.filter(f=>f.labeled).length}`;
}
async function go(d) {
  await save();
  show(idx + d);
}

cv.addEventListener("mousedown", e => {
  e.preventDefault();
  const r = cv.getBoundingClientRect();
  const x = e.clientX-r.left, y = e.clientY-r.top;
  sel = hit(x,y);
  if (sel >= 0) { draw(); return; }
  drag = {x0:x,y0:y,x1:x,y1:y};
});
cv.addEventListener("mousemove", e => {
  if (!drag) return;
  const r = cv.getBoundingClientRect();
  drag.x1 = e.clientX-r.left; drag.y1 = e.clientY-r.top;
  draw();
});
window.addEventListener("mouseup", async () => {
  if (!drag) return;
  const x1 = Math.min(drag.x0, drag.x1), y1 = Math.min(drag.y0, drag.y1);
  const x2 = Math.max(drag.x0, drag.x1), y2 = Math.max(drag.y0, drag.y1);
  drag = null;
  if (x2-x1 < 6 || y2-y1 < 6) { draw(); return; }
  const [nx1, ny1] = toNorm(x1,y1), [nx2, ny2] = toNorm(x2,y2);
  boxes.push({cls, xc:(nx1+nx2)/2, yc:(ny1+ny2)/2, w:nx2-nx1, h:ny2-ny1});
  sel = boxes.length-1;
  draw();
  await save();
});
function hit(px, py) {
  for (let i=boxes.length-1;i>=0;i--) {
    const b = boxes[i];
    const x = b.xc*cv.width - b.w*cv.width/2;
    const y = b.yc*cv.height - b.h*cv.height/2;
    if (px>=x && px<=x+b.w*cv.width && py>=y && py<=y+b.h*cv.height) return i;
  }
  return -1;
}
$("prev").onclick = () => go(-1);
$("next").onclick = () => go(1);
$("undo").onclick = async () => { boxes.pop(); sel=-1; draw(); await save(); };
$("clear").onclick = async () => { boxes=[]; sel=-1; draw(); await save(); };
$("only").onchange = () => show(0);
document.querySelectorAll("[data-cls]").forEach(b => {
  b.onclick = () => {
    cls = Number(b.dataset.cls);
    if (sel>=0) { boxes[sel].cls = cls; draw(); save(); }
    clsBtns();
  };
});
window.addEventListener("keydown", e => {
  if (["INPUT","TEXTAREA"].includes(e.target.tagName)) return;
  if (e.key>="1" && e.key<="4") {
    cls = Number(e.key)-1; clsBtns();
    if (sel>=0) { boxes[sel].cls = cls; draw(); save(); }
  }
  if (e.key==="ArrowRight" || e.key==="d") go(1);
  if (e.key==="ArrowLeft" || e.key==="a") go(-1);
  if (e.key==="Backspace") { e.preventDefault(); boxes.pop(); sel=-1; draw(); save(); }
  if (e.key==="Delete" && sel>=0) { boxes.splice(sel,1); sel=-1; draw(); save(); }
});
window.addEventListener("resize", fit);
clsBtns();
loadList();
</script>
</body>
</html>
"""


def _frames() -> list[Path]:
    FRAMES.mkdir(parents=True, exist_ok=True)
    return sorted(p for p in FRAMES.iterdir() if p.suffix.lower() in EXTS)


def _label_path(name: str) -> Path:
    LABELS.mkdir(parents=True, exist_ok=True)
    return LABELS / (Path(name).stem + ".txt")


def _read_boxes(name: str) -> list[dict]:
    path = _label_path(name)
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        cls, xc, yc, w, h = int(parts[0]), *map(float, parts[1:])
        out.append({"cls": cls, "xc": xc, "yc": yc, "w": w, "h": h})
    return out


def _write_boxes(name: str, boxes: list[dict]) -> None:
    path = _label_path(name)
    if not boxes:
        if path.exists():
            path.unlink()
        return
    lines = []
    for b in boxes:
        cls = int(b["cls"])
        if cls not in NAMES:
            continue
        lines.append(f"{cls} {b['xc']:.6f} {b['yc']:.6f} {b['w']:.6f} {b['h']:.6f}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_yolo() -> str:
    labeled = []
    for img in _frames():
        boxes = _read_boxes(img.name)
        if boxes:
            labeled.append((img, boxes))
    if not labeled:
        return "No labeled frames yet."
    for sub in ("images", "labels"):
        p = DS / sub
        if p.exists():
            shutil.rmtree(p)
    val_i = set(range(0, len(labeled), 5))
    stats = {n: 0 for n in NAMES.values()}
    n_train = n_val = 0
    for i, (img, boxes) in enumerate(labeled):
        split = "val" if i in val_i else "train"
        img_dir = DS / "images" / split
        lbl_dir = DS / "labels" / split
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(img, img_dir / img.name)
        shutil.copy2(_label_path(img.name), lbl_dir / (img.stem + ".txt"))
        for b in boxes:
            stats[NAMES[int(b["cls"])]] += 1
        if split == "train":
            n_train += 1
        else:
            n_val += 1
    (ROOT / "configs" / "model_b_aerial.data.yaml").write_text(
        "path: data/datasets/model_b_aerial\n"
        "train: images/train\n"
        "val: images/val\n\n"
        "names:\n"
        "  0: pothole\n"
        "  1: road_crack\n"
        "  2: manhole\n"
        "  3: road_damage\n",
        encoding="utf-8",
    )
    msg = f"export train={n_train} val={n_val} boxes={stats}"
    (DS / "README.md").write_text(
        "# Aerial DJI Model B — hand boxes\n\n"
        "Label in the browser: `python scripts/label_aerial.py`\n"
        f"{msg}\n",
        encoding="utf-8",
    )
    return msg


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        print(fmt % args)

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if path == "/":
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/list":
            rows = []
            for p in _frames():
                boxes = _read_boxes(p.name)
                rows.append({"name": p.name, "labeled": bool(boxes), "n": len(boxes)})
            self._send(200, json.dumps(rows).encode(), "application/json")
            return
        if path.startswith("/api/labels/"):
            name = path.split("/", 3)[-1]
            self._send(
                200,
                json.dumps({"boxes": _read_boxes(name)}).encode(),
                "application/json",
            )
            return
        if path.startswith("/img/"):
            name = Path(path.split("/", 2)[-1]).name
            fp = FRAMES / name
            if not fp.exists():
                self._send(404, b"missing", "text/plain")
                return
            ctype = "image/jpeg" if fp.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
            self._send(200, fp.read_bytes(), ctype)
            return
        self._send(404, b"not found", "text/plain")

    def do_PUT(self) -> None:  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if not path.startswith("/api/labels/"):
            self._send(404, b"not found", "text/plain")
            return
        name = Path(path.split("/", 3)[-1]).name
        n = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(n) or b"{}")
        _write_boxes(name, payload.get("boxes") or [])
        self._send(200, b'{"ok":true}', "application/json")


def serve(port: int) -> None:
    if not _frames():
        raise SystemExit(f"No frames in {FRAMES}")
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Labeler → {url}")
    print("Draw boxes, then stop with Ctrl+C and run: python scripts/label_aerial.py --export")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    httpd.serve_forever()


def main() -> int:
    p = argparse.ArgumentParser(description="Browser aerial labeler (no CVAT)")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--export", action="store_true", help="Pack labels_hand → train/val YOLO")
    args = p.parse_args()
    if args.export:
        print(export_yolo())
        return 0
    serve(args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
