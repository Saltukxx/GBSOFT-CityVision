import type {CSSProperties, ReactNode} from "react";
import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame, useVideoConfig} from "remotion";
import {C, FONT, G, clamp, contentW, ease, inAt, monoLabel} from "./theme";

/* ------------------------------------------------------------------ */
/* Sahne iskeleti                                                      */
/* ------------------------------------------------------------------ */

export const Stage: React.FC<{children: ReactNode; style?: CSSProperties}> = ({children, style}) => (
  <AbsoluteFill style={{backgroundColor: C.ink, fontFamily: FONT.sans, ...style}}>{children}</AbsoluteFill>
);

/** GBSoft markası + sahne etiketi. Her sahnede aynı yerde. */
export const BrandRow: React.FC<{section: string}> = ({section}) => (
  <div
    style={{
      position: "absolute",
      left: G.margin,
      right: G.margin,
      top: G.brandY,
      zIndex: 60,
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
    }}
  >
    <div style={{display: "flex", alignItems: "center", gap: 13}}>
      <Mark size={24} />
      <span style={{fontSize: 23, fontWeight: 700, letterSpacing: 4.2, color: C.text}}>GBSOFT</span>
      <span style={{width: 1, height: 19, backgroundColor: C.lineStrong, marginLeft: 4}} />
      <span style={{fontSize: 21, fontWeight: 500, letterSpacing: 4.2, color: C.dim}}>CITY VISION</span>
    </div>
    <span style={{...monoLabel(15, C.accent)}}>{section}</span>
  </div>
);

/** Sade marka işareti: kare çerçeve + odak noktası. */
export const Mark: React.FC<{size?: number; color?: string}> = ({size = 24, color = C.accent}) => (
  <svg width={size} height={size} viewBox="0 0 24 24">
    <path d="M2 8V2h6M22 8V2h-6M2 16v6h6M22 16v6h-6" fill="none" stroke={color} strokeWidth="2.4" />
    <circle cx="12" cy="12" r="3.1" fill={color} />
  </svg>
);

/** İlerleme rayı — 8 bölüm, izleyiciye videonun uzunluğunu hissettirir. */
export const ProgressRail: React.FC<{index: number; total?: number}> = ({index, total = 8}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const self = interpolate(frame, [0, durationInFrames], [0, 1], clamp);
  return (
    <div style={{position: "absolute", left: G.margin, right: G.margin, top: G.railY, display: "flex", gap: 6, zIndex: 60}}>
      {Array.from({length: total}).map((_, i) => (
        <div key={i} style={{height: 3, flex: 1, backgroundColor: "rgba(150,182,220,.18)", overflow: "hidden"}}>
          <div
            style={{
              height: "100%",
              width: i < index ? "100%" : i === index ? `${self * 100}%` : "0%",
              backgroundColor: i <= index ? C.accent : "transparent",
            }}
          />
        </div>
      ))}
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* Tipografi                                                           */
/* ------------------------------------------------------------------ */

export const Eyebrow: React.FC<{children: ReactNode; color?: string; delay?: number}> = ({
  children,
  color = C.accent,
  delay = 2,
}) => {
  const frame = useCurrentFrame();
  return (
    <div style={{position: "absolute", left: G.margin, top: G.eyebrowY, zIndex: 50, opacity: inAt(frame, delay, 14)}}>
      <span style={monoLabel(16, color)}>{children}</span>
    </div>
  );
};

/**
 * Satır satır maskeli açılan başlık. Her satır alttan yukarı kayar —
 * yazının kendisi hareket eder, kutu değil; bu daha "kurgulanmış" durur.
 */
export const Headline: React.FC<{
  lines: (string | {t: string; c: string})[];
  size?: number;
  top?: number;
  delay?: number;
  lineHeight?: number;
}> = ({lines, size = 88, top = G.headY, delay = 6, lineHeight = 0.98}) => {
  const frame = useCurrentFrame();
  const lh = size * lineHeight;
  return (
    <div style={{position: "absolute", left: G.margin, top, width: contentW, zIndex: 50}}>
      {lines.map((line, i) => {
        const text = typeof line === "string" ? line : line.t;
        const color = typeof line === "string" ? C.text : line.c;
        const d = delay + i * 7;
        const p = interpolate(frame, [d, d + 26], [0, 1], {...clamp, easing: ease});
        return (
          <div key={text + i} style={{height: lh, overflow: "hidden"}}>
            <div
              style={{
                fontSize: size,
                lineHeight: `${lh}px`,
                fontWeight: 700,
                letterSpacing: -size * 0.035,
                color,
                transform: `translateY(${(1 - p) * lh}px)`,
                opacity: interpolate(p, [0, 0.35], [0, 1], clamp),
                whiteSpace: "nowrap",
              }}
            >
              {text}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export const SubLine: React.FC<{children: ReactNode; top: number; delay?: number; width?: number}> = ({
  children,
  top,
  delay = 24,
  width = 720,
}) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        position: "absolute",
        left: G.margin,
        top,
        width,
        zIndex: 50,
        fontSize: 27,
        lineHeight: 1.42,
        fontWeight: 400,
        color: C.dim,
        opacity: inAt(frame, delay, 18),
      }}
    >
      {children}
    </div>
  );
};

/** Alt bilgi şeridi — ince kural + mono not. */
export const FooterNote: React.FC<{text: string; delay?: number}> = ({text, delay = 40}) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        position: "absolute",
        left: G.margin,
        right: G.margin,
        top: G.footerY,
        zIndex: 60,
        display: "flex",
        alignItems: "center",
        gap: 16,
        opacity: inAt(frame, delay, 20),
      }}
    >
      <span style={{width: 34, height: 1.5, backgroundColor: C.accent}} />
      <span style={monoLabel(15, C.faint)}>{text}</span>
    </div>
  );
};

