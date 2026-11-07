import {makeReel, Tr} from "../series/engine";
import {HOLE, MA1, MA2, MA3, MClose, MEnd, ML1, ML2, ML3, MPayoff, MPile, MTurn, SIGN} from "./scenes";
import TL from "./timeline.json";

/** "Dear Mayor" — dramatised resident letters answered by real footage from our Kartal test flight. */
const TRANSITIONS: Record<string, Tr> = {
  irisHole: {kind: "iris", x: HOLE.x, y: HOLE.y, r0: HOLE.r * 0.95, dur: 20},
  whip: {kind: "whip", dur: 14, axis: "x"},
  push: {kind: "whip", dur: 16, axis: "y"},
  zoom: {kind: "zoom", dur: 14},
  irisCenter: {kind: "iris", x: 540, y: 960, r0: 0, dur: 20},
  irisSign: {kind: "iris", x: SIGN.x, y: SIGN.y, r0: 43, dur: 20},
};

const reel = makeReel({
  timeline: TL,
  transitions: TRANSITIONS,
  components: {l1: ML1, a1: MA1, l2: ML2, a2: MA2, l3: ML3, a3: MA3, pile: MPile, turn: MTurn, payoff: MPayoff, close: MClose, end: MEnd},
  audioDir: "mayor",
  musicGain: 0.55,
});

export const DearMayor = reel.Reel;
export const MAYOR_TOTAL = reel.total;
export const MAYOR_FPS = reel.fps;
