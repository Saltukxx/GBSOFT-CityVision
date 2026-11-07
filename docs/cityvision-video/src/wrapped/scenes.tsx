import React from "react";
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from "remotion";
import HFOOT from "../howto/footage.json";
import {Ball, BallColor, F, inOut, K, lerp, NavyBg, prog, rand, usePop} from "../promo/kit";
import {EndCard} from "../series/endcard";
import S from "./stats.json";
import W from "./vo_words.json";

/** "CityVision Wrapped" — every number comes from stats.json (our own flights' pipeline output). */
const WORDS = W as unknown as Record<string, [string, number][]>;
const w = (scene: string, word: string) => {
  const hit = WORDS[scene].find(([x]) => x === word);
  if (!hit) throw new Error(`VO word not found: ${scene}/${word}`);
  return hit[1];
};
const fmt = (n: number) => Math.round(n).toLocaleString("en-US");
const NAVY = K.navyText;

/* ───────── card kit ───────── */
const Bg: React.FC<{c: string}> = ({c}) => (
  <AbsoluteFill style={{background: c}}>
    <AbsoluteFill style={{background: "radial-gradient(90% 60% at 50% 35%, rgba(255,255,255,0.14), rgba(0,0,0,0) 60%), radial-gradient(80% 50% at 50% 110%, rgba(0,0,0,0.18), rgba(0,0,0,0) 70%)"}} />
  </AbsoluteFill>
);

const Label: React.FC<{text: string; color: string; at?: number; y?: number}> = ({text, color, at = 0, y = 330}) => {
  const f = useCurrentFrame();
  const p = prog(f, at, at + 14);
  return (
    <div style={{position: "absolute", left: 0, right: 0, top: y, textAlign: "center", fontFamily: F.mono, fontSize: 30, letterSpacing: 7, color, opacity: p, transform: `translateY(${(1 - p) * 14}px)`}}>
      {text}
    </div>
  );
};

/** Big number that counts up while it is being said. */
const Big: React.FC<{value: number; from: number; to: number; color: string; y: number; size?: number; render?: (v: number) => string}> = ({value, from, to, color, y, size = 300, render = fmt}) => {
  const f = useCurrentFrame();
  const pop = usePop();
  const v = value * prog(f, from, to, inOut);
  const settle = pop(f, to - 2, {damping: 9, stiffness: 260});
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: y,
        textAlign: "center",
        fontFamily: F.sans,
        fontWeight: 900,
        fontSize: size,
        letterSpacing: -size * 0.05,
        lineHeight: 1,
        color,
        fontVariantNumeric: "tabular-nums",
        opacity: prog(f, from - 6, from + 4),
        transform: `scale(${f >= to - 2 ? 0.94 + 0.06 * settle : 1})`,
      }}
    >
      {render(v)}
    </div>
  );
};

const Line: React.FC<{text: string; color: string; at: number; y: number; size?: number}> = ({text, color, at, y, size = 76}) => {
  const f = useCurrentFrame();
  const p = prog(f, at - 2, at + 16);
  return (
    <div style={{position: "absolute", left: 40, right: 40, top: y, textAlign: "center", fontFamily: F.serif, fontStyle: "italic", fontSize: size, lineHeight: 1.05, color, opacity: p, transform: `translateY(${(1 - p) * 24}px)`, filter: p < 1 ? `blur(${(1 - p) * 8}px)` : undefined}}>
      {text}
    </div>
  );
};

