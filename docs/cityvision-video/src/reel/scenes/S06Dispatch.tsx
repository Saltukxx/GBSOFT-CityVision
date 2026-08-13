import {useCurrentFrame} from "remotion";
import {BrandRow, Eyebrow, FooterNote, Headline, ProgressRail, Stage, SubLine, TechGrid} from "../chrome";
import {C, FONT, G, inAt, monoLabel} from "../theme";
import {VO, localOf} from "../timing";

/**
 * Anlatım: "Belediye ekipleri doğrudan doğru noktaya yönlendiriliyor." +
 * "Bunun için yeni bir ekip kurulmasına gerek kalmıyor."
 */

const NO_NEW_TEAM_AT = localOf(5, VO.s10);

const FIELDS: [string, string, string?][] = [
  ["olay", "POT-00417 · yol yüzey hasarı"],
  ["konum", "Atatürk Bul. 41. Sk."],
  ["birim", "Fen İşleri Müdürlüğü"],
  ["ekip", "YOL-03 (mevcut ekip)"],
  ["öncelik", "YÜKSEK", C.warn],
  ["hedef süre", "24 saat"],
  ["kanıt", "kare + konum eklendi"],
];

const TRACK = ["OLAY AÇILDI", "EKİBE ATANDI", "EKİP YOLDA"];

const STATS: [string, string][] = [
  ["0", "EK PERSONEL"],
  ["0", "YENİ ARAÇ"],
  ["1", "İŞ EMRİ"],
];

export const S06Dispatch: React.FC = () => {
  const frame = useCurrentFrame();
  const noTeam = inAt(frame, NO_NEW_TEAM_AT, 20);

  return (
    <Stage>
      <TechGrid />
      <BrandRow section="06 / 08" />
      <ProgressRail index={5} />

      <Eyebrow>İŞ EMRİ VE YÖNLENDİRME</Eyebrow>
      <Headline lines={["Ekip doğrudan", {t: "doğru noktaya.", c: C.accent}]} size={76} delay={5} />
      <SubLine top={470} delay={18} width={840}>
        Olay, GBSoft Belediye Operasyon Platformunda ilgili birime ve sahadaki ekibe düşer.
      </SubLine>

      {/* İş emri kartı */}
      <div
        style={{
          position: "absolute",
          left: G.margin,
          top: 566,
          width: 904,
          backgroundColor: C.panelSolid,
          border: `1px solid ${C.line}`,
          borderTop: `2px solid ${C.accent}`,
          opacity: inAt(frame, 22, 22),
          transform: `translateY(${(1 - inAt(frame, 22, 22)) * 24}px)`,
        }}
      >
        <div
          style={{
            padding: "24px 32px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            borderBottom: `1px solid ${C.line}`,
          }}
        >
          <span style={monoLabel(15, C.accent)}>İŞ EMRİ</span>
          <span style={{fontFamily: FONT.mono, fontSize: 20, color: C.dim, letterSpacing: 1.4}}>WO-2026-0417</span>
        </div>

        <div style={{padding: "10px 32px 22px"}}>
          {FIELDS.map(([k, v, color], i) => (
            <div
              key={k}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "14px 0",
                borderBottom: i === FIELDS.length - 1 ? "none" : "1px solid rgba(150,182,220,.08)",
                opacity: inAt(frame, 34 + i * 6, 16),
              }}
            >
              <span style={{fontFamily: FONT.mono, fontSize: 19, color: C.faint, letterSpacing: 1.2}}>{k}</span>
              <span style={{fontFamily: FONT.mono, fontSize: 21, color: color ?? C.text, letterSpacing: 0.8}}>{v}</span>
            </div>
          ))}
        </div>

        {/* Durum izleyici */}
        <div style={{padding: "0 32px 30px"}}>
          <div style={{display: "flex", alignItems: "center", gap: 0}}>
            {TRACK.map((label, i) => {
              const p = inAt(frame, 62 + i * 14, 16);
              return (
                <div key={label} style={{flex: 1, display: "flex", alignItems: "center"}}>
                  <div
                    style={{
                      width: 15,
                      height: 15,
                      borderRadius: 8,
                      flexShrink: 0,
                      backgroundColor: p > 0.5 ? C.ok : "transparent",
                      border: `2px solid ${p > 0.5 ? C.ok : C.line}`,
                    }}
                  />
                  {i < TRACK.length - 1 ? (
                    <div style={{flex: 1, height: 2, backgroundColor: C.line, position: "relative", marginLeft: 6, marginRight: 6}}>
                      <div style={{position: "absolute", inset: 0, width: `${inAt(frame, 68 + i * 14, 14) * 100}%`, backgroundColor: C.ok}} />
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
          <div style={{display: "flex", marginTop: 14}}>
            {TRACK.map((label, i) => (
              <div
                key={label}
                style={{
                  flex: 1,
                  textAlign: i === 0 ? "left" : i === TRACK.length - 1 ? "right" : "center",
                  ...monoLabel(14, inAt(frame, 62 + i * 14, 16) > 0.5 ? C.ok : C.faint),
                }}
              >
                {label}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* İkinci cümle: yeni ekip gerekmiyor */}
      <div style={{position: "absolute", left: G.margin, top: 1264, width: 904, opacity: noTeam, transform: `translateY(${(1 - noTeam) * 20}px)`}}>
        <div style={{fontSize: 34, fontWeight: 600, color: C.text, letterSpacing: -0.6}}>
          Bunun için yeni bir ekip kurmak gerekmiyor.
        </div>
        <div style={{marginTop: 28, display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14}}>
          {STATS.map(([v, l], i) => (
            <div
              key={l}
              style={{
                padding: "30px 20px 32px",
                backgroundColor: C.panel,
                border: `1px solid ${C.line}`,
                borderTop: `2px solid ${i === 2 ? C.ok : C.accent}`,
                opacity: inAt(frame, NO_NEW_TEAM_AT + 12 + i * 8, 16),
              }}
            >
              <div style={{fontFamily: FONT.mono, fontSize: 64, fontWeight: 600, color: i === 2 ? C.ok : C.accent, lineHeight: 1}}>{v}</div>
              <div style={{...monoLabel(14, C.faint), marginTop: 16}}>{l}</div>
            </div>
          ))}
        </div>
      </div>

      <FooterNote text="MEVCUT FİLO · MEVCUT EKİP · TEK EKRAN" delay={NO_NEW_TEAM_AT + 34} />
    </Stage>
  );
};
