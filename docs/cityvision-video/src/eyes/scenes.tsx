import {EndCard} from "../series/endcard";
import React from "react";
import {AbsoluteFill, Img, OffthreadVideo, staticFile, useCurrentFrame} from "remotion";
import HFOOT from "../howto/footage.json";
import MFOOT from "../mayor/footage.json";
import MAP from "../mayor/map.json";
import {F, inOut, K, NavyBg, prog, usePop} from "../promo/kit";
import {along, MapCard, Said} from "../series/ui";
import W from "./vo_words.json";

const WORDS = W as unknown as Record<string, [string, number][]>;
const w = (scene: string, word: string) => {
  const hit = WORDS[scene].find(([x]) => x === word);
  if (!hit) throw new Error(`VO word not found: ${scene}/${word}`);
  return hit[1];
};

/** Two halves: the passer-by's glance (white world, top) and CityVision's view (navy world, bottom). */
const TOP = {y: 0, h: 950};
const BOT = {y: 970, h: 950};
const INK = K.navyText;

type Shot = {src: string; w: number; h: number; box: number[]; label: string; video?: {src: string; frames: number; fps: number}};

/** Media placed with "cover" inside a half, the detection box centred a little above the middle. */
const place = (shot: Shot, hh: number, zoom: number) => {
  const s = Math.max(1080 / shot.w, hh / shot.h) * zoom;
  const cx = ((shot.box[0] + shot.box[2]) / 2) * s;
  const cy = ((shot.box[1] + shot.box[3]) / 2) * s;
  const left = Math.min(0, Math.max(1080 - shot.w * s, 540 - cx));
  const top = Math.min(0, Math.max(hh - shot.h * s, hh * 0.5 - cy));
  return {s, left, top};
};

const Media: React.FC<{shot: Shot; hh: number; zoom: number; frozen: boolean; videoSrc?: string}> = ({shot, hh, zoom, frozen, videoSrc}) => {
  const {s, left, top} = place(shot, hh, zoom);
  const style: React.CSSProperties = {position: "absolute", left, top, width: shot.w * s, height: shot.h * s, maxWidth: "none"};
  return videoSrc && !frozen ? <OffthreadVideo src={staticFile(videoSrc)} muted style={style} /> : <Img src={staticFile(shot.src)} style={style} />;
};

const Chip: React.FC<{text: string; dark?: boolean; y: number; at?: number}> = ({text, dark, y, at = 0}) => {
  const f = useCurrentFrame();
  const p = prog(f, at, at + 12);
  return (
    <div
      style={{
        position: "absolute",
        left: 48,
        top: y,
        padding: "12px 22px",
        borderRadius: 999,
        background: dark ? "rgba(8,21,48,0.72)" : "rgba(255,255,255,0.88)",
        border: dark ? "1px solid rgba(255,255,255,0.16)" : "1px solid rgba(14,27,61,0.08)",
        fontFamily: F.mono,
        fontSize: 24,
        letterSpacing: 3,
        color: dark ? "#E6ECF8" : INK,
        opacity: p,
        transform: `translateY(${(1 - p) * 10}px)`,
        display: "flex",
        alignItems: "center",
        gap: 12,
      }}
    >
      <div style={{width: 12, height: 12, borderRadius: 9, background: dark ? K.teal : K.gray}} />
      {text}
    </div>
  );
};

const Divider: React.FC<{draw?: number}> = ({draw = 1}) => (
  <div style={{position: "absolute", left: 540 - 540 * draw, width: 1080 * draw, top: 950, height: 20, background: "#fff", boxShadow: "0 0 30px rgba(0,0,0,0.25)"}} />
);

/* ════════ Intro ════════ */
export const EIntro: React.FC = () => {
  const f = useCurrentFrame();
  const d = prog(f, 0, 30, inOut);
  return (
    <AbsoluteFill>
      <div style={{position: "absolute", left: 0, right: 0, top: 0, height: 960, background: "radial-gradient(120% 90% at 50% 60%, #FFFFFF, #ECEFF4)"}} />
      <div style={{position: "absolute", left: 0, right: 0, top: 960, bottom: 0, overflow: "hidden"}}>
        <NavyBg />
      </div>
      <Divider draw={d} />
      <div style={{position: "absolute", left: 0, right: 0, top: 560, textAlign: "center", fontFamily: F.serif, fontStyle: "italic", fontSize: 120, color: INK, opacity: prog(f, 18, 34), transform: `translateY(${(1 - prog(f, 18, 40)) * 30}px)`}}>
        Seen in passing.
      </div>
      <div style={{position: "absolute", left: 0, right: 0, top: 1240, textAlign: "center", fontFamily: F.sans, fontWeight: 800, fontSize: 92, letterSpacing: -3, color: "#fff", opacity: prog(f, 44, 58), transform: `translateY(${(1 - prog(f, 44, 66)) * 30}px)`}}>
        Seen by City<span style={{color: K.orange}}>Vision</span>.
      </div>
    </AbsoluteFill>
  );
};