/* ════════ intro: a teaser burst of the real numbers, then "Our flights, Wrapped." ════════ */
const FLASH = 15.65; // half a beat at 115 BPM
export const WIntro: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const flashes: [string, string, string][] = [
    ["#FF5A1F", "#fff", `${Math.floor(S.seconds / 60)}:${String(S.seconds % 60).padStart(2, "0")}`],
    ["#F4F5F8", NAVY, fmt(S.frames)],
    ["#0D1F48", K.teal, fmt(S.sightings)],
    ["#0FB5C8", "#fff", fmt(S.issues)],
    ["#F5B300", NAVY, `${Math.round(S.best.confidence * 100)}%`],
    ["#E23A8C", "#fff", fmt(S.rejected)],
    ["#7C5CFF", "#fff", fmt(S.people)],
    ["#F4F5F8", K.green, fmt(S.review)],
  ];
  const k = Math.floor(f / FLASH);
  const lf = f - k * FLASH;
  if (k < flashes.length) {
    const [bg, fg, txt] = flashes[k];
    const z = 1.25 - 0.25 * prog(lf, 0, FLASH, (x) => x);
    return (
      <AbsoluteFill style={{background: bg}}>
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 760,
            textAlign: "center",
            fontFamily: F.sans,
            fontWeight: 900,
            fontSize: 320,
            letterSpacing: -16,
            lineHeight: 1,
            color: fg,
            transform: `scale(${z}) rotate(${(k % 2 ? 1 : -1) * 4}deg)`,
            fontVariantNumeric: "tabular-nums",
          }}
        >
          {txt}
        </div>
      </AbsoluteFill>
    );
  }
  const t0 = flashes.length * FLASH;
  const g = f - t0; // scene time after the burst
  const wr = w("intro", "wrapped");
  const burst = prog(f, wr - 4, wr + 16, inOut);
  const ball = pop(f, t0 + 2, {damping: 9, stiffness: 170});
  return (
    <AbsoluteFill>
      <NavyBg glow="rgba(255,90,31,0.18)" />
      <div style={{position: "absolute", left: 0, right: 0, top: 560, textAlign: "center", fontFamily: F.sans, fontWeight: 900, fontSize: 112, letterSpacing: -4, color: "#fff", opacity: prog(f, w("intro", "our") - 2, w("intro", "our") + 10), transform: `translateY(${(1 - prog(f, w("intro", "our") - 2, w("intro", "our") + 16)) * 30}px)`}}>
        Our flights,
      </div>
      {/* the gift: one orange ball, wrapped in a ribbon — it bursts into the series colours */}
      {burst < 1 ? (
        <div style={{position: "absolute", left: 540 - 170, top: 1020 - 170, width: 340, height: 340, transform: `scale(${ball * (1 + burst * 0.4)})`, opacity: 1 - burst}}>
          <Ball size={340} x={170} y={170} shadow={false} />
          <div style={{position: "absolute", left: 150, top: 0, width: 40, height: 340, background: "#fff", borderRadius: 8, opacity: 0.92}} />
          <div style={{position: "absolute", left: 0, top: 150, width: 340, height: 40, background: "#fff", borderRadius: 8, opacity: 0.92}} />
          <div style={{position: "absolute", left: 120, top: -54, width: 100, height: 70, border: "16px solid #fff", borderRadius: "50% 50% 10% 10%", opacity: 0.92, transform: `rotate(${Math.sin(g / 5) * 6}deg)`}} />
        </div>
      ) : null}
      {(["orange", "teal", "pink", "yellow", "purple", "green", "orange", "teal"] as BallColor[]).map((c, i) => {
        const a = (i / 8) * Math.PI * 2 + 0.4;
        const d = burst * (300 + rand(i) * 200);
        const s = (60 + rand(i + 3) * 70) * Math.min(1, burst * 3) * (1 - prog(f, wr + 40, wr + 70) * 0.3);
        return <Ball key={i} size={s} x={540 + Math.cos(a) * d * 1.1} y={Math.max(780, 1040 + Math.sin(a) * d * 0.9) + Math.sin((f + i * 9) / 14) * 8} color={c} shadow={false} />;
      })}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 860,
          textAlign: "center",
          fontFamily: F.serif,
          fontStyle: "italic",
          fontSize: 270,
          lineHeight: 1,
          color: K.orange,
          transform: `scale(${pop(f, wr - 2, {damping: 8, stiffness: 220})}) rotate(-4deg)`,
          textShadow: "0 20px 60px rgba(0,0,0,0.35)",
        }}
      >
        Wrapped.
      </div>
    </AbsoluteFill>
  );
};

