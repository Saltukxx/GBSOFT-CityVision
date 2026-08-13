/**
 * QA kontak sayfası.
 *
 * Tek bir bundle üzerinden çok sayıda kare basar ve yan yana dizen bir
 * HTML kontak sayfası üretir. Amaç: her render sonrası videoyu baştan sona
 * izlemeden çakışma / boşluk / taşma hatalarını yakalamak.
 *
 *   node scripts/qa-stills.mjs                 -> varsayılan kare seti
 *   node scripts/qa-stills.mjs 100 250 900     -> istenen kareler
 */
import {bundle} from "@remotion/bundler";
import {renderStill, selectComposition} from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const OUT = path.join(root, "qa");
const COMP = "CityVision-Reels-Vertical-Sessiz";

// Sahne başlangıçları (timing.ts ile aynı) + her sahnenin ortası ve sonu.
const SCENE_START = [0, 222, 413, 566, 809, 1120, 1316, 1567];
const TOTAL = 1830;

const defaultFrames = SCENE_START.flatMap((start, i) => {
  const end = (SCENE_START[i + 1] ?? TOTAL) - 1;
  const mid = Math.round((start + end) / 2);
  return [start + 34, mid, end - 10];
}).filter((f) => f >= 0 && f < TOTAL);

const frames = process.argv.slice(2).length
  ? process.argv.slice(2).map(Number)
  : [...new Set(defaultFrames)].sort((a, b) => a - b);

fs.rmSync(OUT, {recursive: true, force: true});
fs.mkdirSync(OUT, {recursive: true});

console.log("bundle...");
const serveUrl = await bundle({entryPoint: path.join(root, "src/index.ts")});
const composition = await selectComposition({serveUrl, id: COMP});

for (const frame of frames) {
  const output = path.join(OUT, `f${String(frame).padStart(4, "0")}.png`);
  await renderStill({composition, serveUrl, output, frame, imageFormat: "png"});
  console.log("  kare", frame);
}

const sceneOf = (f) => SCENE_START.filter((s) => s <= f).length;
const cards = frames
  .map(
    (f) => `<figure>
    <img src="f${String(f).padStart(4, "0")}.png" alt="kare ${f}">
    <figcaption>S0${sceneOf(f)} · kare ${f} · ${(f / 30).toFixed(2)} sn</figcaption>
  </figure>`,
  )
  .join("\n  ");

fs.writeFileSync(
  path.join(OUT, "index.html"),
  `<!doctype html><meta charset="utf-8"><title>City Vision — QA</title>
<style>
  body{margin:0;padding:28px;background:#0b0f16;color:#dbe4f0;font:14px/1.5 ui-sans-serif,system-ui}
  h1{font-size:16px;letter-spacing:2px;font-weight:600;margin:0 0 22px}
  .sheet{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:18px}
  figure{margin:0}
  img{width:100%;display:block;border:1px solid #23324a}
  figcaption{margin-top:7px;font-size:12px;color:#7d8ea6;font-family:ui-monospace,Menlo,monospace}
</style>
<h1>CITY VISION — REEL QA · ${frames.length} KARE</h1>
<div class="sheet">
  ${cards}
</div>`,
);

console.log(`\n${frames.length} kare -> ${path.relative(process.cwd(), OUT)}/index.html`);
process.exit(0);
