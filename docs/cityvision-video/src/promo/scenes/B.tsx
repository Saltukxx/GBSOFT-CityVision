import React from "react";
import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {
  Ball,
  Camera,
  Card,
  clamp,
  F,
  Floaters,
  fmt,
  inOut,
  K,
  Label,
  lerp,
  LogoMark,
  NightBg,
  PaperBg,
  Pill,
  prog,
  rand,
  usePop,
  Words,
} from "../kit";

/* ════════ 06 · "And you find out 43 days later. From a phone call." ════════ */
export const SFindOut: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const day = Math.round(interpolate(f, [16, 76], [1, 43], {...clamp, easing: inOut}));
  const red = prog(f, 84, 100);
  const ring = f > 92 ? Math.sin(f * 2.2) * 5 * (f % 30 < 18 ? 1 : 0) : 0;
  const disc = pop(f, 4, {damping: 12});
  return (
    <AbsoluteFill>
      <NightBg />
      <AbsoluteFill
        style={{
          opacity: red,
          background: "radial-gradient(90% 60% at 50% 45%, #A3301E 0%, #6E1A10 55%, #3A0C07 100%)",
        }}
      />
      <Camera dur={150} to={1.05}>
        <Words text="And you find out" at={0} y={400} size={62} color="#fff" />
        {/* day dial */}
        <div
          style={{
            position: "absolute",
            left: 540 - 230,
            top: 700,
            width: 460,
            height: 460,
            borderRadius: 999,
            transform: `scale(${disc})`,
            background: "radial-gradient(circle at 34% 28%, #FFFFFF 0%, #F4F5F8 45%, #D5D8E0 100%)",
            boxShadow: "0 40px 90px rgba(0,0,0,0.5), inset -14px -20px 40px rgba(0,0,0,0.12)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          {Array.from({length: 43}, (_, i) => {
            const a = (i / 43) * Math.PI * 2 - Math.PI / 2;
            const on = i < day;
            return (
              <div
                key={i}
                style={{
                  position: "absolute",
                  left: 230 + Math.cos(a) * 196 - 3,
                  top: 230 + Math.sin(a) * 196 - 11,
                  width: 6,
                  height: 22,
                  borderRadius: 3,
                  background: on ? K.red : "#C9CDD6",
                  transform: `rotate(${(a * 180) / Math.PI + 90}deg)`,
                }}
              />
            );
          })}
          <Label size={26}>Day</Label>
          <div
            style={{
              fontFamily: F.sans,
              fontWeight: 800,
              fontSize: 170,
              letterSpacing: -6,
              color: K.ink,
              lineHeight: 1,
              fontVariantNumeric: "tabular-nums",
            }}
          >
            {day}
          </div>
        </div>
        <Words text="from a phone call." at={92} y={1250} size={110} serif color="#fff" />
        {/* incoming call pill */}
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 1440,
            display: "flex",
            justifyContent: "center",
            transform: `translateX(${ring}px) scale(${pop(f, 100, {damping: 12})})`,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 22,
              padding: "20px 34px 20px 20px",
              borderRadius: 999,
              background: "rgba(255,255,255,0.14)",
              border: "1px solid rgba(255,255,255,0.22)",
              color: "#fff",
              fontFamily: F.sans,
              fontWeight: 600,
              fontSize: 34,
            }}
          >
            <div style={{width: 64, height: 64, borderRadius: 99, background: "#2FBF71", display: "flex", alignItems: "center", justifyContent: "center"}}>
              <svg width="32" height="32" viewBox="0 0 24 24">
                <path
                  fill="#fff"
                  d="M6.6 10.8a15.1 15.1 0 0 0 6.6 6.6l2.2-2.2a1 1 0 0 1 1-.25 11.4 11.4 0 0 0 3.6.57 1 1 0 0 1 1 1V20a1 1 0 0 1-1 1A17 17 0 0 1 3 4a1 1 0 0 1 1-1h3.5a1 1 0 0 1 1 1c0 1.25.2 2.45.57 3.57a1 1 0 0 1-.25 1z"
                />
              </svg>
            </div>
            Angry resident · line 2
          </div>
        </div>
      </Camera>
    </AbsoluteFill>
  );
};

