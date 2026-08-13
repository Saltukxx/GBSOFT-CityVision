import type {ReactNode} from "react";
import {
  AbsoluteFill,
  CanvasImage,
  Easing,
  Interactive,
  interpolate,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

export const COLORS = {
  bg: "#050916",
  panel: "rgba(12, 23, 45, 0.82)",
  cyan: "#22d3ee",
  blue: "#38bdf8",
  violet: "#a78bfa",
  green: "#34d399",
  yellow: "#fbbf24",
  red: "#fb7185",
  white: "#f8fafc",
  muted: "#a9b6cc",
};

export const Brand: React.FC<{section?: string}> = ({section}) => (
  <div
    style={{
      position: "absolute",
      top: 50,
      left: 82,
      right: 82,
      display: "flex",
      justifyContent: "space-between",
      alignItems: "center",
      zIndex: 20,
      color: COLORS.white,
      fontFamily: "Inter, Arial, sans-serif",
      letterSpacing: 5,
      fontSize: 22,
      fontWeight: 800,
    }}
  >
    <div style={{display: "flex", alignItems: "center", gap: 16}}>
      <div
        style={{
          width: 23,
          height: 23,
          border: `3px solid ${COLORS.cyan}`,
          borderRadius: 7,
          boxShadow: `0 0 24px ${COLORS.cyan}`,
        }}
      />
      GBSOFT
    </div>
    {section ? (
      <div style={{color: COLORS.cyan, fontSize: 16, letterSpacing: 3}}>{section}</div>
    ) : null}
  </div>
);

export const ImageBackdrop: React.FC<{
  src: string;
  darkness?: number;
  scaleTo?: number;
  x?: string;
}> = ({src, darkness = 0.55, scaleTo = 1.08, x = "50%"}) => {
  const frame = useCurrentFrame();
  const {durationInFrames} = useVideoConfig();
  return (
    <AbsoluteFill style={{overflow: "hidden"}}>
      <CanvasImage
        src={staticFile(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          objectPosition: `${x} 50%`,
          scale: interpolate(frame, [0, durationInFrames], [1, scaleTo], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
            easing: Easing.bezier(0.16, 1, 0.3, 1),
          }),
        }}
      />
      <AbsoluteFill
        style={{
          background: `linear-gradient(90deg, rgba(4,8,20,${Math.min(0.96, darkness + 0.28)}) 0%, rgba(4,8,20,${darkness}) 52%, rgba(4,8,20,${Math.max(0.22, darkness - 0.2)}) 100%)`,
        }}
      />
      <AbsoluteFill
        style={{
          background: "radial-gradient(circle at 72% 45%, rgba(34,211,238,.18), transparent 32%), linear-gradient(180deg, rgba(5,9,22,.05), rgba(5,9,22,.7))",
        }}
      />
    </AbsoluteFill>
  );
};

export const NoiseGrid: React.FC = () => (
  <AbsoluteFill
    style={{
      opacity: 0.22,
      backgroundImage:
        "linear-gradient(rgba(56,189,248,.11) 1px, transparent 1px), linear-gradient(90deg, rgba(56,189,248,.11) 1px, transparent 1px)",
      backgroundSize: "80px 80px",
      maskImage: "linear-gradient(to bottom, rgba(0,0,0,.9), transparent 92%)",
    }}
  />
);

export const Reveal: React.FC<{
  children: ReactNode;
  delay?: number;
  y?: number;
  style?: React.CSSProperties;
}> = ({children, delay = 0, y = 42, style}) => {
  const frame = useCurrentFrame();
  return (
    <Interactive.Div
      name="Reveal"
      style={{
        opacity: interpolate(frame, [delay, delay + 24], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
        translate: interpolate(frame, [delay, delay + 30], [`0px ${y}px`, "0px 0px"], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
          easing: Easing.bezier(0.16, 1, 0.3, 1),
        }),
        ...style,
      }}
    >
      {children}
    </Interactive.Div>
  );
};

export const Eyebrow: React.FC<{children: ReactNode}> = ({children}) => (
  <div
    style={{
      color: COLORS.cyan,
      fontSize: 22,
      fontWeight: 800,
      letterSpacing: 5,
      textTransform: "uppercase",
      marginBottom: 22,
    }}
  >
    {children}
  </div>
);

export const BigTitle: React.FC<{children: ReactNode; maxWidth?: number}> = ({children, maxWidth = 1340}) => (
  <div
    style={{
      color: COLORS.white,
      fontSize: 96,
      lineHeight: 0.98,
      fontWeight: 760,
      letterSpacing: -4,
      maxWidth,
      textWrap: "balance",
    }}
  >
    {children}
  </div>
);

export const Body: React.FC<{children: ReactNode; maxWidth?: number}> = ({children, maxWidth = 1100}) => (
  <div
    style={{
      color: COLORS.muted,
      fontSize: 38,
      lineHeight: 1.34,
      fontWeight: 430,
      maxWidth,
      marginTop: 28,
    }}
  >
    {children}
  </div>
);

export const DetectionBox: React.FC<{
  label: string;
  confidence: string;
  top: number;
  left: number;
  width: number;
  height: number;
  color?: string;
  delay?: number;
}> = ({label, confidence, top, left, width, height, color = COLORS.cyan, delay = 0}) => {
  const frame = useCurrentFrame();
  return (
    <div
      style={{
        position: "absolute",
        top,
        left,
        width,
        height,
        border: `5px solid ${color}`,
        opacity: interpolate(frame, [delay, delay + 8, delay + 15, delay + 23], [0, 1, 0.45, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }),
        boxShadow: `0 0 26px ${color}66`,
      }}
    >
      <div
        style={{
          position: "absolute",
          top: -46,
          left: -5,
          padding: "8px 14px",
          background: color,
          color: "#03111c",
          fontSize: 20,
          fontWeight: 900,
          letterSpacing: 1,
          whiteSpace: "nowrap",
        }}
      >
        {label} · {confidence}
      </div>
    </div>
  );
};

export const FooterLine: React.FC<{text?: string}> = ({text = "GBSOFT · CITY VISION"}) => (
  <div
    style={{
      position: "absolute",
      left: 82,
      right: 82,
      bottom: 42,
      display: "flex",
      alignItems: "center",
      gap: 18,
      color: "#73809a",
      fontSize: 15,
      fontWeight: 700,
      letterSpacing: 3,
    }}
  >
    <div style={{height: 2, width: 70, backgroundColor: COLORS.cyan}} />
    {text}
  </div>
);
