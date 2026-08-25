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
import sys
import webbrowser
from collections import defaultdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cityvision.pipeline.dataset_split import (  # noqa: E402
    assign_splits,
    clip_of,
    split_manifest_sha,
)

DS = ROOT / "data" / "datasets" / "model_b_aerial"
FRAMES = DS / "raw_frames"
LABELS = DS / "labels_hand"
REVIEWED = DS / "reviewed.txt"
# Frames the user confirmed as clean asphalt — exported as YOLO background images.
# Kept apart from reviewed.txt, where a box-less frame may just have been skipped.
BACKGROUND = DS / "background.txt"
# Active-learning order from scripts/queue_uncertain.py
PRIORITY = DS / "priority.txt"
# Suggested clean frames from the same script — each still needs a human B press
BACKGROUND_CANDIDATES = DS / "background_candidates.txt"
# External aerial datasets (same domain as our own drone captures, prepared by their own
# scripts/prepare_*.py into this class scheme) folded into train only, on every export, so
# they survive being wiped and rebuilt from labels_hand/. Never touch val/test — clip3 stays
# a clean hold-out and these sources have no clip timeline to split. Not oversampled: unlike
# our own rare-class frames, these already come in bulk.
EXTERNAL_TRAIN_SOURCES = [ROOT / "data" / "datasets" / "uav_pdd2023"]
NAMES = {0: "pothole", 1: "road_crack", 2: "manhole", 3: "road_damage"}
EXTS = {".jpg", ".jpeg", ".png", ".webp"}
# Rare classes get duplicated in the train split so 10 crack boxes are not lost in the noise
RARE_CLASSES = (0, 1)
RARE_OVERSAMPLE = 5
# Hold-out clip: never trained on, used by scripts/eval_aerial.py
TEST_PREFIX = "clip3"
# Every other clip is cut on its own timeline instead of interleaved: the tail goes to val,
# and GUARD frames at the cut are dropped so no val frame borders a train frame.
VAL_TAIL_FRAC = 0.2
GUARD_FRAMES = 1
# Ultralytics recommends roughly 10% empty images; past that the loss drifts toward predicting
# nothing and recall on the rare classes suffers. Train-split only — val/test keep every clean
# frame so false-alarm rate stays honest.
BG_MAX_FRAC = 0.15

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
  #stage { position:relative; height:calc(100% - 92px); background:#000; overflow:auto; }
  /* auto margins center the frame when it fits and collapse to 0 when zoomed past the
     viewport, so the left edge stays reachable by scrolling */
  #wrap { position:relative; display:block; width:max-content; margin:0 auto; }
  #img { display:block; user-select:none; }
  #cv { position:absolute; left:0; top:0; cursor:crosshair; }
  #zoomlab { color:#aaa; min-width:52px; text-align:right; font-variant-numeric:tabular-nums; }
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
  <button id="bg" style="color:#4dd2ff">B Temiz kare</button>
  <button id="undo">Undo</button>
  <button id="clear">Clear</button>
  <button id="zout" title="uzaklas (-)">−</button>
  <button id="zin" title="yakinlas (+)">+</button>
  <button id="z11" title="1 goruntu pikseli = 1 ekran pikseli">1:1</button>
  <button id="zfit" title="sigdir (0)">Sığdır</button>
  <span id="zoomlab"></span>
  <select id="mode" title="frame filter">
    <option value="todo">etiketsiz</option>
    <option value="priority">öncelik</option>
    <option value="bgcand">temiz aday</option>
    <option value="review">revizyon</option>
    <option value="damage">revizyon: çukur/hasar</option>
    <option value="clean">temiz kareler</option>
    <option value="all">hepsi</option>
  </select>
  <select id="clip" title="clip filter"></select>
  <span id="status"></span>
</div>
<div id="stage"><div id="wrap"><img id="img" alt="frame"/><canvas id="cv"></canvas></div></div>
<div id="hint">
  Drag to draw. 1–4 sınıf · B temiz kare · ←/→ kare · Backspace son kutu · Del seçili.
  Zoom: +/− · 0 sığdır · ⌘/Ctrl+tekerlek veya pinch · kaydırma ile gez. Çatlağı 1:1'de çiz.
  Rögar kapağı = Rögar, çukur değil. Oyuk yoksa Hasar. Islak leke / kişi / araç işaretleme.
  B sadece gerçekten temiz kare için — kopya kareyi atlarken B basma (docs/labeling-guide-aerial.md).