/* ════════ 07 · "380 KM to check." ════════ */
const STREETS = [
  ["Ring Road", "18.6 km"],
  ["Main Street", "4.2 km"],
  ["Harbour Ave", "2.9 km"],
  ["Station Road", "3.4 km"],
  ["North Blvd", "7.5 km"],
  ["Mill Lane", "1.8 km"],
  ["Bridge Road", "5.1 km"],
  ["Park Street", "2.2 km"],
  ["Market Sq", "0.9 km"],
  ["West Link", "6.3 km"],
];

export const SKm: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const n = interpolate(f, [6, 80], [1, 380], {...clamp, easing: inOut});
  return (
    <AbsoluteFill>
      <NightBg glow="rgba(255,90,31,0.12)" />
      <Camera dur={150} from={1.06} to={1}>
        <div style={{position: "absolute", inset: 0, perspective: 1400}}>
          {STREETS.map(([name, km], i) => {
            const p = pop(f, 10 + i * 6, {damping: 14});
            // fixed slots above / below the headline, drifting sideways
            const SLOTS = [
              [250, 360], [760, 330], [470, 480], [820, 600], [230, 640],
              [300, 1370], [780, 1400], [520, 1520], [210, 1650], [820, 1640],
            ];
            const dir = SLOTS[i][1] < 960 ? 1 : -1;
            const x = SLOTS[i][0] + dir * (f * 0.5 - 35);
            const y = SLOTS[i][1] + Math.sin((f + i * 30) / 40) * 8;
            const z = (rand(i + 5) - 0.5) * 240;
            const ang = 0;
            return (
              <div
                key={name}
                style={{
                  position: "absolute",
                  left: x,
                  top: y,
                  transform: `translate(-50%, -50%) translateZ(${z}px) scale(${p}) rotateY(${(x - 540) / 30 + ang}deg)`,
                  opacity: Math.min(1, p) * 0.92,
                  filter: z < -80 ? "blur(2px)" : undefined,
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  padding: "16px 22px",
                  borderRadius: 18,
                  background: "linear-gradient(180deg, #1D1F2A, #14151D)",
                  border: "1px solid rgba(255,255,255,0.09)",
                  boxShadow: "0 18px 40px rgba(0,0,0,0.45)",
                  fontFamily: F.sans,
                  fontSize: 28,
                  color: "#E9EAF0",
                  whiteSpace: "nowrap",
                }}
              >
                <div style={{width: 12, height: 12, borderRadius: 9, background: i % 3 === 0 ? K.orange : "#5B6075"}} />
                <span style={{fontWeight: 600}}>{name}</span>
                <span style={{fontFamily: F.mono, color: "#8C90A3", fontSize: 24}}>{km}</span>
              </div>
            );
          })}
        </div>
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 820,
            textAlign: "center",
            fontFamily: F.sans,
            fontWeight: 900,
            fontSize: 210,
            letterSpacing: -10,
            lineHeight: 1,
            color: "#fff",
            transform: `scale(${pop(f, 0, {damping: 12})})`,
          }}
        >
          <span style={{color: K.orange, fontVariantNumeric: "tabular-nums"}}>{fmt(n)}</span> KM
        </div>
        <Words text="of road to check." at={56} y={1060} size={104} serif color="#fff" />
        <Words text="by car. by eye." at={80} y={1210} size={44} color="#8C90A3" weight={500} />
      </Camera>
    </AbsoluteFill>
  );
};