/* ════════ time in the air ════════ */
export const WAir: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const total = S.seconds;
  const t = prog(f, 60, 150, (x) => x);
  return (
    <AbsoluteFill>
      <Bg c="#FF5A1F" />
      <Label text="TIME IN THE AIR" color="rgba(255,255,255,0.85)" />
      <Big value={total} from={w("air", "six") - 4} to={w("air", "minutes") + 12} color="#fff" y={420} size={290} render={(v) => `${Math.floor(v / 60)}:${String(Math.floor(v % 60)).padStart(2, "0")}`} />
      <Line text={`${S.flights} flights · one evening`} color="#fff" at={w("air", "four")} y={730} />
      <div style={{position: "absolute", left: 0, right: 0, top: 900, display: "flex", justifyContent: "center", gap: 18}}>
        {S.flightList.map((fl, i) => (
          <div
            key={fl.start}
            style={{
              transform: `scale(${pop(f, w("air", "flights") + i * 6, {damping: 11})})`,
              padding: "16px 24px",
              borderRadius: 999,
              background: "rgba(255,255,255,0.18)",
              border: "2px solid rgba(255,255,255,0.4)",
              fontFamily: F.mono,
              fontSize: 30,
              color: "#fff",
            }}
          >
            {fl.start}
          </div>
        ))}
      </div>
      {/* the drone crossing with its trail */}
      <svg width={1080} height={1920} style={{position: "absolute", inset: 0}}>
        <path d="M-60 1360 C 260 1200, 600 1500, 1140 1280" fill="none" stroke="rgba(255,255,255,0.6)" strokeWidth={6} strokeDasharray="18 18" strokeDashoffset={-f * 3} />
      </svg>
      <div style={{position: "absolute", left: lerp(-240, 1240, t) - 120, top: 1300 + Math.sin(t * Math.PI * 2) * 60 - 80, transform: `rotate(${Math.sin(f / 8) * 4}deg)`}}>
        <svg width="260" height="116" viewBox="0 0 180 80">
          {[20, 160].map((cx) => (
            <g key={cx}>
              <ellipse cx={cx} cy="14" rx={26 * Math.abs(Math.cos(f * 0.9))} ry="4" fill="#fff" opacity="0.8" />
              <rect x={cx - 3} y="14" width="6" height="16" fill="#fff" />
            </g>
          ))}
          <path d="M20 30 L160 30" stroke="#fff" strokeWidth="8" strokeLinecap="round" />
          <rect x="58" y="22" width="64" height="30" rx="12" fill="#fff" />
          <circle cx="90" cy="58" r="10" fill="#fff" />
        </svg>
      </div>
    </AbsoluteFill>
  );
};

