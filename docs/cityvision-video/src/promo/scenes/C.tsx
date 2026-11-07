import {EndCard} from "../../series/endcard";
import React from "react";
import {AbsoluteFill, interpolate, useCurrentFrame} from "remotion";
import {
  Ball,
  Camera,
  clamp,
  Critter,
  Eyes,
  F,
  Floaters,
  inOut,
  K,
  Label,
  lerp,
  LogoMark,
  OrangeBg,
  PaperBg,
  prog,
  rand,
  usePop,
  Words,
} from "../kit";

/* ════════ 11 · "When a new pothole opens up, it taps you on the shoulder." ════════ */
export const SNotify: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const open = prog(f, 14, 70, inOut);
  const partB = f >= 92;
  const slide = pop(f, 100, {damping: 14, stiffness: 160});
  // the little orange buddy taps twice
  const tap1 = f > 138 && f < 150 ? Math.sin(((f - 138) / 12) * Math.PI) : 0;
  const tap2 = f > 152 && f < 164 ? Math.sin(((f - 152) / 12) * Math.PI) : 0;
  const tap = Math.max(tap1, tap2);
  const buddyIn = pop(f, 118, {damping: 11});
  return (
    <AbsoluteFill>
      <PaperBg tint={partB ? "rgba(255,180,150,0.22)" : "rgba(229,53,43,0.18)"} />
      <Floaters seed={19} />
      <Camera dur={190} to={1.03}>
        <Words text="When a new pothole opens up," at={0} y={420} size={60} out={86} />
        {!partB ? (
          <div style={{position: "absolute", left: 140, top: 760, width: 800, height: 420}}>
            {/* asphalt slab */}
            <div
              style={{
                position: "absolute",
                inset: 0,
                borderRadius: 40,
                background: "radial-gradient(120% 100% at 40% 30%, #737785 0%, #555966 55%, #41444E 100%)",
                transform: "perspective(1200px) rotateX(48deg)",
                boxShadow: "0 50px 80px rgba(30,30,50,0.3)",
              }}
            >
              <div
                style={{
                  position: "absolute",
                  left: "50%",
                  top: "50%",
                  width: 380 * open,
                  height: 230 * open,
                  transform: "translate(-50%, -50%)",
                  borderRadius: "46% 54% 50% 50% / 54% 46% 54% 46%",
                  background: "radial-gradient(closest-side, #121318 55%, #2A2C33 85%, rgba(42,44,51,0) 100%)",
                }}
              />
              {Array.from({length: 10}, (_, i) => {
                const a = rand(i) * Math.PI * 2;
                const d = (150 + rand(i + 3) * 80) * open;
                return (
                  <div
                    key={i}
                    style={{
                      position: "absolute",
                      left: 400 + Math.cos(a) * d,
                      top: 210 + Math.sin(a) * d * 0.6,
                      width: 14 + rand(i + 7) * 14,
                      height: 10 + rand(i + 8) * 10,
                      borderRadius: 4,
                      background: "#2E3038",
                      opacity: open,
                      transform: `rotate(${rand(i) * 90}deg)`,
                    }}
                  />
                );
              })}
            </div>
          </div>
        ) : null}
        {partB ? (
          <>
            <Words text="it taps you on the shoulder." at={92} y={420} size={60} />
            {/* notification */}
            <div
              style={{
                position: "absolute",
                left: 70,
                top: 760,
                width: 940,
                transform: `translateY(${(1 - slide) * -500}px) translateY(${tap * 10}px) scale(${1 - tap * 0.015})`,
                opacity: Math.min(1, slide * 1.5),
              }}
            >
              <div
                style={{
                  borderRadius: 40,
                  padding: "34px 38px",
                  background: "rgba(255,255,255,0.92)",
                  border: "1px solid rgba(17,18,22,0.06)",
                  boxShadow: "0 40px 80px rgba(30,30,60,0.18)",
                  display: "flex",
                  gap: 28,
                }}
              >
                <LogoMark size={96} />
                <div style={{flex: 1}}>
                  <div style={{display: "flex", justifyContent: "space-between", alignItems: "center"}}>
                    <Label size={22}>CityVision</Label>
                    <span style={{fontFamily: F.sans, fontSize: 24, color: K.gray}}>now</span>
                  </div>
                  <div style={{fontFamily: F.sans, fontWeight: 700, fontSize: 40, color: K.ink, marginTop: 8, letterSpacing: -0.8}}>
                    New pothole · Ring Road
                  </div>
                  <div style={{fontFamily: F.sans, fontSize: 30, color: "#5D626E", marginTop: 8, lineHeight: 1.3}}>
                    94% confidence. Photo + GPS attached. Ready for review.
                  </div>
                </div>
              </div>
            </div>
            {/* buddy */}
            <div
              style={{
                position: "absolute",
                left: 790,
                top: 1080 - tap * 70,
                transform: `scale(${buddyIn}) rotate(${-tap * 18}deg)`,
              }}
            >
              <Ball size={170} x={85} y={85}>
                <div style={{marginTop: -10}}>
                  <Eyes w={170} look={-1} />
                </div>
              </Ball>
            </div>
            <div
              style={{
                position: "absolute",
                left: 620,
                top: 1300,
                fontFamily: F.serif,
                fontStyle: "italic",
                fontSize: 60,
                color: K.gray,
                opacity: prog(f, 140, 150),
              }}
            >
              tap{f > 152 ? " tap" : ""}
            </div>
          </>
        ) : null}
      </Camera>
    </AbsoluteFill>
  );
};

