import {EndCard} from "../series/endcard";
import React from "react";
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from "remotion";
import FOOT from "../howto/footage.json";
import MAP from "../howto/map.json";
import {Ball, BallColor, BallLabel, Camera, F, Floaters, inOut, K, lerp, NavyBg, prog, usePop, WhiteBg} from "../promo/kit";
import {beatFrames} from "../series/engine";
import {fitView, lerpView, MapCard, Said} from "../series/ui";
import ROADS from "./roads.json";
import TL from "./timeline.json";
import {w} from "./words";

const bf = beatFrames(TL.bpm);
const SCENE_BEAT: Record<string, number> = (() => {
  const out: Record<string, number> = {};
  let b = 0;
  for (const [id, n] of TL.scenes as [string, number, string][]) {
    out[id] = b;
    b += n;
  }
  return out;
})();
/** Scene-local frame of a beat mark (beats from the scene's start). */
const markFrame = (scene: string, beats: number) => bf(SCENE_BEAT[scene] + beats) - bf(SCENE_BEAT[scene]);

export const TIMER = {x: 940, y: 728, size: 170};
const CARD = {x: 90, y: 720, w: 900, h: 838};

/* ════════ Hook (navy) — "Can you spot it faster than a drone? You get three seconds." ════════ */
export const GHook: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const born = pop(f, w("hook", "three") - 4, {damping: 9, stiffness: 170});
  const fly = prog(f, 214, 246, inOut);
  const size = lerp(380 * born, TIMER.size, fly);
  return (
    <AbsoluteFill>
      <NavyBg glow="rgba(255,90,31,0.12)" />
      <Floaters color="orange" seed={83} scale={0.8} />
      <Camera dur={250} to={1.03}>
        <Said
          words={[
            ["Can", w("hook", "can")],
            ["you", w("hook", "you")],
            ["spot", w("hook", "spot")],
            ["it", w("hook", "it")],
          ]}
          y={430}
          size={96}
          weight={800}
          color="#fff"
          out={208}
        />
        <Said
          words={[
            ["faster", w("hook", "faster")],
            ["than", w("hook", "than")],
            ["a", w("hook", "a")],
            ["drone?", w("hook", "drone")],
          ]}
          y={545}
          size={96}
          weight={800}
          color="#fff"
          highlight={{"drone?": K.orange}}
          out={208}
        />
      </Camera>
      <Ball size={size} x={lerp(540, TIMER.x, fly)} y={lerp(1060, TIMER.y, fly)} shadow={false}>
        <BallLabel size={size * 0.46}>3</BallLabel>
      </Ball>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 1300,
          textAlign: "center",
          fontFamily: F.serif,
          fontStyle: "italic",
          fontSize: 110,
          color: "#fff",
          opacity: prog(f, w("hook", "seconds") - 2, w("hook", "seconds") + 14) * (1 - prog(f, 206, 218)),
        }}
      >
        seconds.
      </div>
    </AbsoluteFill>
  );
};

/* ════════ Round ════════ */
type Shot = {src: string; w: number; h: number; box: number[]; label: string};

/** Square thumbnail zoomed onto the detection box. */
const BoxThumb: React.FC<{shot: Shot; size: number; radius: number}> = ({shot, size, radius}) => {
  const [x1, y1, x2, y2] = shot.box;
  const kk = Math.min((size * 0.78) / Math.max(x2 - x1, y2 - y1), size / Math.min(shot.w, shot.h) * 2.4);
  const k = Math.max(kk, size / shot.h);
  const cx = ((x1 + x2) / 2) * k;
  const cy = ((y1 + y2) / 2) * k;
  const left = Math.min(0, Math.max(size - shot.w * k, size / 2 - cx));
  const top = Math.min(0, Math.max(size - shot.h * k, size / 2 - cy));
  return (
    <div style={{position: "relative", width: size, height: size, borderRadius: radius, overflow: "hidden", background: "#555"}}>
      <Img src={staticFile(shot.src)} style={{position: "absolute", left, top, width: shot.w * k, height: shot.h * k}} />
    </div>
  );
};

