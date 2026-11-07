import React from "react";
import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {
  Ball,
  BallLabel,
  Camera,
  Card,
  clamp,
  Critter,
  F,
  Floaters,
  fmt,
  inOut,
  inQuad,
  K,
  Label,
  lerp,
  OrangeBg,
  PaperBg,
  prog,
  rand,
  usePop,
  Words,
} from "../kit";

/* ════════ 01 · "Your complaint map says 12" ════════ */
export const SMap: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const enter = pop(f, 8, {damping: 15, stiffness: 120});
  const rx = lerp(34, 9, enter) + Math.sin(f / 30) * 1.5;
  const ry = lerp(-18, -7, enter) + Math.cos(f / 36) * 2;
  const n = interpolate(f, [26, 70], [0, 12], {...clamp, easing: inOut});
  // whole card shudders right before the cut
  const shake = f > 104 ? Math.sin(f * 3.1) * (f - 104) * 0.9 : 0;
  const pins = Array.from({length: 12}, (_, i) => ({
    x: 70 + rand(i + 3) * 540,
    y: 40 + rand(i + 41) * 200,
    d: 30 + i * 3,
  }));
  return (
    <AbsoluteFill>
      <OrangeBg />
      <Floaters color="peach" seed={3} enter={4} />
      <Camera dur={140} to={1.05}>
        <Words text="Your complaint map says" at={4} y={430} size={62} color="#fff" weight={600} />
        <div style={{position: "absolute", left: 0, right: 0, top: 600, display: "flex", justifyContent: "center", perspective: 1600}}>
          <div
            style={{
              transform: `translateY(${(1 - enter) * 1500 + shake}px) rotateX(${rx}deg) rotateY(${ry}deg) rotateZ(${shake * 0.05}deg)`,
              transformStyle: "preserve-3d",
            }}
          >
            <Card w={760} h={720}>
              <div style={{padding: "48px 56px"}}>
                <div style={{display: "flex", justifyContent: "space-between", alignItems: "center"}}>
                  <Label>Road issues · this month</Label>
                  <div style={{display: "flex", gap: 8}}>
                    {[0, 1, 2].map((i) => (
                      <div key={i} style={{width: 12, height: 12, borderRadius: 9, background: "#D9DCE3"}} />
                    ))}
                  </div>
                </div>
                <div
                  style={{
                    fontFamily: F.sans,
                    fontWeight: 800,
                    fontSize: 190,
                    letterSpacing: -8,
                    color: K.ink,
                    lineHeight: 1,
                    marginTop: 26,
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {fmt(n)}
                </div>
                <div style={{fontFamily: F.sans, fontSize: 32, color: K.gray, marginTop: 6, fontWeight: 500}}>
                  reported by citizens
                </div>
                {/* mini map */}
                <div
                  style={{
                    position: "relative",
                    marginTop: 36,
                    height: 280,
                    borderRadius: 20,
                    background: "#F1F2F5",
                    overflow: "hidden",
                  }}
                >
                  <svg width="648" height="280" style={{position: "absolute", inset: 0}}>
                    {[
                      "M-10 90 C 160 60, 300 140, 660 110",
                      "M-10 210 C 200 230, 380 170, 660 220",
                      "M180 -10 C 200 100, 150 200, 220 290",
                      "M460 -10 C 430 120, 520 190, 480 290",
                    ].map((d, i) => (
                      <path key={i} d={d} stroke="#fff" strokeWidth={i < 2 ? 18 : 12} fill="none" strokeLinecap="round" />
                    ))}
                  </svg>
                  {pins.map((p, i) => {
                    const s = pop(f, p.d, {damping: 9, stiffness: 260});
                    return (
                      <div
                        key={i}
                        style={{
                          position: "absolute",
                          left: p.x,
                          top: p.y,
                          width: 22,
                          height: 22,
                          borderRadius: 99,
                          background: K.orange,
                          border: "4px solid #fff",
                          transform: `scale(${s})`,
                          boxShadow: "0 4px 10px rgba(255,90,31,0.4)",
                        }}
                      />
                    );
                  })}
                  <div
                    style={{
                      position: "absolute",
                      right: 18,
                      bottom: 18,
                      background: "#E7F7EE",
                      color: "#14804A",
                      fontFamily: F.sans,
                      fontWeight: 700,
                      fontSize: 26,
                      padding: "10px 18px",
                      borderRadius: 99,
                      transform: `scale(${pop(f, 76, {damping: 12})})`,
                    }}
                  >
                    ✓ Under control
                  </div>
                </div>
              </div>
            </Card>
          </div>
        </div>
      </Camera>
    </AbsoluteFill>
  );
};

/* ════════ 02 · WRONG. ════════ */
export const SWrong: React.FC = () => {
  const f = useCurrentFrame();
  const slam = interpolate(f, [0, 7], [1.9, 1], {...clamp, easing: inQuad});
  const shake = f > 6 && f < 26 ? Math.sin(f * 2.7) * (26 - f) * 1.3 : 0;
  const shards = Array.from({length: 18}, (_, i) => {
    const a = (i / 18) * Math.PI * 2 + rand(i) * 0.4;
    const sp = 900 + rand(i + 9) * 900;
    const t = prog(f, 4, 60);
    const r = 40 + rand(i + 4) * 90;
    return {
      x: 540 + Math.cos(a) * sp * t,
      y: 960 + Math.sin(a) * sp * t * 0.8 + t * t * 300,
      rot: rand(i + 2) * 720 * t,
      r,
      o: 1 - prog(f, 30, 60),
      pts: `${r * rand(i + 1)},0 ${r},${r * rand(i + 5)} ${r * rand(i + 6) * 0.6},${r}`,
    };
  });
  return (
    <AbsoluteFill>
      <OrangeBg />
      <Floaters color="peach" seed={5} scale={1.6} />
      {shards.map((s, i) => (
        <svg
          key={i}
          width={s.r}
          height={s.r}
          style={{position: "absolute", left: s.x, top: s.y, opacity: s.o, transform: `rotate(${s.rot}deg)`}}
        >
          <polygon points={s.pts} fill="#fff" opacity={0.92} />
        </svg>
      ))}
      <AbsoluteFill style={{transform: `translate(${shake}px, ${shake * 0.6}px)`}}>
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 770,
            textAlign: "center",
            fontFamily: F.sans,
            fontWeight: 900,
            fontSize: 250,
            letterSpacing: -14,
            color: K.ink,
            transform: `scale(${slam})`,
            lineHeight: 1,
          }}
        >
          WRONG.
        </div>
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 1040,
            textAlign: "center",
            fontFamily: F.serif,
            fontStyle: "italic",
            fontSize: 120,
            color: "#fff",
            opacity: prog(f, 34, 50),
            transform: `translateY(${(1 - prog(f, 34, 54)) * 40}px) rotate(-3deg)`,
            filter: `blur(${(1 - prog(f, 34, 52)) * 10}px)`,
          }}
        >
          by a lot.
        </div>
      </AbsoluteFill>
      {/* white flash on impact */}
      <AbsoluteFill style={{background: "#fff", opacity: interpolate(f, [0, 3], [0.7, 0], clamp)}} />
    </AbsoluteFill>
  );
};

