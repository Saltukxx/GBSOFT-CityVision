import {useCurrentFrame} from "remotion";
import {BrandRow, Eyebrow, FooterNote, Headline, ProgressRail, Stage, SubLine, TechGrid} from "../chrome";
import {CoverageChart} from "../graphics";
import {C, FONT, G, inAt, monoLabel} from "../theme";
import {VO, localOf} from "../timing";

/**
 * Anlatım: "Mevcut araçlar görevlerini sürdürürken şehir de takip ediliyor." +
 * "Sorunlar büyümeden tespit ediliyor ve ekipler daha hızlı harekete geçiyor."
 */

const EARLY_AT = localOf(6, VO.s12);

const KPIS: [string, string, string][] = [
  ["AYNI GÜN", "tespit hedefi", C.accent],
  ["%90", "haftalık yol ağı kapsaması", C.ok],
  ["< %10", "mükerrer görev oranı", C.warn],
];

export const S07Impact: React.FC = () => {
  const frame = useCurrentFrame();
  const early = inAt(frame, EARLY_AT, 20);

  return (
    <Stage>
      <TechGrid />
      <BrandRow section="07 / 08" />
      <ProgressRail index={6} />

      <Eyebrow>PİLOT HEDEFLERİ</Eyebrow>
      <Headline lines={["Araçlar işini yapar,", {t: "şehir taranır.", c: C.accent}]} size={72} delay={5} />
      <SubLine top={452} delay={18} width={860}>
        Güzergâh tekrar ettikçe kapsama büyür; sorun büyümeden kayda geçer.
      </SubLine>

      <div style={{position: "absolute", left: G.margin, top: 558, width: 904}}>
        <CoverageChart w={904} h={600} delay={22} />
      </div>

      {/* İkinci cümle: erken tespit + hızlı müdahale */}
      <div
        style={{
          position: "absolute",
          left: G.margin,
          top: 1198,
          width: 904,
          opacity: early,
          transform: `translateY(${(1 - early) * 20}px)`,
        }}
      >
        <div style={{fontSize: 32, fontWeight: 600, color: C.text, letterSpacing: -0.5}}>
          Sorun büyümeden tespit edilir, ekip daha erken harekete geçer.
        </div>
        <div style={{marginTop: 28, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14}}>
          {KPIS.map(([v, l, color], i) => (
            <div
              key={l}
              style={{
                padding: "26px 18px 28px",
                backgroundColor: C.panel,
                border: `1px solid ${C.line}`,
                borderTop: `2px solid ${color}`,
                opacity: inAt(frame, EARLY_AT + 12 + i * 9, 16),
              }}
            >
              <div
                style={{
                  fontFamily: FONT.mono,
                  fontSize: v.length > 5 ? 34 : 46,
                  fontWeight: 600,
                  color,
                  lineHeight: 1.1,
                  minHeight: 52,
                  display: "flex",
                  alignItems: "center",
                }}
              >
                {v}
              </div>
              <div style={{...monoLabel(14, C.faint), marginTop: 14, lineHeight: 1.5}}>{l}</div>
            </div>
          ))}
        </div>
      </div>

      <FooterNote text="DEĞERLER PİLOT HEDEFİDİR · SAHADA BİRLİKTE KALİBRE EDİLİR" delay={EARLY_AT + 40} />
    </Stage>
  );
};
