import React from "react";
import {useCurrentFrame} from "remotion";
import {makeReel, Tr} from "../series/engine";
import {WAir, WBest, WEnd, WFrames, WHuman, WIntro, WIssues, WOutro, WPeople, WSeen, WTop, WTossed} from "./scenes";
import TL from "./timeline.json";

/** "CityVision Wrapped" — our test flights' real numbers, Wrapped-style. */
const TRANSITIONS: Record<string, Tr> = {
  push: {kind: "whip", dur: 14, axis: "x"},
  irisCenter: {kind: "iris", x: 540, y: 960, r0: 0, dur: 20},
};

let CARDS: {from: number; dur: number}[] = [];

/** Story-style progress segments, one per card (intro → outro). */
const Progress: React.FC = () => {
  const f = useCurrentFrame();
  if (!CARDS.length || f >= CARDS[CARDS.length - 1].from + CARDS[CARDS.length - 1].dur) return null;
  return (
    <div style={{position: "absolute", left: 40, right: 40, top: 150, display: "flex", gap: 8, padding: "10px 12px", borderRadius: 999, background: "rgba(8,21,48,0.28)"}}>
      {CARDS.map((c, i) => {
        const p = Math.max(0, Math.min(1, (f - c.from) / c.dur));
        return (
          <div key={i} style={{flex: 1, height: 6, borderRadius: 3, background: "rgba(255,255,255,0.35)", overflow: "hidden"}}>
            <div style={{width: `${p * 100}%`, height: "100%", background: "#fff"}} />
          </div>
        );
      })}
    </div>
  );
};

const reel = makeReel({
  timeline: TL,
  transitions: TRANSITIONS,
  components: {intro: WIntro, air: WAir, frames: WFrames, seen: WSeen, issues: WIssues, top: WTop, best: WBest, tossed: WTossed, human: WHuman, people: WPeople, outro: WOutro, end: WEnd},
  audioDir: "wrapped",
  overlay: Progress,
});
CARDS = reel.scenes.filter((s) => s.id !== "end").map((s) => ({from: s.from, dur: s.dur}));

export const CityVisionWrapped = reel.Reel;
export const WRAPPED_TOTAL = reel.total;
export const WRAPPED_FPS = reel.fps;
