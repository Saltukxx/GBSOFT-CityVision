import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame} from "remotion";
import {BrandRow, FooterNote, ProgressRail, Stage} from "../chrome";
import {Annotation, type Box} from "../graphics";
import {C, FONT, G, clamp, ease, inAt, monoLabel} from "../theme";

/**
 * Anlatım: "…yol hasarlarını, taşan konteynerleri ve kaçak döküm alanlarını
 * tespit ediyor." Üç sınıf, üç tam kadraj tespit.
 */

const SLOT = 68;

type Item = {
  src: string;
  pos: string;
  title: string;
  score: string;
  color: string;
  label: string;
  meta: string;
  box: Box;
  extra?: Box[];
};

const ITEMS: Item[] = [
  {
    src: "gorseller/02-yol-yuzey-hasari-yakin.png",
    pos: "50% 50%",
    title: "YOL ÇUKURU",
    score: "%96",
    color: C.alert,
    label: "BOZULMUŞ ASFALT",
    meta: "POT-02 · ALAN 1.8 m² · ŞİDDET: ORTA",
    box: {x: 190, y: 872, w: 740, h: 462},
  },
  {
    src: "gorseller/03-tasmis-atik-alani.png",
    pos: "50% 52%",
    title: "TAŞMIŞ ATIK",
    score: "%91",
    color: C.warn,
    label: "TAŞMA BÖLGESİ",
    meta: "WST-01 · 3 KONTEYNER · ÇEVREYE YAYILIM",
    box: {x: 96, y: 848, w: 890, h: 460},
  },
  {
    src: "gorseller/04-yol-isgali-ve-trafik.png",
    pos: "50% 56%",
    title: "KAÇAK DÖKÜM",
    score: "%86",
    color: C.accent,
    label: "MOLOZ ALANI",
    meta: "WST-08 · ALAN 6.4 m² · İNCELEME GEREKLİ",
    box: {x: 392, y: 944, w: 620, h: 396},
    extra: [
      {x: 104, y: 862, w: 316, h: 296},
      {x: 330, y: 770, w: 232, h: 202},
    ],
  },
];

export const S02Detections: React.FC = () => {
  const frame = useCurrentFrame();
  const active = Math.min(ITEMS.length - 1, Math.floor(frame / SLOT));
  const item = ITEMS[active];
  const local = frame - active * SLOT;
  const fade = interpolate(local, [0, 9, SLOT - 9, SLOT], [0, 1, 1, 0], {...clamp, easing: ease});
  const isLast = active === ITEMS.length - 1;

  return (
    <Stage>
      <AbsoluteFill style={{overflow: "hidden"}}>
        <Img
          key={item.src}
          src={staticFile(item.src)}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            objectPosition: item.pos,
            opacity: isLast ? 1 : fade,
            transform: `scale(${interpolate(local, [0, SLOT], [1.01, 1.06], clamp)})`,
          }}
        />
        <AbsoluteFill
          style={{
            background:
              "linear-gradient(180deg, rgba(5,7,14,.94) 0%, rgba(5,7,14,.58) 19%, rgba(5,7,14,.06) 39%," +
              " rgba(5,7,14,.40) 70%, rgba(5,7,14,.95) 100%)",
          }}
        />
      </AbsoluteFill>

      <BrandRow section="02 / 08" />
      <ProgressRail index={1} />

      <div style={{position: "absolute", left: G.margin, top: 252, zIndex: 50, opacity: isLast ? 1 : fade}}>
        <div style={monoLabel(16, item.color)}>TESPİT SINIFI · 0{active + 1} / 03</div>
        <div
          style={{
            marginTop: 20,
            fontSize: 98,
            lineHeight: 0.94,
            fontWeight: 700,
            letterSpacing: -3.6,
            color: C.text,
            transform: `translateY(${(1 - inAt(local, 2, 18)) * 28}px)`,
          }}
        >
          {item.title}
        </div>
      </div>

      <Annotation
        key={`ann-${active}`}
        box={item.box}
        extra={item.extra}
        label={item.label}
        score={item.score}
        meta={item.meta}
        color={item.color}
        delay={active * SLOT + 7}
      />

      <div
        style={{
          position: "absolute",
          left: G.margin,
          right: G.margin,
          top: 1372,
          zIndex: 50,
          display: "flex",
          alignItems: "flex-end",
          justifyContent: "space-between",
          opacity: isLast ? 1 : fade,
        }}
      >
        <div>
          <div style={monoLabel(15, C.faint)}>GÜVEN SKORU</div>
          <div style={{fontFamily: FONT.mono, fontSize: 68, fontWeight: 600, color: item.color, lineHeight: 1, marginTop: 10}}>
            {item.score}
          </div>
        </div>
        <div style={{textAlign: "right"}}>
          <div style={monoLabel(15, C.faint)}>KAYIT</div>
          <div style={{fontFamily: FONT.mono, fontSize: 21, color: C.text, marginTop: 13, lineHeight: 1.5}}>
            KARE · KONUM · ZAMAN
          </div>
        </div>
      </div>

      {/* Sınıf şeridi — hangi sınıfta olduğumuz her an görünür */}
      <div style={{position: "absolute", left: G.margin, right: G.margin, top: 1552, zIndex: 50, display: "flex", gap: 10}}>
        {ITEMS.map((it, i) => (
          <div
            key={it.title}
            style={{
              flex: 1,
              padding: "13px 0 15px",
              textAlign: "center",
              borderTop: `2px solid ${i === active ? it.color : C.line}`,
              backgroundColor: i === active ? "rgba(9,17,31,.92)" : "rgba(9,17,31,.40)",
              ...monoLabel(14, i === active ? C.text : C.faint),
            }}
          >
            {it.title}
          </div>
        ))}
      </div>

      <FooterNote text="TEK MODEL · ÇOK SINIF · TEK GEÇİŞTE" delay={12} />
    </Stage>
  );
};
