import {AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig} from "remotion";
import {BigTitle, Body, Brand, COLORS, FooterLine, ImageBackdrop, Reveal} from "../shared";

export const Scene01Hook: React.FC = () => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  return (
    <AbsoluteFill style={{fontFamily: "Inter, Arial, sans-serif"}}>
      <ImageBackdrop src="assets/cover.jpg" darkness={0.62} scaleTo={1.06} />
      <Brand section="CITY VISION" />
      <div style={{position: "absolute", left: 82, top: 278}}>
        <Reveal delay={12}>
          <div style={{color: COLORS.cyan, fontSize: 22, fontWeight: 850, letterSpacing: 5, marginBottom: 25}}>
            TALEP GELMEDEN GÖRMEK
          </div>
        </Reveal>
        <Reveal delay={26}>
          <BigTitle maxWidth={1120}>Şehir her sorunu söylemez.</BigTitle>
        </Reveal>
        <Reveal delay={54}>
          <Body maxWidth={880}>City Vision, görünmeyeni belediyenin operasyonuna taşır.</Body>
        </Reveal>
      </div>

      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: interpolate(frame, [0, durationInFrames], [-120, 1110], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          }),
          height: 3,
          background: `linear-gradient(90deg, transparent, ${COLORS.cyan}, transparent)`,
          boxShadow: `0 0 34px ${COLORS.cyan}`,
          opacity: 0.72,
        }}
      />
      <FooterLine text="ŞEHRİ GÖREN YAPAY ZEKÂ" />
    </AbsoluteFill>
  );
};
