import {makeReel, Tr} from "../series/engine";
import {GEnd, GHook, GMap, GR1, GR2, GR3, GScore, TIMER} from "./scenes";
import TL from "./timeline.json";

/** "Can you beat the drone?" — a 3-round spot-it game on our own footage. */
const TRANSITIONS: Record<string, Tr> = {
  irisTimer: {kind: "iris", x: TIMER.x, y: TIMER.y, r0: TIMER.size / 2, dur: 22},
  whip: {kind: "whip", dur: 14, axis: "x"},
  push: {kind: "whip", dur: 16, axis: "y"},
  zoom: {kind: "zoom", dur: 14},
  irisCenter: {kind: "iris", x: 540, y: 1140, r0: 0, dur: 20},
};

const reel = makeReel({
  timeline: TL,
  transitions: TRANSITIONS,
  components: {hook: GHook, r1: GR1, r2: GR2, r3: GR3, score: GScore, map: GMap, end: GEnd},
  audioDir: "game",
});

export const BeatTheDrone = reel.Reel;
export const GAME_TOTAL = reel.total;
export const GAME_FPS = reel.fps;