/* ════════ Moments ════════ */
type Variant = "phone" | "drive" | "blink" | "phone2";

const makeMoment = (opts: {shot: Shot; street: string; caption: string; accent: string; variant: Variant; notif?: string; dur: number}): React.FC => {
  const Moment: React.FC = () => {
    const f = useCurrentFrame();
    const pop = usePop();
    const vid = opts.shot.video;
    const HIT = vid ? Math.round((vid.frames / vid.fps) * 60) : 40;
    const frozen = f >= HIT;
    const zoom = 1.12 + prog(f, 0, opts.dur) * 0.06;
    // the passer-by's glance: washed out, out of focus, never still
    const jx = Math.sin(f / 5.1) * 2.5 + Math.sin(f / 11.3) * 2;
    const jy = Math.cos(f / 6.2) * 2;
    const driveBlur = opts.variant === "drive" ? 6 + 10 * Math.abs(Math.sin(f / 18)) : 0;
    const blink = opts.variant === "blink" ? Math.max(0, 1 - Math.abs(f - 70) / 10) : 0;
    const [x1, y1, x2, y2] = opts.shot.box;
    const pl = place(opts.shot, BOT.h, zoom);
    const bx = x1 * pl.s + pl.left;
    const by = y1 * pl.s + pl.top;
    const bw = (x2 - x1) * pl.s;
    const bh = (y2 - y1) * pl.s;
    const bp = pop(f, HIT, {damping: 10, stiffness: 260});
    const flash = frozen ? 1 - prog(f, HIT, HIT + 9) : 0;
    const notifP = opts.notif ? pop(f, 20, {damping: 14, stiffness: 160}) * (1 - prog(f, HIT + 30, HIT + 44)) : 0;
    return (
      <AbsoluteFill style={{background: "#fff"}}>
        {/* ── top: a passer-by ── */}
        <div style={{position: "absolute", left: 0, right: 0, top: TOP.y, height: TOP.h, overflow: "hidden"}}>
          <div
            style={{
              position: "absolute",
              inset: -30,
              transform: `translate(${jx}px, ${jy}px) rotate(${Math.sin(f / 13) * 0.3}deg) scale(1.06)`,
              filter: `grayscale(0.35) blur(${1.5 + driveBlur}px) brightness(1.05) contrast(0.92)`,
            }}
          >
            <OffthreadVideo src={staticFile(opts.street)} muted style={{position: "absolute", left: 30, top: 30, width: 1080, height: TOP.h}} />
          </div>
          <AbsoluteFill style={{background: "linear-gradient(180deg, rgba(255,255,255,0.28), rgba(255,255,255,0.05) 45%, rgba(255,255,255,0.5))"}} />
          {blink > 0 ? (
            <>
              <div style={{position: "absolute", left: 0, right: 0, top: 0, height: (TOP.h / 2) * blink, background: "#0E1B3D"}} />
              <div style={{position: "absolute", left: 0, right: 0, bottom: 0, height: (TOP.h / 2) * blink, background: "#0E1B3D"}} />
            </>
          ) : null}
          {opts.notif ? (
            <div
              style={{
                position: "absolute",
                left: 60,
                right: 60,
                top: 300,
                transform: `translateY(${(1 - Math.min(1, notifP)) * -260}px)`,
                opacity: Math.min(1, notifP * 1.4),
                borderRadius: 34,
                padding: "24px 28px",
                background: "rgba(255,255,255,0.92)",
                boxShadow: "0 24px 50px rgba(20,30,60,0.2)",
                display: "flex",
                gap: 20,
                alignItems: "center",
              }}
            >
              <div style={{width: 64, height: 64, borderRadius: 16, background: "linear-gradient(160deg, #5BE584, #2BB24C)", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontSize: 34, fontFamily: F.sans, fontWeight: 800}}>✉</div>
              <div>
                <div style={{fontFamily: F.sans, fontWeight: 700, fontSize: 28, color: INK}}>Messages · now</div>
                <div style={{fontFamily: F.sans, fontSize: 28, color: "#4A5470", marginTop: 4}}>{opts.notif}</div>
              </div>
            </div>
          ) : null}
          <Chip text="SEEN IN PASSING" y={220} />
          <div
            style={{
              position: "absolute",
              left: 48,
              top: 760,
              fontFamily: F.serif,
              fontStyle: "italic",
              fontSize: 92,
              color: INK,
              opacity: prog(f, HIT - 10, HIT + 6),
              transform: `translateY(${(1 - prog(f, HIT - 10, HIT + 12)) * 24}px)`,
              textShadow: "0 2px 18px rgba(255,255,255,0.9)",
            }}
          >
            {opts.caption}
          </div>
        </div>

        {/* ── bottom: CityVision ── */}
        <div style={{position: "absolute", left: 0, right: 0, top: BOT.y, height: BOT.h, overflow: "hidden", background: "#081530"}}>
          <Media shot={opts.shot} hh={BOT.h} zoom={zoom} frozen={frozen} videoSrc={vid?.src} />
          <AbsoluteFill style={{background: "radial-gradient(90% 80% at 50% 45%, rgba(8,21,48,0) 50%, rgba(8,21,48,0.55) 100%)"}} />
          {frozen ? (
            <div
              style={{
                position: "absolute",
                left: bx,
                top: by,
                width: bw,
                height: bh,
                border: `6px solid ${opts.accent}`,
                borderRadius: 14,
                transform: `scale(${bp})`,
                opacity: Math.min(1, bp),
                boxShadow: `0 0 0 3000px rgba(8,21,48,${0.32 * Math.min(1, bp)})`,
              }}
            >
              <div style={{position: "absolute", left: -6, top: by > 140 ? -52 : undefined, bottom: by > 140 ? undefined : -52, whiteSpace: "nowrap", background: opts.accent, color: "#fff", fontFamily: F.mono, fontSize: 26, padding: "8px 14px", borderRadius: 10}}>
                {opts.shot.label}
              </div>
            </div>
          ) : null}
          <AbsoluteFill style={{background: "#fff", opacity: flash * 0.7}} />
          <Chip text="SEEN BY CITYVISION" dark y={36} />
          <div style={{position: "absolute", right: 48, top: 48, display: "flex", alignItems: "center", gap: 10, fontFamily: F.mono, fontSize: 22, color: "#fff"}}>
            <div style={{width: 14, height: 14, borderRadius: 9, background: K.red, opacity: Math.floor(f / 20) % 2 ? 1 : 0.35}} />
            AI · LIVE
          </div>
          {frozen ? (
            <div
              style={{
                position: "absolute",
                left: 48,
                bottom: 300,
                display: "flex",
                alignItems: "center",
                gap: 14,
                padding: "14px 22px",
                borderRadius: 999,
                background: "rgba(255,255,255,0.95)",
                fontFamily: F.sans,
                fontWeight: 700,
                fontSize: 30,
                color: INK,
                transform: `scale(${pop(f, HIT + 12, {damping: 11})})`,
                transformOrigin: "0% 50%",
              }}
            >
              <div style={{width: 34, height: 34, borderRadius: 99, background: K.green, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 22}}>✓</div>
              logged · photo + GPS
            </div>
          ) : null}
        </div>
        <Divider />
      </AbsoluteFill>
    );
  };
  return Moment;
};

