import React from "react";
import {AbsoluteFill, Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from "remotion";
import {Ball, BallLabel, Camera, F, Floaters, inOut, K, lerp, NavyBg, prog, usePop, WhiteBg} from "../../promo/kit";
import {along, fitView, lerpView, MapCard, polyLen, Said, StepHeader} from "../../series/ui";
import FOOT from "../footage.json";
import MAP from "../map.json";
import {w} from "../words";

export const TIMER = {x: 120, y: 330, size: 120};

/* ════════ 0 · "How does CityVision work? Thirty seconds." ════════ */
export const HHook: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const born = pop(f, w("hook", "thirty") - 4, {damping: 9, stiffness: 170});
  const fly = prog(f, 158, 186, inOut);
  const size = lerp(400 * born, TIMER.size, fly);
  return (
    <AbsoluteFill>
      <WhiteBg />
      <Floaters seed={41} enter={2} />
      <Camera dur={188} to={1.03}>
        <Said
          words={[
            ["How", w("hook", "how")],
            ["does", w("hook", "does")],
            ["CityVision", w("hook", "cityvision")],
            ["work?", w("hook", "work")],
          ]}
          y={500}
          size={84}
          weight={800}
          highlight={{CityVision: K.orange}}
          out={150}
        />
      </Camera>
      <Ball size={size} x={lerp(540, TIMER.x, fly)} y={lerp(1040, TIMER.y, fly)} shadow={fly < 0.4}>
        <BallLabel size={size * 0.36}>30</BallLabel>
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
          color: K.navyText,
          opacity: prog(f, w("hook", "seconds") - 2, w("hook", "seconds") + 14) * (1 - prog(f, 150, 162)),
        }}
      >
        seconds.
      </div>
    </AbsoluteFill>
  );
};

/* ════════ 1 · Fly (real Kartal streets) ════════ */
export const FLY = MAP.fly as [number, number][];
const CARD = {x: 80, y: 690, w: 920, h: 860};

export const Drone: React.FC<{size: number; t: number; color?: string}> = ({size, t, color = "#fff"}) => (
  <svg width={size} height={size} viewBox="-50 -50 100 100" style={{overflow: "visible"}}>
    {[
      [-30, -30],
      [30, -30],
      [-30, 30],
      [30, 30],
    ].map(([x, y], i) => (
      <g key={i}>
        <line x1={0} y1={0} x2={x} y2={y} stroke={color} strokeWidth={7} strokeLinecap="round" />
        <circle cx={x} cy={y} r={17} fill="none" stroke={color} strokeOpacity={0.5} strokeWidth={3} />
        <ellipse cx={x} cy={y} rx={16} ry={3.5} fill={color} opacity={0.8} transform={`rotate(${t * 47 + i * 40} ${x} ${y})`} />
      </g>
    ))}
    <rect x={-15} y={-19} width={30} height={38} rx={10} fill={color} />
    <circle cx={0} cy={12} r={5} fill={K.teal} />
  </svg>
);

