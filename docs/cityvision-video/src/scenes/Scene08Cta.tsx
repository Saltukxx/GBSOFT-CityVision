import {AbsoluteFill, Easing, interpolate, useCurrentFrame} from "remotion";
import {Brand, COLORS, ImageBackdrop, Reveal} from "../shared";

export const Scene08Cta: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{fontFamily: "Inter, Arial, sans-serif"}}>
      <ImageBackdrop src="assets/closing.jpg" darkness={0.56} scaleTo={1.07} x="65%" />
      <Brand section="SIRADAKİ ADIM" />
      <div style={{position: "absolute", left: 82, top: 220}}>
        <Reveal delay={5}>
          <div style={{fontSize: 94, lineHeight: 0.98, color: COLORS.white, fontWeight: 790, letterSpacing: -4, maxWidth: 1000}}>
            Tek bir otobüsle başlayalım.
          </div>
        </Reveal>
        <Reveal delay={38}>
          <div style={{fontSize: 60, lineHeight: 1.08, color: COLORS.cyan, fontWeight: 760, marginTop: 34, maxWidth: 900}}>
            30 günde gerçek sonucu birlikte görelim.
          </div>
        </Reveal>
        <Reveal delay={80} style={{display: "flex", gap: 22, marginTop: 52}}>
          {["1 GÜZERGÂH", "1–2 ARAÇ", "30 GÜN CANLI PİLOT"].map((item) => (
            <div key={item} style={{padding: "20px 25px", borderRadius: 14, backgroundColor: "rgba(7,18,38,.78)", border: `2px solid ${COLORS.cyan}77`, color: COLORS.white, fontSize: 23, fontWeight: 840}}>{item}</div>
          ))}
        </Reveal>
      </div>

      <div
        style={{
          position: "absolute",
          left: 82,
          right: 82,
          bottom: 70,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          opacity: interpolate(frame, [110, 145], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16,1,.3,1)}),
        }}
      >
        <div style={{color: COLORS.white, fontSize: 26, fontWeight: 720}}>gbsoftt.com</div>
        <div style={{display: "flex", gap: 34, color: COLORS.white, fontSize: 24, fontWeight: 650}}>
          <span>info@gbsoftt.com</span><span>0 536 840 92 36</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
