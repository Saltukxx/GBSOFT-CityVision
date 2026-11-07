import {EndCard} from "../../series/endcard";
import React from "react";
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from "remotion";
import {Ball, Camera, F, Floaters, inOut, K, lerp, NavyBg, prog, usePop, WhiteBg} from "../../promo/kit";
import {along, fitView, lerpView, MapCard, polyLen, StepHeader} from "../../series/ui";
import FOOT from "../footage.json";
import MAP from "../map.json";
import {w} from "../words";

/* ════════ 5 · Blur (real frame, blurred by CityVision's own anonymiser) ════════ */
export const HBlur: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const CW = 900;
  const CH = 800;
  const st = FOOT.street;
  const k = CH / st.h;
  const scan = prog(f, w("blur", "faces") - 6, w("blur", "blurred") + 4, inOut);
  const scanX = -40 + (CW + 80) * scan;
  const card = pop(f, 2, {damping: 15, stiffness: 120});
  const regs = st.regions
    .map((r) => ({...r, b: r.box.map((v) => v * k)}))
    // the plate cascade can report the same plate twice — keep one
    .filter((r, i, all) => all.findIndex((o) => o.kind === r.kind && Math.abs(o.b[0] - r.b[0]) < 12 && Math.abs(o.b[1] - r.b[1]) < 12) === i);
  const people = regs.filter((r) => r.kind === "person").length;
  const plates = regs.filter((r) => r.kind === "plate").length;
  const chip = (txt: string, at: number) => {
    const p = pop(f, at, {damping: 11, stiffness: 220});
    return (
      <div
        style={{
          transform: `scale(${p})`,
          transformOrigin: "0% 50%",
          background: K.purple,
          color: "#fff",
          fontFamily: F.sans,
          fontWeight: 700,
          fontSize: 28,
          padding: "12px 20px",
          borderRadius: 999,
          whiteSpace: "nowrap",
          boxShadow: "0 10px 24px rgba(124,92,255,0.35)",
        }}
      >
        {txt}
      </div>
    );
  };
  return (
    <AbsoluteFill>
      <WhiteBg tint="rgba(124,92,255,0.14)" />
      <Floaters color="purple" seed={61} />
      <StepHeader n={5} of={7} word="Blur" sub="in every photo." at={w("blur", "five")} subAt={w("blur", "every")} accent={K.purple} ball="purple" />
      <div
        style={{
          position: "absolute",
          left: 90,
          top: 690,
          width: CW,
          height: CH,
          borderRadius: 40,
          overflow: "hidden",
          background: "#9AA1AE",
          boxShadow: "0 40px 80px rgba(20,30,60,0.2)",
          transform: `translateY(${(1 - card) * 900}px)`,
        }}
      >
        <Img src={staticFile(st.src)} style={{position: "absolute", left: (CW - st.w * k) / 2, top: 0, width: st.w * k, height: CH}} />
        {regs.map((r, i) => {
          const [x1, y1, x2, y2] = r.b;
          const ox = (CW - st.w * k) / 2;
          const on = prog(f, 0, 1) * (scanX > x1 + ox ? 1 : 0);
          const p = pop(f, w("blur", "faces") - 6 + Math.round(((x1 + ox + 40) / (CW + 80)) * (w("blur", "blurred") + 10 - w("blur", "faces"))), {damping: 12, stiffness: 240});
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: x1 + ox - 4,
                top: y1 - 4,
                width: x2 - x1 + 8,
                height: y2 - y1 + 8,
                border: `4px solid ${K.purple}`,
                borderRadius: 10,
                opacity: on,
                transform: `scale(${on ? p : 0})`,
                boxShadow: "0 0 18px rgba(124,92,255,0.5)",
              }}
            />
          );
        })}
        <div style={{position: "absolute", left: scanX - 3, top: 0, bottom: 0, width: 6, background: K.purple, boxShadow: "0 0 30px 8px rgba(124,92,255,0.45)", opacity: scan > 0 && scan < 1 ? 1 : 0}} />
        <div style={{position: "absolute", left: 28, bottom: 28, display: "flex", flexDirection: "column", gap: 12, alignItems: "flex-start"}}>
          {chip(`${people} ${people === 1 ? "person" : "people"} · blurred`, w("blur", "faces") + 14)}
          {chip(`${plates} ${plates === 1 ? "plate" : "plates"} · blurred`, w("blur", "plates") + 14)}
        </div>
        <div
          style={{
            position: "absolute",
            right: 28,
            bottom: 28,
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "10px 16px",
            borderRadius: 999,
            background: "rgba(255,255,255,0.94)",
            fontFamily: F.mono,
            fontSize: 22,
            color: K.navyText,
            transform: `scale(${pop(f, w("blur", "photo"), {damping: 12})})`,
          }}
        >
          <svg width="22" height="22" viewBox="0 0 24 24">
            <path fill={K.purple} d="M17 10V7a5 5 0 0 0-10 0v3H5v12h14V10h-2zm-8 0V7a3 3 0 0 1 6 0v3H9z" />
          </svg>
          irreversible
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ════════ 6 · Approve ════════ */
export const APPROVE_BTN = {x: 760, y: 1290};

