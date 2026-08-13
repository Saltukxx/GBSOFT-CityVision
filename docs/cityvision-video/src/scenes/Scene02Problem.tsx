import {AbsoluteFill, CanvasImage, Easing, interpolate, staticFile, useCurrentFrame} from "remotion";
import {Brand, COLORS, Eyebrow, FooterLine, NoiseGrid, Reveal} from "../shared";

const problems = [
  {src: "assets/pothole.jpg", label: "YOL HASARI", color: COLORS.red},
  {src: "assets/waste.jpg", label: "TAŞMIŞ ATIK", color: COLORS.yellow},
  {src: "assets/detect.jpg", label: "TRAFİK / İŞGAL", color: COLORS.violet},
];

export const Scene02Problem: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.bg, fontFamily: "Inter, Arial, sans-serif"}}>
      <NoiseGrid />
      <Brand section="PROBLEM" />
      <div style={{position: "absolute", left: 82, top: 160}}>
        <Reveal delay={5}><Eyebrow>ŞİKÂYETE BAĞIMLI TESPİT</Eyebrow></Reveal>
        <Reveal delay={15}>
          <div style={{fontSize: 76, lineHeight: 1.02, fontWeight: 780, letterSpacing: -3, color: COLORS.white, maxWidth: 1180}}>
            Belediye, şehrin sorununu<br/><span style={{color: COLORS.red}}>en son</span> öğreniyor.
          </div>
        </Reveal>
      </div>

      <div style={{position: "absolute", left: 82, right: 82, top: 430, display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 24}}>
        {problems.map((problem, index) => (
          <div
            key={problem.label}
            style={{
              position: "relative",
              height: 420,
              overflow: "hidden",
              borderRadius: 24,
              border: `2px solid ${problem.color}77`,
              opacity: interpolate(frame, [35 + index * 16, 60 + index * 16], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              }),
              translate: interpolate(frame, [35 + index * 16, 70 + index * 16], ["0px 80px", "0px 0px"], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
                easing: Easing.bezier(0.16, 1, 0.3, 1),
              }),
            }}
          >
            <CanvasImage src={staticFile(problem.src)} style={{width: "100%", height: "100%", objectFit: "cover"}} />
            <AbsoluteFill style={{background: "linear-gradient(180deg, transparent 38%, rgba(3,7,18,.96))"}} />
            <div style={{position: "absolute", left: 28, bottom: 28, color: COLORS.white, fontSize: 34, fontWeight: 850, letterSpacing: 1}}>
              <span style={{display: "inline-block", width: 13, height: 13, borderRadius: 99, backgroundColor: problem.color, marginRight: 14, boxShadow: `0 0 18px ${problem.color}`}} />
              {problem.label}
            </div>
          </div>
        ))}
      </div>
      <FooterLine text="GÖRÜNMEYEN SORUN · BÜYÜYEN MALİYET" />
    </AbsoluteFill>
  );
};
