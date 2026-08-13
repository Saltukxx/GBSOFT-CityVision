import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from "remotion";
import {Brand, COLORS, Eyebrow, FooterLine, NoiseGrid, Reveal} from "../shared";

const steps = [
  {n: "01", title: "GÖR", desc: "Araç üstü kamera", color: COLORS.cyan},
  {n: "02", title: "ANLA", desc: "Araç içinde analiz", color: COLORS.violet},
  {n: "03", title: "DOĞRULA", desc: "Konum + tekrar gözlem", color: COLORS.yellow},
  {n: "04", title: "HAREKETE GEÇ", desc: "İş emri ve ekip", color: COLORS.green},
];

export const Scene04Flow: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.bg, fontFamily: "Inter, Arial, sans-serif"}}>
      <NoiseGrid />
      <Brand section="ÇALIŞMA PRENSİBİ" />
      <div style={{position: "absolute", left: 82, top: 175}}>
        <Reveal delay={5}><Eyebrow>GÖRÜNTÜDEN İŞ EMRİNE</Eyebrow></Reveal>
        <Reveal delay={15}>
          <div style={{fontSize: 82, color: COLORS.white, fontWeight: 780, letterSpacing: -3}}>Dört adım. Tek akış.</div>
        </Reveal>
      </div>

      <div style={{position: "absolute", left: 82, right: 82, top: 445, display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 34}}>
        {steps.map((step, index) => {
          const delay = 50 + index * 45;
          return (
            <div
              key={step.n}
              style={{
                height: 330,
                padding: "40px 32px",
                borderRadius: 24,
                border: `2px solid ${step.color}66`,
                background: "linear-gradient(145deg, rgba(17,31,60,.95), rgba(6,13,29,.86))",
                opacity: interpolate(frame, [delay, delay + 24], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16,1,.3,1)}),
                translate: interpolate(frame, [delay, delay + 35], ["0px 75px", "0px 0px"], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16,1,.3,1)}),
                boxShadow: frame > delay + 30 ? `0 0 45px ${step.color}14` : "none",
              }}
            >
              <div style={{fontSize: 24, color: step.color, fontWeight: 900, letterSpacing: 4}}>{step.n}</div>
              <div style={{marginTop: 58, fontSize: step.title.length > 8 ? 38 : 52, color: COLORS.white, fontWeight: 880, letterSpacing: -1}}>{step.title}</div>
              <div style={{marginTop: 24, fontSize: 28, lineHeight: 1.25, color: COLORS.muted}}>{step.desc}</div>
            </div>
          );
        })}
      </div>
      <div
        style={{
          position: "absolute",
          left: 174,
          top: 816,
          width: interpolate(frame, [60, 260], [0, 1550], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16,1,.3,1)}),
          height: 4,
          background: `linear-gradient(90deg, ${COLORS.cyan}, ${COLORS.violet}, ${COLORS.yellow}, ${COLORS.green})`,
          boxShadow: `0 0 26px ${COLORS.cyan}88`,
        }}
      />
      <Reveal delay={270} style={{position: "absolute", left: 82, top: 865, color: COLORS.white, fontSize: 36, fontWeight: 650}}>
        Yüzler ve plakalar maskelenir. Ham video araçtan çıkmaz.
      </Reveal>
      <FooterLine />
    </AbsoluteFill>
  );
};
