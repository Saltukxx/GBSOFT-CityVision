import {interpolate, useCurrentFrame} from "remotion";
import {BrandRow, Eyebrow, FooterNote, Headline, ProgressRail, Stage, TechGrid} from "../chrome";
import {C, FONT, G, clamp, ease, inAt, monoLabel} from "../theme";
import {VO, localOf} from "../timing";

/**
 * Anlatım: "Uçuş tamamlandığında görüntüler merkezi sistemde analiz ediliyor." +
 * "Tespit edilen her sorun konumu ve görüntüsüyle birlikte sisteme kaydediliyor."
 */

const RECORD_AT = localOf(3, VO.s06); // ikinci cümlede olay kaydı açılır

const STEPS = [
  {n: "01", t: "UÇ", d: "Drone tanımlı koridoru standart profille görüntüler.", tag: "PLANLI", c: C.accent},
  {n: "02", t: "ANALİZ ET", d: "Uçuş görüntüsü merkezi GPU görevinde işlenir.", tag: "ASENKRON", c: C.accent},
  {n: "03", t: "KAYDA GEÇ", d: "Olay tipi, tahmini konum ve kanıt karesi indekse yazılır.", tag: "OTOMATİK", c: C.ok},
];

const RECORD: [string, string][] = [
  ["tip", "yol_yuzey_hasari"],
  ["konum", "39.90861 N / 41.26722 E"],
  ["zaman", "13.08.2026 · 08:41"],
  ["drone", "DJI-DOCK-01 / AERIAL"],
  ["güven", "%94"],
  ["kanıt", "kare + 6 sn video"],
];

const TOP = 500;
const STEP_H = 176;
const GAP = 18;
const RAIL_X = G.margin + 33;

export const S04Pipeline: React.FC = () => {
  const frame = useCurrentFrame();
  const railTop = TOP + 55;
  const railBottom = TOP + 2 * (STEP_H + GAP) + 55;
  const railDraw = interpolate(frame, [22, 106], [0, 1], {...clamp, easing: ease});
  const rec = inAt(frame, RECORD_AT, 24);

  return (
    <Stage>
      <TechGrid />
      <BrandRow section="04 / 08" />
      <ProgressRail index={3} />

      <Eyebrow>MERKEZİ GÖRÜNTÜ ANALİZİ</Eyebrow>
      <Headline lines={["Uçuş tamamlanır,", {t: "olaylar haritaya düşer.", c: C.ok}]} size={62} delay={5} />

      <svg viewBox={`0 0 ${G.W} ${G.H}`} style={{position: "absolute", inset: 0, width: "100%", height: "100%", zIndex: 20}}>
        <line x1={RAIL_X} y1={railTop} x2={RAIL_X} y2={railBottom} stroke={C.line} strokeWidth="2" />
        <line x1={RAIL_X} y1={railTop} x2={RAIL_X} y2={railTop + (railBottom - railTop) * railDraw} stroke={C.accent} strokeWidth="2" />
      </svg>

      {STEPS.map((step, i) => {
        const top = TOP + i * (STEP_H + GAP);
        const p = inAt(frame, 18 + i * 20, 22);
        return (
          <div key={step.n} style={{position: "absolute", left: G.margin, top, width: 904, height: STEP_H, zIndex: 30}}>
            <div
              style={{
                position: "absolute",
                left: 0,
                top: 22,
                width: 66,
                height: 66,
                borderRadius: 33,
                backgroundColor: C.ink,
                border: `2px solid ${p > 0.4 ? step.c : C.line}`,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                opacity: Math.min(1, p * 1.6),
              }}
            >
              <span style={{fontFamily: FONT.mono, fontSize: 21, fontWeight: 600, color: p > 0.4 ? step.c : C.faint}}>{step.n}</span>
            </div>

            <div
              style={{
                position: "absolute",
                left: 108,
                top: 0,
                width: 796,
                height: STEP_H,
                backgroundColor: C.panel,
                border: `1px solid ${C.line}`,
                borderLeft: `2px solid ${step.c}`,
                padding: "26px 30px",
                opacity: p,
                transform: `translateX(${(1 - p) * 28}px)`,
              }}
            >
              <div style={{display: "flex", justifyContent: "space-between", alignItems: "flex-start"}}>
                <div style={{fontSize: 44, fontWeight: 700, letterSpacing: -1.2, color: C.text, lineHeight: 1}}>{step.t}</div>
                <div style={{...monoLabel(13, step.c), padding: "6px 11px", border: `1px solid ${step.c}55`}}>{step.tag}</div>
              </div>
              <div style={{marginTop: 18, fontSize: 23, lineHeight: 1.38, color: C.dim, maxWidth: 640}}>{step.d}</div>
            </div>
          </div>
        );
      })}

      {/* Sisteme düşen olay kaydı */}
      <div
        style={{
          position: "absolute",
          left: G.margin,
          top: 1108,
          width: 904,
          backgroundColor: C.panelSolid,
          border: `1px solid ${C.line}`,
          borderTop: `2px solid ${C.ok}`,
          opacity: rec,
          transform: `translateY(${(1 - rec) * 24}px)`,
          zIndex: 30,
        }}
      >
        <div
          style={{
            padding: "22px 30px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            borderBottom: `1px solid ${C.line}`,
          }}
        >
          <span style={monoLabel(15, C.ok)}>SİSTEME DÜŞEN OLAY KAYDI</span>
          <span style={{fontFamily: FONT.mono, fontSize: 20, color: C.dim, letterSpacing: 1.4}}>POT-00417</span>
        </div>
        <div style={{padding: "8px 30px 20px"}}>
          {RECORD.map(([k, v], i) => (
            <div
              key={k}
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                padding: "13px 0",
                borderBottom: i === RECORD.length - 1 ? "none" : `1px solid rgba(150,182,220,.08)`,
                opacity: inAt(frame, RECORD_AT + 12 + i * 5, 14),
              }}
            >
              <span style={{fontFamily: FONT.mono, fontSize: 19, color: C.faint, letterSpacing: 1.2}}>{k}</span>
              <span style={{fontFamily: FONT.mono, fontSize: 21, color: k === "güven" ? C.ok : C.text, letterSpacing: 0.8}}>{v}</span>
            </div>
          ))}
        </div>
      </div>

      <FooterNote text="HAM VİDEO KORUMALI DEPOYA · DASHBOARD'A YALNIZCA OLAY VE KANIT" delay={RECORD_AT + 42} />
    </Stage>
  );
};
