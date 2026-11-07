import {Audio} from "@remotion/media";
import {CameraMotionBlur} from "@remotion/motion-blur";
import React from "react";
import {AbsoluteFill, Easing, Freeze, interpolate, Sequence, staticFile, useCurrentFrame} from "remotion";
import {inOut, outExpo, prog} from "./kit";
import {SFeed, SMap, SSays, SWhere, SWrong} from "./scenes/A";
import {SEvery, SFindOut, SKm, SLogo, SReal} from "./scenes/B";
import {SEnd, SFewer, SMorning, SNotify, SOneTap} from "./scenes/C";
import TL from "./timeline.json";

const COMPONENTS: Record<string, React.FC> = {
  map: SMap,
  wrong: SWrong,
  says: SSays,
  where: SWhere,
  feed: SFeed,
  findout: SFindOut,
  km: SKm,
  logo: SLogo,
  every: SEvery,
  real: SReal,
  notify: SNotify,
  onetap: SOneTap,
  morning: SMorning,
  fewer: SFewer,
  end: SEnd,
};

type Tr =
  | {kind: "cut"}
  | {kind: "iris"; x: number; y: number; r0: number; dur: number; zoomPrev?: number}
  | {kind: "whip"; dur: number; axis: "x" | "y"}
  | {kind: "zoom"; dur: number};

/** How each scene enters. Iris centres sit on a ball in the outgoing scene, so the ball becomes the portal. */
const TRANSITIONS: Record<string, Tr> = {
  cut: {kind: "cut"},
  irisO: {kind: "iris", x: 550, y: 894, r0: 36, dur: 22},
  irisBall: {kind: "iris", x: 690, y: 1000, r0: 235, dur: 20},
  zoom: {kind: "zoom", dur: 14},
  irisDrop: {kind: "iris", x: 540, y: 770, r0: 0, dur: 14},
  irisPupil: {kind: "iris", x: 540, y: 770, r0: 49, dur: 22, zoomPrev: 6},
  irisPin: {kind: "iris", x: 540, y: 960, r0: 210, dur: 20},
  whip: {kind: "whip", dur: 14, axis: "x"},
  push: {kind: "whip", dur: 16, axis: "y"},
  irisLogo: {kind: "iris", x: 540, y: 620, r0: 0, dur: 20},
};

const BEAT = 3600 / TL.bpm;
export const beatFrame = (b: number) => Math.floor(b * BEAT + 0.5);

export const SCENES = (() => {
  let beats = 0;
  return (TL.scenes as [string, number, string][]).map(([id, n, tr]) => {
    const from = beatFrame(beats);
    beats += n;
    return {id, from, dur: beatFrame(beats) - from, tr: TRANSITIONS[tr]};
  });
})();

export const PROMO_FPS = TL.fps;
export const PROMO_TOTAL = SCENES[SCENES.length - 1].from + SCENES[SCENES.length - 1].dur;

const trDur = (t: Tr | undefined) => (!t || t.kind === "cut" ? 0 : t.dur);

/**
 * One scene plus its transition handles. The incoming scene starts exactly on its beat;
 * the outgoing one holds its last frame underneath until the incoming transition is done.
 */
const Shell: React.FC<{dur: number; enter: Tr; exit?: Tr; children: React.ReactNode}> = ({dur, enter, exit, children}) => {
  const f = useCurrentFrame();
  const style: React.CSSProperties = {};
  // entering
  if (enter.kind === "iris") {
    // slow start so the portal reads, then it rushes open
    const e = prog(f, 0, enter.dur, Easing.bezier(0.62, 0, 0.32, 1));
    const r = enter.r0 + (2300 - enter.r0) * e;
    if (e < 1) style.clipPath = `circle(${r}px at ${enter.x}px ${enter.y}px)`;
  } else if (enter.kind === "whip") {
    const e = prog(f, 0, enter.dur, inOut);
    const d = (1 - e) * (enter.axis === "x" ? 1080 : 1920);
    if (e < 1) style.transform = enter.axis === "x" ? `translateX(${d}px)` : `translateY(${d}px)`;
  } else if (enter.kind === "zoom") {
    const e = prog(f, 0, enter.dur, outExpo);
    if (e < 1) {
      style.transform = `scale(${0.7 + 0.3 * e})`;
      style.opacity = e;
    }
  }
  // exiting (we are the previous scene under the next one's transition)
  if (exit && f >= dur) {
    const x = prog(f, dur, dur + trDur(exit), inOut);
    if (exit.kind === "whip") {
      const d = -x * (exit.axis === "x" ? 1080 : 1920);
      style.transform = exit.axis === "x" ? `translateX(${d}px)` : `translateY(${d}px)`;
    } else if (exit.kind === "zoom") {
      style.transform = `scale(${1 + x * 0.8})`;
      style.opacity = 1 - x;
    } else if (exit.kind === "iris" && exit.zoomPrev) {
      const z = interpolate(x, [0, 1], [1, exit.zoomPrev], {extrapolateRight: "clamp"});
      style.transform = `scale(${z})`;
      style.transformOrigin = `${exit.x}px ${exit.y}px`;
    }
  }
  return (
    <AbsoluteFill style={style}>
      <Freeze frame={dur - 1} active={f >= dur}>
        {children}
      </Freeze>
    </AbsoluteFill>
  );
};

const Visuals: React.FC = () => (
  <AbsoluteFill style={{background: "#F2F3F6"}}>
    {SCENES.map((s, i) => {
      const C = COMPONENTS[s.id];
      const next = SCENES[i + 1]?.tr;
      const hold = trDur(next);
      return (
        <Sequence key={s.id} from={s.from} durationInFrames={s.dur + hold} name={s.id}>
          <Shell dur={s.dur} enter={s.tr} exit={next}>
            <C />
          </Shell>
        </Sequence>
      );
    })}
  </AbsoluteFill>
);

export const CityVisionPromo: React.FC<{withAudio?: boolean; blur?: boolean; voice?: boolean}> = ({
  withAudio = true,
  blur = true,
  voice = false,
}) => (
  <AbsoluteFill>
    {blur ? (
      <CameraMotionBlur shutterAngle={170} samples={6}>
        <Visuals />
      </CameraMotionBlur>
    ) : (
      <Visuals />
    )}
    {/* static dither: breaks up 8-bit banding in the big gradients (invisible at normal viewing) */}
    <AbsoluteFill
      style={{
        backgroundImage: `url("data:image/svg+xml;utf8,${encodeURIComponent(
          "<svg xmlns='http://www.w3.org/2000/svg' width='256' height='256'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.5  0 0 0 0 0.5  0 0 0 0 0.5  0 0 0 1 0'/></filter><rect width='256' height='256' filter='url(%23n)'/></svg>",
        ).replace("%2523", "%23")}")`,
        opacity: 0.045,
        mixBlendMode: "overlay",
        pointerEvents: "none",
      }}
    />
    {withAudio ? (
      <>
        <Audio
          src={staticFile(voice ? "promo/music_duck.wav" : "promo/music.wav")}
          volume={(f) =>
            interpolate(f, [0, 12, PROMO_TOTAL - 40, PROMO_TOTAL], [0, 0.5, 0.5, 0], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })
          }
        />
        <Audio src={staticFile(voice ? "promo/sfx_duck.wav" : "promo/sfx.wav")} volume={0.9} />
        {voice ? <Audio src={staticFile("promo/vo.wav")} volume={1} /> : null}
      </>
    ) : null}
  </AbsoluteFill>
);
