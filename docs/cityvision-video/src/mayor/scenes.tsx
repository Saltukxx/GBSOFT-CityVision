import {EndCard} from "../series/endcard";
import {loadFont as loadHand} from "@remotion/google-fonts/Caveat";
import {loadFont as loadType} from "@remotion/google-fonts/SpecialElite";
import React from "react";
import {AbsoluteFill, Img, OffthreadVideo, staticFile, useCurrentFrame} from "remotion";
import FOOT from "./footage.json";
import MAP from "./map.json";
import {Camera, F, Floaters, inOut, K, lerp, LogoMark, NavyBg, prog, rand, usePop, WhiteBg} from "../promo/kit";
import {fitView, lerpView, MapCard, polyLen, Said} from "../series/ui";
import W from "./vo_words.json";

const hand = loadHand("normal", {weights: ["500", "700"], subsets: ["latin"]});
const type = loadType("normal", {weights: ["400"], subsets: ["latin"]});
const HAND = `${hand.fontFamily}, cursive`;
const TYPE = `${type.fontFamily}, 'Courier New', monospace`;
const INK = "#1E2A5A";

const WORDS = W as unknown as Record<string, [string, number][]>;
/** Frame where the voice starts the nth occurrence of `word` in `scene`. */
const w = (scene: string, word: string, nth = 0) => {
  const hits = WORDS[scene].filter(([x]) => x === word.toLowerCase());
  if (!hits[nth]) throw new Error(`VO word not found: ${scene}/${word}#${nth}`);
  return hits[nth][1];
};
/** Words of a line, in order, with their frames (punctuation kept from `text`). */
const timed = (scene: string, text: string, from = 0): [string, number][] => {
  const seq = WORDS[scene];
  let k = from;
  return text.split(" ").map((tok) => {
    const bare = tok.toLowerCase().replace(/[^a-z0-9'’-]/g, "");
    while (k < seq.length && seq[k][0] !== bare) k++;
    const at = k < seq.length ? seq[k][1] : seq[seq.length - 1][1];
    k++;
    return [tok, at];
  });
};

/* ───────── shared pieces ───────── */
const Paper: React.FC<{rot: number; enter: number; children: React.ReactNode; h?: number; ruled?: boolean; color?: string}> = ({
  rot,
  enter,
  children,
  h = 1080,
  ruled = true,
  color = "#FBF7EE",
}) => (
  <div
    style={{
      position: "absolute",
      left: 90,
      top: 400,
      width: 900,
      height: h,
      borderRadius: 10,
      background: ruled
        ? `repeating-linear-gradient(180deg, ${color} 0px, ${color} 77px, rgba(90,120,190,0.22) 77px, rgba(90,120,190,0.22) 79px)`
        : color,
      backgroundPosition: "0 46px",
      boxShadow: "0 40px 90px rgba(20,30,60,0.22), 0 4px 12px rgba(20,30,60,0.08)",
      transform: `translateY(${(1 - enter) * 1500}px) rotate(${rot}deg)`,
      overflow: "hidden",
    }}
  >
    {ruled ? <div style={{position: "absolute", left: 96, top: 0, bottom: 0, width: 3, background: "rgba(220,80,80,0.35)"}} /> : null}
    <div style={{position: "absolute", inset: 0, background: "radial-gradient(120% 80% at 30% 20%, rgba(255,255,255,0.5), rgba(0,0,0,0.04))"}} />
    {children}
  </div>
);

/** Handwriting: each word is "written" left→right as it is spoken. */
const Hand: React.FC<{words: [string, number][]; size: number; color?: string; circle?: string; weight?: number}> = ({
  words,
  size,
  color = INK,
  circle,
  weight = 500,
}) => {
  const f = useCurrentFrame();
  return (
    <div style={{fontFamily: HAND, fontSize: size, fontWeight: weight, color, lineHeight: 1.22, display: "flex", flexWrap: "wrap", columnGap: size * 0.26}}>
      {words.map(([tok, at], i) => {
        const p = prog(f, at - 2, at + Math.max(6, tok.length * 2.2), (x) => x);
        const isCircle = circle && tok.toLowerCase().startsWith(circle);
        return (
          <span key={i} style={{position: "relative", display: "inline-block"}}>
            <span style={{display: "inline-block", clipPath: `inset(-20% ${(1 - p) * 100}% -20% -10%)`}}>{tok}</span>
            {isCircle ? (
              <svg width="150%" height="140%" viewBox="0 0 100 60" preserveAspectRatio="none" style={{position: "absolute", left: "-25%", top: "-16%", overflow: "visible", pointerEvents: "none"}}>
                <path
                  d="M12 34 C 6 14, 40 4, 70 8 C 96 12, 98 44, 66 52 C 40 58, 8 52, 10 30 C 12 18, 30 12, 44 12"
                  fill="none"
                  stroke={K.orange}
                  strokeWidth={3.2}
                  strokeLinecap="round"
                  pathLength={1}
                  strokeDasharray="1"
                  strokeDashoffset={1 - prog(f, at + 8, at + 30)}
                />
              </svg>
            ) : null}
          </span>
        );
      })}
    </div>
  );
};

const Stamp: React.FC<{at: number; color: string; label: string}> = ({at, color, label}) => {
  const f = useCurrentFrame();
  const s = interpolateStamp(f - at);
  return (
    <div
      style={{
        position: "absolute",
        right: 40,
        bottom: 120,
        transform: `rotate(-9deg) scale(${s})`,
        opacity: f >= at ? 1 : 0,
        border: `6px solid ${color}`,
        outline: `2px solid ${color}`,
        outlineOffset: 6,
        borderRadius: 14,
        padding: "16px 26px",
        color,
        fontFamily: F.mono,
        fontWeight: 500,
        fontSize: 34,
        letterSpacing: 3,
        lineHeight: 1.25,
        textAlign: "center",
        background: "rgba(255,255,255,0.92)",
        mixBlendMode: "normal",
      }}
    >
      FOUND ON THE
      <br />
      FIRST FLIGHT
      <div style={{fontSize: 20, letterSpacing: 2, marginTop: 6, opacity: 0.85}}>{label}</div>
    </div>
  );
};
// slam: big → overshoot small → settle
const interpolateStamp = (t: number) => (t < 0 ? 2.2 : t < 5 ? lerp(2.2, 0.92, t / 5) : t < 10 ? lerp(0.92, 1, (t - 5) / 5) : 1);

const Overhead: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <div
      style={{
        position: "absolute",
        left: 0,
        right: 0,
        top: 330,
        textAlign: "center",
        fontFamily: F.serif,
        fontStyle: "italic",
        fontSize: 96,
        color: "#fff",
        opacity: prog(f, 0, 14),
        transform: `translateY(${(1 - prog(f, 0, 18)) * 20}px)`,
      }}
    >
      Meanwhile, overhead…
    </div>
  );
};

