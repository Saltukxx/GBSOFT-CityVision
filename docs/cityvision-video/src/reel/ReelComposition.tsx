import {Audio} from "@remotion/media";
import {TransitionSeries, linearTiming} from "@remotion/transitions";
import {fade} from "@remotion/transitions/fade";
import {AbsoluteFill, interpolate, staticFile} from "remotion";
import "./fonts";
import {S01Hook} from "./scenes/S01Hook";
import {S02Detections} from "./scenes/S02Detections";
import {S03Sensor} from "./scenes/S03Sensor";
import {S04Pipeline} from "./scenes/S04Pipeline";
import {S05Fusion} from "./scenes/S05Fusion";
import {S06Dispatch} from "./scenes/S06Dispatch";
import {S07Impact} from "./scenes/S07Impact";
import {S08Close} from "./scenes/S08Close";
import {C} from "./theme";
import {MUSIC, SCENE_DURATIONS, TOTAL, TRANSITION} from "./timing";

const SCENES = [
  {name: "01 · Planlı drone taraması", C: S01Hook},
  {name: "02 · Ne tespit ediyor", C: S02Detections},
  {name: "03 · Tekrarlanabilir uçuş", C: S03Sensor},
  {name: "04 · Merkezi analiz ve kayıt", C: S04Pipeline},
  {name: "05 · Üç gözlem, tek olay", C: S05Fusion},
  {name: "06 · İş emri ve yönlendirme", C: S06Dispatch},
  {name: "07 · Kapsama ve erken tespit", C: S07Impact},
  {name: "08 · Kapanış", C: S08Close},
];

/**
 * Geçişler kısa ve tek tip: seslendirme cümle sınırlarında kesiliyor,
 * geçişin kendisi dikkat çekmemeli.
 */
const timing = linearTiming({durationInFrames: TRANSITION});

export const CityVisionReel: React.FC<{withAudio?: boolean}> = ({withAudio = false}) => (
  <AbsoluteFill style={{backgroundColor: C.ink}}>
    <TransitionSeries>
      {SCENES.flatMap((scene, i) => {
        const Scene = scene.C;
        const seq = (
          <TransitionSeries.Sequence key={scene.name} durationInFrames={SCENE_DURATIONS[i]} name={scene.name}>
            <Scene />
          </TransitionSeries.Sequence>
        );
        return i === SCENES.length - 1
          ? [seq]
          : [seq, <TransitionSeries.Transition key={`t-${i}`} presentation={fade()} timing={timing} />];
      })}
    </TransitionSeries>

    {withAudio ? (
      <>
        {/* Müzik yatağı: anlatım altında kısık, kapanışta biraz açılıp sönüyor. */}
        <Audio
          src={staticFile("muzik-lightbeats.mp3")}
          trimBefore={MUSIC.trimBefore}
          volume={(f) =>
            interpolate(
              f,
              [0, 24, MUSIC.liftAt, MUSIC.liftAt + 30, TOTAL - 26, TOTAL],
              [0, MUSIC.bed, MUSIC.bed, MUSIC.tail, MUSIC.tail, 0],
              {extrapolateLeft: "clamp", extrapolateRight: "clamp"},
            )
          }
        />
      </>
    ) : null}
  </AbsoluteFill>
);

export const REEL_DURATION = TOTAL;
