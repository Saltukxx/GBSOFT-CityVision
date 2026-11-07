import {loadFont as loadSerif} from "@remotion/google-fonts/InstrumentSerif";
import {loadFont as loadSans} from "@remotion/google-fonts/InterTight";
import {loadFont as loadMono} from "@remotion/google-fonts/GeistMono";
import React from "react";
import {AbsoluteFill, Easing, interpolate, spring, useCurrentFrame, useVideoConfig} from "remotion";

/* ───────── fonts ───────── */
const sans = loadSans("normal", {weights: ["400", "500", "600", "700", "800", "900"], subsets: ["latin"]});
const serif = loadSerif("italic", {weights: ["400"], subsets: ["latin"]});
const mono = loadMono("normal", {weights: ["400", "500"], subsets: ["latin"]});

export const F = {
  sans: `${sans.fontFamily}, 'Helvetica Neue', Arial, sans-serif`,
  serif: `${serif.fontFamily}, Georgia, serif`,
  mono: `${mono.fontFamily}, ui-monospace, Menlo, monospace`,
};

/* ───────── palette ───────── */
export const K = {
  orange: "#FF5A1F",
  orangeDeep: "#E2400C",
  ink: "#111216",
  gray: "#8B909B",
  grayLight: "#B9BDC6",
  paper: "#F2F3F6",
  night: "#08090E",
  pothole: "#4F46E5",
  crack: "#E23A8C",
  bin: "#16A34A",
  box: "#B9834E",
  red: "#E5352B",
  // series palette: white first, navy second, one accent per scene
  navy: "#0B1A3A",
  navyText: "#0E1B3D",
  teal: "#0FB5C8",
  yellow: "#F5B300",
  yellowText: "#C98A00",
  pink: "#E23A8C",
  purple: "#7C5CFF",
  green: "#16A34A",
};

/* ───────── motion helpers ───────── */
export const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;
export const outExpo = Easing.bezier(0.16, 1, 0.3, 1);
export const inOut = Easing.bezier(0.65, 0, 0.35, 1);
export const inQuad = Easing.bezier(0.55, 0, 1, 0.45);

/** 0 → 1 between frames a and b with ease. */
export const prog = (f: number, a: number, b: number, ease = outExpo) =>
  interpolate(f, [a, b], [0, 1], {...clamp, easing: ease});

/** Springy pop: 0 → 1 (with overshoot). */
export const usePop = () => {
  const {fps} = useVideoConfig();
  return (f: number, delay: number, cfg: {damping?: number; stiffness?: number; mass?: number} = {}) =>
    spring({frame: f - delay, fps, config: {damping: 11, stiffness: 170, mass: 0.7, ...cfg}});
};

export const lerp = (a: number, b: number, t: number) => a + (b - a) * t;

/** Deterministic pseudo-random. */
export const rand = (i: number) => {
  const x = Math.sin(i * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
};

export const fmt = (n: number) => Math.round(n).toLocaleString("en-US");

/* ───────── backgrounds ───────── */
export const PaperBg: React.FC<{tint?: string}> = ({tint = "rgba(255,180,150,0.22)"}) => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(120% 70% at 50% 42%, #FAFAFB 0%, #EEEFF3 55%, #E3E5EB 100%)`,
    }}
  >
    <AbsoluteFill style={{background: `radial-gradient(90% 40% at 50% 105%, ${tint} 0%, rgba(0,0,0,0) 70%)`}} />
  </AbsoluteFill>
);

export const OrangeBg: React.FC = () => (
  <AbsoluteFill
    style={{
      background: `radial-gradient(110% 70% at 50% 40%, #FF7436 0%, #FF5A1F 45%, #EE4812 100%)`,
    }}
  />
);

export const NightBg: React.FC<{glow?: string}> = ({glow = "rgba(80,90,160,0.18)"}) => (
  <AbsoluteFill style={{background: `radial-gradient(90% 60% at 50% 45%, #141623 0%, #08090E 70%)`}}>
    <AbsoluteFill style={{background: `radial-gradient(60% 35% at 50% 50%, ${glow} 0%, rgba(0,0,0,0) 70%)`}} />
  </AbsoluteFill>
);

