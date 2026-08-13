import {parseMedia} from "@remotion/media-parser";
import {nodeReader} from "@remotion/media-parser/node";

const src = process.argv[2];
const r = await parseMedia({
  src,
  fields: {durationInSeconds: true, audioCodec: true},
  reader: nodeReader,
});
console.log(JSON.stringify({seconds: r.durationInSeconds, frames30: Math.ceil(r.durationInSeconds * 30), codec: r.audioCodec}));