export const HApprove: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const tap = w("approve", "approves");
  const move = prog(f, tap - 40, tap - 4, inOut);
  const press = f >= tap - 2 && f < tap + 8 ? 0.94 : 1;
  const done = f >= tap + 4;
  const stamp = pop(f, tap + 6, {damping: 9, stiffness: 220});
  const card = pop(f, 2, {damping: 15, stiffness: 120});
  // card at (90, 720); button centre in global coords = APPROVE_BTN
  const cx = lerp(1000, APPROVE_BTN.x + 10, move);
  const cy = lerp(1700, APPROVE_BTN.y + 10, move);
  return (
    <AbsoluteFill>
      <WhiteBg tint="rgba(22,163,74,0.14)" />
      <Floaters color="green" seed={67} />
      <StepHeader n={6} of={7} word="Approve" sub="a person decides." at={w("approve", "six")} subAt={w("approve", "someone")} accent={K.green} ball="green" />
      <div
        style={{
          position: "absolute",
          left: 90,
          top: 720,
          width: 900,
          height: 660,
          borderRadius: 40,
          background: "#fff",
          boxShadow: "0 40px 80px rgba(20,30,60,0.16)",
          overflow: "hidden",
          transform: `translateY(${(1 - card) * 900}px)`,
        }}
      >
        <div style={{position: "relative", height: 300, overflow: "hidden", background: "#444852"}}>
          {(() => {
            const e = FOOT.evidence[2];
            const k = 900 / e.w;
            const top = Math.min(0, 150 - ((e.box[1] + e.box[3]) / 2) * k);
            const [a1, b1, a2, b2] = e.box.map((q) => q * k);
            return (
              <>
                <Img src={staticFile(e.src)} style={{position: "absolute", left: 0, top, width: 900, height: e.h * k}} />
                <div style={{position: "absolute", left: a1, top: b1 + top, width: a2 - a1, height: b2 - b1, border: `5px solid ${K.orange}`, borderRadius: 12}} />
              </>
            );
          })()}
          <div style={{position: "absolute", left: 24, top: 24, padding: "8px 14px", borderRadius: 999, background: "rgba(255,255,255,0.9)", fontFamily: F.mono, fontSize: 20, color: K.navyText}}>
            needs review
          </div>
        </div>
        <div style={{padding: "28px 40px"}}>
          <div style={{fontFamily: F.sans, fontWeight: 800, fontSize: 44, color: K.navyText}}>Pothole · Kartal</div>
          <div style={{fontFamily: F.sans, fontSize: 28, color: "#6B7286", marginTop: 6}}>{Math.round(FOOT.pothole.conf * 100)}% confidence · seen 3× · photo + GPS</div>
        </div>
        <div style={{position: "absolute", left: 40, right: 40, bottom: 40, display: "flex", gap: 24}}>
          <div
            style={{
              flex: 1,
              height: 96,
              borderRadius: 999,
              border: "3px solid #D5D9E2",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: F.sans,
              fontWeight: 700,
              fontSize: 34,
              color: "#7A8194",
            }}
          >
            Reject
          </div>
          <div
            style={{
              flex: 1,
              height: 96,
              borderRadius: 999,
              background: done ? "linear-gradient(180deg, #22C55E, #15803D)" : "linear-gradient(180deg, #2BD06A, #16A34A)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: F.sans,
              fontWeight: 800,
              fontSize: 34,
              color: "#fff",
              transform: `scale(${press})`,
              boxShadow: "0 14px 30px rgba(22,163,74,0.35)",
            }}
          >
            {done ? "Approved ✓" : "Approve"}
          </div>
        </div>
      </div>
      {/* tap ring */}
      {f >= tap - 2 ? (
        <div
          style={{
            position: "absolute",
            left: APPROVE_BTN.x - 40 - prog(f, tap - 2, tap + 20) * 50,
            top: APPROVE_BTN.y - 40 - prog(f, tap - 2, tap + 20) * 50,
            width: 80 + prog(f, tap - 2, tap + 20) * 100,
            height: 80 + prog(f, tap - 2, tap + 20) * 100,
            borderRadius: 999,
            border: `5px solid ${K.green}`,
            opacity: 1 - prog(f, tap - 2, tap + 20),
          }}
        />
      ) : null}
      {/* finger */}
      <div
        style={{
          position: "absolute",
          left: cx - 34,
          top: cy - 34,
          width: 68,
          height: 68,
          borderRadius: 999,
          background: "rgba(255,255,255,0.9)",
          border: `5px solid ${K.navy}`,
          boxShadow: "0 12px 26px rgba(11,26,58,0.3)",
          transform: `scale(${press})`,
          opacity: prog(f, tap - 44, tap - 34) * (1 - prog(f, tap + 24, tap + 34)),
        }}
      />
      {/* stamp */}
      <div style={{position: "absolute", left: 770, top: 650, transform: `scale(${stamp}) rotate(-10deg)`}}>
        <Ball size={170} x={85} y={85} color="green">
          <svg width="90" height="90" viewBox="0 0 24 24">
            <path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="#fff" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </Ball>
      </div>
    </AbsoluteFill>
  );
};

