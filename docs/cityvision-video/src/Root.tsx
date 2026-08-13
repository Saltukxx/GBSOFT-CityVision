import {Composition, Folder} from "remotion";
import {CityVisionVideo} from "./Composition";
import {CityVisionReel} from "./reel/ReelComposition";
import {S01Hook} from "./reel/scenes/S01Hook";
import {S02Detections} from "./reel/scenes/S02Detections";
import {S03Sensor} from "./reel/scenes/S03Sensor";
import {S04Pipeline} from "./reel/scenes/S04Pipeline";
import {S05Fusion} from "./reel/scenes/S05Fusion";
import {S06Dispatch} from "./reel/scenes/S06Dispatch";
import {S07Impact} from "./reel/scenes/S07Impact";
import {S08Close} from "./reel/scenes/S08Close";
import {Scene01Hook} from "./scenes/Scene01Hook";
import {Scene02Problem} from "./scenes/Scene02Problem";
import {Scene03Sensor} from "./scenes/Scene03Sensor";
import {Scene04Flow} from "./scenes/Scene04Flow";
import {Scene05Detections} from "./scenes/Scene05Detections";
import {Scene06Trust} from "./scenes/Scene06Trust";
import {Scene07Impact} from "./scenes/Scene07Impact";
import {Scene08Cta} from "./scenes/Scene08Cta";
import {SCENE_DURATIONS, TOTAL} from "./reel/timing";

const landscape = {fps: 30, width: 1920, height: 1080};
const portrait = {fps: 30, width: 1080, height: 1920};

const REEL_SCENES = [S01Hook, S02Detections, S03Sensor, S04Pipeline, S05Fusion, S06Dispatch, S07Impact, S08Close];
const REEL_NAMES = [
  "R01-Hook",
  "R02-Detections",
  "R03-Sensor",
  "R04-Pipeline",
  "R05-Fusion",
  "R06-Dispatch",
  "R07-Impact",
  "R08-Close",
];

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* Yayına çıkan dikey reel — seslendirmeye kilitli */}
      <Composition id="CityVision-Reels-Vertical" component={CityVisionReel} durationInFrames={TOTAL} {...portrait} />
      <Composition
        id="CityVision-Reels-Vertical-Sessiz"
        component={CityVisionReel}
        durationInFrames={TOTAL}
        defaultProps={{withAudio: false}}
        {...portrait}
      />

      {/* Tek tek sahne provaları (studio'da hızlı iterasyon için) */}
      <Folder name="Reel-Sahneler">
        {REEL_SCENES.map((Scene, i) => (
          <Composition
            key={REEL_NAMES[i]}
            id={REEL_NAMES[i]}
            component={Scene}
            durationInFrames={SCENE_DURATIONS[i]}
            {...portrait}
          />
        ))}
      </Folder>

      {/* Eski yatay 90 sn tanıtım — ayrı seslendirmeyle çalışır */}
      <Composition id="CityVision-Tanitim-Yatay" component={CityVisionVideo} durationInFrames={2700} {...landscape} />
      <Folder name="Yatay-Sahneler">
        <Composition id="Scene01-Hook" component={Scene01Hook} durationInFrames={300} {...landscape} />
        <Composition id="Scene02-Problem" component={Scene02Problem} durationInFrames={360} {...landscape} />
        <Composition id="Scene03-Sensor" component={Scene03Sensor} durationInFrames={390} {...landscape} />
        <Composition id="Scene04-Flow" component={Scene04Flow} durationInFrames={420} {...landscape} />
        <Composition id="Scene05-Detections" component={Scene05Detections} durationInFrames={420} {...landscape} />
        <Composition id="Scene06-Trust" component={Scene06Trust} durationInFrames={360} {...landscape} />
        <Composition id="Scene07-Impact" component={Scene07Impact} durationInFrames={300} {...landscape} />
        <Composition id="Scene08-Cta" component={Scene08Cta} durationInFrames={255} {...landscape} />
      </Folder>
    </>
  );
};
