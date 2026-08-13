import {useCurrentFrame} from "remotion";
import {Backdrop, BrandRow, Eyebrow, FooterNote, Headline, Panel, ProgressRail, Stage} from "../chrome";
import {Annotation, RouteMap} from "../graphics";
import {C, FONT, G, inAt, monoLabel} from "../theme";

/** Anlatım: "Mevcut araçlara yerleştirilen kameralar yolculuk sırasında çevreyi izliyor." */

const SPECS: [string, string, string][] = [
  ["1080p · 15 fps", "ARAÇ ÜSTÜ KAMERA", C.accent],
  ["12.4 km", "GÜNLÜK GÜZERGÂH", C.accent],
  ["MASKELİ", "YÜZ VE PLAKA", C.ok],
];

const ramp = (frame: number, a: number, b: number) => Math.min(1, Math.max(0, (frame - a) / (b - a)));

export const S03Sensor: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <Stage>
      <Backdrop src="gorseller/05-mobil-sehir-sensoru-otobus.png" from={1.02} to={1.06} topScrim={0.91} bottomScrim={0.94} />
      <BrandRow section="03 / 08" />
      <ProgressRail index={2} />

      <Eyebrow>MOBİL ŞEHİR SENSÖRÜ</Eyebrow>
      <Headline lines={["Mevcut araçlara", {t: "bir kamera.", c: C.accent}]} size={80} delay={5} />

      <Panel delay={18} style={{left: G.margin, top: 570, width: 904, height: 364}}>
        <div
          style={{
            height: 44,
            padding: "0 14px",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            borderBottom: `1px solid ${C.line}`,
          }}
        >
          <span style={monoLabel(15, C.text)}>CANLI GÜZERGÂH · HAT 25</span>
          <span style={monoLabel(15, C.accent)}>{(ramp(frame, 26, 112) * 12.4).toFixed(1)} KM TARANDI</span>
        </div>
        <div style={{padding: 12}}>
          <RouteMap w={880} h={292} delay={26} />
        </div>
      </Panel>

      <Annotation color={C.accent} delay={48} box={{x: 296, y: 1020, w: 516, h: 276}} label="MOBİL SENSÖR" score="AKTİF" />

      <div
        style={{
          position: "absolute",
          left: G.margin,
          top: 1404,
          width: 904,
          display: "grid",
          gridTemplateColumns: "repeat(3, 1fr)",
          gap: 14,
        }}
      >
        {SPECS.map(([value, label, color], i) => {
          const p = inAt(frame, 76 + i * 9, 20);
          return (
            <div
              key={label}
              style={{
                padding: "20px 16px 22px",
                backgroundColor: C.panel,
                border: `1px solid ${C.line}`,
                borderTop: `2px solid ${color}`,
                opacity: p,
                transform: `translateY(${(1 - p) * 22}px)`,
              }}
            >
              <div style={{fontFamily: FONT.mono, fontSize: 23, fontWeight: 600, color: C.text, letterSpacing: 0.4}}>{value}</div>
              <div style={{...monoLabel(14, C.faint), marginTop: 10}}>{label}</div>
            </div>
          );
        })}
      </div>

      <FooterNote text="YENİ DEVRİYE EKİBİ YOK · YENİ GÜZERGÂH YOK" delay={104} />
    </Stage>
  );
};