export const WhiteBg: React.FC<{tint?: string}> = ({tint = "rgba(140,160,210,0.16)"}) => (
  <AbsoluteFill style={{background: "radial-gradient(120% 70% at 50% 40%, #FFFFFF 0%, #F6F7FA 55%, #E9ECF2 100%)"}}>
    <AbsoluteFill style={{background: `radial-gradient(90% 40% at 50% 105%, ${tint} 0%, rgba(0,0,0,0) 70%)`}} />
  </AbsoluteFill>
);

export const NavyBg: React.FC<{glow?: string}> = ({glow = "rgba(15,181,200,0.10)"}) => (
  <AbsoluteFill style={{background: "radial-gradient(110% 70% at 50% 40%, #17306A 0%, #0D1F48 50%, #081530 100%)"}}>
    <AbsoluteFill style={{background: `radial-gradient(60% 35% at 50% 55%, ${glow} 0%, rgba(0,0,0,0) 70%)`}} />
  </AbsoluteFill>
);

/* ───────── glossy sphere ───────── */
export type BallColor = "orange" | "peach" | "white" | "yellow" | "teal" | "pink" | "purple" | "green" | "navy";

type BallProps = {
  size: number;
  x: number;
  y: number;
  color?: BallColor;
  scaleX?: number;
  scaleY?: number;
  blur?: number;
  shadow?: boolean;
  opacity?: number;
  children?: React.ReactNode;
  rotate?: number;
};

const BALL_GRAD: Record<NonNullable<BallProps["color"]>, string> = {
  orange:
    "radial-gradient(circle at 34% 28%, #FFC3A1 0%, #FF8C52 12%, #FF5E22 38%, #EC4510 64%, #B8300A 88%, #8E2406 100%)",
  peach: "radial-gradient(circle at 34% 28%, #FFFFFF 0%, #FFF1E8 18%, #F6D8C8 52%, #E3B49E 82%, #CF9C86 100%)",
  white: "radial-gradient(circle at 34% 28%, #FFFFFF 0%, #FBFBFC 30%, #E7E9EE 70%, #CDD1D9 100%)",
  yellow: "radial-gradient(circle at 34% 28%, #FFF6C9 0%, #FFD860 20%, #FDB61F 55%, #E6900A 85%, #C67508 100%)",
  teal: "radial-gradient(circle at 34% 28%, #C8F7FC 0%, #5FDDEB 16%, #14B8CB 45%, #0A8FA3 78%, #066A7A 100%)",
  pink: "radial-gradient(circle at 34% 28%, #FFD0E5 0%, #F56FAE 16%, #E23A8C 45%, #B81F6B 78%, #8A1450 100%)",
  purple: "radial-gradient(circle at 34% 28%, #E2DAFF 0%, #A792FF 16%, #7C5CFF 45%, #5A3BDB 78%, #3F27A8 100%)",
  green: "radial-gradient(circle at 34% 28%, #CFF7DD 0%, #5FD98A 16%, #22B455 45%, #15823D 78%, #0E5F2C 100%)",
  navy: "radial-gradient(circle at 34% 28%, #8EA3D6 0%, #3C5596 16%, #1B3170 45%, #0F1F4D 78%, #08132F 100%)",
};

const BALL_GLOW: Record<BallColor, string> = {
  orange: "rgba(240,80,20,0.28)",
  peach: "rgba(90,60,40,0.12)",
  white: "rgba(40,50,80,0.12)",
  yellow: "rgba(240,170,20,0.28)",
  teal: "rgba(15,181,200,0.28)",
  pink: "rgba(226,58,140,0.28)",
  purple: "rgba(124,92,255,0.28)",
  green: "rgba(22,163,74,0.28)",
  navy: "rgba(11,26,58,0.3)",
};