/* ------------------------------------------------------------------ */
/* Görsel katmanlar                                                    */
/* ------------------------------------------------------------------ */

/**
 * Tam kadraj fotoğraf + okunabilirlik için üst/alt degrade.
 * Yavaş ve tek yönlü bir push-in; salınım yok.
 */
export const Backdrop: React.FC<{
  src: string;
  position?: string;
  from?: number;
  to?: number;
  topScrim?: number;
  bottomScrim?: number;
}> = ({src, position = "50% 50%", from = 1, to = 1.05, topScrim = 0.9, bottomScrim = 0.92}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  const scale = interpolate(frame, [0, durationInFrames], [from, to], {
    ...clamp,
    easing: Easing.bezier(0.33, 0, 0.5, 1),
  });
  return (
    <AbsoluteFill style={{overflow: "hidden", backgroundColor: C.ink}}>
      <Img
        src={staticFile(src)}
        style={{width: "100%", height: "100%", objectFit: "cover", objectPosition: position, transform: `scale(${scale})`}}
      />
      <AbsoluteFill
        style={{
          background:
            `linear-gradient(180deg, rgba(5,7,14,${topScrim}) 0%, rgba(5,7,14,${topScrim * 0.62}) 17%,` +
            ` rgba(5,7,14,0.10) 42%, rgba(5,7,14,0.34) 74%, rgba(5,7,14,${bottomScrim}) 100%)`,
        }}
      />
    </AbsoluteFill>
  );
};

/** Çok ince teknik grid — yalnızca grafik sahnelerde, arka planı boş bırakmamak için. */
export const TechGrid: React.FC<{opacity?: number}> = ({opacity = 1}) => (
  <AbsoluteFill
    style={{
      opacity,
      backgroundImage:
        `linear-gradient(rgba(150,182,220,.07) 1px, transparent 1px),` +
        ` linear-gradient(90deg, rgba(150,182,220,.07) 1px, transparent 1px)`,
      backgroundSize: "60px 60px",
      backgroundPosition: `${G.margin}px 0px`,
      maskImage: "linear-gradient(to bottom, transparent 10%, black 26%, black 84%, transparent 97%)",
    }}
  />
);

/** İçerik kartı — tüm panellerde aynı kenarlık dili. */
export const Panel: React.FC<{
  style?: CSSProperties;
  children?: ReactNode;
  accent?: string;
  delay?: number;
}> = ({style, children, accent, delay = 0}) => {
  const frame = useCurrentFrame();
  const p = inAt(frame, delay, 22);
  return (
    <div
      style={{
        position: "absolute",
        backgroundColor: C.panel,
        border: `1px solid ${C.line}`,
        borderTop: accent ? `2px solid ${accent}` : `1px solid ${C.line}`,
        opacity: p,
        transform: `translateY(${(1 - p) * 26}px)`,
        ...style,
      }}
    >
      {children}
    </div>
  );
};
