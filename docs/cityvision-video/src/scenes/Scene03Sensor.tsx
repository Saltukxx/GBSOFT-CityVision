import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from "remotion";
import {BigTitle, Body, Brand, COLORS, DetectionBox, FooterLine, ImageBackdrop, Reveal} from "../shared";

export const Scene03Sensor: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{fontFamily: "Inter, Arial, sans-serif"}}>
      <ImageBackdrop src="assets/closing.jpg" darkness={0.47} scaleTo={1.1} x="62%" />
      <Brand section="ÇÖZÜM" />
      <div style={{position: "absolute", left: 82, top: 235, zIndex: 5}}>
        <Reveal delay={5}>
          <BigTitle maxWidth={920}>Planlı drone uçuşu, tekrarlanabilir şehir taramasına dönüşür.</BigTitle>
        </Reveal>
        <Reveal delay={42}>
          <Body maxWidth={760}>Sabit rota. Sabit çekim standardı. Karşılaştırılabilir sonuç.</Body>
        </Reveal>
        <Reveal delay={82} style={{display: "flex", gap: 18, marginTop: 42}}>
          {["DRONE / DOCK", "MERKEZİ ANALİZ", "PLANLI UÇUŞ"].map((item, i) => (
            <div key={item} style={{padding: "18px 24px", border: `2px solid ${i === 1 ? COLORS.violet : COLORS.cyan}88`, backgroundColor: "rgba(6,13,29,.72)", borderRadius: 14, color: COLORS.white, fontSize: 22, fontWeight: 850, letterSpacing: 1}}>
              {item}
            </div>
          ))}
        </Reveal>
      </div>

      <div
        style={{
          position: "absolute",
          right: 310,
          bottom: 250,
          width: interpolate(frame, [60, 115], [0, 470], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16,1,.3,1)}),
          height: 5,
          backgroundColor: COLORS.cyan,
          transformOrigin: "right center",
          rotate: "-14deg",
          boxShadow: `0 0 28px ${COLORS.cyan}`,
        }}
      />
      <DetectionBox label="DRONE ŞEHİR TARAMASI" confidence="AKTİF" top={510} left={1180} width={560} height={300} color={COLORS.cyan} delay={68} />
      <FooterLine text="TEKRARLI UÇUŞ · ÖLÇÜLEBİLİR KAPSAMA" />
    </AbsoluteFill>
  );
};