const makeRound = (opts: {
  id: "r1" | "r2" | "r3";
  n: number;
  target: string;
  targetWord: string;
  shot: Shot;
  accent: string;
  ball: BallColor;
  reveal: string;
  seed: number;
}): React.FC => {
  const Round: React.FC = () => {
    const f = useCurrentFrame();
    const pop = usePop();
    const COUNT = markFrame(opts.id, 5);
    const REVEAL = markFrame(opts.id, 11);
    const sec = [COUNT, markFrame(opts.id, 7), markFrame(opts.id, 9)];
    const left = f < sec[1] ? 3 : f < sec[2] ? 2 : 1;
    const lastTick = f >= REVEAL ? REVEAL : f >= sec[2] ? sec[2] : f >= sec[1] ? sec[1] : COUNT;
    const bump = f >= COUNT ? 1 + 0.14 * Math.max(0, 1 - (f - lastTick) / 10) : 1;
    const sharp = prog(f, COUNT - 4, COUNT + 6);
    const revealed = f >= REVEAL;
    const k = CARD.h / opts.shot.h;
    const imgW = opts.shot.w * k;
    const ox = (CARD.w - imgW) / 2;
    const [x1, y1, x2, y2] = opts.shot.box.map((v, i) => v * k + (i % 2 === 0 ? ox : 0));
    const bp = pop(f, REVEAL, {damping: 10, stiffness: 260});
    const flash = revealed ? 1 - prog(f, REVEAL, REVEAL + 9) : 0;
    const bar = f < COUNT ? 1 : 1 - prog(f, COUNT, REVEAL, (x) => x);
    const card = pop(f, 2, {damping: 15, stiffness: 120});
    const targetAt = w(opts.id, opts.targetWord);
    const timerOut = prog(f, REVEAL + 2, REVEAL + 14);
    return (
      <AbsoluteFill>
        <WhiteBg />
        <Floaters color={opts.ball} seed={opts.seed} />
        {/* header */}
        <div style={{position: "absolute", left: 0, right: 0, top: 300, display: "flex", justifyContent: "center", alignItems: "center", gap: 16}}>
          <div style={{position: "relative", width: 58, height: 58, transform: `scale(${pop(f, w(opts.id, "round"), {damping: 12})})`}}>
            <Ball size={58} x={29} y={29} color={opts.ball} shadow={false}>
              <span style={{fontFamily: F.sans, fontWeight: 800, fontSize: 30, color: "#fff"}}>{opts.n}</span>
            </Ball>
          </div>
          <div style={{fontFamily: F.mono, fontSize: 26, letterSpacing: 4, color: "rgba(14,27,61,0.5)", opacity: prog(f, 8, 18)}}>ROUND {opts.n} / 3</div>
        </div>
        <Said words={[["Find", w(opts.id, "find")], ["the", w(opts.id, "the")]]} y={378} size={72} weight={700} />
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 462,
            textAlign: "center",
            fontFamily: F.sans,
            fontWeight: 900,
            fontSize: opts.target.length > 8 ? 124 : 150,
            letterSpacing: -7,
            lineHeight: 1,
            color: K.navyText,
            opacity: prog(f, targetAt - 2, targetAt + 8),
            transform: `scale(${0.6 + 0.4 * Math.min(1.06, pop(f, targetAt - 2, {damping: 11, stiffness: 220}))})`,
          }}
        >
          {opts.target}
          <span style={{color: opts.accent}}>.</span>
        </div>
        {/* photo */}
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
            boxShadow: "0 40px 80px rgba(20,30,60,0.22)",
            transform: `translateY(${(1 - card) * 900}px)`,
          }}
        >
          <div
            style={{
              position: "absolute",
              inset: 0,
              filter: sharp < 1 ? `blur(${(1 - sharp) * 26}px)` : undefined,
              transform: `scale(${1.08 - 0.08 * sharp + (revealed ? prog(f, REVEAL, REVEAL + 90) * 0.05 : 0)})`,
              transformOrigin: `${(x1 + x2) / 2}px ${(y1 + y2) / 2}px`,
            }}
          >
            <Img src={staticFile(opts.shot.src)} style={{position: "absolute", left: ox, top: 0, width: imgW, height: CARD.h}} />
            {revealed ? (
              <div
                style={{
                  position: "absolute",
                  left: x1,
                  top: y1,
                  width: x2 - x1,
                  height: y2 - y1,
                  border: `6px solid ${opts.accent}`,
                  borderRadius: 14,
                  transform: `scale(${bp})`,
                  opacity: Math.min(1, bp),
                  boxShadow: `0 0 0 3000px rgba(8,21,48,${0.35 * Math.min(1, bp)})`,
                }}
              >
                <div
                  style={{
                    position: "absolute",
                    left: -6,
                    top: y1 > 70 ? -52 : undefined,
                    bottom: y1 > 70 ? undefined : -52,
                    whiteSpace: "nowrap",
                    background: opts.accent,
                    color: "#fff",
                    fontFamily: F.mono,
                    fontSize: 26,
                    padding: "8px 14px",
                    borderRadius: 10,
                  }}
                >
                  {opts.shot.label}
                </div>
              </div>
            ) : null}
          </div>
          {/* "ready?" veil during the title */}
          <AbsoluteFill
            style={{
              background: "rgba(8,21,48,0.35)",
              opacity: 1 - sharp,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: F.serif,
              fontStyle: "italic",
              fontSize: 120,
              color: "#fff",
            }}
          >
            <span style={{opacity: prog(f, COUNT - 40, COUNT - 26), transform: `scale(${0.9 + 0.1 * prog(f, COUNT - 40, COUNT - 20)})`}}>ready?</span>
          </AbsoluteFill>
          <AbsoluteFill style={{background: "#fff", opacity: flash * 0.8}} />
          {/* countdown bar */}
          <div style={{position: "absolute", left: 0, bottom: 0, height: 12, width: `${bar * 100}%`, background: opts.accent, opacity: f >= COUNT && !revealed ? 1 : 0}} />
          {revealed ? (
            <div
              style={{
                position: "absolute",
                left: 28,
                top: 28,
                display: "flex",
                alignItems: "center",
                gap: 12,
                padding: "12px 20px",
                borderRadius: 999,
                background: "rgba(255,255,255,0.95)",
                fontFamily: F.sans,
                fontWeight: 700,
                fontSize: 28,
                color: K.navyText,
                transform: `scale(${pop(f, REVEAL + 6, {damping: 11})})`,
                transformOrigin: "0% 50%",
              }}
            >
              <div style={{width: 30, height: 30, borderRadius: 99, background: K.green, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20}}>✓</div>
              CityVision found it
            </div>
          ) : null}
          <div
            style={{
              position: "absolute",
              left: 28,
              bottom: 34,
              padding: "8px 14px",
              borderRadius: 10,
              background: "rgba(8,21,48,0.6)",
              fontFamily: F.mono,
              fontSize: 20,
              color: "#fff",
              opacity: revealed ? 1 : 0,
            }}
          >
            real flight · Kartal · faces & plates blurred
          </div>
        </div>
        {/* timer ball */}
        <Ball size={TIMER.size * bump * (1 - timerOut)} x={TIMER.x} y={TIMER.y} shadow={false}>
          <BallLabel size={TIMER.size * 0.46}>{left}</BallLabel>
        </Ball>
        {/* reveal word, big italic */}
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 1590,
            textAlign: "center",
            fontFamily: F.serif,
            fontStyle: "italic",
            fontSize: 76,
            color: opts.accent,
            opacity: prog(f, REVEAL + 6, REVEAL + 20),
            transform: `translateY(${(1 - prog(f, REVEAL + 6, REVEAL + 24)) * 20}px)`,
          }}
        >
          {opts.reveal}
        </div>
      </AbsoluteFill>
    );
  };
  return Round;
};