/* ════════ 7 · Fix (real streets: depot → the pothole) ════════ */
const FIX = MAP.fix as [number, number][];
const FIX_CARD = {x: 80, y: 690, w: 920, h: 860};
const fixView = () => fitView(MAP.fixBox, FIX_CARD.w, FIX_CARD.h);
export const FIX_CHECK = (() => {
  const v = fixView();
  const p = FIX[FIX.length - 1];
  return {x: FIX_CARD.x + (p[0] - v.cx) * v.s + FIX_CARD.w / 2, y: FIX_CARD.y + (p[1] - v.cy) * v.s + FIX_CARD.h / 2 - 50};
})();

const Van: React.FC = () => (
  <svg width={110} height={62} viewBox="0 0 110 62">
    <rect x={0} y={4} width={78} height={54} rx={10} fill="#fff" />
    <rect x={74} y={8} width={34} height={46} rx={12} fill={K.orange} />
    <rect x={88} y={14} width={14} height={34} rx={5} fill="#0E1B3D" opacity={0.75} />
    <rect x={10} y={24} width={56} height={14} rx={4} fill={K.orange} />
  </svg>
);

export const HFix: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const draw = prog(f, 8, 46, inOut);
  const arrive = w("fix", "there") + 6;
  const t = prog(f, 30, arrive, inOut);
  const v = along(FIX, t);
  const len = polyLen(FIX);
  const fixed = pop(f, arrive, {damping: 8, stiffness: 220});
  const card = pop(f, 2, {damping: 15, stiffness: 120});
  const v0 = fixView();
  const view = lerpView({...v0, s: v0.s * 0.9}, v0, prog(f, 0, 90, inOut));
  return (
    <AbsoluteFill>
      <NavyBg glow="rgba(255,90,31,0.12)" />
      <Floaters color="orange" seed={71} scale={0.8} />
      <StepHeader n={7} of={7} word="Fix" sub="straight there." at={w("fix", "seven")} subAt={w("fix", "straight")} accent={K.orange} ball="orange" dark />
      <MapCard
        src={staticFile("maps/kartal-navy.png")}
        mapW={MAP.w}
        mapH={MAP.h}
        w={FIX_CARD.w}
        h={FIX_CARD.h}
        view={view}
        dark
        style={{left: FIX_CARD.x, top: FIX_CARD.y, transform: `translateY(${(1 - card) * 900}px)`}}
      >
        {(proj, sc) => {
          const pts = FIX.map(([x, y]) => proj(x, y));
          const [ex, ey] = pts[pts.length - 1];
          const [sx, sy] = pts[0];
          const [vx, vy] = proj(v.x, v.y);
          const ring = prog(f, arrive, arrive + 24);
          return (
            <>
              <svg width={FIX_CARD.w} height={FIX_CARD.h} style={{position: "absolute", inset: 0}}>
                <polyline points={pts.map(([x, y]) => `${x},${y}`).join(" ")} fill="none" stroke={K.orange} strokeWidth={9} strokeLinejoin="round" strokeLinecap="round" strokeDasharray={`${len * sc * draw} ${len * sc * 2}`} />
              </svg>
              <div style={{position: "absolute", left: sx - 11, top: sy - 11, width: 22, height: 22, borderRadius: 99, background: "#fff", border: `5px solid ${K.orange}`}} />
              <div style={{position: "absolute", left: sx + 18, top: sy - 14, fontFamily: F.mono, fontSize: 22, color: "rgba(255,255,255,0.75)"}}>crew</div>
              <div style={{position: "absolute", left: ex - 50, top: ey - 100}}>
                {fixed < 0.05 ? (
                  <Ball size={100} x={50} y={50} color="orange" />
                ) : (
                  <Ball size={100 * fixed} x={50} y={50} color="green">
                    <svg width="56" height="56" viewBox="0 0 24 24">
                      <path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="#fff" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </Ball>
                )}
              </div>
              {f >= arrive ? (
                <div style={{position: "absolute", left: ex - 60 - ring * 70, top: ey - 110 - ring * 70, width: 120 + ring * 140, height: 120 + ring * 140, borderRadius: 999, border: `5px solid ${K.green}`, opacity: 1 - ring}} />
              ) : null}
              <div style={{position: "absolute", left: vx - 55, top: vy - 31, transform: `rotate(${v.a}deg) scale(${pop(f, 22, {damping: 12})})`}}>
                <Van />
              </div>
              <div
                style={{
                  position: "absolute",
                  left: 24,
                  top: 24,
                  padding: "10px 16px",
                  borderRadius: 14,
                  background: "rgba(8,21,48,0.75)",
                  border: "1px solid rgba(255,255,255,0.16)",
                  fontFamily: F.mono,
                  fontSize: 22,
                  color: "#E6ECF8",
                  opacity: prog(f, 20, 34),
                }}
              >
                {(MAP.fixMeters / 1000).toFixed(1)} km · work order #0412
              </div>
            </>
          );
        }}
      </MapCard>
    </AbsoluteFill>
  );
};

