import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from "remotion";
import {BrandRow, Mark, ProgressRail, Stage} from "../chrome";
import {C, FONT, G, clamp, ease, inAt, monoLabel} from "../theme";

/**
 * Anlatım: "GBSoft City Vision şehir yönetimini daha hızlı, daha düzenli ve
 * daha verimli hâle getiriyor." Üç sıfat, seslendirmedeki virgüllere oturur.
 *
 * Kompozisyon bilinçli olarak bölünmüş: üstte düz zemin üzerinde tipografi,
 * altta net bir kenarla başlayan fotoğraf. Yazı fotoğrafın üzerine binmez.
 */

const WORDS: [string, number][] = [
  ["Daha hızlı.", 10],
  ["Daha düzenli.", 43],
  ["Daha verimli.", 72],
];

const LOCKUP_AT = 118;
const PHOTO_TOP = 1010;

export const S08Close: React.FC = () => {
  const frame = useCurrentFrame();
  const lock = inAt(frame, LOCKUP_AT, 24);
  const contact = inAt(frame, LOCKUP_AT + 28, 24);
  const scale = interpolate(frame, [0, 263], [1.04, 1.11], {...clamp, easing: Easing.bezier(0.33, 0, 0.5, 1)});

  return (
    <Stage>
      {/* Alt bant: fotoğraf, üst kenarı yumuşak geçişle zemine bağlanıyor */}
      <AbsoluteFill style={{top: PHOTO_TOP, overflow: "hidden"}}>
        <Img
          src={staticFile("gorseller/10-cityvision-yol-ana-gorsel.png")}
          style={{
            position: "absolute",
            left: 0,
            top: -PHOTO_TOP * 0.52,
            width: "100%",
            height: G.H,
            objectFit: "cover",
            objectPosition: "50% 62%",
            transform: `scale(${scale})`,
          }}
        />
        <AbsoluteFill
          style={{
            background:
              "linear-gradient(180deg, #05070E 0%, rgba(5,7,14,.78) 9%, rgba(5,7,14,.18) 26%," +
              " rgba(5,7,14,.30) 62%, rgba(5,7,14,.96) 100%)",
          }}
        />
      </AbsoluteFill>

      <BrandRow section="08 / 08" />
      <ProgressRail index={7} />

      {/* Üç sıfat — düz zemin üzerinde */}
      <div style={{position: "absolute", left: G.margin, top: 336, width: 904, zIndex: 50}}>
        {WORDS.map(([w, d], i) => {
          const p = interpolate(frame, [d, d + 24], [0, 1], {...clamp, easing: ease});
          return (
            <div key={w} style={{height: 104, overflow: "hidden"}}>
              <div
                style={{
                  fontSize: 92,
                  lineHeight: "104px",
                  fontWeight: 700,
                  letterSpacing: -3.2,
                  color: i === 2 ? C.accent : C.text,
                  transform: `translateY(${(1 - p) * 104}px)`,
                }}
              >
                {w}
              </div>
            </div>
          );
        })}
      </div>

      {/* Marka kilidi */}
      <div style={{position: "absolute", left: G.margin, top: 700, width: 904, zIndex: 50, opacity: lock}}>
        <div style={{height: 1, backgroundColor: C.line, marginBottom: 38, transform: `scaleX(${lock})`, transformOrigin: "left"}} />
        <div style={{display: "flex", alignItems: "center", gap: 18}}>
          <Mark size={40} />
          <span style={{fontSize: 40, fontWeight: 700, letterSpacing: 5, color: C.text}}>GBSOFT</span>
          <span style={{width: 1, height: 30, backgroundColor: C.lineStrong, margin: "0 6px"}} />
          <span style={{fontSize: 40, fontWeight: 600, letterSpacing: 3, color: C.accent}}>CITY VISION</span>
        </div>
        <div style={{marginTop: 24, fontSize: 30, color: C.dim, lineHeight: 1.4}}>
          Şehri yöneten yazılım, şehri gören yapay zekâ.
        </div>
      </div>

      {/* İletişim — fotoğrafın üstünde tam genişlikte künye bandı */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: 1540,
          height: 160,
          zIndex: 50,
          backgroundColor: "rgba(5,7,14,.93)",
          borderTop: `1px solid ${C.lineStrong}`,
          padding: `30px ${G.margin}px 0`,
          opacity: contact,
        }}
      >
        <div style={{display: "flex", justifyContent: "space-between", alignItems: "flex-start"}}>
          <div>
            <div style={{fontFamily: FONT.mono, fontSize: 30, color: C.text, letterSpacing: 1}}>gbsoftt.com</div>
            <div style={{...monoLabel(16, C.dim), marginTop: 14}}>ATA TEKNOKENT · ERZURUM</div>
          </div>
          <div style={{textAlign: "right", fontFamily: FONT.mono, fontSize: 21, color: C.text, lineHeight: 1.6}}>
            info@gbsoftt.com
            <br />
            0 536 840 92 36
          </div>
        </div>
      </div>
    </Stage>
  );
};