/* ════════ Letter 1 — handwritten (Bill) ════════ */
export const HOLE = {x: 540, y: 1010, r: 130};

export const ML1: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const enter = pop(f, 0, {damping: 16, stiffness: 120});
  const hole = prog(f, 330, 372, inOut);
  const pts = Array.from({length: 22}, (_, i) => {
    const a = (i / 22) * Math.PI * 2;
    const r = HOLE.r * hole * (0.82 + rand(i + 3) * 0.3);
    return `${HOLE.x + Math.cos(a) * r},${HOLE.y + Math.sin(a) * r}`;
  }).join(" ");
  return (
    <AbsoluteFill>
      <WhiteBg />
      <Camera dur={376} to={1.04}>
        <Paper rot={-1.6} enter={enter}>
          <div style={{position: "absolute", left: 130, right: 60, top: 70}}>
            <Hand words={timed("l1", "Dear Mayor,")} size={92} weight={700} />
            <div style={{height: 26}} />
            <Hand words={timed("l1", "There's been a hole outside my door since March.", 2)} size={70} circle="hole" />
            <div style={{height: 22}} />
            <Hand words={timed("l1", "My wife tripped on it last week.", 11)} size={70} />
            <div style={{height: 60}} />
            <div style={{fontFamily: HAND, fontSize: 56, color: "rgba(30,42,90,0.75)", opacity: prog(f, 352, 366)}}>— a resident, Kadıköy</div>
          </div>
        </Paper>
      </Camera>
      {/* the hole tears open — the next scene is seen through it */}
      {hole > 0 ? (
        <svg width={1080} height={1920} style={{position: "absolute", inset: 0}}>
          <polygon points={pts} fill="#0D1F48" stroke="#2A2C33" strokeWidth={6} strokeLinejoin="round" />
        </svg>
      ) : null}
    </AbsoluteFill>
  );
};