/* ════════ 03 · "It says 12" → "There are actually 147" ════════ */
export const SSays: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const born = pop(f, 10, {damping: 9, stiffness: 160});
  const grow = pop(f, 118, {damping: 6, stiffness: 90, mass: 0.9});
  const size = 380 * born + 200 * grow;
  const n = interpolate(f, [118, 232], [12, 147], {...clamp, easing: inOut});
  const wob = f > 118 ? Math.sin((f - 118) / 2.6) * Math.exp(-(f - 118) / 22) * 0.09 : 0;
  return (
    <AbsoluteFill>
      <PaperBg />
      <Floaters seed={7} enter={6} />
      <Camera dur={230} to={1.03}>
        <Words text="It says there are" at={0} y={400} size={64} out={104} />
        <Words text="There are actually" at={112} y={400} size={64} accent={{actually: K.orange}} />
        <Ball size={size} x={540} y={1000 - grow * 40} scaleX={1 + wob} scaleY={1 - wob}>
          <BallLabel size={size * 0.34}>{fmt(n)}</BallLabel>
        </Ball>
        <Words text="issues." at={30} y={1300} size={120} serif color={K.orange} out={104} />
        <div
          style={{
            position: "absolute",
            left: 760,
            top: 640,
            fontFamily: F.serif,
            fontStyle: "italic",
            fontSize: 56,
            color: K.gray,
            opacity: prog(f, 234, 244),
            transform: `rotate(-8deg) translateY(${(1 - prog(f, 234, 248)) * 20}px)`,
          }}
        >
          (gulp)
        </div>
      </Camera>
    </AbsoluteFill>
  );
};

