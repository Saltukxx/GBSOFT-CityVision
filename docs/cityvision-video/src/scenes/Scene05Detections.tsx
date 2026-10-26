import {AbsoluteFill, CanvasImage, Easing, interpolate, staticFile, useCurrentFrame} from "remotion";
import {Brand, COLORS, DetectionBox, FooterLine, Reveal} from "../shared";

const items = [
  {src: "assets/pothole_close.jpg", title: "Yol çukuru ve yüzey hasarı", score: "%96", color: COLORS.red},
  {src: "assets/waste.jpg", title: "Taşmış konteyner ve atık", score: "%91", color: COLORS.yellow},
  {src: "assets/road_wide.jpg", title: "Geniş yol yüzeyi bozulması", score: "%86", color: COLORS.violet},
  {src: "assets/detect.jpg", title: "Kaçak döküm ve moloz", score: "%88", color: COLORS.cyan},
];

export const Scene05Detections: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{backgroundColor: COLORS.bg, fontFamily: "Inter, Arial, sans-serif"}}>
      <Brand section="TESPİT KAPSAMI" />
      <Reveal delay={5} style={{position: "absolute", left: 82, top: 160}}>
        <div style={{fontSize: 82, color: COLORS.white, fontWeight: 780, letterSpacing: -3}}>Şehirde neleri görüyor?</div>
        <div style={{fontSize: 32, color: COLORS.muted, marginTop: 15}}>İlk pilotta ölçülebilir, kanıtlı ve konumlandırılmış olaylar.</div>
      </Reveal>

      <div style={{position: "absolute", left: 82, right: 82, top: 350, bottom: 110, display: "grid", gridTemplateColumns: "1fr 1fr", gridTemplateRows: "1fr 1fr", gap: 22}}>
        {items.map((item, index) => {
          const delay = 45 + index * 24;
          return (
            <div
              key={item.title}
              style={{
                position: "relative",
                overflow: "hidden",
                borderRadius: 22,
                border: `2px solid ${item.color}55`,
                opacity: interpolate(frame, [delay, delay + 24], [0, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16,1,.3,1)}),
                scale: interpolate(frame, [delay, delay + 30], [0.94, 1], {extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.bezier(.16,1,.3,1), output: "perceptual-scale"}),
              }}
            >
              <CanvasImage src={staticFile(item.src)} style={{width: "100%", height: "100%", objectFit: "cover", scale: interpolate(frame, [delay, 420], [1, 1.08], {extrapolateLeft: "clamp", extrapolateRight: "clamp"})}} />
              <AbsoluteFill style={{background: "linear-gradient(180deg, transparent 38%, rgba(3,7,18,.97))"}} />
              <div style={{position: "absolute", left: 28, bottom: 24, right: 28, display: "flex", justifyContent: "space-between", alignItems: "end"}}>
                <div style={{color: COLORS.white, fontSize: 30, fontWeight: 820}}>{item.title}</div>
                <div style={{color: item.color, fontSize: 34, fontWeight: 900}}>{item.score}</div>
              </div>
              {index === 0 ? <DetectionBox label="YÜZEY HASARI" confidence={item.score} top={90} left={220} width={250} height={120} color={item.color} delay={delay + 25} /> : null}
              {index === 2 ? <DetectionBox label="YÜZEY BOZULMASI" confidence={item.score} top={105} left={330} width={290} height={135} color={item.color} delay={delay + 25} /> : null}
            </div>
          );
        })}
      </div>
      <FooterLine text="ADAY OLAY · GÜVEN SKORU · KONUM · KANIT" />
    </AbsoluteFill>
  );
};