export const HFly: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const draw = prog(f, w("fly", "planned") - 24, w("fly", "route") + 10, inOut);
  const len = polyLen(FLY);
  const t = prog(f, 66, 306, inOut);
  const d = along(FLY, t);
  const card = pop(f, 4, {damping: 15, stiffness: 120});
  const overview = fitView(MAP.flyBox, CARD.w, CARD.h);
  const close = {cx: d.x, cy: d.y, s: overview.s * 1.55};
  const view = lerpView(overview, close, prog(f, 70, 300, inOut) * 0.7);
  const days = ["Mon", "Wed", "Fri"];
  return (
    <AbsoluteFill>
      <NavyBg />
      <Floaters color="teal" seed={43} scale={0.8} />
      <StepHeader n={1} of={7} word="Fly" sub="same streets, every time." at={w("fly", "one")} subAt={w("fly", "same")} accent={K.teal} ball="teal" dark />
      <MapCard
        src={staticFile("maps/kartal-navy.png")}
        mapW={MAP.w}
        mapH={MAP.h}
        w={CARD.w}
        h={CARD.h}
        view={view}
        dark
        style={{left: CARD.x, top: CARD.y, transform: `translateY(${(1 - card) * 900}px)`}}
      >
        {(proj, sc) => {
          const pts = FLY.map(([x, y]) => proj(x, y));
          const line = pts.map(([x, y]) => `${x},${y}`).join(" ");
          const [dx, dy] = proj(d.x, d.y);
          const [sx, sy] = pts[0];
          return (
            <>
              {days.map((day, i) => {
                const a = prog(f, w("fly", "every") - 30 + i * 12, w("fly", "every") - 10 + i * 12);
                return (
                  <svg key={day} width={CARD.w} height={CARD.h} style={{position: "absolute", inset: 0, opacity: a * 0.35}}>
                    <polyline points={pts.map(([x, y]) => `${x + (i - 1) * 7},${y + (i - 1) * 7}`).join(" ")} fill="none" stroke={K.teal} strokeWidth={4} strokeLinejoin="round" />
                  </svg>
                );
              })}
              <svg width={CARD.w} height={CARD.h} style={{position: "absolute", inset: 0}}>
                <polyline points={line} fill="none" stroke={K.teal} strokeWidth={9} strokeLinejoin="round" strokeLinecap="round" strokeDasharray={`${len * sc * draw} ${len * sc * 2}`} />
                <polyline points={line} fill="none" stroke="#fff" strokeWidth={3} strokeDasharray="10 16" strokeDashoffset={-f * 2} opacity={0.55 * draw} />
                <circle cx={sx} cy={sy} r={13} fill="#fff" stroke={K.teal} strokeWidth={5} opacity={draw > 0 ? 1 : 0} />
              </svg>
              <div
                style={{
                  position: "absolute",
                  left: dx - 90,
                  top: dy - 90,
                  width: 180,
                  height: 180,
                  borderRadius: 999,
                  background: "radial-gradient(closest-side, rgba(15,181,200,0.38), rgba(15,181,200,0))",
                  opacity: prog(f, 66, 80),
                }}
              />
              <div style={{position: "absolute", left: dx - 55, top: dy - 55, transform: `rotate(${d.a + 90}deg) scale(${pop(f, 60, {damping: 12})})`}}>
                <Drone size={110} t={f} />
              </div>
              <div style={{position: "absolute", right: 24, top: 24, display: "flex", flexDirection: "column", gap: 12, alignItems: "flex-end"}}>
                {days.map((day, i) => {
                  const p = pop(f, w("fly", "every") - 30 + i * 12, {damping: 12});
                  return (
                    <div
                      key={day}
                      style={{
                        transform: `scale(${p})`,
                        transformOrigin: "100% 50%",
                        display: "flex",
                        gap: 12,
                        alignItems: "center",
                        padding: "12px 18px",
                        borderRadius: 999,
                        background: "rgba(8,21,48,0.75)",
                        border: "1px solid rgba(255,255,255,0.16)",
                        fontFamily: F.mono,
                        fontSize: 24,
                        color: "#E6ECF8",
                      }}
                    >
                      <div style={{width: 12, height: 12, borderRadius: 9, background: K.teal}} />
                      {day} 07:00
                    </div>
                  );
                })}
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
                Kartal, İstanbul · {(MAP.flyMeters / 1000).toFixed(1)} km
              </div>
            </>
          );
        }}
      </MapCard>
    </AbsoluteFill>
  );
};

/* ════════ 2 · Spot (real DJI footage, real detections, anonymised) ════════ */
type Shot = {src: string; w: number; h: number; box: number[]; label: string};