export const Ball: React.FC<BallProps> = ({
  size,
  x,
  y,
  color = "orange",
  scaleX = 1,
  scaleY = 1,
  blur = 0,
  shadow = true,
  opacity = 1,
  children,
  rotate = 0,
}) => (
  <div
    style={{
      position: "absolute",
      left: x - size / 2,
      top: y - size / 2,
      width: size,
      height: size,
      opacity,
      filter: blur ? `blur(${blur}px)` : undefined,
    }}
  >
    {shadow ? (
      <div
        style={{
          position: "absolute",
          left: size * 0.12,
          top: size * 0.86,
          width: size * 0.76,
          height: size * 0.2,
          borderRadius: "50%",
          background: "radial-gradient(closest-side, rgba(60,20,5,0.28), rgba(60,20,5,0))",
          transform: `scaleX(${scaleX})`,
        }}
      />
    ) : null}
    <div
      style={{
        position: "absolute",
        inset: 0,
        borderRadius: "50%",
        background: BALL_GRAD[color],
        transform: `rotate(${rotate}deg) scale(${scaleX}, ${scaleY})`,
        transformOrigin: "50% 100%",
        boxShadow:
          color === "peach" || color === "white"
            ? `inset ${-size * 0.05}px ${-size * 0.07}px ${size * 0.14}px rgba(90,60,40,0.18)`
            : `inset ${-size * 0.05}px ${-size * 0.07}px ${size * 0.14}px rgba(0,0,0,0.28), 0 ${size * 0.08}px ${size * 0.22}px ${BALL_GLOW[color]}`,
        overflow: "hidden",
      }}
    >
      {/* specular highlight */}
      <div
        style={{
          position: "absolute",
          left: "18%",
          top: "11%",
          width: "34%",
          height: "22%",
          borderRadius: "50%",
          background: "radial-gradient(closest-side, rgba(255,255,255,0.85), rgba(255,255,255,0))",
          transform: "rotate(-28deg)",
        }}
      />
      {/* bottom rim light */}
      <div
        style={{
          position: "absolute",
          left: "22%",
          bottom: "4%",
          width: "56%",
          height: "18%",
          borderRadius: "50%",
          background: "radial-gradient(closest-side, rgba(255,190,150,0.35), rgba(255,190,150,0))",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {children}
      </div>
    </div>
  </div>
);

/** Number label inside an orange ball. */
export const BallLabel: React.FC<{size: number; children: React.ReactNode}> = ({size, children}) => (
  <div
    style={{
      fontFamily: F.sans,
      fontWeight: 700,
      fontSize: size,
      color: "#FFF7F2",
      letterSpacing: -size * 0.03,
      textShadow: "0 2px 6px rgba(120,25,0,0.35)",
      fontVariantNumeric: "tabular-nums",
    }}
  >
    {children}
  </div>
);

/** Small drifting spheres at the frame edges (depth-of-field accents). */
export const Floaters: React.FC<{
  color?: BallProps["color"];
  count?: number;
  seed?: number;
  enter?: number;
  scale?: number;
}> = ({color = "orange", count = 7, seed = 1, enter = 0, scale = 1}) => {
  const f = useCurrentFrame();
  const pop = usePop();
  const items = Array.from({length: count}, (_, i) => {
    const r1 = rand(seed * 31 + i);
    const r2 = rand(seed * 71 + i * 3);
    const r3 = rand(seed * 13 + i * 7);
    const side = i % 2 === 0 ? -1 : 1;
    const x = side < 0 ? 40 + r1 * 150 : 1040 - r1 * 150;
    const y = 260 + ((i * 0.618 + r2) % 1) * 1380;
    const size = (18 + r3 * 46) * scale;
    const depth = r3; // bigger = closer = blurrier
    const p = pop(f, enter + i * 3, {damping: 13});
    const dy = Math.sin((f + i * 40) / (50 + r1 * 30)) * 14;
    const dx = Math.cos((f + i * 25) / (70 + r2 * 30)) * 10;
    return (
      <Ball
        key={i}
        size={size * p}
        x={x + dx}
        y={y + dy}
        color={color}
        shadow={false}
        blur={depth > 0.7 ? 3 : 0}
        opacity={0.95}
      />
    );
  });
  return <AbsoluteFill>{items}</AbsoluteFill>;
};

/* ───────── typography ───────── */
type WordsProps = {
  text: string;
  at: number;
  y: number;
  size?: number;
  weight?: number;
  color?: string;
  serif?: boolean;
  stagger?: number;
  out?: number;
  letterSpacing?: number;
  align?: "center" | "left";
  x?: number;
  /** words to render in italic serif, with an optional colour */
  accent?: Record<string, string>;
};

/** Word-by-word rise + de-blur. */
export const Words: React.FC<WordsProps> = ({
  text,
  at,
  y,
  size = 64,
  weight = 600,
  color = K.ink,
  serif = false,
  stagger = 4,
  out,
  letterSpacing,
  align = "center",
  x = 0,
  accent = {},
}) => {
  const f = useCurrentFrame();
  const words = text.split(" ");
  const outP = out !== undefined ? prog(f, out, out + 12, inQuad) : 0;
  return (
    <div
      style={{
        position: "absolute",
        left: align === "center" ? 60 : x,
        right: align === "center" ? 60 : undefined,
        top: y,
        textAlign: align,
        fontFamily: serif ? F.serif : F.sans,
        fontStyle: serif ? "italic" : "normal",
        fontWeight: serif ? 400 : weight,
        fontSize: size,
        lineHeight: 1.08,
        letterSpacing: letterSpacing ?? (serif ? -size * 0.01 : -size * 0.025),
        color,
        opacity: 1 - outP,
        transform: `translateY(${-outP * 30}px)`,
        filter: outP ? `blur(${outP * 10}px)` : undefined,
      }}
    >
      {words.map((w, i) => {
        const p = prog(f, at + i * stagger, at + i * stagger + 18);
        const acc = accent[w];
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              marginRight: i < words.length - 1 ? size * 0.24 : 0,
              opacity: p,
              transform: `translateY(${(1 - p) * size * 0.45}px) scale(${0.96 + p * 0.04})`,
              filter: p < 1 ? `blur(${(1 - p) * 12}px)` : undefined,
              fontFamily: acc ? F.serif : undefined,
              fontStyle: acc ? "italic" : undefined,
              fontWeight: acc ? 400 : undefined,
              color: acc || undefined,
              fontSize: acc ? size * 1.18 : undefined,
              letterSpacing: acc ? -size * 0.005 : undefined,
            }}
          >
            {w}
          </span>
        );
      })}
    </div>
  );
};

