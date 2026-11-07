import React from "react";
import {Sequence, useCurrentFrame} from "remotion";
import {Ball, BallLabel, prog} from "../promo/kit";
import {makeReel, Tr} from "../series/engine";
import {HFly, HHook, HMerge, HPin, HSpot, PIN_SEL_SCREEN, TIMER} from "./scenes/A";
import {APPROVE_BTN, FIX_CHECK, HApprove, HBlur, HEnd, HFix, HRecap} from "./scenes/B";
import TL from "./timeline.json";

/** Every iris opens from an object in the outgoing scene (timer ball, pin, button, check). */
const TRANSITIONS: Record<string, Tr> = {
  irisTimer: {kind: "iris", x: TIMER.x, y: TIMER.y, r0: TIMER.size / 2, dur: 22},
  whip: {kind: "whip", dur: 14, axis: "x"},
  push: {kind: "whip", dur: 16, axis: "y"},
  zoom: {kind: "zoom", dur: 14},
  irisPin: {kind: "iris", x: PIN_SEL_SCREEN.x, y: PIN_SEL_SCREEN.y - 50, r0: 30, dur: 20},
  irisApprove: {kind: "iris", x: APPROVE_BTN.x, y: APPROVE_BTN.y, r0: 48, dur: 20},
  irisCheck: {kind: "iris", x: FIX_CHECK.x, y: FIX_CHECK.y, r0: 50, dur: 20},
  irisCenter: {kind: "iris", x: 540, y: 960, r0: 0, dur: 20},
};

let timerSpan = {from: 0, to: 0};

/** The "30 seconds" ball: counts down from the first step to the end card. */
const Timer: React.FC = () => {
  const f = useCurrentFrame();
  const span = timerSpan.to - timerSpan.from;
  const left = Math.max(0, Math.ceil(30 - (30 * f) / span));
  const bump = f % 60 < 8 ? 1 + 0.06 * (1 - (f % 60) / 8) : 1;
  const out = prog(f, span + 4, span + 16);
  const size = TIMER.size * bump * (1 - out);
  return (
    <Ball size={size} x={TIMER.x} y={TIMER.y} shadow={false}>
      <BallLabel size={size * 0.36}>{left}</BallLabel>
    </Ball>
  );
};

const TimerLayer: React.FC = () => (
  <Sequence from={timerSpan.from} durationInFrames={timerSpan.to - timerSpan.from + 20} name="timer">
    <Timer />
  </Sequence>
);

const reel = makeReel({
  timeline: TL,
  transitions: TRANSITIONS,
  components: {
    hook: HHook,
    fly: HFly,
    spot: HSpot,
    pin: HPin,
    merge: HMerge,
    blur: HBlur,
    approve: HApprove,
    fix: HFix,
    recap: HRecap,
    end: HEnd,
  },
  audioDir: "howto",
  overlay: TimerLayer,
});

const byId = Object.fromEntries(reel.scenes.map((s) => [s.id, s]));
timerSpan = {from: byId.fly.from, to: byId.end.from};

export const HowItWorks = reel.Reel;
export const HOWTO_TOTAL = reel.total;
export const HOWTO_FPS = reel.fps;
export const HOWTO_SCENES = reel.scenes;
