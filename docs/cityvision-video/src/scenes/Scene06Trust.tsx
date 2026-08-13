import {AbsoluteFill, CanvasImage, Easing, interpolate, staticFile, useCurrentFrame} from "remotion";
import {Brand, COLORS, FooterLine, NoiseGrid, Reveal} from "../shared";

const observations = ["assets/obs_road1.jpg", "assets/obs_road2.jpg", "assets/obs_road3.jpg"];

export const Scene06Trust: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.bg, fontFamily: "Inter, Arial, sans-serif"}}>
      <NoiseGrid />
      <Brand section="GÜVEN MOTORU" />
      <Reveal delay={5} style={{position: "absolute", left: 82, top: 160}}>
        <div style={{fontSize: 80, lineHeight: 1, color: COLORS.white, fontWeight: 780, letterSpacing: -3}}>Aynı çukur için<br/><span style={{color: COLORS.cyan}}>üç iş emri açılmaz.</span></div>
      </Reveal>

      <div style={{position: "absolute", left: 82, top: 470, display: "flex", gap: 22}}>
        {observations.map((src, index) => (
          <div
            key={src}
            style={{
              width: 310,
              height: 245,
              borderRadius: 18,
              overflow: "hidden",
              border: `2px solid ${COLORS.cyan}66`,
              opacity: interpolate(frame, [45 + index * 28, 70 + index * 28], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp"}),
              translate: interpolate(frame, [45 + index * 28, 78 + index * 28], ["0px 55px", "0px 0px"], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16,1,.3,1)}),
            }}
          >
            <CanvasImage src={staticFile(src)} style={{width: "100%", height: "100%", objectFit: "cover"}} />
            <div style={{position: "absolute", left: 16, bottom: 14, padding: "7px 12px", borderRadius: 8, backgroundColor: "rgba(3,7,18,.86)", color: COLORS.white, fontWeight: 800, fontSize: 18}}>GÖZLEM {index + 1}</div>
          </div>
        ))}
      </div>

      {[0, 1, 2].map((i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            left: 392 + i * 332,
            top: 590,
            width: interpolate(frame, [130 + i * 18, 190 + i * 18], [0, 330 - i * 35], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16,1,.3,1)}),
            height: 3,
            backgroundColor: COLORS.cyan,
            rotate: `${-16 + i * 16}deg`,
            transformOrigin: "left center",
            boxShadow: `0 0 18px ${COLORS.cyan}`,
          }}
        />
      ))}

      <div
        style={{
          position: "absolute",
          right: 82,
          top: 390,
          width: 650,
          height: 410,
          borderRadius: 28,
          border: `3px solid ${COLORS.green}`,
          background: "linear-gradient(145deg, rgba(15,37,58,.98), rgba(5,13,28,.98))",
          boxShadow: `0 0 70px ${COLORS.green}25`,
          opacity: interpolate(frame, [175, 215], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16,1,.3,1)}),
          scale: interpolate(frame, [175, 220], [0.85, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16,1,.3,1), output: "perceptual-scale"}),
          padding: "50px 55px",
        }}
      >
        <div style={{color: COLORS.green, fontSize: 21, fontWeight: 900, letterSpacing: 4}}>TEK ŞEHİR OLAYI</div>
        <div style={{color: COLORS.white, fontSize: 52, fontWeight: 850, marginTop: 28}}>POT-18222</div>
        <div style={{display: "flex", gap: 52, marginTop: 42}}>
          <div><div style={{color: COLORS.muted, fontSize: 19}}>GÖZLEM</div><div style={{color: COLORS.white, fontSize: 44, fontWeight: 880}}>3 araç · 4 kez</div></div>
          <div><div style={{color: COLORS.muted, fontSize: 19}}>GÜVEN</div><div style={{color: COLORS.green, fontSize: 52, fontWeight: 900}}>%97</div></div>
        </div>
        <div style={{marginTop: 34, color: COLORS.muted, fontSize: 25}}>Emin değilse iş emri açmaz.</div>
      </div>
      <FooterLine text="TEKRAR GÖZLEM · TEK KAYIT · DAHA YÜKSEK GÜVEN" />
    </AbsoluteFill>
  );
};
