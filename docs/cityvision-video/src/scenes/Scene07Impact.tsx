import {AbsoluteFill, CanvasImage, Easing, interpolate, staticFile, useCurrentFrame} from "remotion";
import {Brand, COLORS, FooterLine, Reveal} from "../shared";

const stats = [
  {value: "AYNI GÜN", label: "tespit hedefi", color: COLORS.cyan},
  {value: "%92", label: "haftalık yol kapsaması hedefi", color: COLORS.green},
  {value: "< %10", label: "mükerrer görev hedefi", color: COLORS.violet},
];

export const Scene07Impact: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.bg, fontFamily: "Inter, Arial, sans-serif"}}>
      <CanvasImage src={staticFile("slides/slide-27.png")} style={{width: "100%", height: "100%", objectFit: "cover", opacity: 0.18, filter: "blur(2px)", scale: 1.04}} />
      <AbsoluteFill style={{background: "linear-gradient(90deg, rgba(5,9,22,.98), rgba(5,9,22,.84), rgba(5,9,22,.92))"}} />
      <Brand section="PİLOT HEDEFLERİ" />
      <Reveal delay={5} style={{position: "absolute", left: 82, top: 170}}>
        <div style={{fontSize: 86, color: COLORS.white, fontWeight: 790, letterSpacing: -3}}>Belediye için ne değişiyor?</div>
        <div style={{fontSize: 34, color: COLORS.muted, marginTop: 18}}>Başarı kriterleri ilk günden ölçülebilir.</div>
      </Reveal>
      <div style={{position: "absolute", left: 82, right: 82, top: 440, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 28}}>
        {stats.map((stat, index) => (
          <div
            key={stat.value}
            style={{
              height: 310,
              padding: "46px 38px",
              borderRadius: 25,
              border: `2px solid ${stat.color}66`,
              backgroundColor: "rgba(8,18,38,.9)",
              opacity: interpolate(frame, [45 + index * 32, 75 + index * 32], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16,1,.3,1)}),
              translate: interpolate(frame, [45 + index * 32, 85 + index * 32], ["0px 70px", "0px 0px"], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16,1,.3,1)}),
            }}
          >
            <div style={{fontSize: stat.value.length > 6 ? 54 : 76, color: stat.color, fontWeight: 920, letterSpacing: -2}}>{stat.value}</div>
            <div style={{marginTop: 32, color: COLORS.white, fontSize: 31, lineHeight: 1.24, fontWeight: 650}}>{stat.label}</div>
            <div style={{height: 4, width: interpolate(frame, [120 + index * 25, 205 + index * 25], [0, 260], {extrapolateLeft: "clamp", extrapolateRight: "clamp"}), marginTop: 34, backgroundColor: stat.color, boxShadow: `0 0 18px ${stat.color}`}} />
          </div>
        ))}
      </div>
      <Reveal delay={210} style={{position: "absolute", left: 82, top: 815, color: COLORS.white, fontSize: 35, fontWeight: 650}}>
        City Vision görür. GBSoft platformu işi bitirir.
      </Reveal>
      <FooterLine text="DEĞERLER PİLOT HEDEFİDİR · SAHADA BİRLİKTE KALİBRE EDİLİR" />
    </AbsoluteFill>
  );
};