</div>
<script>
const COLORS = {0:"#ff4d4d",1:"#3dff6e",2:"#ffa64d",3:"#d24dff"};
const NAMES = {0:"pothole",1:"road_crack",2:"manhole",3:"road_damage"};
let files=[], view=[], idx=0, boxes=[], cls=0, drag=null, sel=-1, natW=1, natH=1;
// zoom is a multiplier on the fit-to-viewport size, so 1 always means "whole frame visible"
let zoom=1, baseW=1, baseH=1, pan=null;
const ZOOM_MIN=1, ZOOM_MAX=12, ZOOM_STEP=1.25;

const $ = id => document.getElementById(id);
const img = $("img"), cv = $("cv"), ctx = cv.getContext("2d"), stage = $("stage");

function clsBtns() {
  document.querySelectorAll("[data-cls]").forEach(b => {
    b.classList.toggle("active", Number(b.dataset.cls)===cls);
  });
}
function clipOf(name) {
  // Mirrors cityvision.pipeline.dataset_split.clip_of: strip the trailing
  // "_<digits>ms" timestamp suffix; whatever's left is the clip id, whatever
  // the source's naming style. Falls back to the full stem if there's no
  // "...ms" suffix to strip (e.g. a non-frame file that shouldn't be here).
  const stem = name.replace(/\.[^.]+$/, "");
  const i = stem.lastIndexOf("_");
  if (i < 0) return stem;
  const tail = stem.slice(i + 1);
  return /^\d+ms$/.test(tail) ? stem.slice(0, i) : stem;
}
async function loadList() {
  files = await (await fetch("/api/list")).json();
  if (!files.length) { $("status").textContent = "No frames in raw_frames/"; return; }
  const sel = $("clip");
  const clips = [...new Set(files.map(f => clipOf(f.name)))].sort();
  sel.innerHTML = "";
  const add = (v, t) => { const o=document.createElement("option"); o.value=v; o.textContent=t; sel.appendChild(o); };
  add("", "all clips");
  if (clips.some(c => c.startsWith("clip"))) add("new", "yeni klipler");
  clips.forEach(c => add(c, c));
  // deep link: /?clip=clip4&mode=todo
  const qs = new URLSearchParams(location.search);
  const has = (el, v) => v !== null && [...el.options].some(o => o.value === v);
  if (has($("mode"), qs.get("mode"))) $("mode").value = qs.get("mode");
  if (has(sel, qs.get("clip"))) sel.value = qs.get("clip");
  else if (clips.includes("clip1")) sel.value = "clip1";
  else if ([...sel.options].some(o => o.value==="new")) sel.value = "new";
  await show(0);
}
function rebuildView() {
  let list = files.slice();
  const clip = $("clip").value;
  if (clip === "new") list = list.filter(f => clipOf(f.name).startsWith("clip"));
  else if (clip) list = list.filter(f => clipOf(f.name) === clip);
  const mode = $("mode").value;
  if (mode === "todo") {
    list = list.filter(f => !f.labeled && !f.reviewed);
  } else if (mode === "priority") {
    list = list.filter(f => f.rank >= 0 && !f.labeled && !f.background);
    list.sort((a,b) => a.rank - b.rank);
  } else if (mode === "bgcand") {
    list = list.filter(f => f.bgCandidate && !f.labeled && !f.background);
  } else if (mode === "review") {
    list = list.filter(f => f.labeled);
  } else if (mode === "damage") {
    list = list.filter(f => f.classes.includes(0) || f.classes.includes(3));
  } else if (mode === "clean") {
    list = list.filter(f => f.background);
  }
  view = list.length ? list : [];
}
async function show(i) {
  rebuildView();
  if (!view.length) {
    $("status").textContent = "Bu filtrede kare yok";
    img.removeAttribute("src");
    ctx && ctx.clearRect(0,0,cv.width,cv.height);
    return;
  }
  idx = Math.max(0, Math.min(i, view.length-1));
  const rec = view[idx];
  const data = await (await fetch("/api/labels/"+encodeURIComponent(rec.name))).json();
  boxes = data.boxes || [];
  sel = -1;
  img.onload = fit;
  img.src = "/img/"+encodeURIComponent(rec.name)+"?t="+Date.now();
  if (img.complete) fit();
  setStatus(rec);
}
function setStatus(rec) {
  const tag = rec.background ? " [temiz]" : "";
  const nb = files.filter(f=>f.background).length;
  $("status").textContent =
    `${idx+1}/${view.length}  ${rec.name}${tag}  boxes=${boxes.length}` +
    `  labeled=${files.filter(f=>f.labeled).length}  temiz=${nb}`;
}
function fit() {
  natW = img.naturalWidth || 1; natH = img.naturalHeight || 1;
  const s = Math.min(stage.clientWidth / natW, stage.clientHeight / natH);
  baseW = Math.max(1, Math.round(natW * s));
  baseH = Math.max(1, Math.round(natH * s));
  applyZoom();
}
// keep: client coords that should stay under the cursor while zooming
function applyZoom(keep) {
  let anchor = null;
  if (keep) {
    const r = img.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) {
      anchor = {nx:(keep.cx-r.left)/r.width, ny:(keep.cy-r.top)/r.height, cx:keep.cx, cy:keep.cy};
    }
  }
  img.style.width = Math.round(baseW * zoom) + "px";
  img.style.height = Math.round(baseH * zoom) + "px";
  cv.width = img.clientWidth; cv.height = img.clientHeight;
  draw();
  if (anchor) {
    const r = img.getBoundingClientRect();
    stage.scrollLeft += (r.left + anchor.nx*r.width) - anchor.cx;
    stage.scrollTop += (r.top + anchor.ny*r.height) - anchor.cy;
  }
  // 1:1 means one source pixel per screen pixel; on a downscaled fit that is > 100%
  const pct = Math.round((cv.width / natW) * 100);
  $("zoomlab").textContent = pct + "%";
}
function setZoom(z, keep) {
  const next = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, z));
  if (Math.abs(next - zoom) < 1e-3) return;
  zoom = next;
  applyZoom(keep);
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
  let res;
  for (let i = 0; i < 3; i++) {
    try {
      res = await fetch("/api/labels/"+encodeURIComponent(rec.name), {
        method:"PUT", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({boxes})
      });
      if (res.ok) break;
    } catch (err) {
      if (i === 2) throw err;
    }
    await new Promise(r => setTimeout(r, 400 * (i + 1)));
  }
  if (!res || !res.ok) throw new Error("save "+(res && res.status));
  rec.labeled = boxes.length > 0;
  rec.n = boxes.length;
  rec.classes = [...new Set(boxes.map(b => b.cls))].sort();
  if (rec.labeled) {
    rec.background = false;
    rec.reviewed = true;
  }
  const src = files.find(f => f.name === rec.name);
  if (src) {
    src.labeled = rec.labeled;
    src.n = rec.n;
    src.classes = rec.classes;
    src.background = rec.background;
    src.reviewed = rec.reviewed;
  }
  setStatus(rec);
}
async function go(d) {
  const name = view[idx] && view[idx].name;
  try { await save(); }
  catch (err) { $("status").textContent = "Kayıt olmadı — sayfayı yenile"; return; }
  rebuildView();
  if (!view.length) { show(0); return; }
  const i = name ? view.findIndex(f => f.name === name) : -1;
  // A box or B press drops the current frame from "etiketsiz"; idx then
  // already points at the former next item. idx+1 would skip one.
  if (d > 0) show(i >= 0 ? i + 1 : idx);
  else show(i >= 0 ? i - 1 : idx - 1);
}
async function markBackground() {
  const rec = view[idx];
  if (!rec) return;
  const on = !rec.background;
  await fetch("/api/background/"+encodeURIComponent(rec.name), {
    method:"PUT", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({on})
  });
  if (on) { boxes = []; sel = -1; draw(); }
  rec.background = on;
  rec.labeled = false;
  rec.reviewed = true;
  rec.n = 0;
  rec.classes = [];
  const src = files.find(f => f.name === rec.name);
  if (src) {
    src.background = on;
    src.labeled = false;
    src.reviewed = true;
    src.n = 0;
    src.classes = [];
  }
  setStatus(rec);
  if (on) {
    rebuildView();
    show(idx);
  }
}