/* ════════ 08 · CityVision logo reveal ════════ */
export const SLogo: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const m = pop(f, 2, {damping: 10, stiffness: 180});
  const lock = prog(f, 8, 30);
  const word = "CityVision";
  return (
    <AbsoluteFill>
      <PaperBg />
      <Floaters seed={13} enter={10} />
      <Camera dur={100} to={1.04}>
        <div style={{position: "absolute", left: 0, right: 0, top: 640, display: "flex", justifyContent: "center"}}>
          <div style={{transform: `scale(${m}) rotate(${(1 - Math.min(1, m)) * -20}deg)`}}>
            <LogoMark size={260} t={lock} />
          </div>
        </div>
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 960,
            textAlign: "center",
            fontFamily: F.sans,
            fontWeight: 800,
            fontSize: 150,
            letterSpacing: -6,
            color: K.ink,
            lineHeight: 1,
          }}
        >
          {word.split("").map((c, i) => {
            const p = prog(f, 14 + i * 2, 34 + i * 2);
            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  opacity: p,
                  transform: `translateY(${(1 - p) * 70}px)`,
                  filter: p < 1 ? `blur(${(1 - p) * 10}px)` : undefined,
                  color: i >= 4 ? K.orange : K.ink,
                }}
              >
                {c}
              </span>
            );
          })}
        </div>
        <Words text="by GBSoft" at={40} y={1140} size={64} serif color={K.gray} />
      </Camera>
    </AbsoluteFill>
  );
};

/* ════════ 09 · Every flight. Every street. Every defect. → one map ════════ */
const DetectThumb: React.FC<{label: string; conf: string; color: string; seed: number}> = ({label, conf, color, seed}) => (
  <div style={{position: "absolute", inset: 0}}>
    {/* asphalt */}
    <div
      style={{
        position: "absolute",
        inset: 0,
        background: `radial-gradient(120% 90% at ${30 + rand(seed) * 40}% 40%, #6E7280 0%, #4D515C 55%, #3B3E47 100%)`,
      }}
    />
    <svg width="100%" height="100%" style={{position: "absolute", inset: 0}} viewBox="0 0 400 280" preserveAspectRatio="none">
      <line x1="200" y1="0" x2="200" y2="280" stroke="#E9D9A0" strokeWidth="6" strokeDasharray="34 26" opacity="0.8" />
      <ellipse cx={120 + rand(seed + 1) * 160} cy={150} rx="54" ry="30" fill="#24262C" opacity="0.9" />
    </svg>
    <div
      style={{
        position: "absolute",
        left: `${18 + rand(seed + 1) * 40}%`,
        top: "34%",
        width: "36%",
        height: "38%",
        border: `5px solid ${color}`,
        borderRadius: 10,
      }}
    >
      <div
        style={{
          position: "absolute",
          left: -5,
          top: -46,
          background: color,
          color: "#fff",
          fontFamily: F.mono,
          fontSize: 22,
          padding: "6px 10px",
          borderRadius: 8,
          whiteSpace: "nowrap",
        }}
      >
        {label} {conf}
      </div>
    </div>
  </div>
);

const RouteCard: React.FC<{t: number}> = ({t}) => (
  <div style={{position: "absolute", inset: 0, background: "#F1F2F5"}}>
    <svg width="100%" height="100%" viewBox="0 0 400 280">
      {["M-10 70 C 120 40, 260 110, 410 80", "M-10 200 C 140 230, 260 160, 410 210", "M130 -10 C 150 120, 110 200, 160 290"].map(
        (d, i) => (
          <path key={i} d={d} stroke="#fff" strokeWidth="16" fill="none" />
        ),
      )}
      <path
        d="M20 240 C 80 200, 120 120, 200 130 S 330 60, 380 40"
        stroke={K.orange}
        strokeWidth="6"
        fill="none"
        strokeDasharray="14 10"
        strokeDashoffset={-t * 2}
        strokeLinecap="round"
      />
      <circle cx={lerp(20, 380, (t % 120) / 120)} cy={lerp(240, 40, (t % 120) / 120)} r="12" fill={K.ink} />
    </svg>
    <div style={{position: "absolute", left: 22, top: 18}}>
      <Label size={20}>Flight 0412 · same route</Label>
    </div>
  </div>
);