/* ════════ 12 · "One tap." → "Crew sent." ════════ */
export const SOneTap: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const slide = prog(f, 26, 52, inOut);
  const morph = prog(f, 60, 76, inOut);
  const check = prog(f, 70, 96);
  return (
    <AbsoluteFill>
      <PaperBg />
      <Floaters seed={23} />
      <Camera dur={140} to={1.04}>
        <Words text="One tap." at={0} y={500} size={76} weight={700} out={58} />
        {/* approve slider → morphs into the check */}
        <div
          style={{
            position: "absolute",
            left: 540 - lerp(300, 0, morph),
            top: 900 - 70,
            width: lerp(600, 0.01, morph),
            height: 140,
            borderRadius: 999,
            background: `linear-gradient(180deg, #FF7A3E, ${K.orange})`,
            boxShadow: "0 24px 50px rgba(255,90,31,0.35), inset 0 3px 0 rgba(255,255,255,0.3)",
            transform: `scale(${pop(f, 4, {damping: 12})})`,
            opacity: 1 - morph,
          }}
        >
          <div
            style={{
              position: "absolute",
              left: 0,
              right: 0,
              top: 0,
              bottom: 0,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: F.sans,
              fontWeight: 600,
              fontSize: 36,
              color: "rgba(255,255,255,0.85)",
              opacity: 1 - slide,
              paddingLeft: 90,
            }}
          >
            slide to approve
          </div>
          <div
            style={{
              position: "absolute",
              left: lerp(12, 600 - 128, slide),
              top: 12,
              width: 116,
              height: 116,
              borderRadius: 999,
              background: "radial-gradient(circle at 35% 30%, #FFFFFF, #ECEEF2)",
              boxShadow: "0 6px 16px rgba(120,30,0,0.3)",
            }}
          />
        </div>
        <svg width="1080" height="1920" style={{position: "absolute", inset: 0}}>
          <path
            d="M380 920 L500 1040 L730 760"
            fill="none"
            stroke={K.orange}
            strokeWidth="64"
            strokeLinecap="round"
            strokeLinejoin="round"
            pathLength={1}
            strokeDasharray="1"
            strokeDashoffset={1 - check}
            style={{filter: "drop-shadow(0 18px 24px rgba(255,90,31,0.35))"}}
          />
        </svg>
        <Words text="Crew sent." at={84} y={1150} size={130} serif color={K.orange} />
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 1330,
            textAlign: "center",
            fontFamily: F.mono,
            fontSize: 28,
            color: K.gray,
            opacity: prog(f, 100, 114),
          }}
        >
          Work order #0412 · Ring Road · with photo + GPS
        </div>
      </Camera>
    </AbsoluteFill>
  );
};

