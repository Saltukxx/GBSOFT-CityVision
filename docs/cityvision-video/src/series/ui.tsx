import React from "react";
import {Img, useCurrentFrame} from "remotion";
import {Ball, BallColor, F, K, prog, usePop} from "../promo/kit";

/** Text where each word appears on its own frame (e.g. the frame the voice says it). */
export const Said: React.FC<{
  words: [string, number][];
  y: number;
  size?: number;
  weight?: number;
  color?: string;
  serif?: boolean;
  out?: number;
  highlight?: Record<string, string>;
}> = ({words, y, size = 70, weight = 700, color = K.navyText, serif = false, out, highlight = {}}) => {
  const f = useCurrentFrame();
  const o = out !== undefined ? 1 - prog(f, out, out + 12) : 1;
  return (
    <div
      style={{
        position: "absolute",
        left: 60,
        right: 60,
        top: y,
        textAlign: "center",
        fontFamily: serif ? F.serif : F.sans,
        fontStyle: serif ? "italic" : "normal",
        fontWeight: serif ? 400 : weight,
        fontSize: size,
        lineHeight: 1.1,
        letterSpacing: serif ? -size * 0.01 : -size * 0.03,
        color,
        opacity: o,
      }}
    >
      {words.map(([wd, at], i) => {
        const p = prog(f, at - 2, at + 14);
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              marginRight: i < words.length - 1 ? size * 0.24 : 0,
              opacity: p,
              transform: `translateY(${(1 - p) * size * 0.4}px)`,
              filter: p < 1 ? `blur(${(1 - p) * 10}px)` : undefined,
              color: highlight[wd] || undefined,
            }}
          >
            {wd}
          </span>
        );
      })}
    </div>
  );
};

/** "STEP 3 / 7" · big word · italic accent line. */
export const StepHeader: React.FC<{
  n: number;
  of: number;
  word: string;
  sub: string;
  at: number;
  subAt: number;
  accent: string;
  ball: BallColor;
  dark?: boolean;
}> = ({n, of, word, sub, at, subAt, accent, ball, dark = false}) => {
  const f = useCurrentFrame();
  const pop = usePop();
  const p = pop(f, at, {damping: 12, stiffness: 200});
  const sp = prog(f, subAt - 2, subAt + 16);
  const ink = dark ? "#FFFFFF" : K.navyText;
  return (
    <>
      <div style={{position: "absolute", left: 0, right: 0, top: 300, display: "flex", justifyContent: "center", alignItems: "center", gap: 16}}>
        <div style={{position: "relative", width: 58, height: 58, transform: `scale(${p})`}}>
          <Ball size={58} x={29} y={29} color={ball} shadow={false}>
            <span style={{fontFamily: F.sans, fontWeight: 800, fontSize: 30, color: "#fff"}}>{n}</span>
          </Ball>
        </div>
        <div
          style={{
            fontFamily: F.mono,
            fontSize: 26,
            letterSpacing: 4,
            color: dark ? "rgba(255,255,255,0.6)" : "rgba(14,27,61,0.5)",
            opacity: prog(f, at + 2, at + 12),
          }}
        >
          STEP {n} / {of}
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 380,
          textAlign: "center",
          fontFamily: F.sans,
          fontWeight: 900,
          fontSize: 168,
          letterSpacing: -8,
          lineHeight: 1,
          color: ink,
          transform: `scale(${0.6 + 0.4 * Math.min(1.08, p)})`,
          opacity: Math.min(1, p * 1.5),
        }}
      >
        {word}
        <span style={{color: accent}}>.</span>
      </div>
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 562,
          textAlign: "center",
          fontFamily: F.serif,
          fontStyle: "italic",
          fontSize: 68,
          color: accent,
          opacity: sp,
          transform: `translateY(${(1 - sp) * 24}px)`,
          filter: sp < 1 ? `blur(${(1 - sp) * 8}px)` : undefined,
        }}
      >
        {sub}
      </div>
    </>
  );
};