export const SEvery: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const collapse = prog(f, 186, 226, inOut);
  const orbit = interpolate(f, [0, 250], [-14, 10]);
  const cards: {x: number; y: number; z: number; w: number; h: number; ry: number; at: number; el: React.ReactNode}[] = [
    {x: 300, y: 560, z: -100, w: 520, h: 360, ry: 14, at: 0, el: <RouteCard t={f} />},
    {x: 780, y: 760, z: 80, w: 460, h: 320, ry: -10, at: 8, el: <DetectThumb label="pothole" conf="0.94" color={K.orange} seed={1} />},
    {x: 330, y: 1040, z: 160, w: 470, h: 330, ry: 12, at: 62, el: <DetectThumb label="crack" conf="0.88" color={K.crack} seed={4} />},
    {x: 790, y: 1240, z: -60, w: 440, h: 300, ry: -14, at: 70, el: <DetectThumb label="overflowing bin" conf="0.91" color={K.bin} seed={8} />},
    {x: 360, y: 1420, z: -160, w: 420, h: 280, ry: 10, at: 124, el: <DetectThumb label="dumping" conf="0.86" color={K.box} seed={12} />},
    {x: 760, y: 470, z: -220, w: 380, h: 260, ry: -8, at: 130, el: <DetectThumb label="pothole" conf="0.97" color={K.orange} seed={16} />},
  ];
  const label = f < 62 ? "Every flight." : f < 124 ? "Every street." : f < 186 ? "Every defect." : "One map.";
  const labelAt = f < 62 ? 4 : f < 124 ? 62 : f < 186 ? 124 : 192;
  return (
    <AbsoluteFill>
      <PaperBg />
      <Floaters seed={17} />
      <AbsoluteFill style={{perspective: 1500}}>
        <AbsoluteFill style={{transformStyle: "preserve-3d", transform: `rotateY(${orbit}deg) rotateX(6deg)`}}>
          {cards.map((c, i) => {
            const p = pop(f, c.at + 2, {damping: 14, stiffness: 140});
            const x = lerp(c.x, 540, collapse);
            const y = lerp(c.y, 960, collapse);
            const z = lerp(c.z, -300 + i * 4, collapse);
            const s = lerp(1, 0.5, collapse);
            return (
              <div
                key={i}
                style={{
                  position: "absolute",
                  left: x,
                  top: y,
                  transform: `translate(-50%, -50%) translateZ(${z + (1 - p) * -900}px) rotateY(${c.ry * (1 - collapse)}deg) rotateZ(${(i - 2.5) * 2 * (1 - collapse)}deg) scale(${s})`,
                  opacity: Math.min(1, p * 1.4) * (1 - prog(f, 222, 232)),
                }}
              >
                <Card w={c.w} h={c.h}>
                  {c.el}
                </Card>
              </div>
            );
          })}
        </AbsoluteFill>
      </AbsoluteFill>
      {/* collapse target: orange orb */}
      <Ball size={420 * pop(f, 220, {damping: 9})} x={540} y={960}>
        <svg width="200" height="200" viewBox="0 0 24 24" style={{opacity: prog(f, 226, 236)}}>
          <path fill="#FFF7F2" d="M12 2a7 7 0 0 0-7 7c0 5.2 7 13 7 13s7-7.8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z" />
        </svg>
      </Ball>
      <div key={label}>
        <Pill text={label} y={1580} at={labelAt} />
      </div>
    </AbsoluteFill>
  );
};

/* ════════ 10 · Overview — the real number ════════ */
const LEGEND = [
  {name: "Potholes", n: 71, c: K.orange},
  {name: "Cracks", n: 52, c: K.crack},
  {name: "Overflowing bins", n: 15, c: K.bin},
  {name: "Illegal dumping", n: 9, c: K.box},
];