cv.addEventListener("mousedown", e => {
  e.preventDefault();
  if (e.button === 1) {
    pan = {cx:e.clientX, cy:e.clientY, sl:stage.scrollLeft, st:stage.scrollTop};
    return;
  }
  if (e.button !== 0) return;
  const r = cv.getBoundingClientRect();
  const x = e.clientX-r.left, y = e.clientY-r.top;
  sel = hit(x,y);
  if (sel >= 0) { draw(); return; }
  drag = {x0:x,y0:y,x1:x,y1:y};
});
cv.addEventListener("mousemove", e => {
  if (pan) {
    stage.scrollLeft = pan.sl - (e.clientX - pan.cx);
    stage.scrollTop = pan.st - (e.clientY - pan.cy);
    return;
  }
  if (!drag) return;
  const r = cv.getBoundingClientRect();
  drag.x1 = e.clientX-r.left; drag.y1 = e.clientY-r.top;
  draw();
});
stage.addEventListener("wheel", e => {
  if (!e.ctrlKey && !e.metaKey) return;   // plain wheel keeps panning the frame
  e.preventDefault();
  setZoom(zoom * (e.deltaY < 0 ? ZOOM_STEP : 1/ZOOM_STEP), {cx:e.clientX, cy:e.clientY});
}, {passive:false});
window.addEventListener("mouseup", async () => {
  if (pan) { pan = null; return; }
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
$("bg").onclick = () => markBackground();
$("zin").onclick = () => setZoom(zoom * ZOOM_STEP);
$("zout").onclick = () => setZoom(zoom / ZOOM_STEP);
$("z11").onclick = () => setZoom(natW / baseW);
$("zfit").onclick = () => setZoom(1);
$("mode").onchange = () => show(0);
$("clip").onchange = () => show(0);
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
  if (e.key==="b" || e.key==="B") { e.preventDefault(); markBackground(); }
  if (e.key==="+" || e.key==="=") { e.preventDefault(); setZoom(zoom * ZOOM_STEP); }
  if (e.key==="-" || e.key==="_") { e.preventDefault(); setZoom(zoom / ZOOM_STEP); }
  if (e.key==="0") { e.preventDefault(); setZoom(1); }
  if (e.key==="9") { e.preventDefault(); setZoom(natW / baseW); }
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


def _reviewed() -> set[str]:
    if not REVIEWED.exists():
        return set()
    return {ln.strip() for ln in REVIEWED.read_text(encoding="utf-8").splitlines() if ln.strip()}


def _mark_reviewed(name: str) -> None:
    names = _reviewed()
    names.add(Path(name).name)
    REVIEWED.write_text("\n".join(sorted(names)) + "\n", encoding="utf-8")


def _read_list(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _background() -> set[str]:
    return set(_read_list(BACKGROUND))


def _set_background(name: str, on: bool) -> None:
    names = _background()
    key = Path(name).name
    if on:
        names.add(key)
    else:
        names.discard(key)
    BACKGROUND.write_text("\n".join(sorted(names)) + "\n", encoding="utf-8")


def _priority_rank() -> dict[str, int]:
    return {Path(n).name: i for i, n in enumerate(_read_list(PRIORITY))}


def _background_candidates() -> set[str]:
    return {Path(n).name for n in _read_list(BACKGROUND_CANDIDATES)}


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


README_MARKER = "<!-- export stats below; edited by hand above -->"


def _write_generated_readme(generated: str) -> None:
    """Replace only the generated tail so the hand-written clip manifest survives exports."""
    path = DS / "README.md"
    head = (
        "# Aerial DJI Model B — hand boxes\n\n"
        "Label in the browser: `python scripts/label_aerial.py`\n"
        "Guide: `docs/labeling-guide-aerial.md`\n"
    )
    if path.exists():
        existing = path.read_text(encoding="utf-8")
        head = existing.split(README_MARKER)[0].rstrip("\n")
    path.write_text(f"{head}\n\n{README_MARKER}\n\n{generated}", encoding="utf-8")


def _cap_train_background(items: list[tuple[Path, list[dict], str]]) -> tuple[list, int]:
    """Trim train-split clean frames to BG_MAX_FRAC, spread evenly across clips.

    Clean frames arrive in bursts (one session over one clip), so a plain head-of-list cut
    would hand the whole background budget to a single clip.
    """
    labeled_imgs = 0
    bg_by_clip: dict[str, list[tuple[Path, list[dict], str]]] = defaultdict(list)
    for entry in items:
        img, boxes, split = entry
        if split != "train":
            continue
        if boxes:
            rare = any(int(b["cls"]) in RARE_CLASSES for b in boxes)
            labeled_imgs += RARE_OVERSAMPLE if rare else 1
        else:
            bg_by_clip[clip_of(img.name)].append(entry)

    total_bg = sum(len(v) for v in bg_by_clip.values())
    allowed = int(round(BG_MAX_FRAC * labeled_imgs / (1 - BG_MAX_FRAC)))
    if total_bg <= allowed:
        return items, 0

    clips = sorted(bg_by_clip)
    for c in clips:
        bg_by_clip[c].sort(key=lambda e: e[0].name)
    keep: set[str] = set()
    depth = 0
    while len(keep) < allowed:
        progressed = False
        for c in clips:
            if depth < len(bg_by_clip[c]) and len(keep) < allowed:
                keep.add(bg_by_clip[c][depth][0].name)
                progressed = True
        if not progressed:
            break
        depth += 1

    trimmed = [e for e in items if e[1] or e[2] != "train" or e[0].name in keep]
    return trimmed, total_bg - len(keep)


def export_yolo() -> str:
    frames = _frames()
    clean = _background()
    usable = [img for img in frames if _read_boxes(img.name) or img.name in clean]
    splits = assign_splits(
        [img.name for img in usable],
        test_prefix=TEST_PREFIX,
        val_tail_frac=VAL_TAIL_FRAC,
        guard_frames=GUARD_FRAMES,
    )
    items: list[tuple[Path, list[dict], str]] = []
    dropped = 0
    for img in usable:
        split = splits[img.name]
        if split == "drop":
            dropped += 1
            continue
        items.append((img, _read_boxes(img.name), split))
    if not any(boxes for _, boxes, _ in items):
        return "No labeled frames yet."
    items, bg_trimmed = _cap_train_background(items)

    for sub in ("images", "labels"):
        p = DS / sub
        if p.exists():
            shutil.rmtree(p)

    stats = {n: 0 for n in NAMES.values()}
    counts = {"train": 0, "val": 0, "test": 0}
    bg_counts = {"train": 0, "val": 0, "test": 0}
    oversampled = 0

    for img, boxes, split in items:
        img_dir = DS / "images" / split
        lbl_dir = DS / "labels" / split
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)

        copies = [img.name]
        rare = any(int(b["cls"]) in RARE_CLASSES for b in boxes)
        if rare and split == "train":
            copies += [f"{img.stem}_ov{k}{img.suffix}" for k in range(1, RARE_OVERSAMPLE)]
        for dest_name in copies:
            dest = Path(dest_name)
            shutil.copy2(img, img_dir / dest.name)
            label_dest = lbl_dir / (dest.stem + ".txt")
            if boxes:
                shutil.copy2(_label_path(img.name), label_dest)
            else:
                # Empty label file = YOLO background image (hard negative)
                label_dest.write_text("", encoding="utf-8")
        oversampled += len(copies) - 1

        counts[split] += len(copies)
        if not boxes:
            bg_counts[split] += 1
        for b in boxes:
            stats[NAMES[int(b["cls"])]] += len(copies)

    external_added = 0
    for src_root in EXTERNAL_TRAIN_SOURCES:
        src_img_dir = src_root / "images" / "train"
        src_lbl_dir = src_root / "labels" / "train"
        if not src_img_dir.exists():
            continue
        img_dir = DS / "images" / "train"
        lbl_dir = DS / "labels" / "train"
        img_dir.mkdir(parents=True, exist_ok=True)
        lbl_dir.mkdir(parents=True, exist_ok=True)
        for img in sorted(src_img_dir.iterdir()):
            if img.suffix.lower() not in EXTS:
                continue
            lbl = src_lbl_dir / f"{img.stem}.txt"
            if not lbl.exists():
                continue
            shutil.copy2(img, img_dir / img.name)
            shutil.copy2(lbl, lbl_dir / lbl.name)
            counts["train"] += 1
            external_added += 1
            boxes_text = lbl.read_text(encoding="utf-8").strip()
            if not boxes_text:
                bg_counts["train"] += 1
                continue
            for line in boxes_text.splitlines():
                stats[NAMES[int(line.split()[0])]] += 1

    manifest = {
        split: split_manifest_sha(DS / "images" / split)
        for split in ("train", "val", "test")
    }
    (ROOT / "configs" / "model_b_aerial.data.yaml").write_text(
        "path: data/datasets/model_b_aerial\n"
        "train: images/train\n"
        "val: images/val\n"
        f"# hold-out (scripts/eval_aerial.py): {TEST_PREFIX} → images/test\n"
        "test: images/test\n"
        f"# split_manifest train={manifest['train']}\n"
        f"# split_manifest val={manifest['val']}\n"
        f"# split_manifest test={manifest['test']}\n\n"
        "names:\n"
        "  0: pothole\n"
        "  1: road_crack\n"
        "  2: manhole\n"
        "  3: road_damage\n",
        encoding="utf-8",
    )
    msg = (
        f"export train={counts['train']} val={counts['val']} test={counts['test']} "
        f"(bg train={bg_counts['train']} val={bg_counts['val']} test={bg_counts['test']}, "
        f"bg over cap dropped={bg_trimmed}, rare copies={oversampled}, "
        f"guard dropped={dropped}, external train added={external_added}) boxes={stats}"
    )
    generated = (
        f"Split is clip-based: `{TEST_PREFIX}` = hold-out test; every other clip is cut on "
        f"its timeline (last {int(VAL_TAIL_FRAC * 100)}% to val, {GUARD_FRAMES} frame(s) at "
        "the cut dropped).\n"
        "Frames listed in `background.txt` export as empty labels (hard negatives), capped at "
        f"{int(BG_MAX_FRAC * 100)}% of the train split and spread across clips.\n"
        f"Train frames holding pothole/road_crack are copied {RARE_OVERSAMPLE}x.\n\n"
        f"{msg}\n"
    )
    _write_generated_readme(generated)
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

    def handle_one_request(self) -> None:
        try:
            super().handle_one_request()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True

    def do_GET(self) -> None:  # noqa: N802
        path = unquote(urlparse(self.path).path)
        if path == "/":
            self._send(200, HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/list":
            done = _reviewed()
            clean = _background()
            rank = _priority_rank()
            candidates = _background_candidates()
            rows = []
            for p in _frames():
                boxes = _read_boxes(p.name)
                rows.append(
                    {
                        "name": p.name,
                        "labeled": bool(boxes),
                        "reviewed": p.name in done or bool(boxes),
                        "background": p.name in clean,
                        "bgCandidate": p.name in candidates,
                        "rank": rank.get(p.name, -1),
                        "classes": sorted({int(b["cls"]) for b in boxes}),
                        "n": len(boxes),
                    }
                )
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
        n = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(n) or b"{}")

        if path.startswith("/api/background/"):
            name = Path(path.split("/", 3)[-1]).name
            on = bool(payload.get("on", True))
            if on:
                _write_boxes(name, [])
            _set_background(name, on)
            _mark_reviewed(name)
            self._send(200, b'{"ok":true}', "application/json")
            return

        if not path.startswith("/api/labels/"):
            self._send(404, b"not found", "text/plain")
            return
        name = Path(path.split("/", 3)[-1]).name
        boxes = payload.get("boxes") or []
        _write_boxes(name, boxes)
        if boxes:
            # A drawn box overrides an earlier "clean frame" call
            _set_background(name, False)
            # Autosave fires on every navigation, so a box-less save means the frame
            # was skipped, not decided. Only a box or a B press retires it from the queue.
            _mark_reviewed(name)
        self._send(200, b'{"ok":true}', "application/json")


def extract_frames(video: Path, prefix: str, every_sec: float, max_width: int) -> int:
    import cv2

    if not video.exists():
        raise SystemExit(f"Missing video: {video}")
    cap = cv2.VideoCapture(str(video))
    if not cap.isOpened():
        raise SystemExit(f"Cannot open video (still downloading?): {video}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    n_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    dur_ms = (n_frames / fps) * 1000.0 if fps and n_frames else 0.0
    FRAMES.mkdir(parents=True, exist_ok=True)
    n_ok = 0
    t_ms = 0.0
    step_ms = max(1.0, every_sec * 1000.0)
    while t_ms <= dur_ms + 1:
        cap.set(cv2.CAP_PROP_POS_MSEC, t_ms)
        ok, frame = cap.read()
        if not ok:
            break
        h, w = frame.shape[:2]
        if w > max_width:
            scale = max_width / w
            frame = cv2.resize(
                frame,
                (max_width, int(h * scale)),
                interpolation=cv2.INTER_AREA,
            )
        dest = FRAMES / f"{prefix}_{int(round(t_ms)):07d}ms.jpg"
        cv2.imwrite(str(dest), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
        n_ok += 1
        print(f"  {dest.name}", flush=True)
        t_ms += step_ms
    cap.release()
    print(f"extracted {n_ok} frames → {FRAMES} prefix={prefix}")
    return n_ok


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
    p.add_argument("--extract", default=None, help="Video path to sample into raw_frames/")
    p.add_argument("--prefix", default="clip", help="Filename prefix for --extract")
    p.add_argument("--every-sec", type=float, default=1.0, help="Keyframe interval")
    p.add_argument("--max-width", type=int, default=1920)
    args = p.parse_args()
    if args.export:
        print(export_yolo())
        return 0
    if args.extract:
        extract_frames(Path(args.extract).expanduser(), args.prefix, args.every_sec, args.max_width)
        return 0
    serve(args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
