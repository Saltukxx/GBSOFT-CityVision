import {Audio} from "@remotion/media";
import {TransitionSeries, linearTiming} from "@remotion/transitions";
import {fade} from "@remotion/transitions/fade";
import {slide} from "@remotion/transitions/slide";
import {wipe} from "@remotion/transitions/wipe";
import {AbsoluteFill, staticFile} from "remotion";
import {Scene01Hook} from "./scenes/Scene01Hook";
import {Scene02Problem} from "./scenes/Scene02Problem";
import {Scene03Sensor} from "./scenes/Scene03Sensor";
import {Scene04Flow} from "./scenes/Scene04Flow";
import {Scene05Detections} from "./scenes/Scene05Detections";
import {Scene06Trust} from "./scenes/Scene06Trust";
import {Scene07Impact} from "./scenes/Scene07Impact";
import {Scene08Cta} from "./scenes/Scene08Cta";

const transitionTiming = linearTiming({durationInFrames: 15});

export const CityVisionVideo: React.FC = () => {
  return (
    <AbsoluteFill style={{backgroundColor: "#050916"}}>
      <TransitionSeries>
        <TransitionSeries.Sequence durationInFrames={300} name="Şikâyet gelmeden görmek">
          <Scene01Hook />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={transitionTiming} />

        <TransitionSeries.Sequence durationInFrames={360} name="Görünmeyen şehir sorunları">
          <Scene02Problem />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({direction: "from-right"})} timing={transitionTiming} />

        <TransitionSeries.Sequence durationInFrames={390} name="Araçlar şehir sensörüne dönüşür">
          <Scene03Sensor />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={wipe({direction: "from-left"})} timing={transitionTiming} />

        <TransitionSeries.Sequence durationInFrames={420} name="Dört adımlı akış">
          <Scene04Flow />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={transitionTiming} />

        <TransitionSeries.Sequence durationInFrames={420} name="Tespit kapsamı">
          <Scene05Detections />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={slide({direction: "from-bottom"})} timing={transitionTiming} />

        <TransitionSeries.Sequence durationInFrames={360} name="Güven ve olay birleştirme">
          <Scene06Trust />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={fade()} timing={transitionTiming} />

        <TransitionSeries.Sequence durationInFrames={300} name="Pilot hedefleri">
          <Scene07Impact />
        </TransitionSeries.Sequence>
        <TransitionSeries.Transition presentation={wipe({direction: "from-right"})} timing={transitionTiming} />

        <TransitionSeries.Sequence durationInFrames={255} name="Pilot çağrısı">
          <Scene08Cta />
        </TransitionSeries.Sequence>
      </TransitionSeries>

      <Audio
        src={staticFile("voiceover.wav")}
        volume={(frame) =>
          frame < 20
            ? frame / 20
            : frame > 2650
              ? Math.max(0, (2700 - frame) / 50)
              : 1
        }
      />
    </AbsoluteFill>
  );
};