/* ════════ Answers — real footage (navy) ════════ */
type Shot = {src: string; w: number; h: number; box: number[]; label: string};
const CARD = {x: 90, y: 560, w: 900, h: 838};

const Answer: React.FC<{shot: Shot; color: string; ball: "orange" | "pink" | "teal"; video?: boolean; seed: number}> = ({shot, color, ball, video, seed}) => {
  const f = useCurrentFrame();
  const pop = usePop();
  const k = CARD.h / shot.h;
  const imgW = shot.w * k;
  const ox = (CARD.w - imgW) / 2;
  const [x1, y1, x2, y2] = shot.box.map((v, i) => v * k + (i % 2 === 0 ? ox : 0));
  const vid = (shot as Shot & {video?: {src: string; frames: number; fps: number}}).video;
  const FREEZE = video && vid ? Math.round((vid.frames / vid.fps) * 60) : 18; // the clip ends on the detection frame
  const bp = pop(f, FREEZE, {damping: 10, stiffness: 260});
  const flash = f >= FREEZE ? 1 - prog(f, FREEZE, FREEZE + 9) : 0;
  const card = pop(f, 0, {damping: 15, stiffness: 140});
  return (
    <AbsoluteFill>
      <NavyBg />
      <Floaters color={ball} seed={seed} scale={0.7} />
      <Overhead />
      <div
        style={{
          position: "absolute",
          left: CARD.x,
          top: CARD.y,
          width: CARD.w,
          height: CARD.h,
          borderRadius: 40,
          overflow: "hidden",
          background: "#3A3D46",
          boxShadow: "0 40px 80px rgba(0,0,0,0.4)",
          transform: `scale(${0.92 + 0.08 * card})`,
        }}
      >
        <div style={{position: "absolute", inset: 0, transform: `scale(${1 + prog(f, 0, 157) * 0.06})`, transformOrigin: `${(x1 + x2) / 2}px ${(y1 + y2) / 2}px`}}>
          {video && vid && f < FREEZE ? (
            <OffthreadVideo src={staticFile(vid.src)} muted style={{position: "absolute", left: ox, top: 0, width: imgW, height: CARD.h}} />
          ) : (
            <Img src={staticFile(shot.src)} style={{position: "absolute", left: ox, top: 0, width: imgW, height: CARD.h}} />
          )}
          {f >= FREEZE ? (
            <div
              style={{
                position: "absolute",
                left: x1,
                top: y1,
                width: x2 - x1,
                height: y2 - y1,
                border: `6px solid ${color}`,
                borderRadius: 14,
                transform: `scale(${bp})`,
                opacity: Math.min(1, bp),
                boxShadow: `0 0 0 3000px rgba(8,21,48,${0.3 * Math.min(1, bp)})`,
              }}
            >
              <div style={{position: "absolute", left: -6, top: y1 > 70 ? -52 : undefined, bottom: y1 > 70 ? undefined : -52, whiteSpace: "nowrap", background: color, color: "#fff", fontFamily: F.mono, fontSize: 26, padding: "8px 14px", borderRadius: 10}}>
                {shot.label}
              </div>
            </div>
          ) : null}
        </div>
        <AbsoluteFill style={{background: "#fff", opacity: flash * 0.75}} />
        <div style={{position: "absolute", left: 28, bottom: 30, padding: "8px 14px", borderRadius: 10, background: "rgba(8,21,48,0.6)", fontFamily: F.mono, fontSize: 20, color: "#fff"}}>
          our test flight · faces & plates blurred
        </div>
      </div>
      <Stamp at={FREEZE + 14} color={color} label={`${MAP.pins[1].lat.toFixed(4)}° N · ${MAP.pins[1].lon.toFixed(4)}° E`} />
    </AbsoluteFill>
  );
};

export const MA1: React.FC = () => <Answer shot={FOOT.pothole} color={K.orange} ball="orange" video seed={131} />;
export const MA2: React.FC = () => <Answer shot={FOOT.crack} color={K.pink} ball="pink" seed={137} />;
export const MA3: React.FC = () => <Answer shot={FOOT.damage} color={K.teal} ball="teal" seed={139} />;