/* ════════ 04 · "where were they hiding?" ════════ */
const QPATH: [number, number][] = (() => {
  // question-mark hook + dot, sampled as points (centre 540, 940)
  const pts: [number, number][] = [];
  for (let i = 0; i <= 16; i++) {
    const a = Math.PI * 1.05 - (i / 16) * Math.PI * 1.45;
    pts.push([540 + Math.cos(a) * 150, 820 - Math.sin(a) * 150]);
  }
  const last = pts[pts.length - 1];
  for (let i = 1; i <= 6; i++) pts.push([lerp(last[0], 540, i / 6), lerp(last[1], 1050, i / 6)]);
  return pts;
})();

export const SWhere: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  // big ball flies to corner and becomes the "real count" tally
  const fly = prog(f, 0, 22, inOut);
  const textT = prog(f, 22, 70);
  const r = 300;
  return (
    <AbsoluteFill>
      <PaperBg />
      <Floaters seed={9} />
      <Ball size={lerp(580, 120, fly)} x={lerp(540, 130, fly)} y={lerp(960, 330, fly)} shadow={fly < 0.5}>
        <BallLabel size={lerp(580, 120, fly) * 0.34}>147</BallLabel>
      </Ball>
      <div style={{position: "absolute", left: 210, top: 304, opacity: prog(f, 18, 30)}}>
        <Label size={26}>actually out there</Label>
      </div>
      {QPATH.map(([x, y], i) => {
        const s = pop(f, 14 + i * 1.6, {damping: 10, stiffness: 240});
        const m = prog(f, 62 + i * 0.5, 80 + i * 0.5, inOut);
        return <Ball key={i} size={50 * s * (1 - m * 0.6)} x={lerp(x, 690, m)} y={lerp(y + 40, 1000, m)} shadow={false} opacity={1 - prog(f, 78 + i * 0.5, 82 + i * 0.5)} />;
      })}
      {(() => {
        const m = prog(f, 64, 82, inOut);
        return (
          <Ball
            size={lerp(78 * pop(f, 14 + QPATH.length * 1.6 + 4, {damping: 8}), 314 * pop(f, 74, {damping: 9}), m)}
            x={lerp(540, 690, m)}
            y={lerp(1190, 1000, m)}
            shadow={m > 0.5}
          >
            <BallLabel size={104 * prog(f, 80, 90)}>12</BallLabel>
          </Ball>
        );
      })()}
      <svg width="1080" height="1920" style={{position: "absolute", inset: 0}}>
        <defs>
          <path id="arc" d={`M ${540 - r} 900 A ${r} ${r} 0 0 1 ${540 + r} 900`} />
        </defs>
        <text fontFamily={F.sans} fontWeight={600} fontSize={52} fill={K.ink} letterSpacing={2} opacity={1 - prog(f, 58, 70)}>
          <textPath href="#arc" startOffset="50%" textAnchor="middle" style={{opacity: textT}} letterSpacing={lerp(18, 2, textT)}>
            where were they hiding?
          </textPath>
        </text>
      </svg>
    </AbsoluteFill>
  );
};

/* ════════ 05 · characters feed the ball 12 → 147 ════════ */
const BEATS = [
  {kind: "pothole" as const, title: "Potholes nobody reported", add: 59, color: K.pothole},
  {kind: "crack" as const, title: "Cracks quietly spreading", add: 52, color: K.crack},
  {kind: "bin" as const, title: "Bins overflowing", add: 15, color: K.bin},
  {kind: "box" as const, title: "Illegal dumping", add: 9, color: K.box},
];
const BEAT = 94;

