import {Img, interpolate, staticFile, useCurrentFrame} from "remotion";
import {BrandRow, Eyebrow, FooterNote, Headline, ProgressRail, Stage, SubLine, TechGrid} from "../chrome";
import {C, FONT, G, clamp, ease, inAt, monoLabel} from "../theme";
import {VO, localOf} from "../timing";

/**
 * Anlatım: "Aynı sorun tekrarlı uçuşlarda yeniden görüldüğünde kayıtlar
 * tek bir olay altında birleştiriliyor." + "Bu sayede aynı sorun için birden
 * fazla iş emri oluşturulmuyor."
 */

const NO_DUP_AT = localOf(4, VO.s08);

const OBS = [
  {src: "gorseller/06-yol-hasari-gozlem-01.png", source: "UÇUŞ-001", time: "08:41", score: "%81"},
  {src: "gorseller/07-yol-hasari-gozlem-02.png", source: "UÇUŞ-002", time: "11:06", score: "%88"},
  {src: "gorseller/08-yol-hasari-gozlem-03.png", source: "UÇUŞ-003", time: "16:22", score: "%93"},
];

const THUMB = 268;
const THUMB_TOP = 592;
const CARD_TOP = 1058;

export const S05Fusion: React.FC = () => {
  const frame = useCurrentFrame();
  const merge = interpolate(frame, [96, 138], [0, 1], {...clamp, easing: ease});
  const conf = Math.round(interpolate(frame, [124, 172], [0, 97], {...clamp, easing: ease}));
  const dup = inAt(frame, NO_DUP_AT, 20);

  return (
    <Stage>
      <TechGrid opacity={0.85} />
      <BrandRow section="05 / 08" />
      <ProgressRail index={4} />

      <Eyebrow color={C.ok}>MÜKERRER KAYIT ÖNLEME</Eyebrow>
      <Headline lines={["Üç ayrı uçuş,", {t: "tek olay.", c: C.ok}]} size={82} delay={5} />
      <SubLine top={486} delay={20} width={850}>
        Aynı noktada tekrar görülen sorun yeni bir kayıt açmaz; mevcut olayın güvenini yükseltir.
      </SubLine>

      {OBS.map((o, i) => {
        const x = G.margin + i * (THUMB + 50);
        const p = inAt(frame, 28 + i * 12, 22);
        return (
          <div
            key={o.src}
            style={{position: "absolute", left: x, top: THUMB_TOP, width: THUMB, opacity: p, transform: `translateY(${(1 - p) * 24}px)`}}
          >
            <div style={{width: THUMB, height: THUMB, overflow: "hidden", border: `1px solid ${C.lineStrong}`}}>
              <Img src={staticFile(o.src)} style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: "50% 58%"}} />
            </div>
            <div style={{marginTop: 14, ...monoLabel(15, C.dim)}}>GÖZLEM 0{i + 1}</div>
            <div style={{marginTop: 9, fontFamily: FONT.mono, fontSize: 17, color: C.faint, lineHeight: 1.55}}>
              {o.source}
              <br />
              {o.time} · {o.score}
            </div>
          </div>
        );
      })}

      <svg viewBox={`0 0 ${G.W} ${G.H}`} style={{position: "absolute", inset: 0, width: "100%", height: "100%", zIndex: 25}}>
        {OBS.map((_, i) => {
          const sx = G.margin + i * (THUMB + 50) + THUMB / 2;
          const sy = 958;
          const ey = CARD_TOP - 4;
          const mx = G.W / 2;
          return (
            <path
              key={i}
              d={`M ${sx} ${sy} C ${sx} ${sy + 50}, ${mx + (sx - mx) * 0.22} ${ey - 44}, ${mx} ${ey}`}
              fill="none"
              stroke={C.accent}
              strokeWidth="2"
              strokeOpacity="0.72"
              pathLength="1"
              strokeDasharray="1"
              strokeDashoffset={1 - inAt(frame, 84 + i * 6, 26)}
            />
          );
        })}
        <circle cx={G.W / 2} cy={CARD_TOP - 4} r={5 + (1 - merge) * 14} fill={C.ok} opacity={merge} />
      </svg>

      <div
        style={{
          position: "absolute",
          left: G.margin,
          top: CARD_TOP,
          width: 904,
          backgroundColor: C.panelSolid,
          border: `1px solid ${C.line}`,
          borderTop: `2px solid ${C.ok}`,
          opacity: merge,
          transform: `translateY(${(1 - merge) * 24}px)`,
          zIndex: 30,
        }}
      >
        <div style={{padding: "24px 32px 0", display: "flex", justifyContent: "space-between", alignItems: "center"}}>
          <span style={monoLabel(15, C.ok)}>BİRLEŞTİRİLMİŞ OLAY</span>
          <span style={{fontFamily: FONT.mono, fontSize: 20, color: C.dim, letterSpacing: 1.4}}>POT-00417</span>
        </div>
        <div style={{padding: "16px 32px 0", fontSize: 42, fontWeight: 700, letterSpacing: -1.2, color: C.text}}>Yol yüzey hasarı</div>
        <div style={{padding: "10px 32px 0", ...monoLabel(17, C.dim)}}>ATATÜRK BUL. 41. SK · 39.90861 N / 41.26722 E</div>

        <div style={{padding: "28px 32px 0"}}>
          <div style={{display: "flex", justifyContent: "space-between", alignItems: "baseline"}}>
            <span style={monoLabel(15, C.faint)}>BİRLEŞİK GÜVEN SKORU</span>
            <span style={{fontFamily: FONT.mono, fontSize: 38, fontWeight: 600, color: C.ok}}>%{conf}</span>
          </div>
          <div style={{marginTop: 14, height: 8, backgroundColor: "rgba(150,182,220,.14)", position: "relative"}}>
            <div style={{position: "absolute", inset: 0, width: `${conf}%`, backgroundColor: C.ok}} />
            <div style={{position: "absolute", left: "80%", top: -6, width: 2, height: 20, backgroundColor: C.warn}} />
          </div>
          <div style={{marginTop: 12, display: "flex", justifyContent: "space-between", ...monoLabel(14, C.faint)}}>
            <span>%0</span>
            <span style={{color: C.warn}}>EŞİK %80</span>
            <span>%100</span>
          </div>
        </div>

        <div style={{margin: "26px 32px 0", height: 1, backgroundColor: C.line}} />
        <div style={{padding: "20px 32px 26px", display: "flex", justifyContent: "space-between", alignItems: "center"}}>
          <span style={monoLabel(16, C.dim)}>KAYNAK: 3 UÇUŞ · 3 GÖZLEM</span>
          <span style={{...monoLabel(16, C.ok)}}>TEK OLAY</span>
        </div>
      </div>

      {/* İkinci cümle: mükerrer iş emri yok */}
      <div
        style={{
          position: "absolute",
          left: G.margin,
          top: 1524,
          width: 904,
          height: 96,
          backgroundColor: "rgba(47,207,155,.08)",
          border: `1px solid ${C.ok}55`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 30px",
          opacity: dup,
          transform: `translateY(${(1 - dup) * 18}px)`,
          zIndex: 35,
        }}
      >
        <span style={{fontSize: 30, fontWeight: 600, color: C.text}}>Aynı sorun için ikinci iş emri açılmaz.</span>
        <span style={{fontFamily: FONT.mono, fontSize: 34, fontWeight: 600, color: C.ok}}>3 → 1</span>
      </div>

      <FooterNote text="EŞİK ALTINDAKİ KAYIT PERSONEL İNCELEMESİNE DÜŞER" delay={NO_DUP_AT + 26} />
    </Stage>
  );
};