/** Black rounded caption pill (bottom label). */
export const Pill: React.FC<{text: string; y: number; at: number; out?: number; bg?: string; color?: string}> = ({
  text,
  y,
  at,
  out,
  bg = K.ink,
  color = "#fff",
}) => {
  const f = useCurrentFrame();
  const pop = usePop();
  const p = pop(f, at, {damping: 14, stiffness: 220});
  const o = out !== undefined ? 1 - prog(f, out, out + 8) : 1;
  return (
    <div style={{position: "absolute", left: 0, right: 0, top: y, display: "flex", justifyContent: "center"}}>
      <div
        style={{
          background: bg,
          color,
          fontFamily: F.sans,
          fontWeight: 700,
          fontSize: 42,
          letterSpacing: -0.6,
          padding: "20px 38px",
          borderRadius: 999,
          transform: `scale(${p})`,
          opacity: Math.min(1, p) * o,
          boxShadow: "0 18px 40px rgba(0,0,0,0.18)",
        }}
      >
        {text}
      </div>
    </div>
  );
};

/* ───────── characters ───────── */
export const Eyes: React.FC<{w: number; look?: number; blink?: boolean; worried?: boolean}> = ({
  w,
  look = 0,
  blink = false,
  worried = false,
}) => {
  const e = w * 0.2;
  const eye = (k: number) => (
    <div
      key={k}
      style={{
        width: e,
        height: blink ? e * 0.12 : e,
        borderRadius: 999,
        background: "#fff",
        position: "relative",
        boxShadow: "inset 0 -2px 3px rgba(0,0,0,0.15)",
        transform: worried ? `rotate(${k ? 14 : -14}deg)` : undefined,
      }}
    >
      {!blink && (
        <div
          style={{
            position: "absolute",
            width: e * 0.52,
            height: e * 0.52,
            borderRadius: 999,
            background: "#0D0E12",
            left: e * 0.24 + look * e * 0.18,
            top: e * 0.26,
          }}
        />
      )}
    </div>
  );
  return <div style={{display: "flex", gap: e * 0.45}}>{[0, 1].map(eye)}</div>;
};