export const HSpot: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const card = pop(f, 4, {damping: 15, stiffness: 120});
  const CW = 880;
  const CH = 820;
  const shots: {at: number; shot: Shot; color: string}[] = [
    {at: w("spot", "potholes"), shot: FOOT.pothole, color: K.orange},
    {at: w("spot", "cracks"), shot: FOOT.crack, color: K.pink},
    {at: w("spot", "road"), shot: FOOT.damage, color: K.teal},
  ];
  // the intro clip's last frame IS the pothole detection frame
  const introLen = Math.round((FOOT.intro.frames / FOOT.intro.fps) * 60);
  const introStart = shots[0].at - introLen;
  const cur = [...shots].reverse().find((s) => f >= s.at);
  const found = shots.filter((s) => f >= s.at).length;
  const sc = CH / 1080;
  return (
    <AbsoluteFill>
      <WhiteBg />
      <Floaters seed={47} />
      <StepHeader n={2} of={7} word="Spot" sub="every frame." at={w("spot", "two")} subAt={w("spot", "every")} accent={K.orange} ball="orange" />
      <div
        style={{
          position: "absolute",
          left: 100,
          top: 690,
          width: CW,
          height: CH,
          borderRadius: 40,
          overflow: "hidden",
          background: "#3A3D46",
          boxShadow: "0 40px 80px rgba(20,30,60,0.25)",
          transform: `translateY(${(1 - card) * 900}px)`,
        }}
      >
        {!cur ? (
          <Sequence from={introStart} durationInFrames={introLen} layout="none">
            <OffthreadVideo src={staticFile(FOOT.intro.src)} muted style={{position: "absolute", left: 0, top: 0, width: FOOT.intro.w * sc, height: CH}} />
          </Sequence>
        ) : (
          (() => {
            const k = 1 + prog(f, cur.at, cur.at + 60) * 0.05;
            const [x1, y1, x2, y2] = cur.shot.box.map((v) => v * sc);
            const bp = pop(f, cur.at, {damping: 10, stiffness: 260});
            const flash = 1 - prog(f, cur.at, cur.at + 8);
            return (
              <>
                <div style={{position: "absolute", inset: 0, transform: `scale(${k})`, transformOrigin: `${(x1 + x2) / 2}px ${(y1 + y2) / 2}px`}}>
                  <Img src={staticFile(cur.shot.src)} style={{position: "absolute", left: 0, top: 0, width: cur.shot.w * sc, height: CH}} />
                  <div
                    style={{
                      position: "absolute",
                      left: x1,
                      top: y1,
                      width: x2 - x1,
                      height: y2 - y1,
                      border: `5px solid ${cur.color}`,
                      borderRadius: 12,
                      transform: `scale(${bp})`,
                      opacity: Math.min(1, bp),
                      boxShadow: "0 0 0 2000px rgba(0,0,0,0.12)",
                    }}
                  >
                    <div
                      style={{
                        position: "absolute",
                        left: -5,
                        top: y1 > 60 ? -46 : undefined,
                        bottom: y1 > 60 ? undefined : -46,
                        whiteSpace: "nowrap",
                        background: cur.color,
                        color: "#fff",
                        fontFamily: F.mono,
                        fontSize: 24,
                        padding: "6px 12px",
                        borderRadius: 8,
                      }}
                    >
                      {cur.shot.label}
                    </div>
                  </div>
                </div>
                <AbsoluteFill style={{background: "#fff", opacity: flash * 0.75}} />
              </>
            );
          })()
        )}
        {/* viewfinder chrome */}
        {[0, 1, 2, 3].map((c) => (
          <div
            key={c}
            style={{
              position: "absolute",
              width: 70,
              height: 70,
              borderColor: "rgba(255,255,255,0.9)",
              borderStyle: "solid",
              borderWidth: `${c < 2 ? 5 : 0}px ${c % 2 ? 5 : 0}px ${c >= 2 ? 5 : 0}px ${c % 2 ? 0 : 5}px`,
              left: c % 2 ? undefined : 28,
              right: c % 2 ? 28 : undefined,
              top: c < 2 ? 28 : undefined,
              bottom: c >= 2 ? 28 : undefined,
            }}
          />
        ))}
        <div style={{position: "absolute", left: 120, top: 44, display: "flex", alignItems: "center", gap: 12, fontFamily: F.mono, fontSize: 22, color: "#fff", textShadow: "0 1px 4px rgba(0,0,0,0.6)"}}>
          <div style={{width: 14, height: 14, borderRadius: 9, background: K.red, opacity: Math.floor(f / 20) % 2 ? 1 : 0.35}} />
          AI · LIVE
        </div>
        <div
          style={{
            position: "absolute",
            right: 120,
            top: 36,
            padding: "8px 16px",
            borderRadius: 999,
            background: "rgba(255,255,255,0.92)",
            fontFamily: F.sans,
            fontWeight: 700,
            fontSize: 26,
            color: K.navyText,
            transform: `scale(${found ? 1 + 0.12 * Math.max(0, 1 - (f - shots[found - 1].at) / 10) : 1})`,
          }}
        >
          {found} found
        </div>
        <div
          style={{
            position: "absolute",
            left: 40,
            bottom: 40,
            padding: "8px 14px",
            borderRadius: 10,
            background: "rgba(8,21,48,0.6)",
            fontFamily: F.mono,
            fontSize: 20,
            color: "#fff",
          }}
        >
          real flight · Kartal · faces & plates blurred
        </div>
      </div>
    </AbsoluteFill>
  );
};

