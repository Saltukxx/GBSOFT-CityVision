import {loadFont as loadOutfit} from "@remotion/google-fonts/Outfit";
import React from "react";
import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame} from "remotion";
import MAP from "../mayor/map.json";
import {Ball, F, inOut, K, lerp, NavyBg, outExpo, prog, usePop} from "../promo/kit";
import GB from "./gbsoft.json";

/**
 * Shared closing card for the series — "lock-on".
 * A live district map breathes behind; viewfinder brackets fly in and lock onto the CityVision mark,
 * a scan line passes, the wordmark rises, then "a product by gbsoft" with its blue square dropping in last.
 * `loop` draws whatever the reel's first frame is, revealed at the very end so the reel loops seamlessly.
 */
export const MARK = {x: 540, y: 540, size: 168};
// the gbsoft wordmark's letterforms are closest to Outfit Bold — cityvision is set the same way
const OUTFIT = loadOutfit("normal", {weights: ["700"], subsets: ["latin"]}).fontFamily;

export const EndCard: React.FC<{
  dur: number;
  cityAt?: number;
  bookAt?: number;
  note?: string;
  loop?: {mode: "iris" | "halves"; at: number; to: React.ReactNode; bottom?: React.ReactNode};
}> = ({dur, cityAt = 6, bookAt = 60, note, loop}) => {
  const f = useCurrentFrame();
  const pop = usePop();

  // ── background: the city, breathing ──
  const fly = MAP.fly as [number, number][];
  const xs = fly.map((p) => p[0]);
  const ys = fly.map((p) => p[1]);
  const mcx = (Math.min(...xs) + Math.max(...xs)) / 2;
  const mcy = (Math.min(...ys) + Math.max(...ys)) / 2;
  const ms = 0.62 + prog(f, 0, dur, (x) => x) * 0.08;
  const len = fly.slice(1).reduce((a, p, i) => a + Math.hypot(p[0] - fly[i][0], p[1] - fly[i][1]), 0);
  const draw = prog(f, 4, Math.min(dur - 20, 150), inOut);
  const mx = (x: number) => (x - mcx) * ms + 540;
  const my = (y: number) => (y - mcy) * ms + 980;

  // ── lock-on brackets ──
  const lock = prog(f, 0, 26, outExpo);
  const box = {x0: lerp(-40, 150, lock), y0: lerp(-40, 400, lock), x1: lerp(1120, 930, lock), y1: lerp(1960, 1290, lock)};
  const B = 86;
  const scan = prog(f, 26, 62, inOut);

  // ── wordmark ──
  const word = "CityVision";
  const mark = pop(f, cityAt - 4, {damping: 10, stiffness: 190});

  // ── gbsoft signature ──
  const gbAt = Math.max(bookAt + 18, 70);
  const gbW = 520;
  const k = gbW / GB.w;
  const reveal = prog(f, gbAt, gbAt + 22, inOut);
  const [sx0, sy0, sx1, sy1] = GB.square;
  const drop = pop(f, gbAt + 20, {damping: 8, stiffness: 240});
  const glow = prog(f, gbAt + 22, gbAt + 40) * (1 - prog(f, gbAt + 40, gbAt + 80));

  return (
    <AbsoluteFill>
      <NavyBg glow="rgba(15,181,200,0.10)" />
      {/* living map */}
      <div style={{position: "absolute", inset: 0, opacity: 0.15}}>
        <Img src={staticFile(MAP.navy)} style={{position: "absolute", left: mx(0), top: my(0), width: MAP.w * ms, height: MAP.h * ms, maxWidth: "none"}} />
      </div>
      <svg width={1080} height={1920} style={{position: "absolute", inset: 0, opacity: 0.55}}>
        <polyline points={fly.map(([x, y]) => `${mx(x)},${my(y)}`).join(" ")} fill="none" stroke={K.teal} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={`${len * ms * draw} ${len * ms * 2}`} />
      </svg>
      <AbsoluteFill style={{background: "radial-gradient(70% 45% at 50% 42%, rgba(8,21,48,0.15) 0%, rgba(8,21,48,0.78) 70%, rgba(6,14,34,0.95) 100%)"}} />

      {/* viewfinder lock-on */}
      {[0, 1, 2, 3].map((c) => {
        const left = c % 2 === 0;
        const top = c < 2;
        return (
          <div
            key={c}
            style={{
              position: "absolute",
              left: left ? box.x0 : box.x1 - B,
              top: top ? box.y0 : box.y1 - B,
              width: B,
              height: B,
              borderColor: "rgba(255,255,255,0.9)",
              borderStyle: "solid",
              borderWidth: `${top ? 5 : 0}px ${left ? 0 : 5}px ${top ? 0 : 5}px ${left ? 5 : 0}px`,
              borderRadius: 6,
              opacity: 0.35 + 0.65 * lock,
            }}
          />
        );
      })}
      <div style={{position: "absolute", left: box.x0 + 8, top: box.y0 - 40, fontFamily: F.mono, fontSize: 20, letterSpacing: 3, color: "rgba(255,255,255,0.55)", opacity: prog(f, 20, 32)}}>
        CV · LOCKED
      </div>
      <div style={{position: "absolute", right: 1080 - box.x1 + 8, top: box.y0 - 40, fontFamily: F.mono, fontSize: 20, letterSpacing: 2, color: "rgba(255,255,255,0.55)", opacity: prog(f, 24, 36)}}>
        {MAP.pins[1].lat.toFixed(4)}° N · {MAP.pins[1].lon.toFixed(4)}° E
      </div>
      {scan > 0 && scan < 1 ? (
        <div style={{position: "absolute", left: box.x0, width: box.x1 - box.x0, top: lerp(box.y0, box.y1, scan), height: 3, background: K.teal, boxShadow: "0 0 24px 6px rgba(15,181,200,0.45)", opacity: 0.9}} />
      ) : null}

      {/* CityVision mark: dark tile, white brackets, the orange ball */}
      <div style={{position: "absolute", left: MARK.x - MARK.size / 2, top: MARK.y - MARK.size / 2, transform: `scale(${mark})`}}>
        <div
          style={{
            position: "relative",
            width: MARK.size,
            height: MARK.size,
            borderRadius: MARK.size * 0.26,
            background: "linear-gradient(160deg, #1D2B55 0%, #0B1430 100%)",
            border: "1.5px solid rgba(255,255,255,0.14)",
            boxShadow: "0 30px 70px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.12)",
          }}
        >
          {[0, 1, 2, 3].map((c) => {
            const inset = lerp(-18, MARK.size * 0.12, prog(f, cityAt, cityAt + 18, outExpo));
            const b = MARK.size * 0.22;
            const st: React.CSSProperties = {position: "absolute", width: b, height: b, borderColor: "#fff", borderStyle: "solid", borderRadius: b * 0.3};
            if (c === 0) Object.assign(st, {left: inset, top: inset, borderWidth: "6px 0 0 6px"});
            if (c === 1) Object.assign(st, {right: inset, top: inset, borderWidth: "6px 6px 0 0"});
            if (c === 2) Object.assign(st, {left: inset, bottom: inset, borderWidth: "0 0 6px 6px"});
            if (c === 3) Object.assign(st, {right: inset, bottom: inset, borderWidth: "0 6px 6px 0"});
            return <div key={c} style={st} />;
          })}
          <Ball size={MARK.size * 0.4 * (1 + 0.05 * Math.sin(f / 9))} x={MARK.size / 2} y={MARK.size / 2} shadow={false} />
        </div>
      </div>

      <div style={{position: "absolute", left: 0, right: 0, top: 676, display: "flex", justifyContent: "center", alignItems: "flex-end"}}>
        <div style={{fontFamily: OUTFIT, fontWeight: 700, fontSize: 158, letterSpacing: -5, lineHeight: 1, color: "#fff", display: "flex"}}>
          {word.toLowerCase().split("").map((c, i) => {
            const p = prog(f, cityAt + 6 + i * 2, cityAt + 26 + i * 2);
            return (
              <span key={i} style={{display: "inline-block", opacity: p, transform: `translateY(${(1 - p) * 60}px)`, filter: p < 1 ? `blur(${(1 - p) * 10}px)` : undefined}}>
                {c}
              </span>
            );
          })}
        </div>
        {(() => {
          const d = pop(f, cityAt + 30, {damping: 8, stiffness: 240});
          return (
            <div
              style={{
                width: 30,
                height: 30,
                marginLeft: 8,
                marginBottom: 14,
                background: K.orange,
                opacity: f >= cityAt + 30 ? 1 : 0,
                transform: `translateY(${(1 - Math.min(1, d)) * -60}px) scale(${interpolate(d, [0, 1, 1.3], [0.4, 1, 1.12])})`,
                boxShadow: "0 0 24px rgba(255,90,31,0.55)",
              }}
            />
          );
        })()}
      </div>
      <div style={{position: "absolute", left: 0, right: 0, top: 872, textAlign: "center", fontFamily: F.serif, fontStyle: "italic", fontSize: 54, color: "#C6D3F0", opacity: prog(f, cityAt + 26, cityAt + 42), transform: `translateY(${(1 - prog(f, cityAt + 26, cityAt + 46)) * 16}px)`}}>
        your city, seen from above.
      </div>
      <div style={{position: "absolute", left: 0, right: 0, top: 960, textAlign: "center", fontFamily: F.sans, fontWeight: 500, fontSize: 34, letterSpacing: 0.5, color: "rgba(198,211,240,0.75)", opacity: prog(f, cityAt + 34, cityAt + 50)}}>
        Drone + AI road inspection for cities
      </div>

      {/* CTA */}
      <div style={{position: "absolute", left: 0, right: 0, top: 1070, display: "flex", justifyContent: "center"}}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 18,
            padding: "26px 54px",
            borderRadius: 999,
            background: "linear-gradient(180deg, #FFFFFF, #E9EEF8)",
            color: K.navyText,
            fontFamily: F.sans,
            fontWeight: 800,
            fontSize: 46,
            boxShadow: "0 24px 60px rgba(0,0,0,0.35), 0 0 0 8px rgba(255,255,255,0.06)",
            transform: `scale(${pop(f, bookAt - 4, {damping: 10})})`,
          }}
        >
          Book a demo
          <span style={{color: K.orange, display: "inline-block", transform: `translateX(${Math.sin(f / 10) * 6}px)`}}>→</span>
        </div>
      </div>
      <div style={{position: "absolute", left: 0, right: 0, top: 1218, textAlign: "center", fontFamily: F.mono, fontSize: 36, letterSpacing: 2, color: "#fff", opacity: prog(f, bookAt + 8, bookAt + 20)}}>
        gbsoftt.com
      </div>

      {/* a product by gbsoft — letters reveal, the blue square drops in as the full stop */}
      <div style={{position: "absolute", left: 0, right: 0, top: 1336, textAlign: "center", fontFamily: F.mono, fontSize: 24, letterSpacing: 6, color: "rgba(198,211,240,0.6)", opacity: prog(f, gbAt - 6, gbAt + 6)}}>
        A PRODUCT BY
      </div>
      <div style={{position: "absolute", left: 540 - gbW / 2, top: 1384, width: gbW, height: GB.h * k}}>
        <Img src={staticFile("brand/gbsoft-white-letters.png")} style={{position: "absolute", left: 0, top: 0, width: gbW, height: GB.h * k, clipPath: `inset(-5% ${(1 - reveal) * 100}% -5% 0)`}} />
        <div
          style={{
            position: "absolute",
            left: sx0 * k,
            top: sy0 * k - (1 - Math.min(1, drop)) * 110,
            width: (sx1 - sx0) * k,
            height: (sy1 - sy0) * k,
            background: GB.blue,
            opacity: f >= gbAt + 20 ? 1 : 0,
            transform: `scale(${interpolate(drop, [0, 1, 1.3], [0.4, 1, 1.12])})`,
            boxShadow: `0 0 ${30 * glow}px ${10 * glow}px rgba(0,85,255,${0.6 * glow})`,
          }}
        />
      </div>

      {note ? (
        <div style={{position: "absolute", left: 60, right: 60, top: 1640, textAlign: "center", fontFamily: F.sans, fontSize: 22, color: "rgba(255,255,255,0.42)", opacity: prog(f, 30, 44)}}>{note}</div>
      ) : null}

      {/* loop back into the reel's first frame */}
      {loop && loop.mode === "iris" && f >= loop.at ? (
        <AbsoluteFill style={{clipPath: `circle(${lerp(30, 2300, prog(f, loop.at, dur - 2, inOut))}px at ${MARK.x}px ${MARK.y}px)`}}>{loop.to}</AbsoluteFill>
      ) : null}
      {loop && loop.mode === "halves" && f >= loop.at ? (
        <>
          <div style={{position: "absolute", left: 0, right: 0, top: 0, height: 960, overflow: "hidden", transform: `translateY(${(1 - prog(f, loop.at, dur - 2, inOut)) * -1000}px)`}}>{loop.to}</div>
          <div style={{position: "absolute", left: 0, right: 0, top: 960, bottom: 0, overflow: "hidden", transform: `translateY(${(1 - prog(f, loop.at, dur - 2, inOut)) * 1000}px)`}}>{loop.bottom}</div>
        </>
      ) : null}
    </AbsoluteFill>
  );
};