/* ════════ Letter 2 — a message (Jessica) ════════ */
export const ML2: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const enter = pop(f, 0, {damping: 16, stiffness: 120});
  const bubbles: [string, number][] = [
    ["Dear Mayor,", w("l2", "dear")],
    ["The road on our street is cracking.", w("l2", "the")],
    ["I've called twice.", w("l2", "i've")],
    ["Nobody came.", w("l2", "nobody")],
  ];
  return (
    <AbsoluteFill>
      <WhiteBg />
      <Floaters color="pink" seed={149} />
      <div style={{position: "absolute", left: 540 - 270, top: 360, transform: `translateY(${(1 - enter) * 1500}px) rotate(1.4deg)`}}>
        <div style={{width: 540, height: 1120, borderRadius: 78, background: "#0E0F14", padding: 14, boxShadow: "0 60px 110px rgba(20,20,40,0.32)"}}>
          <div style={{position: "relative", width: "100%", height: "100%", borderRadius: 66, overflow: "hidden", background: "#F4F5F8"}}>
            <div style={{position: "absolute", left: "50%", top: 16, width: 140, height: 38, marginLeft: -70, borderRadius: 20, background: "#0E0F14"}} />
            <div style={{position: "absolute", left: 0, right: 0, top: 70, height: 120, background: "rgba(255,255,255,0.9)", borderBottom: "1px solid #E3E6EC", display: "flex", alignItems: "center", gap: 16, padding: "0 28px"}}>
              <div style={{width: 64, height: 64, borderRadius: 99, background: "linear-gradient(160deg, #C9D2E6, #9AA7C6)", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: F.sans, fontWeight: 700, fontSize: 26, color: "#fff"}}>MO</div>
              <div>
                <div style={{fontFamily: F.sans, fontWeight: 700, fontSize: 28, color: K.navyText}}>Mayor’s Office</div>
                <div style={{fontFamily: F.sans, fontSize: 20, color: K.gray}}>Contact form</div>
              </div>
            </div>
            <div style={{position: "absolute", left: 24, right: 24, top: 230, display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 16}}>
              {bubbles.map(([t, at], i) => {
                const typing = f >= at - 18 && f < at;
                const p = pop(f, at, {damping: 13, stiffness: 220});
                const last = i === bubbles.length - 1;
                return (
                  <React.Fragment key={i}>
                    {typing ? (
                      <div style={{alignSelf: "flex-end", padding: "18px 24px", borderRadius: 30, background: "#E2E6EE", display: "flex", gap: 8}}>
                        {[0, 1, 2].map((d) => (
                          <div key={d} style={{width: 12, height: 12, borderRadius: 9, background: "#8B93A6", opacity: 0.4 + 0.6 * Math.abs(Math.sin((f + d * 6) / 6))}} />
                        ))}
                      </div>
                    ) : null}
                    {f >= at ? (
                      <div
                        style={{
                          maxWidth: 400,
                          padding: "18px 24px",
                          borderRadius: "30px 30px 8px 30px",
                          background: last ? K.pink : "#3B6FE0",
                          color: "#fff",
                          fontFamily: F.sans,
                          fontWeight: last ? 700 : 500,
                          fontSize: last ? 40 : 32,
                          lineHeight: 1.25,
                          transform: `scale(${p})`,
                          transformOrigin: "100% 100%",
                        }}
                      >
                        {t}
                      </div>
                    ) : null}
                  </React.Fragment>
                );
              })}
              <div style={{fontFamily: F.sans, fontSize: 20, color: K.gray, opacity: prog(f, w("l2", "came") + 10, w("l2", "came") + 24)}}>Delivered · no reply</div>
            </div>
          </div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ════════ Letter 3 — typewriter (Chris) ════════ */
export const ML3: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const enter = pop(f, 0, {damping: 16, stiffness: 120});
  const Type: React.FC<{words: [string, number][]; size: number}> = ({words, size}) => (
    <div style={{fontFamily: TYPE, fontSize: size, color: "#22242B", lineHeight: 1.35, display: "flex", flexWrap: "wrap", columnGap: size * 0.5}}>
      {words.map(([tok, at], i) => {
        const n = Math.max(0, Math.min(tok.length, Math.floor((f - at + 2) / 2.2)));
        return (
          <span key={i} style={{whiteSpace: "pre"}}>
            {tok.slice(0, n)}
            <span style={{opacity: 0}}>{tok.slice(n)}</span>
          </span>
        );
      })}
    </div>
  );
  const sec = w("l3", "second", 1);
  return (
    <AbsoluteFill>
      <WhiteBg />
      <Floaters color="teal" seed={151} />
      <Camera dur={188} to={1.05}>
        <Paper rot={1.2} enter={enter} ruled={false} color="#FFFEFA" h={980}>
          <div style={{position: "absolute", left: 90, right: 80, top: 100}}>
            <Type words={timed("l3", "Dear Mayor,")} size={58} />
            <div style={{height: 40}} />
            <Type words={timed("l3", "That's my second tyre this year.", 2)} size={58} />
            <div style={{height: 60}} />
            <div style={{position: "relative", display: "inline-block", transform: `scale(${f >= sec ? 1 : 0.9})`, transformOrigin: "0% 50%"}}>
              <Type words={[["Second.", sec]]} size={120} />
              <svg width="420" height="40" viewBox="0 0 420 40" style={{position: "absolute", left: -6, top: 150}}>
                {[0, 1].map((k) => (
                  <path
                    key={k}
                    d={`M4 ${12 + k * 14} C 120 ${4 + k * 14}, 260 ${20 + k * 12}, 410 ${8 + k * 14}`}
                    fill="none"
                    stroke={K.red}
                    strokeWidth={6}
                    strokeLinecap="round"
                    pathLength={1}
                    strokeDasharray="1"
                    strokeDashoffset={1 - prog(f, sec + 16 + k * 8, sec + 28 + k * 8)}
                  />
                ))}
              </svg>
            </div>
            <div style={{fontFamily: TYPE, fontSize: 36, color: "rgba(34,36,43,0.6)", marginTop: 120, opacity: prog(f, 168, 180)}}>— a driver, Kadıköy</div>
          </div>
        </Paper>
      </Camera>
    </AbsoluteFill>
  );
};

