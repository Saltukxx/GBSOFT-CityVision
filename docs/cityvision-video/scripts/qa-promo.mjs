// Renders stills of the English promo into qa-promo/ and tiles them into sheets.
//   node scripts/qa-promo.mjs               -> 3 frames per scene
//   node scripts/qa-promo.mjs 120 340 900   -> specific frames
import {bundle} from "@remotion/bundler";
import {renderStill, selectComposition} from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const PROJECT = process.env.QA_PROJECT || "promo";
const OUT = path.join(root, `qa-${PROJECT}`);
const TL = JSON.parse(fs.readFileSync(path.join(root, `src/${PROJECT}/timeline.json`), "utf8"));
const BEAT = 3600 / TL.bpm;
const bf = (b) => Math.floor(b * BEAT + 0.5);
let beats = 0;
const scenes = TL.scenes.map(([id, n]) => { const from = bf(beats); beats += n; return {id, from, dur: bf(beats) - from}; });
const frames = process.argv.slice(2).length
  ? process.argv.slice(2).map(Number)
  : scenes.flatMap((s) => [s.from + Math.round(s.dur * 0.3), s.from + Math.round(s.dur * 0.6), s.from + s.dur - 4]);

fs.mkdirSync(OUT, {recursive: true});
for (const f of fs.readdirSync(OUT)) fs.rmSync(path.join(OUT, f));
const serveUrl = await bundle({entryPoint: path.join(root, "src/index.ts")});
const composition = await selectComposition({serveUrl, id: {promo: "CityVision-Promo-EN-QA", howto: "CityVision-HowItWorks-QA", game: "CityVision-BeatTheDrone-QA", mayor: "CityVision-DearMayor-QA", eyes: "CityVision-DifferentEyes-QA", wrapped: "CityVision-Wrapped-QA"}[PROJECT]});
for (const frame of frames) {
  const sc = scenes.filter((s) => s.from <= frame).pop();
  const scale = Number(process.env.QA_SCALE || 0.5);
  const output = path.join(OUT, `f${String(frame).padStart(4, "0")}-${sc.id}.png`);
  await renderStill({composition, serveUrl, output, frame, imageFormat: "png", scale});
  console.log("frame", frame, sc.id);
}