export const SReal: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const enter = pop(f, 0, {damping: 16, stiffness: 140});
  const n = interpolate(f, [8, 50], [0, 147], {...clamp, easing: inOut});
  const pins = Array.from({length: 26}, (_, i) => ({
    x: 30 + rand(i * 5 + 1) * 820,
    y: 20 + rand(i * 7 + 2) * 300,
    c: LEGEND[i % 4].c,
  }));
  return (
    <AbsoluteFill>
      <PaperBg />
      <div
        style={{
          position: "absolute",
          left: 60,
          top: 340,
          transform: `translateY(${(1 - enter) * 900}px) perspective(1600px) rotateX(${(1 - enter) * 20}deg)`,
        }}
      >
        <Card w={960} h={1110}>
          <div style={{padding: "44px 50px"}}>
            <div style={{display: "flex", alignItems: "center", gap: 18}}>
              <LogoMark size={56} />
              <div style={{fontFamily: F.sans, fontWeight: 700, fontSize: 40, color: K.ink, letterSpacing: -1}}>Overview</div>
              <div style={{marginLeft: "auto", fontFamily: F.mono, fontSize: 24, color: K.gray}}>after today's flight</div>
            </div>
            <div style={{marginTop: 40}}>
              <Label>What your roads actually have</Label>
            </div>
            <div
              style={{
                marginTop: 18,
                display: "inline-flex",
                alignItems: "baseline",
                gap: 18,
                background: `linear-gradient(180deg, #FF7A3E, ${K.orange})`,
                borderRadius: 999,
                padding: "16px 46px 20px",
                boxShadow: "0 20px 40px rgba(255,90,31,0.35), inset 0 2px 0 rgba(255,255,255,0.35)",
                transform: `scale(${pop(f, 6, {damping: 10})})`,
                transformOrigin: "0% 50%",
              }}
            >
              <span style={{fontFamily: F.sans, fontWeight: 800, fontSize: 150, color: "#fff", letterSpacing: -6, lineHeight: 1, fontVariantNumeric: "tabular-nums"}}>
                {fmt(n)}
              </span>
              <span style={{fontFamily: F.sans, fontWeight: 600, fontSize: 44, color: "rgba(255,255,255,0.9)"}}>issues</span>
            </div>
            {/* map */}
            <div style={{position: "relative", marginTop: 40, height: 360, borderRadius: 24, background: "#F1F2F5", overflow: "hidden"}}>
              <svg width="860" height="360" style={{position: "absolute", inset: 0}}>
                {[
                  "M-10 80 C 200 50, 500 150, 870 90",
                  "M-10 270 C 260 300, 560 200, 870 280",
                  "M210 -10 C 240 120, 170 240, 260 370",
                  "M600 -10 C 560 140, 680 230, 620 370",
                ].map((d, i) => (
                  <path key={i} d={d} stroke="#fff" strokeWidth={i < 2 ? 22 : 14} fill="none" strokeLinecap="round" />
                ))}
              </svg>
              {pins.map((p, i) => (
                <div
                  key={i}
                  style={{
                    position: "absolute",
                    left: p.x,
                    top: p.y,
                    width: 24,
                    height: 24,
                    borderRadius: 99,
                    background: p.c,
                    border: "4px solid #fff",
                    transform: `scale(${pop(f, 14 + i * 1.5, {damping: 9, stiffness: 260})})`,
                    boxShadow: "0 4px 10px rgba(0,0,0,0.18)",
                  }}
                />
              ))}
            </div>
            {/* legend */}
            <div style={{marginTop: 34, display: "flex", flexDirection: "column", gap: 18}}>
              {LEGEND.map((l, i) => {
                const p = prog(f, 26 + i * 6, 50 + i * 6);
                return (
                  <div
                    key={l.name}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 18,
                      opacity: p,
                      transform: `translateX(${(1 - p) * 40}px)`,
                      fontFamily: F.sans,
                      fontSize: 34,
                      color: K.ink,
                      fontWeight: 500,
                    }}
                  >
                    <div style={{width: 18, height: 18, borderRadius: 9, background: l.c}} />
                    {l.name}
                    <div style={{flex: 1, height: 10, borderRadius: 5, background: "#EEF0F3", marginLeft: 12, overflow: "hidden"}}>
                      <div style={{width: `${(l.n / 71) * 100 * p}%`, height: "100%", borderRadius: 5, background: l.c}} />
                    </div>
                    <span style={{fontFamily: F.mono, fontSize: 30, width: 60, textAlign: "right"}}>{l.n}</span>
                  </div>
                );
              })}
            </div>
            <div
              style={{
                marginTop: 34,
                fontFamily: F.sans,
                fontSize: 28,
                color: K.gray,
                opacity: prog(f, 60, 76),
              }}
            >
              Seen on 3 flights? Still <b style={{color: K.ink}}>one</b> work order.
            </div>
          </div>
        </Card>
      </div>
      <Pill text="The real number." y={1580} at={52} />
    </AbsoluteFill>
  );
};