/* ════════ Pile — letters keep coming (last beat is the music's silence) ════════ */
export const MPile: React.FC = () => {
  const f = useCurrentFrame();
  const FREEZE = 94;
  const t = Math.min(f, FREEZE);
  const N = 30;
  return (
    <AbsoluteFill>
      <WhiteBg />
      {Array.from({length: N}, (_, i) => {
        const at = i * 3;
        const p = prog(t, at, at + 16);
        if (p <= 0) return null;
        const x = 120 + rand(i * 7) * 840;
        const y = 300 + rand(i * 11) * 1300;
        const rot = (rand(i * 13) - 0.5) * 40;
        const kind = i % 3;
        return (
          <div
            key={i}
            style={{
              position: "absolute",
              left: x - 210,
              top: lerp(-700, y - 140, p),
              width: 420,
              height: 280,
              borderRadius: 8,
              background: kind === 1 ? "#FFFFFF" : "#FBF7EE",
              boxShadow: "0 20px 40px rgba(20,30,60,0.2)",
              transform: `rotate(${rot * p + (1 - p) * 40}deg)`,
              padding: "26px 30px",
            }}
          >
            <div style={{fontFamily: kind === 1 ? TYPE : HAND, fontSize: kind === 1 ? 32 : 44, color: INK}}>Dear Mayor,</div>
            {[0, 1, 2, 3].map((l) => (
              <div key={l} style={{height: 8, borderRadius: 4, marginTop: 22, width: `${60 + rand(i * 3 + l) * 35}%`, background: "rgba(30,42,90,0.22)"}} />
            ))}
          </div>
        );
      })}
      {/* the silent beat: everything stops, the room goes quiet */}
      <AbsoluteFill style={{background: "#081530", opacity: f >= FREEZE ? 0.25 + 0.75 * prog(f, FREEZE, FREEZE + 30, inOut) : 0}} />
    </AbsoluteFill>
  );
};