const MOM_DUR = 188;
export const EM1 = makeMoment({shot: {...HFOOT.pothole, video: {src: HFOOT.intro.src, frames: HFOOT.intro.frames, fps: HFOOT.intro.fps}}, street: "eyes/street/walk.mp4", caption: "walked past it.", accent: K.orange, variant: "phone", notif: "Running late, be there in 5", dur: MOM_DUR});
export const EM2 = makeMoment({shot: MFOOT.crack, street: "eyes/street/over.mp4", caption: "stepped right over it.", accent: K.pink, variant: "phone2", dur: MOM_DUR});
export const EM3 = makeMoment({shot: MFOOT.pothole as Shot, street: "eyes/street/around.mp4", caption: "stepped around it.", accent: K.teal, variant: "phone2", dur: MOM_DUR});
export const EM4 = makeMoment({shot: MFOOT.damage, street: "eyes/street/phone.mp4", caption: "didn't look down.", accent: K.purple, variant: "phone2", dur: MOM_DUR});

const THUMBS: Shot[] = [HFOOT.pothole, MFOOT.crack, MFOOT.pothole as Shot, MFOOT.damage];
const TCOL = [K.orange, K.pink, K.teal, K.purple];

const BoxThumb: React.FC<{shot: Shot; size: number}> = ({shot, size}) => {
  const [x1, y1, x2, y2] = shot.box;
  const k = Math.max(size / Math.min(shot.w, shot.h), (size * 0.8) / Math.max(x2 - x1, y2 - y1));
  const left = Math.min(0, Math.max(size - shot.w * k, size / 2 - ((x1 + x2) / 2) * k));
  const top = Math.min(0, Math.max(size - shot.h * k, size / 2 - ((y1 + y2) / 2) * k));
  return (
    <div style={{position: "relative", width: size, height: size, borderRadius: size * 0.2, overflow: "hidden"}}>
      <Img src={staticFile(shot.src)} style={{position: "absolute", left, top, width: shot.w * k, height: shot.h * k}} />
    </div>
  );
};

