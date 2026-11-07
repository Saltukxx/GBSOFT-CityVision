import {Audio} from "@remotion/media";
import {CameraMotionBlur} from "@remotion/motion-blur";
import React from "react";
import {AbsoluteFill, Easing, Freeze, interpolate, Sequence, staticFile, useCurrentFrame} from "remotion";
import {inOut, outExpo, prog} from "../promo/kit";

/**
 * Shared reel engine for the CityVision series.
 * - Scenes live on a beat grid (timeline.json, lengths in beats), so every cut lands on the music.
 * - Each scene enters with a transition; the outgoing scene holds its last frame underneath.
 * - Camera motion blur, a static dither (kills gradient banding) and the audio stems are added here.
 */

export type Tr =
  | {kind: "cut"}
  | {kind: "iris"; x: number; y: number; r0: number; dur: number; zoomPrev?: number}
  | {kind: "whip"; dur: number; axis: "x" | "y"}
  | {kind: "zoom"; dur: number};

export type Timeline = {fps: number; bpm: number; scenes: (string | number)[][]};

export const beatFrames = (bpm: number) => (b: number) => Math.floor(b * (3600 / bpm) + 0.5);

export const layout = (tl: Timeline, transitions: Record<string, Tr>) => {
  const bf = beatFrames(tl.bpm);
  let beats = 0;
  const scenes = (tl.scenes as [string, number, string][]).map(([id, n, tr]) => {
    const from = bf(beats);
    beats += n;
    return {id, from, dur: bf(beats) - from, tr: tr === "cut" ? ({kind: "cut"} as Tr) : transitions[tr]};
  });
  const last = scenes[scenes.length - 1];
  return {scenes, total: last.from + last.dur};
};

const trDur = (t: Tr | undefined) => (!t || t.kind === "cut" ? 0 : t.dur);

const Shell: React.FC<{dur: number; enter: Tr; exit?: Tr; children: React.ReactNode}> = ({dur, enter, exit, children}) => {
  const f = useCurrentFrame();
  const style: React.CSSProperties = {};
  if (enter.kind === "iris") {
    const e = prog(f, 0, enter.dur, Easing.bezier(0.62, 0, 0.32, 1));
    if (e < 1) style.clipPath = `circle(${enter.r0 + (2300 - enter.r0) * e}px at ${enter.x}px ${enter.y}px)`;
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
  if (exit && f >= dur) {
    const x = prog(f, dur, dur + trDur(exit), inOut);
    if (exit.kind === "whip") {
      const d = -x * (exit.axis === "x" ? 1080 : 1920);
      style.transform = exit.axis === "x" ? `translateX(${d}px)` : `translateY(${d}px)`;
    } else if (exit.kind === "zoom") {
      style.transform = `scale(${1 + x * 0.8})`;
      style.opacity = 1 - x;
    } else if (exit.kind === "iris" && exit.zoomPrev) {
      style.transform = `scale(${interpolate(x, [0, 1], [1, exit.zoomPrev], {extrapolateRight: "clamp"})})`;
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

const DITHER = `url("data:image/svg+xml;utf8,${encodeURIComponent(
  "<svg xmlns='http://www.w3.org/2000/svg' width='256' height='256'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.5  0 0 0 0 0.5  0 0 0 0 0.5  0 0 0 1 0'/></filter><rect width='256' height='256' filter='url(%23n)'/></svg>",
).replace("%2523", "%23")}")`;

export type ReelProps = {withAudio?: boolean; blur?: boolean; voice?: boolean};

export const makeReel = (opts: {
  timeline: Timeline;
  transitions: Record<string, Tr>;
  components: Record<string, React.FC>;
  /** folder under public/ holding music.wav, sfx.wav, vo.wav, music_duck.wav, sfx_duck.wav */
  audioDir: string;
  /** drawn above all scenes (inside motion blur), e.g. a persistent timer */
  overlay?: React.FC;
  musicGain?: number;
}) => {
  const {scenes, total} = layout(opts.timeline, opts.transitions);
  const Overlay = opts.overlay;
  const Visuals: React.FC = () => (
    <AbsoluteFill style={{background: "#fff"}}>
      {scenes.map((s, i) => {
        const C = opts.components[s.id];
        const next = scenes[i + 1]?.tr;
        return (
          <Sequence key={s.id} from={s.from} durationInFrames={s.dur + trDur(next)} name={s.id}>
            <Shell dur={s.dur} enter={s.tr} exit={next}>
              <C />
            </Shell>
          </Sequence>
        );
      })}
      {Overlay ? <Overlay /> : null}
    </AbsoluteFill>
  );
  const gain = opts.musicGain ?? 0.5;
  const Reel: React.FC<ReelProps> = ({withAudio = true, blur = true, voice = true}) => (
    <AbsoluteFill>
      {blur ? (
        <CameraMotionBlur shutterAngle={170} samples={6}>
          <Visuals />
        </CameraMotionBlur>
      ) : (
        <Visuals />
      )}
      <AbsoluteFill style={{backgroundImage: DITHER, opacity: 0.045, mixBlendMode: "overlay", pointerEvents: "none"}} />
      {withAudio ? (
        <>
          <Audio
            src={staticFile(`${opts.audioDir}/${voice ? "music_duck" : "music"}.wav`)}
            volume={(f) =>
              interpolate(f, [0, 6, total - 40, total], [0, gain, gain, 0], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})
            }
          />
          <Audio src={staticFile(`${opts.audioDir}/${voice ? "sfx_duck" : "sfx"}.wav`)} volume={0.9} />
          {voice ? <Audio src={staticFile(`${opts.audioDir}/vo.wav`)} /> : null}
        </>
      ) : null}
    </AbsoluteFill>
  );
  return {Reel, scenes, total, fps: opts.timeline.fps};
};
