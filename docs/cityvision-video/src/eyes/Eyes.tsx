import {makeReel, Tr} from "../series/engine";
import {EEnd, EIntro, EM1, EM2, EM3, EM4, EMap, ETally} from "./scenes";
import TL from "./timeline.json";

/** "Same street. Different eyes." — a passer-by's glance vs CityVision, on our own footage. */
const TRANSITIONS: Record<string, Tr> = {
  irisCenter: {kind: "iris", x: 540, y: 960, r0: 0, dur: 20},
};

const reel = makeReel({
  timeline: TL,
  transitions: TRANSITIONS,
  components: {intro: EIntro, m1: EM1, m2: EM2, m3: EM3, m4: EM4, tally: ETally, map: EMap, end: EEnd},
  audioDir: "eyes",
  musicGain: 0.55,
});

export const DifferentEyes = reel.Reel;
export const EYES_TOTAL = reel.total;
export const EYES_FPS = reel.fps;