/* ════════ 8 · Recap — "Fly. Spot. Pin. Fix. Repeat." ════════ */
export const HRecap: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const rows: [string, string, "teal" | "orange" | "yellow" | "green"][] = [
    ["Fly", "fly", "teal"],
    ["Spot", "spot", "orange"],
    ["Pin", "pin", "yellow"],
    ["Fix", "fix", "green"],
  ];
  const rep = w("recap", "repeat");
  return (
    <AbsoluteFill>
      <WhiteBg />
      <Floaters seed={73} />
      <Camera dur={188} to={1.03}>
        {rows.map(([label, key, color], i) => {
          const at = w("recap", key);
          const p = pop(f, at - 2, {damping: 11, stiffness: 220});
          const y = 420 + i * 180;
          return (
            <div key={label} style={{position: "absolute", left: 250, top: y, display: "flex", alignItems: "center", gap: 40, opacity: Math.min(1, p * 1.4)}}>
              <div style={{position: "relative", width: 120, height: 120, transform: `scale(${p})`}}>
                <Ball size={120} x={60} y={60} color={color} shadow={false}>
                  <span style={{fontFamily: F.sans, fontWeight: 800, fontSize: 52, color: "#fff"}}>{i + 1}</span>
                </Ball>
              </div>
              <div
                style={{
                  fontFamily: F.sans,
                  fontWeight: 900,
                  fontSize: 140,
                  letterSpacing: -6,
                  color: K.navyText,
                  transform: `translateX(${(1 - Math.min(1, p)) * 60}px)`,
                }}
              >
                {label}.
              </div>
            </div>
          );
        })}
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 1150,
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            gap: 26,
            opacity: prog(f, rep - 2, rep + 12),
            transform: `translateY(${(1 - prog(f, rep - 2, rep + 16)) * 30}px)`,
          }}
        >
          <svg width="110" height="110" viewBox="0 0 24 24" style={{transform: `rotate(${(f - rep) * 4}deg)`}}>
            <path fill="none" stroke={K.orange} strokeWidth="2.6" strokeLinecap="round" d="M20 12a8 8 0 1 1-2.34-5.66" />
            <path fill={K.orange} d="M20.5 3.5v5.2h-5.2z" />
          </svg>
          <span style={{fontFamily: F.serif, fontStyle: "italic", fontSize: 150, color: K.navyText}}>Repeat.</span>
        </div>
      </Camera>
    </AbsoluteFill>
  );
};

/* ════════ 9 · End card (navy) → closes into white = frame 1 ════════ */
export const HEnd: React.FC = () => (
  <EndCard
    dur={251}
    cityAt={w("end", "cityvision")}
    bookAt={w("end", "book")}
    note="Real footage from our test flight · faces & plates blurred · map © OpenStreetMap"
    loop={{mode: "iris", at: 220, to: <WhiteBg />}}
  />
);
