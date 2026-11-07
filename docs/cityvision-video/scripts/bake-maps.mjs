// Bakes public/maps/<name>-{light,navy}.svg → .png at full resolution.
//   node scripts/bake-maps.mjs                         (kartal, src/howto/map.json)
//   node scripts/bake-maps.mjs kadikoy src/mayor/map.json
import {bundle} from "@remotion/bundler";
import {renderStill, selectComposition} from "@remotion/renderer";
import fs from "node:fs";
import path from "node:path";
import {fileURLToPath} from "node:url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const [name = "kartal", metaPath = "src/howto/map.json"] = process.argv.slice(2);
const meta = JSON.parse(fs.readFileSync(path.join(root, metaPath), "utf8"));
const serveUrl = await bundle({entryPoint: path.join(root, "src/index.ts")});
for (const theme of ["light", "navy"]) {
  const inputProps = {src: `maps/${name}-${theme}.svg`};
  const composition = await selectComposition({serveUrl, id: "MapBake", inputProps});
  await renderStill({
    composition: {...composition, width: meta.w, height: meta.h},
    serveUrl,
    inputProps,
    output: path.join(root, `public/maps/${name}-${theme}.png`),
    imageFormat: "png",
  });
  console.log("baked", theme);
}