/** Glossy body with eyes, used for issue characters. */
export const Critter: React.FC<{
  kind: "pothole" | "crack" | "bin" | "box";
  x: number;
  y: number;
  s: number;
  t: number;
  look?: number;
}> = ({kind, x, y, s, t, look = 1}) => {
  const squash = 1 + Math.sin(t / 5) * 0.035;
  const blink = Math.floor(t) % 70 > 66;
  const W = 230 * s;
  let body: React.ReactNode;
  if (kind === "pothole") {
    body = (
      <div
        style={{
          width: W,
          height: W * 0.92,
          borderRadius: "48% 52% 46% 54% / 56% 50% 50% 44%",
          background:
            "radial-gradient(circle at 34% 28%, #A5A8FF 0%, #6E6CF6 18%, #4F46E5 48%, #3328B8 78%, #251C8C 100%)",
          boxShadow: `inset -12px -18px 30px rgba(20,10,80,0.45), 0 20px 40px rgba(79,70,229,0.28)`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: W * 0.06,
        }}
      >
        <Eyes w={W} look={look} blink={blink} />
        <div style={{width: W * 0.36, height: W * 0.13, borderRadius: "50%", background: "#14104A", opacity: 0.9}} />
      </div>
    );
  } else if (kind === "crack") {
    body = (
      <svg width={W} height={W} viewBox="0 0 230 230" style={{overflow: "visible"}}>
        <defs>
          <radialGradient id="crk" cx="34%" cy="28%" r="80%">
            <stop offset="0" stopColor="#FFB3D5" />
            <stop offset="0.25" stopColor="#F2589E" />
            <stop offset="0.7" stopColor="#D42A7A" />
            <stop offset="1" stopColor="#9C175A" />
          </radialGradient>
        </defs>
        <path
          d="M128 6 L70 104 L112 108 L58 224 L176 92 L130 88 L170 10 Z"
          fill="url(#crk)"
          stroke="#9C175A"
          strokeWidth="3"
          strokeLinejoin="round"
        />
        <foreignObject x="72" y="62" width="110" height="60">
          <div style={{display: "flex", justifyContent: "center", paddingTop: 6}}>
            <Eyes w={110} look={look} blink={blink} worried />
          </div>
        </foreignObject>
      </svg>
    );
  } else if (kind === "bin") {
    const lid = Math.max(0, Math.sin(t / 6)) * 22;
    body = (
      <div style={{position: "relative", width: W, height: W * 1.05}}>
        <div
          style={{
            position: "absolute",
            left: W * 0.06,
            top: W * 0.02,
            width: W * 0.88,
            height: W * 0.14,
            borderRadius: W * 0.05,
            background: "linear-gradient(180deg, #4ADE80, #15803D)",
            transform: `rotate(${-lid}deg)`,
            transformOrigin: "0% 100%",
            boxShadow: "0 4px 8px rgba(0,0,0,0.15)",
          }}
        />
        {/* trash poking out */}
        <div
          style={{
            position: "absolute",
            left: W * 0.2,
            top: W * 0.08 - lid * 0.5,
            width: W * 0.24,
            height: W * 0.16,
            background: "#F5F0E6",
            borderRadius: 6,
            transform: "rotate(-12deg)",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: W * 0.52,
            top: W * 0.06 - lid * 0.7,
            width: W * 0.2,
            height: W * 0.18,
            background: "#C9D4E5",
            borderRadius: 30,
          }}
        />
        <div
          style={{
            position: "absolute",
            left: W * 0.12,
            top: W * 0.17,
            width: W * 0.76,
            height: W * 0.86,
            borderRadius: `${W * 0.06}px ${W * 0.06}px ${W * 0.12}px ${W * 0.12}px`,
            background: "linear-gradient(90deg, #15803D 0%, #22C55E 30%, #4ADE80 45%, #16A34A 75%, #0F6B30 100%)",
            boxShadow: "0 20px 40px rgba(22,163,74,0.25)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Eyes w={W * 0.85} look={look} blink={blink} />
        </div>
      </div>
    );
  } else {
    body = (
      <div style={{position: "relative", width: W, height: W * 0.86}}>
        <div
          style={{
            position: "absolute",
            inset: 0,
            borderRadius: 14,
            background: "linear-gradient(160deg, #E2B07C 0%, #C8925A 45%, #A8743F 100%)",
            boxShadow: "inset -10px -14px 24px rgba(90,50,10,0.3), 0 20px 40px rgba(150,95,40,0.28)",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: "44%",
            top: 0,
            width: "12%",
            height: "100%",
            background: "rgba(240,215,170,0.75)",
          }}
        />
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: "46%",
            display: "flex",
            justifyContent: "center",
          }}
        >
          <Eyes w={W * 0.9} look={look} blink={blink} />
        </div>
        <div
          style={{
            position: "absolute",
            right: W * 0.08,
            bottom: W * 0.08,
            fontFamily: F.mono,
            fontSize: W * 0.07,
            color: "rgba(80,45,10,0.65)",
          }}
        >
          FRAGILE?
        </div>
      </div>
    );
  }
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        transform: `translate(-50%, -50%) scale(${2 - squash}, ${squash})`,
        transformOrigin: "50% 100%",
      }}
    >
      {body}
    </div>
  );
};