/* ════════ Tally (the last beat is the music's silence) ════════ */
const TallyPanels: React.FC<{t: number; split?: number}> = ({t, split = 0}) => {
  const pop = usePop();
  const logged = THUMBS.filter((_, i) => t >= 8 + i * 10).length;
  return (
    <>
      <div style={{position: "absolute", left: 0, right: 0, top: 0, height: 960, background: "radial-gradient(120% 90% at 50% 60%, #FFFFFF, #ECEFF4)", transform: `translateY(${-split * 1000}px)`}}>
        <Chip text="SEEN IN PASSING" y={220} />
        <div style={{position: "absolute", left: 0, right: 0, top: 420, textAlign: "center", fontFamily: F.mono, fontSize: 34, letterSpacing: 5, color: K.gray}}>NOTICED</div>
        <div style={{position: "absolute", left: 0, right: 0, top: 470, textAlign: "center", fontFamily: F.sans, fontWeight: 900, fontSize: 300, letterSpacing: -12, lineHeight: 1, color: "#C4C9D4"}}>0</div>
      </div>
      <div style={{position: "absolute", left: 0, right: 0, top: 960, bottom: 0, overflow: "hidden", transform: `translateY(${split * 1000}px)`}}>
        <NavyBg glow="rgba(22,163,74,0.12)" />
        <Chip text="SEEN BY CITYVISION" dark y={46} />
        <div style={{position: "absolute", left: 0, right: 0, top: 170, textAlign: "center", fontFamily: F.mono, fontSize: 34, letterSpacing: 5, color: "rgba(255,255,255,0.65)"}}>LOGGED</div>
        <div style={{position: "absolute", left: 0, right: 0, top: 220, textAlign: "center", fontFamily: F.sans, fontWeight: 900, fontSize: 300, letterSpacing: -12, lineHeight: 1, color: K.green}}>{logged}</div>
        <div style={{position: "absolute", left: 0, right: 0, top: 560, display: "flex", justifyContent: "center", gap: 20}}>
          {THUMBS.map((s, i) => (
            <div key={i} style={{position: "relative", transform: `scale(${pop(t, 8 + i * 10, {damping: 10, stiffness: 240})})`}}>
              <div style={{border: `5px solid ${TCOL[i]}`, borderRadius: 30}}>
                <BoxThumb shot={s} size={150} />
              </div>
              <div style={{position: "absolute", right: -10, bottom: -10, width: 44, height: 44, borderRadius: 99, background: K.green, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 26, fontWeight: 800}}>✓</div>
            </div>
          ))}
        </div>
      </div>
      <div style={{position: "absolute", left: 0, right: 0, top: 950, height: 20, background: "#fff", opacity: 1 - split}} />
    </>
  );
};

export const ETally: React.FC = () => {
  const f = useCurrentFrame();
  return (
    <AbsoluteFill style={{background: "#fff"}}>
      <TallyPanels t={Math.min(f, 94)} />
    </AbsoluteFill>
  );
};