/* ════════ 13 · "Every morning, 06:30, before the first shift." ════════ */
export const SMorning: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const sunUp = pop(f, 0, {damping: 14, stiffness: 90});
  const partB = f >= 125;
  const phone = pop(f, 125, {damping: 15, stiffness: 120});
  const droneT = prog(f, 40, 130, inOut);
  const minute = Math.round(interpolate(f, [30, 60], [0, 30], clamp));
  const time = `06:${String(minute).padStart(2, "0")}`;
  return (
    <AbsoluteFill>
      <PaperBg tint="rgba(255,200,90,0.3)" />
      <Camera dur={230} to={1.03}>
        {/* sun */}
        <div style={{position: "absolute", left: 250, top: lerp(900, 560, sunUp) - prog(f, 117, 137) * 500, opacity: 1 - prog(f, 117, 133)}}>
          <svg width="400" height="400" viewBox="-200 -200 400 400" style={{position: "absolute", left: -200, top: -200, transform: `rotate(${f * 0.6}deg)`}}>
            {Array.from({length: 12}, (_, i) => {
              const a = (i / 12) * Math.PI * 2;
              return (
                <line key={i} x1={Math.cos(a) * 150} y1={Math.sin(a) * 150} x2={Math.cos(a) * 185} y2={Math.sin(a) * 185} stroke="#F7B32B" strokeWidth="10" strokeLinecap="round" opacity={sunUp} />
              );
            })}
          </svg>
          <Ball size={230} x={0} y={0} color="yellow" shadow={false} />
        </div>
        {!partB ? (
          <>
            <Words text="Every morning," at={8} y={760} size={60} align="left" x={480} out={115} />
            <div
              style={{
                position: "absolute",
                left: 480,
                top: 840,
                fontFamily: F.sans,
                fontWeight: 800,
                fontSize: 170,
                letterSpacing: -6,
                color: K.ink,
                lineHeight: 1,
                fontVariantNumeric: "tabular-nums",
                opacity: prog(f, 24, 36) * (1 - prog(f, 115, 125)),
                transform: `translateY(${(1 - prog(f, 24, 40)) * 40}px)`,
              }}
            >
              {time}
            </div>
            <Words text="before the first shift." at={66} y={1250} size={96} serif color={K.ink} out={115} />
            {/* drone crossing on its planned route */}
            <svg width="1080" height="1920" style={{position: "absolute", inset: 0}}>
              <path d="M-40 1150 C 260 1060, 700 1200, 1120 1080" stroke={K.grayLight} strokeWidth="4" strokeDasharray="14 14" fill="none" opacity={prog(f, 36, 50)} />
            </svg>
            <Drone x={lerp(-120, 1200, droneT)} y={1110 + Math.sin(droneT * Math.PI * 3) * 20} t={f} />
          </>
        ) : null}
        {partB ? (
          <>
            <Words text="you know exactly where to go." at={131} y={360} size={58} />
            <div
              style={{
                position: "absolute",
                left: 540 - 230,
                top: 560,
                transform: `translateY(${(1 - phone) * 1200}px) rotate(${(1 - phone) * 8}deg)`,
              }}
            >
              <div
                style={{
                  width: 460,
                  height: 940,
                  borderRadius: 72,
                  background: "#0E0F14",
                  padding: 14,
                  boxShadow: "0 60px 100px rgba(20,20,40,0.35)",
                }}
              >
                <div
                  style={{
                    width: "100%",
                    height: "100%",
                    borderRadius: 60,
                    overflow: "hidden",
                    background: "linear-gradient(180deg, #FFE2B8 0%, #FFB27A 45%, #FF7A45 100%)",
                    position: "relative",
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                  }}
                >
                  <div style={{width: 130, height: 36, borderRadius: 20, background: "#0E0F14", marginTop: 16}} />
                  <div style={{fontFamily: F.sans, fontWeight: 600, fontSize: 24, color: "rgba(40,20,10,0.6)", marginTop: 24}}>Tuesday</div>
                  <div style={{fontFamily: F.sans, fontWeight: 700, fontSize: 130, color: "#fff", letterSpacing: -5, lineHeight: 1}}>06:30</div>
                  {[
                    ["Overnight flight done", "Ring Road · North Blvd · 41 km"],
                    ["23 priority repairs", "Sorted by risk, nearest first"],
                    ["Crew A route ready", "6 stops · 2h 10m"],
                  ].map(([t, s], i) => {
                    const p = pop(f, 157 + i * 9, {damping: 13});
                    return (
                      <div
                        key={t}
                        style={{
                          width: 400,
                          marginTop: i === 0 ? 70 : 14,
                          borderRadius: 26,
                          padding: "18px 22px",
                          background: "rgba(255,255,255,0.78)",
                          display: "flex",
                          gap: 16,
                          alignItems: "center",
                          transform: `translateY(${(1 - p) * 60}px) scale(${0.9 + 0.1 * p})`,
                          opacity: Math.min(1, p),
                        }}
                      >
                        <LogoMark size={52} />
                        <div>
                          <div style={{fontFamily: F.sans, fontWeight: 700, fontSize: 24, color: K.ink}}>{t}</div>
                          <div style={{fontFamily: F.sans, fontSize: 20, color: "#5D626E", marginTop: 2}}>{s}</div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </>
        ) : null}
      </Camera>
    </AbsoluteFill>
  );
};

const Drone: React.FC<{x: number; y: number; t: number}> = ({x, y, t}) => (
  <div style={{position: "absolute", left: x - 90, top: y - 40, transform: `rotate(${Math.sin(t / 9) * 3}deg)`}}>
    <svg width="180" height="80" viewBox="0 0 180 80">
      {[20, 160].map((cx) => (
        <g key={cx}>
          <ellipse cx={cx} cy="14" rx={26 * Math.abs(Math.cos(t * 0.9))} ry="4" fill="#9AA0AC" opacity="0.7" />
          <rect x={cx - 3} y="14" width="6" height="16" fill="#2A2C33" />
        </g>
      ))}
      <path d="M20 30 L160 30" stroke="#2A2C33" strokeWidth="8" strokeLinecap="round" />
      <rect x="58" y="22" width="64" height="30" rx="12" fill="#1A1C22" />
      <circle cx="90" cy="58" r="10" fill="#2A2C33" />
      <circle cx="90" cy="58" r="5" fill={K.orange} />
    </svg>
  </div>
);

/* ════════ 14 · payoff: the issues get fixed → "Fewer complaints. Safer streets." ════════ */
const FIXES = [
  {kind: "pothole" as const, x: 170},
  {kind: "crack" as const, x: 410},
  {kind: "bin" as const, x: 660},
  {kind: "box" as const, x: 905},
];
/** half-beat spacing so the fixes land on the groove */
const fixAt = (i: number) => Math.round(31 + i * 15.65);

export const SFewer: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const wipe = prog(f, 125, 147, inOut);
  return (
    <AbsoluteFill>
      <PaperBg />
      <Words text="Fewer complaints." at={2} y={470} size={108} weight={800} letterSpacing={-5} />
      {FIXES.map((c, i) => {
        const inP = pop(f, 4 + i * 4, {damping: 12});
        const t0 = fixAt(i);
        const gone = prog(f, t0, t0 + 7, inOut);
        const badge = pop(f, t0 + 3, {damping: 9, stiffness: 240});
        return (
          <React.Fragment key={c.kind}>
            {gone < 1 ? (
              <div style={{position: "absolute", left: 0, top: 0, transform: `scale(${Math.min(1, inP)})`, transformOrigin: `${c.x}px 1040px`, opacity: 1 - gone}}>
                <div style={{transform: `scale(${1 + gone * 0.25}, ${1 - gone})`, transformOrigin: `${c.x}px 1110px`}}>
                  <Critter kind={c.kind} x={c.x} y={1040} s={0.66} t={f + i * 17} look={i < 2 ? 1 : -1} />
                </div>
              </div>
            ) : null}
            {/* puff */}
            {Array.from({length: 8}, (_, k) => {
              const t = prog(f, t0, t0 + 18);
              if (t <= 0 || t >= 1) return null;
              const a = (k / 8) * Math.PI * 2 + i;
              return (
                <div
                  key={k}
                  style={{
                    position: "absolute",
                    left: c.x + Math.cos(a) * 120 * t - 9,
                    top: 1040 + Math.sin(a) * 120 * t - 9,
                    width: 18 * (1 - t),
                    height: 18 * (1 - t),
                    borderRadius: 99,
                    background: k % 2 ? K.orange : "#FFD2B8",
                  }}
                />
              );
            })}
            {/* fixed badge */}
            <div
              style={{
                position: "absolute",
                left: c.x - 62,
                top: 1040 - 62,
                width: 124,
                height: 124,
                borderRadius: 999,
                background: "radial-gradient(circle at 34% 28%, #86EFAC 0%, #22C55E 40%, #15803D 100%)",
                boxShadow: "0 16px 30px rgba(22,163,74,0.3), inset -6px -8px 16px rgba(0,60,20,0.3)",
                transform: `scale(${badge})`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <svg width="64" height="64" viewBox="0 0 24 24">
                <path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="#fff" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray="1" strokeDashoffset={1 - prog(f, t0 + 4, t0 + 14)} />
              </svg>
            </div>
            <div
              style={{
                position: "absolute",
                left: c.x - 100,
                width: 200,
                top: 1130,
                textAlign: "center",
                fontFamily: F.serif,
                fontStyle: "italic",
                fontSize: 46,
                color: K.gray,
                opacity: prog(f, t0 + 6, t0 + 16),
              }}
            >
              fixed
            </div>
          </React.Fragment>
        );
      })}
      {/* deep blue wipe */}
      <AbsoluteFill
        style={{
          clipPath: `circle(${wipe * 140}% at 50% 110%)`,
          background: "radial-gradient(100% 70% at 50% 40%, #4C46E0 0%, #2E2AA8 55%, #1A1766 100%)",
        }}
      >
        <svg width="1080" height="1920" style={{position: "absolute", inset: 0}}>
          <path
            d="M-60 1400 C 300 1300, 700 1500, 1140 1360"
            stroke="#FFD25A"
            strokeWidth="16"
            fill="none"
            strokeLinecap="round"
            strokeDasharray="70 50"
            strokeDashoffset={-f * 6}
            opacity={prog(f, 150, 170)}
          />
        </svg>
        <Floaters color="white" seed={29} enter={130} />
        <div
          style={{
            position: "absolute",
            left: 0,
            right: 0,
            top: 790,
            textAlign: "center",
            fontFamily: F.serif,
            fontStyle: "italic",
            fontSize: 190,
            color: "#fff",
            lineHeight: 0.95,
            letterSpacing: -2,
          }}
        >
          {["Safer", "streets."].map((w, i) => {
            const p = prog(f, 140 + i * 8, 162 + i * 8);
            return (
              <div key={w} style={{opacity: p, transform: `translateY(${(1 - p) * 60}px)`, filter: p < 1 ? `blur(${(1 - p) * 14}px)` : undefined}}>
                {w}
              </div>
            );
          })}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/* ════════ 15 · End card ════════ */
export const SEnd: React.FC = () => (
  <EndCard dur={219} cityAt={8} bookAt={62} loop={{mode: "iris", at: 190, to: <OrangeBg />}} />
);