/* ───────── brand mark ───────── */
export const LogoMark: React.FC<{size: number; t?: number; light?: boolean}> = ({size, t = 1, light = false}) => {
  const b = size * 0.22;
  const inset = lerp(-size * 0.12, size * 0.1, t);
  const corner = (r: number) => {
    const pos: React.CSSProperties = {position: "absolute", width: b, height: b, borderColor: light ? K.navy : "#fff", borderStyle: "solid"};
    const w = Math.max(3, size * 0.055);
    if (r === 0) Object.assign(pos, {left: inset, top: inset, borderWidth: `${w}px 0 0 ${w}px`, borderTopLeftRadius: b * 0.3});
    if (r === 1) Object.assign(pos, {right: inset, top: inset, borderWidth: `${w}px ${w}px 0 0`, borderTopRightRadius: b * 0.3});
    if (r === 2) Object.assign(pos, {left: inset, bottom: inset, borderWidth: `0 0 ${w}px ${w}px`, borderBottomLeftRadius: b * 0.3});
    if (r === 3) Object.assign(pos, {right: inset, bottom: inset, borderWidth: `0 ${w}px ${w}px 0`, borderBottomRightRadius: b * 0.3});
    return <div key={r} style={pos} />;
  };
  return (
    <div
      style={{
        position: "relative",
        width: size,
        height: size,
        borderRadius: size * 0.26,
        background: light ? "linear-gradient(160deg, #FFFFFF 0%, #E7EBF3 100%)" : "linear-gradient(160deg, #23252E 0%, #0B0C10 100%)",
        boxShadow: `0 ${size * 0.12}px ${size * 0.3}px rgba(0,0,0,0.25)`,
      }}
    >
      {[0, 1, 2, 3].map(corner)}
      <Ball size={size * 0.38 * t} x={size / 2} y={size / 2} shadow={false} />
    </div>
  );
};

/* ───────── generic UI card ───────── */
export const Card: React.FC<{
  w: number;
  h: number;
  children?: React.ReactNode;
  style?: React.CSSProperties;
  dark?: boolean;
}> = ({w, h, children, style, dark}) => (
  <div
    style={{
      width: w,
      height: h,
      borderRadius: 30,
      background: dark ? "linear-gradient(180deg, #1B1D27, #12131A)" : "linear-gradient(180deg, #FFFFFF, #F8F9FB)",
      border: dark ? "1px solid rgba(255,255,255,0.08)" : "1px solid rgba(17,18,22,0.06)",
      boxShadow: dark
        ? "0 30px 60px rgba(0,0,0,0.5)"
        : "0 40px 80px rgba(30,30,60,0.16), 0 6px 16px rgba(30,30,60,0.06)",
      overflow: "hidden",
      position: "relative",
      ...style,
    }}
  >
    {children}
  </div>
);

/** Small uppercase label. */
export const Label: React.FC<{children: React.ReactNode; color?: string; size?: number}> = ({
  children,
  color = K.gray,
  size = 24,
}) => (
  <div
    style={{
      fontFamily: F.sans,
      fontWeight: 600,
      fontSize: size,
      letterSpacing: size * 0.06,
      textTransform: "uppercase",
      color,
    }}
  >
    {children}
  </div>
);

/** Whole-scene camera: gentle push-in. */
export const Camera: React.FC<{dur: number; from?: number; to?: number; children: React.ReactNode}> = ({
  dur,
  from = 1,
  to = 1.04,
  children,
}) => {
  const f = useCurrentFrame();
  const s = interpolate(f, [0, dur], [from, to], clamp);
  return <AbsoluteFill style={{transform: `scale(${s})`}}>{children}</AbsoluteFill>;
};