/* ════════ 3 · Pin (real map, real evidence photo, real coordinates) ════════ */
export const PIN_TYPES = [
  {c: K.pink, label: "Crack"},
  {c: K.orange, label: "Pothole"},
  {c: K.teal, label: "Road damage"},
];
const PIN_CARD = {x: 80, y: 690, w: 920, h: 820};
export const pinView = () => fitView(MAP.pinBox, PIN_CARD.w, PIN_CARD.h);
/** Selected (pothole) pin in screen coordinates — the next scene irises out of it. */
export const PIN_SEL_SCREEN = (() => {
  const v = pinView();
  const p = MAP.pins[1];
  return {x: PIN_CARD.x + (p.x - v.cx) * v.s + PIN_CARD.w / 2, y: PIN_CARD.y + (p.y - v.cy) * v.s + PIN_CARD.h / 2};
})();

export const HPin: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const first = w("pin", "each");
  const ev = pop(f, w("pin", "photo") - 4, {damping: 13});
  const sel = MAP.pins[1];
  const gps = `${sel.lat.toFixed(5)}° N, ${sel.lon.toFixed(5)}° E`;
  const typed = Math.round(prog(f, w("pin", "gps"), w("pin", "gps") + 34, (x) => x) * gps.length);
  const card = pop(f, 2, {damping: 15, stiffness: 120});
  const v0 = pinView();
  const view = lerpView({...v0, s: v0.s * 0.85}, v0, prog(f, 0, 60, inOut));
  const evid = FOOT.evidence[1];
  return (
    <AbsoluteFill>
      <WhiteBg tint="rgba(245,179,0,0.16)" />
      <Floaters color="yellow" seed={53} />
      <StepHeader n={3} of={7} word="Pin" sub="photo + GPS." at={w("pin", "three")} subAt={w("pin", "photo")} accent={K.yellowText} ball="yellow" />
      <MapCard
        src={staticFile("maps/kartal-light.png")}
        mapW={MAP.w}
        mapH={MAP.h}
        w={PIN_CARD.w}
        h={PIN_CARD.h}
        view={view}
        style={{left: PIN_CARD.x, top: PIN_CARD.y, transform: `scale(${0.9 + 0.1 * card})`, opacity: Math.min(1, card * 1.4)}}
      >
        {(proj) => (
          <>
            {MAP.pins.map((p, i) => {
              const [x, y] = proj(p.x, p.y);
              const drop = pop(f, first + i * 7, {damping: 9, stiffness: 220});
              const isSel = i === 1;
              const ring = isSel ? prog(f, w("pin", "pin") - 6, w("pin", "pin") + 30) : 0;
              return (
                <React.Fragment key={i}>
                  {isSel && ring > 0 ? (
                    <div style={{position: "absolute", left: x - 30 - ring * 60, top: y - 30 - ring * 60, width: 60 + ring * 120, height: 60 + ring * 120, borderRadius: 999, border: `6px solid ${K.yellow}`, opacity: 1 - ring}} />
                  ) : null}
                  <div style={{position: "absolute", left: x - 18, top: y - 6, width: 36, height: 12, borderRadius: "50%", background: "rgba(0,0,0,0.2)", transform: `scale(${Math.min(1, drop)})`}} />
                  <div style={{position: "absolute", left: x - 30, top: y - 80 - (1 - Math.min(1, drop)) * 300, opacity: Math.min(1, drop * 2)}}>
                    <svg width={60} height={84} viewBox="0 0 24 34">
                      <path d="M12 0C5.4 0 0 5.2 0 11.7 0 20.5 12 34 12 34s12-13.5 12-22.3C24 5.2 18.6 0 12 0z" fill={PIN_TYPES[i].c} stroke="#fff" strokeWidth={1.2} />
                      <circle cx={12} cy={11.5} r={4.6} fill="#fff" />
                    </svg>
                  </div>
                </React.Fragment>
              );
            })}
            {(() => {
              const [x, y] = proj(sel.x, sel.y);
              const left = x + 40 > PIN_CARD.w - 420 ? x - 440 : x + 40;
              return (
                <div
                  style={{
                    position: "absolute",
                    left,
                    top: Math.max(30, Math.min(PIN_CARD.h - 360, y - 170)),
                    width: 400,
                    borderRadius: 26,
                    background: "#fff",
                    boxShadow: "0 24px 50px rgba(20,30,60,0.22)",
                    overflow: "hidden",
                    transform: `scale(${ev})`,
                    transformOrigin: left < x ? "100% 50%" : "0% 50%",
                    opacity: Math.min(1, ev * 1.5),
                  }}
                >
                  <div style={{position: "relative", height: 200, overflow: "hidden"}}>
                    <Img src={staticFile(evid.src)} style={{position: "absolute", left: 0, top: 0, width: 400, height: (400 * evid.h) / evid.w}} />
                    {(() => {
                      const k = 400 / evid.w;
                      const [a1, b1, a2, b2] = evid.box.map((q) => q * k);
                      return <div style={{position: "absolute", left: a1, top: b1, width: a2 - a1, height: b2 - b1, border: `4px solid ${K.orange}`, borderRadius: 8}} />;
                    })()}
                  </div>
                  <div style={{padding: "18px 22px"}}>
                    <div style={{fontFamily: F.sans, fontWeight: 700, fontSize: 30, color: K.navyText}}>Pothole · Kartal</div>
                    <div style={{fontFamily: F.mono, fontSize: 20, color: "#5D626E", marginTop: 8, minHeight: 26}}>
                      {gps.slice(0, typed)}
                      <span style={{opacity: typed < gps.length && Math.floor(f / 8) % 2 ? 1 : 0}}>▌</span>
                    </div>
                    <div style={{fontFamily: F.mono, fontSize: 20, color: K.gray, marginTop: 4, opacity: prog(f, w("pin", "pin"), w("pin", "pin") + 10)}}>
                      {FOOT.pothole.label} · 07:12
                    </div>
                  </div>
                </div>
              );
            })()}
          </>
        )}
      </MapCard>
    </AbsoluteFill>
  );
};