/* ════════ Turn — on the drop (Sarah) ════════ */
export const MTurn: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill>
      <NavyBg glow="rgba(255,90,31,0.14)" />
      <Floaters color="orange" seed={157} scale={0.8} />
      <Camera dur={125} to={1.05}>
        <Said words={timed("turn", "What if the city")} y={700} size={104} weight={800} color="#fff" />
        <div style={{position: "absolute", left: 0, right: 0, top: 840, textAlign: "center", fontFamily: F.serif, fontStyle: "italic", fontSize: 190, color: K.orange, lineHeight: 1}}>
          {timed("turn", "found it first?").map(([tok, at], i) => {
            const p = prog(f, at - 2, at + 14);
            return (
              <span key={i} style={{display: "inline-block", marginRight: 34, opacity: p, transform: `translateY(${(1 - p) * 50}px)`, filter: p < 1 ? `blur(${(1 - p) * 12}px)` : undefined}}>
                {tok}
              </span>
            );
          })}
        </div>
      </Camera>
    </AbsoluteFill>
  );
};

/* ════════ Payoff — the real map (Sarah) ════════ */
export const MPayoff: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const CW = 920;
  const CH = 920;
  const v0 = fitView(MAP.flyBox, CW, CH);
  const view = lerpView({...v0, s: v0.s * 0.82}, v0, prog(f, 0, 120, inOut));
  const fly = MAP.fly as number[][];
  const len = polyLen(fly as [number, number][]);
  const draw = prog(f, w("payoff", "flies") - 10, w("payoff", "schedule") + 20, inOut);
  const shots = [FOOT.crack, FOOT.pothole, FOOT.damage];
  const colors = [K.pink, K.orange, K.teal];
  const writeAt = w("payoff", "write");
  const card = pop(f, 2, {damping: 15, stiffness: 120});
  return (
    <AbsoluteFill>
      <WhiteBg tint="rgba(15,181,200,0.12)" />
      <Floaters color="teal" seed={163} />
      <Said words={timed("payoff", "CityVision flies your streets")} y={290} size={66} weight={800} highlight={{CityVision: K.orange}} />
      <Said words={timed("payoff", "on a schedule,", 4)} y={372} size={66} weight={800} />
      <Said words={timed("payoff", "and puts every issue on the map.", 7)} y={462} size={46} weight={500} color="#4A5470" />
      <MapCard
        src={staticFile(MAP.light)}
        mapW={MAP.w}
        mapH={MAP.h}
        w={CW}
        h={CH}
        view={view}
        style={{left: 80, top: 570, transform: `scale(${0.92 + 0.08 * card})`, opacity: Math.min(1, card * 1.4)}}
      >
        {(proj, sc) => (
          <>
            <svg width={CW} height={CH} style={{position: "absolute", inset: 0}}>
              <polyline
                points={fly.map(([x, y]) => proj(x, y).join(",")).join(" ")}
                fill="none"
                stroke={K.teal}
                strokeWidth={8}
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeDasharray={`${len * sc * draw} ${len * sc * 2}`}
              />
            </svg>
            <div style={{position: "absolute", right: 24, top: 24, display: "flex", gap: 10}}>
              {["Mon", "Wed", "Fri"].map((d, i) => (
                <div
                  key={d}
                  style={{
                    transform: `scale(${pop(f, w("payoff", "schedule") + i * 6, {damping: 12})})`,
                    padding: "10px 16px",
                    borderRadius: 999,
                    background: "rgba(255,255,255,0.95)",
                    boxShadow: "0 6px 16px rgba(20,30,60,0.15)",
                    fontFamily: F.mono,
                    fontSize: 22,
                    color: K.navyText,
                  }}
                >
                  {d}
                </div>
              ))}
            </div>
            {MAP.pins.map((p, i) => {
              const [x, y] = proj(p.x, p.y);
              const q = pop(f, w("payoff", "every") + i * 8, {damping: 10, stiffness: 220});
              const s = shots[i];
              const [b1, b2, b3, b4] = s.box;
              const kk = Math.max(80 / s.h, (80 * 0.8) / Math.max(b3 - b1, b4 - b2));
              const left = Math.min(0, Math.max(80 - s.w * kk, 40 - ((b1 + b3) / 2) * kk));
              const top = Math.min(0, Math.max(80 - s.h * kk, 40 - ((b2 + b4) / 2) * kk));
              // a little letter that never needs to be written
              const lp = pop(f, writeAt - 70 + i * 8, {damping: 12});
              const gone = prog(f, writeAt + 4 + i * 4, writeAt + 18 + i * 4, inOut);
              return (
                <React.Fragment key={i}>
                  <div style={{position: "absolute", left: x - 50, top: y - 120, transform: `scale(${q})`, transformOrigin: "50% 100%"}}>
                    <div style={{width: 100, height: 100, borderRadius: 24, background: "#fff", padding: 10, boxShadow: "0 14px 30px rgba(20,30,60,0.25)", border: `4px solid ${colors[i]}`}}>
                      <div style={{position: "relative", width: 80, height: 80, borderRadius: 16, overflow: "hidden"}}>
                        <Img src={staticFile(s.src)} style={{position: "absolute", left, top, width: s.w * kk, height: s.h * kk}} />
                      </div>
                    </div>
                    <div style={{width: 0, height: 0, margin: "0 auto", borderLeft: "12px solid transparent", borderRight: "12px solid transparent", borderTop: `14px solid ${colors[i]}`}} />
                  </div>
                  {lp > 0.01 && gone < 1 ? (
                    <div
                      style={{
                        position: "absolute",
                        left: x + 46,
                        top: y - 150 - gone * 60,
                        width: 90,
                        height: 62,
                        borderRadius: 6,
                        background: "#FBF7EE",
                        boxShadow: "0 8px 18px rgba(20,30,60,0.2)",
                        transform: `scale(${lp * (1 - gone)}) rotate(${(i - 1) * 8 + gone * 30}deg)`,
                        opacity: 1 - gone,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        fontFamily: HAND,
                        fontSize: 22,
                        color: INK,
                      }}
                    >
                      Dear…
                    </div>
                  ) : null}
                </React.Fragment>
              );
            })}
          </>
        )}
      </MapCard>
      <div style={{position: "absolute", left: 0, right: 0, top: 1530, display: "flex", justifyContent: "center"}}>
        <div
          style={{
            transform: `scale(${pop(f, writeAt + 8, {damping: 11})})`,
            background: K.navy,
            color: "#fff",
            fontFamily: F.sans,
            fontWeight: 700,
            fontSize: 38,
            padding: "20px 36px",
            borderRadius: 999,
            boxShadow: "0 18px 40px rgba(11,26,58,0.3)",
          }}
        >
          Found before the first letter.
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ════════ Close — the reply, handwritten (Sarah) ════════ */
export const SIGN = {x: 214, y: 1160};

export const MClose: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const enter = pop(f, 0, {damping: 16, stiffness: 120});
  return (
    <AbsoluteFill>
      <WhiteBg />
      <Floaters seed={167} />
      <Paper rot={-1} enter={enter} h={1000}>
        <div style={{position: "absolute", left: 130, right: 60, top: 70}}>
          <Hand words={timed("close", "Dear Mayor,")} size={92} weight={700} />
          <div style={{height: 30}} />
          <Hand words={timed("close", "We found it first.", 2)} size={104} weight={700} color={K.navyText} />
          <div style={{height: 80}} />
          <div style={{display: "flex", alignItems: "center", gap: 22, opacity: prog(f, 118, 132)}}>
            <div style={{transform: `scale(${pop(f, 118, {damping: 11})})`}}>
              <LogoMark size={86} t={prog(f, 120, 140)} />
            </div>
            <div style={{fontFamily: HAND, fontSize: 70, fontWeight: 700, color: INK}}>— CityVision</div>
          </div>
          <div style={{height: 50}} />
          <Hand words={[["P.S.", 146], ["We'd", 150], ["love", 154], ["to", 157], ["show", 160], ["you.", 164]]} size={58} color="rgba(30,42,90,0.8)" />
        </div>
      </Paper>
    </AbsoluteFill>
  );
};

/* ════════ End (navy) → closes into white = frame 1 ════════ */
export const MEnd: React.FC = () => (
  <EndCard
    dur={188}
    cityAt={4}
    bookAt={w("end", "book") + 6}
    note="Letters dramatised · footage: our own test flight · faces & plates blurred"
    loop={{mode: "iris", at: 158, to: <WhiteBg />}}
  />
);