/* ════════ Map — on the drop the halves split open ════════ */
export const EMap: React.FC = () => {
  const f = useCurrentFrame();
  const pop = usePop();
  const split = prog(f, 0, 26, inOut);
  const fly = MAP.fly as [number, number][];
  const pins = [0.14, 0.4, 0.64, 0.88].map((t) => along(fly, t));
  const xs = fly.map((p) => p[0]);
  const ys = fly.map((p) => p[1]);
  const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
  const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
  const s0 = Math.min(980 / (Math.max(...xs) - Math.min(...xs) + 300), 1300 / (Math.max(...ys) - Math.min(...ys) + 300));
  const view = {cx, cy: cy - 40 / s0, s: s0 * (1.12 - 0.12 * prog(f, 0, 250, inOut))};
  const len = fly.slice(1).reduce((a, p, i) => a + Math.hypot(p[0] - fly[i][0], p[1] - fly[i][1]), 0);
  const draw = prog(f, 14, 90, inOut);
  return (
    <AbsoluteFill style={{background: "#F3F1EC"}}>
      <MapCard src={staticFile(MAP.light)} mapW={MAP.w} mapH={MAP.h} w={1080} h={1920} view={view} style={{left: 0, top: 0, borderRadius: 0, boxShadow: "none", border: "none"}}>
        {(proj, sc) => (
          <>
            <svg width={1080} height={1920} style={{position: "absolute", inset: 0}}>
              <polyline points={fly.map(([x, y]) => proj(x, y).join(",")).join(" ")} fill="none" stroke={K.navy} strokeWidth={9} strokeLinecap="round" strokeLinejoin="round" strokeDasharray={`${len * sc * draw} ${len * sc * 2}`} opacity={0.85} />
            </svg>
            {pins.map((p, i) => {
              const [x, y] = proj(p.x, p.y);
              const q = pop(f, 30 + i * 9, {damping: 10, stiffness: 220});
              return (
                <div key={i} style={{position: "absolute", left: x - 64, top: y - 150, transform: `scale(${q})`, transformOrigin: "50% 100%"}}>
                  <div style={{width: 128, height: 128, borderRadius: 30, background: "#fff", padding: 9, boxShadow: "0 16px 34px rgba(20,30,60,0.28)", border: `5px solid ${TCOL[i]}`}}>
                    <BoxThumb shot={THUMBS[i]} size={100} />
                  </div>
                  <div style={{width: 0, height: 0, margin: "0 auto", borderLeft: "14px solid transparent", borderRight: "14px solid transparent", borderTop: `16px solid ${TCOL[i]}`}} />
                </div>
              );
            })}
          </>
        )}
      </MapCard>
      <AbsoluteFill style={{background: "linear-gradient(180deg, rgba(255,255,255,0.92) 0%, rgba(255,255,255,0.6) 22%, rgba(255,255,255,0) 38%)"}} />
      <Said words={[["Same", w("map", "same")], ["street.", w("map", "street")]]} y={250} size={120} weight={900} />
      <div style={{position: "absolute", left: 0, right: 0, top: 380, textAlign: "center", fontFamily: F.serif, fontStyle: "italic", fontSize: 130, color: K.orange}}>
        {[
          ["Different", w("map", "different")],
          ["eyes.", w("map", "eyes")],
        ].map(([t, at], i) => {
          const p = prog(f, (at as number) - 2, (at as number) + 14);
          return (
            <span key={i} style={{display: "inline-block", marginRight: 28, opacity: p, transform: `translateY(${(1 - p) * 40}px)`, filter: p < 1 ? `blur(${(1 - p) * 10}px)` : undefined}}>
              {t}
            </span>
          );
        })}
      </div>
      <div style={{position: "absolute", left: 0, right: 0, top: 1620, display: "flex", justifyContent: "center", opacity: prog(f, 120, 134)}}>
        <div style={{padding: "12px 22px", borderRadius: 999, background: "rgba(255,255,255,0.92)", fontFamily: F.mono, fontSize: 24, color: INK, boxShadow: "0 8px 20px rgba(20,30,60,0.15)"}}>
          4 issues · each with photo + GPS
        </div>
      </div>
      {split < 1 ? <TallyPanels t={94} split={split} /> : null}
    </AbsoluteFill>
  );
};

/* ════════ End — the halves close again = frame 1 ════════ */
export const EEnd: React.FC = () => (
  <EndCard
    dur={188}
    cityAt={w("end", "cityvision")}
    bookAt={w("end", "book")}
    note="Drone footage: our own test flight · faces & plates blurred · map © OpenStreetMap"
    loop={{
      mode: "halves",
      at: 158,
      to: <div style={{position: "absolute", inset: 0, background: "radial-gradient(120% 90% at 50% 60%, #FFFFFF, #ECEFF4)"}} />,
      bottom: <NavyBg />,
    }}
  />
);