/* ════════ frames filmed ════════ */
export const WFrames: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  return (
    <AbsoluteFill>
      <Bg c="#F4F5F8" />
      <Label text="FRAMES FILMED" color="rgba(14,27,61,0.6)" />
      <Big value={S.frames} from={w("frames", "ten") - 2} to={w("frames", "frames")} color={NAVY} y={420} size={250} />
      <div style={{position: "absolute", left: 60, right: 60, top: 760, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, transform: `translateY(${-prog(f, 0, 188, (x) => x) * 80}px)`}}>
        {Array.from({length: 24}, (_, i) => {
          const p = pop(f, 4 + i * 3, {damping: 12, stiffness: 220});
          return (
            <div key={i} style={{aspectRatio: "16 / 9", borderRadius: 14, overflow: "hidden", transform: `scale(${p}) rotateY(${(1 - Math.min(1, p)) * 90}deg)`, boxShadow: "0 8px 20px rgba(14,27,61,0.15)"}}>
              <Img src={staticFile(`wrapped/mosaic/${String(i).padStart(2, "0")}.jpg`)} style={{width: "100%", height: "100%", objectFit: "cover"}} />
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ════════ sightings ════════ */
export const WSeen: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const bc = S.sightingsByClass;
  const chips: [string, number, string][] = [
    ["road damage", bc.road_damage, K.teal],
    ["pothole", bc.pothole, K.orange],
    ["crack", bc.road_crack, K.pink],
  ];
  return (
    <AbsoluteFill>
      <NavyBg glow="rgba(15,181,200,0.16)" />
      {/* a rain of little detection boxes */}
      {Array.from({length: 90}, (_, i) => {
        const at = 8 + i * 1.2;
        const p = pop(f, at, {damping: 12, stiffness: 260});
        const x = rand(i * 3 + 1) * 1000 + 40;
        const y = rand(i * 5 + 2) * 1700 + 100;
        if (y > 300 && y < 1250 && x > 120 && x < 960) return null;
        return <div key={i} style={{position: "absolute", left: x, top: y, width: 46, height: 32, border: `3px solid ${[K.teal, K.orange, K.pink][i % 3]}`, borderRadius: 6, transform: `scale(${p})`, opacity: 0.55 * Math.min(1, p)}} />;
      })}
      <Label text="TIMES IT SPOTTED DAMAGE" color="rgba(255,255,255,0.7)" />
      <Big value={S.sightings} from={w("seen", "nine") - 2} to={w("seen", "times")} color={K.teal} y={420} />
      <Line text="and it never blinked." color="#fff" at={w("seen", "spotted")} y={770} />
      <div style={{position: "absolute", left: 0, right: 0, top: 920, display: "flex", justifyContent: "center", gap: 16, flexWrap: "wrap"}}>
        {chips.map(([name, n, c], i) => (
          <div key={name} style={{transform: `scale(${pop(f, w("seen", "spotted") + 10 + i * 6, {damping: 11})})`, display: "flex", alignItems: "center", gap: 12, padding: "14px 22px", borderRadius: 999, background: "rgba(255,255,255,0.1)", border: "1px solid rgba(255,255,255,0.2)", fontFamily: F.sans, fontWeight: 600, fontSize: 30, color: "#fff"}}>
            <div style={{width: 16, height: 16, borderRadius: 4, border: `3px solid ${c}`}} />
            {fmt(n)} {name}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/* ════════ merged into issues (waffle of 75) ════════ */
export const WIssues: React.FC = () => {
  const f = useCurrentFrame();
  const ic = S.issuesByClass;
  const cells: string[] = [...Array(ic.road_damage).fill(K.teal), ...Array(ic.pothole).fill(K.orange), ...Array(ic.road_crack).fill(K.pink)];
  const merge = prog(f, w("issues", "merged") - 4, w("issues", "seventy-five") + 10, inOut);
  const COLS = 15;
  const CELL = 56;
  const GAP = 8;
  const gx0 = 540 - (COLS * CELL + (COLS - 1) * GAP) / 2;
  return (
    <AbsoluteFill>
      <Bg c="#F4F5F8" />
      <Label text="MERGED INTO" color="rgba(14,27,61,0.6)" />
      <Big value={S.issues} from={w("issues", "seventy-five") - 4} to={w("issues", "seventy-five") + 16} color={K.orange} y={400} />
      <Line text="seen many times. logged once." color={NAVY} at={w("issues", "real")} y={730} size={70} />
      {cells.map((c, i) => {
        const col = i % COLS;
        const row = Math.floor(i / COLS);
        const tx = gx0 + col * (CELL + GAP);
        const ty = 900 + row * (CELL + GAP);
        // each issue gathers from scattered sightings
        const sx = rand(i * 7 + 1) * 1000 + 40;
        const sy = rand(i * 11 + 3) * 600 + 1150;
        const x = lerp(sx, tx, merge);
        const y = lerp(sy, ty, merge);
        return <div key={i} style={{position: "absolute", left: x, top: y, width: CELL, height: CELL, borderRadius: lerp(28, 12, merge), background: c, opacity: 0.25 + 0.75 * merge, transform: `scale(${lerp(0.4, 1, merge)})`}} />;
      })}
      <div style={{position: "absolute", left: 0, right: 0, top: 1260, display: "flex", justifyContent: "center", gap: 26, opacity: prog(f, w("issues", "issues"), w("issues", "issues") + 12)}}>
        {[
          ["road damage", ic.road_damage, K.teal],
          ["potholes", ic.pothole, K.orange],
          ["crack", ic.road_crack, K.pink],
        ].map(([n, v, c]) => (
          <div key={n as string} style={{display: "flex", alignItems: "center", gap: 10, fontFamily: F.sans, fontSize: 30, fontWeight: 600, color: NAVY}}>
            <div style={{width: 20, height: 20, borderRadius: 6, background: c as string}} />
            {v} {n}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

/* ════════ top category (bars, one hue, direct labels) ════════ */
export const WTop: React.FC = () => {
  const f = useCurrentFrame();
  const ic = S.issuesByClass;
  const rows: [string, number][] = [
    ["Road damage", ic.road_damage],
    ["Potholes", ic.pothole],
    ["Cracks", ic.road_crack],
  ];
  const max = ic.road_damage;
  const grow = prog(f, w("top", "road") - 10, w("top", "damage") + 20, inOut);
  return (
    <AbsoluteFill>
      <Bg c="#F5B300" />
      <Label text="TOP CATEGORY" color="rgba(14,27,61,0.7)" />
      <div style={{position: "absolute", left: 0, right: 0, top: 410, textAlign: "center", fontFamily: F.sans, fontWeight: 900, fontSize: 150, letterSpacing: -6, lineHeight: 0.95, color: NAVY}}>
        {["Road", "damage."].map((t, i) => {
          const at = i === 0 ? w("top", "road") : w("top", "damage");
          const p = prog(f, at - 2, at + 12);
          return (
            <div key={t} style={{opacity: p, transform: `translateY(${(1 - p) * 40}px)`}}>
              {t}
            </div>
          );
        })}
      </div>
      <div style={{position: "absolute", left: 110, right: 110, top: 820, display: "flex", flexDirection: "column", gap: 34}}>
        {rows.map(([name, v], i) => {
          const g = prog(grow, i * 0.15, i * 0.15 + 0.7);
          return (
            <div key={name}>
              <div style={{display: "flex", justifyContent: "space-between", fontFamily: F.sans, fontWeight: 700, fontSize: 36, color: NAVY, marginBottom: 10}}>
                <span>{name}</span>
                <span style={{fontVariantNumeric: "tabular-nums"}}>{Math.round(v * g)}</span>
              </div>
              <div style={{height: 46, borderRadius: 4, background: "rgba(14,27,61,0.12)"}}>
                <div style={{width: `${Math.max(1.2, (v / max) * 100) * g}%`, height: "100%", borderRadius: 4, background: NAVY}} />
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ════════ strongest find ════════ */
export const WBest: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const shot = HFOOT.pothole;
  const CW = 860;
  const CH = 640;
  const k = Math.max(CW / shot.w, CH / shot.h) * 1.25;
  const [x1, y1, x2, y2] = shot.box;
  const left = Math.min(0, Math.max(CW - shot.w * k, CW / 2 - ((x1 + x2) / 2) * k));
  const top = Math.min(0, Math.max(CH - shot.h * k, CH / 2 - ((y1 + y2) / 2) * k));
  const box = pop(f, w("best", "pothole") - 2, {damping: 10, stiffness: 260});
  return (
    <AbsoluteFill>
      <NavyBg glow="rgba(255,90,31,0.18)" />
      <Label text="STRONGEST FIND" color="rgba(255,255,255,0.7)" />
      <div style={{position: "absolute", left: 540 - CW / 2, top: 420, width: CW, height: CH, borderRadius: 36, overflow: "hidden", boxShadow: "0 40px 80px rgba(0,0,0,0.45)", transform: `scale(${pop(f, w("best", "find") - 6, {damping: 13})}) rotate(-2deg)`}}>
        <Img src={staticFile(shot.src)} style={{position: "absolute", left, top, width: shot.w * k, height: shot.h * k}} />
        <div style={{position: "absolute", left: x1 * k + left, top: y1 * k + top, width: (x2 - x1) * k, height: (y2 - y1) * k, border: `6px solid ${K.orange}`, borderRadius: 14, transform: `scale(${box})`, opacity: Math.min(1, box)}} />
        <div style={{position: "absolute", left: 24, top: 24, padding: "10px 18px", borderRadius: 999, background: "rgba(255,255,255,0.95)", fontFamily: F.sans, fontWeight: 800, fontSize: 28, color: NAVY}}>#1 · pothole</div>
      </div>
      <Big value={Math.round(S.best.confidence * 100)} from={w("best", "ninety-eight") - 4} to={w("best", "percent")} color={K.orange} y={1110} size={260} render={(v) => `${Math.round(v)}%`} />
      <Line text="sure. (we checked.)" color="#fff" at={w("best", "sure")} y={1390} size={66} />
    </AbsoluteFill>
  );
};

/* ════════ maybes thrown out ════════ */
export const WTossed: React.FC = () => {
  const f = useCurrentFrame();
  const out = w("tossed", "thrown");
  return (
    <AbsoluteFill>
      <Bg c="#E23A8C" />
      <Label text="MAYBES, THROWN OUT" color="rgba(255,255,255,0.85)" />
      <Big value={S.rejected} from={w("tossed", "three") - 2} to={w("tossed", "sixty-five") + 10} color="#fff" y={420} />
      <Line text="not sure? not logged." color="#fff" at={w("tossed", "maybes")} y={760} />
      {Array.from({length: 40}, (_, i) => {
        const x0 = 120 + (i % 8) * 110;
        const y0 = 940 + Math.floor(i / 8) * 80;
        const fall = prog(f, out - 10 + i * 0.8, out + 26 + i * 0.8, (t) => t * t);
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x0 + (rand(i) - 0.5) * 30,
              top: y0 + fall * 900,
              width: 70,
              height: 46,
              border: "3px dashed rgba(255,255,255,0.85)",
              borderRadius: 8,
              transform: `rotate(${fall * (rand(i + 9) - 0.5) * 240}deg)`,
              opacity: 1 - fall,
            }}
          />
        );
      })}
    </AbsoluteFill>
  );
};

/* ════════ flagged for a human ════════ */
export const WHuman: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  return (
    <AbsoluteFill>
      <Bg c="#F4F5F8" />
      <Label text="FLAGGED FOR A HUMAN" color="rgba(14,27,61,0.6)" />
      <Big value={S.review} from={w("human", "twelve") - 4} to={w("human", "twelve") + 18} color={K.green} y={420} />
      <Line text="a person makes the call." color={NAVY} at={w("human", "human")} y={760} />
      <div style={{position: "absolute", left: 0, right: 0, top: 960, height: 520}}>
        {Array.from({length: S.review}, (_, i) => {
          const p = pop(f, 10 + i * 4, {damping: 12, stiffness: 200});
          const a = (i - (S.review - 1) / 2) * 7;
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: 540 - 170,
                top: 40,
                width: 340,
                height: 420,
                borderRadius: 26,
                background: "#fff",
                boxShadow: "0 14px 30px rgba(14,27,61,0.16)",
                transformOrigin: "50% 120%",
                transform: `rotate(${a * Math.min(1, p)}deg) scale(${0.6 + 0.4 * Math.min(1, p)})`,
                opacity: Math.min(1, p),
                padding: 24,
              }}
            >
              <div style={{height: 180, borderRadius: 16, background: "linear-gradient(160deg, #7B808C, #4A4E58)"}} />
              <div style={{height: 18, width: "70%", borderRadius: 9, background: "#E6E9EF", marginTop: 24}} />
              <div style={{height: 14, width: "45%", borderRadius: 7, background: "#EEF0F4", marginTop: 14}} />
              <div style={{display: "flex", gap: 12, marginTop: 34}}>
                <div style={{flex: 1, height: 52, borderRadius: 999, border: "3px solid #D5D9E2"}} />
                <div style={{flex: 1, height: 52, borderRadius: 999, background: K.green}} />
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/* ════════ people, all blurred ════════ */
type Street = {src: string; w: number; h: number; regions: {kind: string; box: number[]}[]};
export const WPeople: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const st = HFOOT.street as Street;
  const CW = 860;
  const CH = 600;
  const k = Math.max(CW / st.w, CH / st.h);
  const ox = (CW - st.w * k) / 2;
  const oy = (CH - st.h * k) / 2;
  return (
    <AbsoluteFill>
      <Bg c="#7C5CFF" />
      <Label text="TIMES IT SAW A PERSON" color="rgba(255,255,255,0.85)" />
      <Big value={S.people} from={w("people", "over") - 4} to={w("people", "times")} color="#fff" y={420} size={280} />
      <div style={{position: "absolute", left: 540 - CW / 2, top: 760, width: CW, height: CH, borderRadius: 36, overflow: "hidden", boxShadow: "0 40px 80px rgba(30,10,90,0.4)", transform: `scale(${pop(f, 10, {damping: 13})}) rotate(2deg)`}}>
        <Img src={staticFile(st.src)} style={{position: "absolute", left: ox, top: oy, width: st.w * k, height: st.h * k}} />
        {st.regions
          .filter((r) => r.kind === "person")
          .map((r, i) => {
            const p = pop(f, w("people", "every") + i * 5, {damping: 10, stiffness: 260});
            const [a, b, c, d] = r.box.map((v) => v * k);
            return <div key={i} style={{position: "absolute", left: a + ox - 4, top: b + oy - 4, width: c - a + 8, height: d - b + 8, border: "4px solid #fff", borderRadius: 10, transform: `scale(${p})`, opacity: Math.min(1, p), boxShadow: "0 0 18px rgba(255,255,255,0.6)"}} />;
          })}
      </div>
      <Line text="every face, blurred." color="#fff" at={w("people", "blurred") - 10} y={1420} />
    </AbsoluteFill>
  );
};

/* ════════ outro: imagine a year ════════ */
export const WOutro: React.FC = () => {
  const f = useCurrentFrame();
  const now = w("outro", "now");
  const yr = w("outro", "year");
  return (
    <AbsoluteFill>
      <NavyBg glow="rgba(255,90,31,0.16)" />
      <div style={{position: "absolute", left: 0, right: 0, top: 380, textAlign: "center", fontFamily: F.sans, fontWeight: 900, fontSize: 96, letterSpacing: -4, lineHeight: 1.05, color: "#fff", opacity: prog(f, 2, 14) * (1 - prog(f, now - 10, now))}}>
        All of that,
        <br />
        <span style={{color: K.teal}}>in half an hour.</span>
      </div>
      <div style={{position: "absolute", left: 0, right: 0, top: 360, textAlign: "center", fontFamily: F.sans, fontWeight: 900, fontSize: 104, letterSpacing: -4, color: "#fff", opacity: prog(f, now - 2, now + 12)}}>
        Now imagine
      </div>
      <div style={{position: "absolute", left: 0, right: 0, top: 470, textAlign: "center", fontFamily: F.serif, fontStyle: "italic", fontSize: 220, lineHeight: 1, color: K.orange, opacity: prog(f, yr - 4, yr + 10), transform: `scale(${0.8 + 0.2 * prog(f, yr - 4, yr + 14)}) rotate(-3deg)`}}>
        a year.
      </div>
      {/* 52 weeks lighting up */}
      <div style={{position: "absolute", left: 90, right: 90, top: 860, display: "grid", gridTemplateColumns: "repeat(13, 1fr)", gap: 10}}>
        {Array.from({length: 52}, (_, i) => {
          const on = prog(f, now + 10 + i * 1.6, now + 18 + i * 1.6);
          return <div key={i} style={{aspectRatio: "1", borderRadius: 10, background: on > 0 ? `rgba(255,90,31,${0.25 + 0.75 * on})` : "rgba(255,255,255,0.08)", transform: `scale(${0.8 + 0.2 * on})`}} />;
        })}
      </div>
      <div style={{position: "absolute", left: 0, right: 0, top: 1240, textAlign: "center", fontFamily: F.mono, fontSize: 28, letterSpacing: 4, color: "rgba(255,255,255,0.6)", opacity: prog(f, now + 90, now + 104)}}>
        ONE FLIGHT A WEEK · 52 WEEKS
      </div>
    </AbsoluteFill>
  );
};

/* ════════ end ════════ */
export const WEnd: React.FC = () => (
  <EndCard
    dur={219}
    cityAt={w("end", "cityvision")}
    bookAt={w("end", "book")}
    note="All numbers: our own drone flights · faces & plates blurred"
    loop={{mode: "iris", at: 190, to: <NavyBg glow="rgba(255,90,31,0.18)" />}}
  />
);