/* ════════ 4 · Merge ════════ */
const SIGHTINGS = [
  ["Flight 0408", "Mon 07:12"],
  ["Flight 0410", "Wed 07:09"],
  ["Flight 0412", "Fri 07:14"],
];

const Thumb: React.FC<{seed: number}> = ({seed}) => {
  const e = FOOT.evidence[seed % FOOT.evidence.length];
  const k = 150 / (e.h * 1.0);
  const [a1, b1, a2, b2] = e.box.map((q) => q * k);
  const shift = Math.max(0, Math.min(e.w * k - 150, (a1 + a2) / 2 - 75));
  return (
    <div style={{position: "relative", width: 150, height: 150, borderRadius: 18, overflow: "hidden", background: "#444852"}}>
      <Img src={staticFile(e.src)} style={{position: "absolute", left: -shift, top: 0, width: e.w * k, height: 150}} />
      <div style={{position: "absolute", left: a1 - shift, top: b1, width: a2 - a1, height: b2 - b1, border: `3px solid ${K.orange}`, borderRadius: 6}} />
    </div>
  );
};

export const HMerge: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const merge = prog(f, w("merge", "still") - 4, w("merge", "still") + 22, inOut);
  const ticket = pop(f, w("merge", "work") - 8, {damping: 13, stiffness: 150});
  const badge = pop(f, w("merge", "one") - 2, {damping: 9, stiffness: 240});
  return (
    <AbsoluteFill>
      <NavyBg glow="rgba(226,58,140,0.12)" />
      <Floaters color="pink" seed={59} scale={0.8} />
      <StepHeader n={4} of={7} word="Merge" sub="one issue." at={w("merge", "four")} subAt={w("merge", "issue")} accent={K.pink} ball="pink" dark />
      {SIGHTINGS.map(([a, b], i) => {
        const p = pop(f, w("merge", "seen") - 8 + i * 12, {damping: 13, stiffness: 160});
        const y0 = 720 + i * 200;
        const y = lerp(y0, 860, merge) - ticket * 60;
        const rot = lerp((i - 1) * 3, (i - 1) * 2.2, merge);
        const off = merge * (2 - i) * 10;
        return (
          <div
            key={a}
            style={{
              position: "absolute",
              left: 150 + off,
              top: y + off,
              width: 780,
              height: 190,
              borderRadius: 28,
              background: "#fff",
              boxShadow: "0 24px 50px rgba(0,0,0,0.35)",
              display: "flex",
              alignItems: "center",
              gap: 26,
              padding: "0 20px",
              transform: `translateX(${(1 - Math.min(1, p)) * (i % 2 ? 1100 : -1100)}px) rotate(${rot}deg)`,
              zIndex: 3 - i,
            }}
          >
            <Thumb seed={i} />
            <div>
              <div style={{fontFamily: F.sans, fontWeight: 700, fontSize: 36, color: K.navyText}}>Pothole · Kartal</div>
              <div style={{fontFamily: F.mono, fontSize: 24, color: "#6B7286", marginTop: 8}}>
                {a} · {b}
              </div>
            </div>
          </div>
        );
      })}
      {/* ×3 badge */}
      <div
        style={{
          position: "absolute",
          left: 850,
          top: 820 - ticket * 60,
          zIndex: 5,
          transform: `scale(${badge})`,
        }}
      >
        <Ball size={130} x={65} y={65} color="pink">
          <span style={{fontFamily: F.sans, fontWeight: 800, fontSize: 46, color: "#fff"}}>×3</span>
        </Ball>
      </div>
      {/* work order */}
      <div
        style={{
          position: "absolute",
          left: 150,
          top: 1110,
          width: 780,
          borderRadius: 28,
          background: "#fff",
          overflow: "hidden",
          display: "flex",
          boxShadow: "0 30px 60px rgba(0,0,0,0.35)",
          transform: `translateY(${(1 - ticket) * 1000}px)`,
          opacity: ticket > 0.01 ? 1 : 0,
        }}
      >
        <div style={{width: 18, background: K.pink}} />
        <div style={{padding: "28px 32px"}}>
          <div style={{fontFamily: F.mono, fontSize: 24, letterSpacing: 3, color: K.pink}}>WORK ORDER #0412</div>
          <div style={{fontFamily: F.sans, fontWeight: 800, fontSize: 44, color: K.navyText, marginTop: 8}}>1 pothole · Kartal</div>
          <div style={{fontFamily: F.sans, fontSize: 28, color: "#6B7286", marginTop: 6}}>Seen on 3 flights · Mon–Fri</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};