/** Street grid for map cards (card-local coordinates). */
export const Streets: React.FC<{w: number; h: number; color: string; seed?: number}> = ({w, h, color}) => (
  <svg width={w} height={h} style={{position: "absolute", inset: 0}}>
    {[0.12, 0.38, 0.62, 0.88].map((y, i) => (
      <line key={`h${i}`} x1={0} x2={w} y1={y * h} y2={y * h} stroke={color} strokeWidth={i % 2 ? 26 : 16} />
    ))}
    {[0.09, 0.36, 0.7, 0.91].map((x, i) => (
      <line key={`v${i}`} y1={0} y2={h} x1={x * w} x2={x * w} stroke={color} strokeWidth={i % 2 ? 16 : 26} />
    ))}
  </svg>
);

/** Point at arc-length fraction t along a polyline. */
export const along = (pts: [number, number][], t: number): {x: number; y: number; a: number} => {
  const seg = pts.slice(1).map((p, i) => Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]));
  const total = seg.reduce((a, b) => a + b, 0);
  let d = Math.max(0, Math.min(1, t)) * total;
  for (let i = 0; i < seg.length; i++) {
    if (d <= seg[i] || i === seg.length - 1) {
      const k = seg[i] ? Math.min(1, d / seg[i]) : 0;
      const [x0, y0] = pts[i];
      const [x1, y1] = pts[i + 1];
      return {x: x0 + (x1 - x0) * k, y: y0 + (y1 - y0) * k, a: (Math.atan2(y1 - y0, x1 - x0) * 180) / Math.PI};
    }
    d -= seg[i];
  }
  return {x: pts[0][0], y: pts[0][1], a: 0};
};

export const polyLen = (pts: [number, number][]) =>
  pts.slice(1).reduce((a, p, i) => a + Math.hypot(p[0] - pts[i][0], p[1] - pts[i][1]), 0);

/** Camera over a baked map image: centre (cx, cy) in map pixels and scale s (screen px per map px). */
export type MapView = {cx: number; cy: number; s: number};

export const fitView = (box: number[], w: number, h: number): MapView => ({
  cx: (box[0] + box[2]) / 2,
  cy: (box[1] + box[3]) / 2,
  s: Math.min(w / (box[2] - box[0]), h / (box[3] - box[1])),
});

export const lerpView = (a: MapView, b: MapView, t: number): MapView => ({
  cx: a.cx + (b.cx - a.cx) * t,
  cy: a.cy + (b.cy - a.cy) * t,
  // zoom interpolates in log space so it feels like a constant-speed camera
  s: Math.exp(Math.log(a.s) + (Math.log(b.s) - Math.log(a.s)) * t),
});

/** A real map inside a rounded card. `children(proj)` draws overlays in card pixels. */
export const MapCard: React.FC<{
  src: string;
  mapW: number;
  mapH: number;
  w: number;
  h: number;
  view: MapView;
  dark?: boolean;
  credit?: string;
  style?: React.CSSProperties;
  children?: (proj: (x: number, y: number) => [number, number], s: number) => React.ReactNode;
}> = ({src, mapW, mapH, w, h, view, dark, credit = "© OpenStreetMap", style, children}) => {
  const proj = (x: number, y: number): [number, number] => [(x - view.cx) * view.s + w / 2, (y - view.cy) * view.s + h / 2];
  const [ox, oy] = proj(0, 0);
  return (
    <div
      style={{
        position: "absolute",
        width: w,
        height: h,
        borderRadius: 40,
        overflow: "hidden",
        background: dark ? "#10244F" : "#F3F1EC",
        border: dark ? "1px solid rgba(255,255,255,0.08)" : "1px solid rgba(14,27,61,0.06)",
        boxShadow: dark ? "0 40px 80px rgba(0,0,0,0.35)" : "0 40px 80px rgba(20,30,60,0.16)",
        ...style,
      }}
    >
      <Img
        src={src}
        style={{position: "absolute", left: ox, top: oy, width: mapW * view.s, height: mapH * view.s, maxWidth: "none"}}
      />
      {children ? children(proj, view.s) : null}
      <div
        style={{
          position: "absolute",
          right: 18,
          bottom: 14,
          fontFamily: F.sans,
          fontSize: 16,
          color: dark ? "rgba(255,255,255,0.45)" : "rgba(14,27,61,0.45)",
        }}
      >
        {credit}
      </div>
    </div>
  );
};
