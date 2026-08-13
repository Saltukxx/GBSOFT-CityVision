import {interpolate, useCurrentFrame} from "remotion";
import {Backdrop, BrandRow, Eyebrow, Headline, ProgressRail, Stage} from "../chrome";
import {Annotation} from "../graphics";
import {C, FONT, G, clamp, ease, inAt, monoLabel} from "../theme";
import {VO, localOf} from "../timing";

/** İkinci cümlenin ("artık görebiliyor") başladığı yerel kare. */
const BEAT = localOf(0, VO.s02);

export const S01Hook: React.FC = () => {
  const frame = useCurrentFrame();
  // Beat'ler üst üste biner: arada boş kare kalmaz
  const outA = interpolate(frame, [BEAT - 20, BEAT - 4], [1, 0], {...clamp, easing: ease});

  return (
    <Stage>
      <Backdrop src="gorseller/10-cityvision-yol-ana-gorsel.png" from={1.03} to={1.09} topScrim={0.92} bottomScrim={0.9} />
      <BrandRow section="01 / 08" />
      <ProgressRail index={0} />

      {/* Beat 1 — araçlar zaten oradalar */}
      <div style={{opacity: outA}}>
        <Eyebrow>HER GÜN · AYNI SOKAKLAR</Eyebrow>
        <Headline lines={["ŞEHRİ", "ZATEN", "GEZİYORLAR."]} size={112} lineHeight={0.92} delay={6} />
      </div>

      {/* Beat 2 — artık görüyorlar */}
      <div style={{opacity: inAt(frame, BEAT - 12, 14)}}>
        <Eyebrow color={C.alert} delay={BEAT - 12}>
          ARTIK GÖRÜYORLAR DA
        </Eyebrow>
        <Headline
          lines={["GÖRDÜĞÜNÜ", {t: "KAYDA", c: C.alert}, {t: "GEÇİRİYOR.", c: C.alert}]}
          size={104}
          lineHeight={0.94}
          delay={BEAT - 8}
        />
      </div>

      <Annotation
        color={C.alert}
        delay={BEAT + 12}
        box={{x: 372, y: 1284, w: 540, h: 318}}
        label="YÜZEY BOZULMASI"
        score="%94"
      />

      <div
        style={{
          position: "absolute",
          left: G.margin,
          right: G.margin,
          top: G.footerY,
          zIndex: 55,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          opacity: inAt(frame, BEAT + 40, 20),
        }}
      >
        <span style={{fontFamily: FONT.mono, fontSize: 19, color: C.dim, letterSpacing: 1.2}}>25-BSK-118 · 08:41</span>
        <span style={monoLabel(17, C.faint)}>39.90861 N / 41.26722 E</span>
      </div>
    </Stage>
  );
};