export const SFeed: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const bi = Math.min(3, Math.floor(f / BEAT));
  const lf = f - bi * BEAT;
  const beat = BEATS[bi];
  const before = 12 + BEATS.slice(0, bi).reduce((a, b) => a + b.add, 0);
  const hitAt = 40;
  const n = before + beat.add * prog(lf, hitAt, hitAt + 26, inOut);
  const total = 12 + BEATS.reduce((a, b) => a + b.add, 0);
  const size = 300 + (n / total) * 170;
  const hit = lf > hitAt ? Math.sin((lf - hitAt) / 2.4) * Math.exp(-(lf - hitAt) / 14) * 0.12 : 0;

  // character enters from the left, feeds, slides out
  const inP = pop(lf, 2, {damping: 13, stiffness: 150});
  const outP = prog(lf, BEAT - 14, BEAT, inQuad);
  const cx = lerp(-200, 270, inP) - outP * 600;
  const cy = 1020;
  const lunge = lf > hitAt - 10 && lf < hitAt + 10 ? Math.sin(((lf - (hitAt - 10)) / 20) * Math.PI) * 40 : 0;

  const done = f > BEAT * 4 - 26;
  const finalPulse = done ? pop(f, BEAT * 4 - 26, {damping: 7}) : 0;

  return (
    <AbsoluteFill>
      <PaperBg />
      <Floaters seed={11} />
      {/* target tally in the corner */}
      <Ball size={120 * (1 + (done ? Math.sin(finalPulse * Math.PI) * 0.25 : 0))} x={130} y={330} shadow={false}>
        <BallLabel size={41}>{total}</BallLabel>
      </Ball>
      <div style={{position: "absolute", left: 210, top: 304}}>
        <Label size={26}>actually out there</Label>
      </div>

      {/* headline per beat (keyed so the word animation restarts) */}
      <div key={bi} style={{position: "absolute", inset: 0}}>
        <BeatTitle text={beat.title} lf={lf} />
      </div>

      {/* feeding particles */}
      {Array.from({length: 7}, (_, i) => {
        const t = prog(lf, hitAt - 14 + i * 2, hitAt + i * 2, inQuad);
        if (t <= 0 || t >= 1) return null;
        const x = lerp(cx + 90, 690, t);
        const y = lerp(cy - 10, 1000, t) - Math.sin(t * Math.PI) * (60 + i * 12);
        return <div key={i} style={{position: "absolute", left: x, top: y, width: 22, height: 22, borderRadius: 99, background: beat.color}} />;
      })}

      <Critter kind={beat.kind} x={cx + lunge} y={cy} s={1.25} t={f} look={1} />

      <Ball size={size} x={690} y={1000} scaleX={1 + hit} scaleY={1 - hit}>
        <BallLabel size={size * 0.33}>{fmt(n)}</BallLabel>
      </Ball>

      {/* delta label */}
      <div
        style={{
          position: "absolute",
          left: 120,
          top: 1210,
          fontFamily: F.sans,
          fontWeight: 800,
          fontStyle: "italic",
          fontSize: 120,
          letterSpacing: -4,
          color: beat.color,
          opacity: Math.min(1, pop(lf, hitAt + 2, {damping: 10})) * (1 - outP),
          transform: `scale(${pop(lf, hitAt + 2, {damping: 8, stiffness: 260})}) rotate(-4deg)`,
          transformOrigin: "0% 50%",
        }}
      >
        +{beat.add}
      </div>

      {done ? (
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 1370,
            textAlign: "center",
            fontFamily: F.serif,
            fontStyle: "italic",
            fontSize: 84,
            color: K.ink,
            opacity: prog(f, BEAT * 4 - 22, BEAT * 4 - 8),
          }}
        >
          there they are.
        </div>
      ) : null}
    </AbsoluteFill>
  );
};

const BeatTitle: React.FC<{text: string; lf: number}> = ({text, lf}) => {
  const words = text.split(" ");
  return (
    <div
      style={{
        position: "absolute",
        left: 60,
        right: 60,
        top: 470,
        textAlign: "center",
        fontFamily: F.sans,
        fontWeight: 600,
        fontSize: 64,
        letterSpacing: -1.6,
        color: K.ink,
        opacity: 1 - prog(lf, BEAT - 12, BEAT - 2),
      }}
    >
      {words.map((w, i) => {
        const p = prog(lf, i * 4, i * 4 + 18);
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              marginRight: 15,
              opacity: p,
              transform: `translateY(${(1 - p) * 28}px)`,
              filter: p < 1 ? `blur(${(1 - p) * 12}px)` : undefined,
            }}
          >
            {w}
          </span>
        );
      })}
    </div>
  );
};