export const GR1 = makeRound({id: "r1", n: 1, target: "pothole", targetWord: "pothole", shot: FOOT.pothole, accent: K.orange, ball: "orange", reveal: "easy.", seed: 89});
export const GR2 = makeRound({id: "r2", n: 2, target: "road damage", targetWord: "road", shot: FOOT.damage, accent: K.teal, ball: "teal", reveal: "got it?", seed: 97});
export const GR3 = makeRound({id: "r3", n: 3, target: "crack", targetWord: "crack", shot: FOOT.crack, accent: K.pink, ball: "pink", reveal: "most people miss this one.", seed: 101});

/* ════════ Score (navy) — "Three for three. How did you do?" ════════ */
export const GScore: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const shots = [FOOT.pothole, FOOT.damage, FOOT.crack];
  const colors = [K.orange, K.teal, K.pink];
  const ticks = [w("score", "three"), w("score", "for"), w("score", "three", 1)];
  const n = ticks.filter((t) => f >= t).length;
  return (
    <AbsoluteFill>
      <NavyBg glow="rgba(22,163,74,0.12)" />
      <Floaters color="teal" seed={103} scale={0.8} />
      <Said words={[["How", w("score", "how")], ["did", w("score", "did")], ["you", w("score", "you")], ["do?", w("score", "do")]]} y={340} size={96} weight={800} color="#fff" />
      {[
        {who: "You", val: "?", sub: "/3", color: "#fff", at: 10},
        {who: "CityVision", val: String(n), sub: "/3", color: K.green, at: 2},
      ].map((c, i) => {
        const p = pop(f, c.at, {damping: 13, stiffness: 160});
        return (
          <div
            key={c.who}
            style={{
              position: "absolute",
              left: i === 0 ? 90 : 560,
              top: 560,
              width: 430,
              height: 560,
              borderRadius: 40,
              background: i === 0 ? "rgba(255,255,255,0.06)" : "rgba(255,255,255,0.1)",
              border: `2px solid ${i === 0 ? "rgba(255,255,255,0.14)" : "rgba(34,197,94,0.55)"}`,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              transform: `translateY(${(1 - p) * 600}px)`,
            }}
          >
            <div style={{fontFamily: F.mono, fontSize: 28, letterSpacing: 4, color: "rgba(255,255,255,0.65)"}}>{c.who.toUpperCase()}</div>
            <div style={{fontFamily: F.sans, fontWeight: 900, fontSize: 230, letterSpacing: -10, lineHeight: 1, color: c.color, marginTop: 10, opacity: i === 0 ? 0.55 + 0.45 * Math.abs(Math.sin(f / 14)) : 1}}>
              {c.val}
              <span style={{fontSize: 110, color: "rgba(255,255,255,0.45)"}}>{c.sub}</span>
            </div>
            {i === 1 ? (
              <div style={{display: "flex", gap: 14, marginTop: 26}}>
                {shots.map((s, j) => {
                  const q = pop(f, ticks[j], {damping: 10, stiffness: 240});
                  return (
                    <div key={j} style={{position: "relative", width: 110, height: 110, transform: `scale(${q})`}}>
                      <div style={{position: "absolute", inset: 0, borderRadius: 22, overflow: "hidden", border: `4px solid ${colors[j]}`}}>
                        <BoxThumb shot={s} size={102} radius={18} />
                      </div>
                      <div style={{position: "absolute", right: -10, bottom: -10, width: 40, height: 40, borderRadius: 99, background: K.green, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24, fontWeight: 800}}>✓</div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div style={{fontFamily: F.serif, fontStyle: "italic", fontSize: 44, color: "rgba(255,255,255,0.7)", marginTop: 26}}>be honest.</div>
            )}
          </div>
        );
      })}
      <div style={{position: "absolute", left: 0, right: 0, top: 1190, display: "flex", justifyContent: "center"}}>
        <div
          style={{
            background: "#fff",
            color: K.navyText,
            fontFamily: F.sans,
            fontWeight: 800,
            fontSize: 40,
            padding: "24px 44px",
            borderRadius: 999,
            transform: `scale(${pop(f, w("score", "do") + 4, {damping: 10})})`,
            boxShadow: "0 24px 50px rgba(0,0,0,0.3)",
          }}
        >
          Drop your score in the comments <span style={{color: K.orange}}>↓</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ════════ Map — "Now picture that on every street in your city." ════════ */
const NET = ROADS as number[][][];

export const GMap: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const CW = 920;
  const CH = 1000;
  const v0 = fitView(MAP.flyBox, CW, CH);
  const vWide = fitView([300, 250, 2700, 2350], CW, CH);
  const view = lerpView(v0, vWide, prog(f, w("map", "every") - 20, w("map", "city") + 20, inOut));
  const spread = prog(f, w("map", "every") - 6, w("map", "city") + 26, inOut);
  const shots = [FOOT.crack, FOOT.pothole, FOOT.damage];
  const colors = [K.pink, K.orange, K.teal];
  const card = pop(f, 2, {damping: 15, stiffness: 120});
  const cx = MAP.pins[1].x;
  const cy = MAP.pins[1].y;
  return (
    <AbsoluteFill>
      <WhiteBg tint="rgba(15,181,200,0.14)" />
      <Floaters color="teal" seed={107} />
      <Said
        words={[["Every", w("map", "every")], ["street.", w("map", "street")]]}
        y={330}
        size={120}
        weight={900}
        highlight={{"street.": K.teal}}
      />
      <Said words={[["Every", w("map", "every") + 20], ["week.", w("map", "city")]]} y={470} size={72} serif color={K.navyText} />
      <MapCard
        src={staticFile("maps/kartal-light.png")}
        mapW={MAP.w}
        mapH={MAP.h}
        w={CW}
        h={CH}
        view={view}
        style={{left: 80, top: 600, transform: `scale(${0.9 + 0.1 * card})`, opacity: Math.min(1, card * 1.4)}}
      >
        {(proj) => (
          <>
            <svg width={CW} height={CH} style={{position: "absolute", inset: 0}}>
              {NET.map((pts, i) => {
                const [mx, my] = pts[Math.floor(pts.length / 2)];
                const d = Math.hypot(mx - cx, my - cy) / 1700;
                const a = Math.max(0, Math.min(1, (spread - d) * 6));
                if (a <= 0) return null;
                return (
                  <polyline
                    key={i}
                    points={pts.map(([x, y]) => proj(x, y).join(",")).join(" ")}
                    fill="none"
                    stroke={K.teal}
                    strokeWidth={4}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    opacity={0.75 * a}
                  />
                );
              })}
              <polyline points={(MAP.fly as number[][]).map(([x, y]) => proj(x, y).join(",")).join(" ")} fill="none" stroke={K.navy} strokeWidth={7} strokeLinecap="round" strokeLinejoin="round" opacity={0.85} />
            </svg>
            {MAP.pins.map((p, i) => {
              const [x, y] = proj(p.x, p.y);
              const q = pop(f, 6 + i * 10, {damping: 10, stiffness: 220});
              const s = shots[i];
              return (
                <div key={i} style={{position: "absolute", left: x - 56, top: y - 128, transform: `scale(${q})`, transformOrigin: "50% 100%"}}>
                  <div style={{width: 112, height: 112, borderRadius: 26, background: "#fff", padding: 8, boxShadow: "0 14px 30px rgba(20,30,60,0.25)", border: `4px solid ${colors[i]}`}}>
                    <BoxThumb shot={s} size={88} radius={18} />
                  </div>
                  <div style={{width: 0, height: 0, margin: "0 auto", borderLeft: "12px solid transparent", borderRight: "12px solid transparent", borderTop: `14px solid ${colors[i]}`}} />
                </div>
              );
            })}
          </>
        )}
      </MapCard>
    </AbsoluteFill>
  );
};

/* ════════ End (white) → closes into navy = frame 1 of the hook ════════ */
export const GEnd: React.FC = () => (
  <EndCard
    dur={219}
    cityAt={w("end", "cityvision")}
    bookAt={w("end", "book")}
    note="Real footage from our test flight · faces & plates blurred"
    loop={{mode: "iris", at: 188, to: <NavyBg glow="rgba(255,90,31,0.12)" />}}
  />
);
