import {Easing, interpolate} from "remotion";

/**
 * City Vision — dikey reel tasarım sistemi.
 *
 * Tasarım ilkeleri:
 *  - Tek vurgu rengi (accent). Uyarı/onay renkleri yalnızca anlam taşıdığında.
 *  - Sabit sayfa gridi: her sahne aynı kenar boşluğu ve aynı dikey ritmi kullanır.
 *  - Parıltı/grain/tarama efekti yok; çizgiler ince ve ölçülü.
 *  - Sayısal her şey mono tipografiyle: ürün arayüzü hissi verir.
 */

export const C = {
  ink: "#05070E",
  ink2: "#0A1220",
  panel: "rgba(9, 17, 31, 0.86)",
  panelSolid: "#0B1524",
  line: "rgba(150, 182, 220, 0.16)",
  lineStrong: "rgba(150, 182, 220, 0.34)",
  text: "#EDF3FA",
  dim: "#94A7C1",
  faint: "#5C6E88",
  accent: "#27B6E6",
  accentDim: "rgba(39, 182, 230, 0.16)",
  alert: "#FF6A55",
  warn: "#F0B03C",
  ok: "#2FCF9B",
} as const;

/** Sayfa gridi — tüm sahneler bu değerlere hizalanır. */
export const G = {
  W: 1080,
  H: 1920,
  margin: 88,
  brandY: 104,
  railY: 166,
  eyebrowY: 258,
  headY: 296,
  /** İçerik bu satırın altına taşmaz (dikey platform arayüzü payı). */
  safeBottom: 1624,
  footerY: 1668,
} as const;

export const col = (x: number) => G.margin + x;
export const contentW = G.W - G.margin * 2; // 904

export const FONT = {
  sans: "'Inter Tight', 'Helvetica Neue', Arial, sans-serif",
  mono: "'IBM Plex Mono', ui-monospace, Menlo, monospace",
} as const;

/** Tek bir yumuşama eğrisi — tüm hareketler aynı karakterde. */
export const ease = Easing.bezier(0.22, 1, 0.3, 1);
export const clamp = {extrapolateLeft: "clamp", extrapolateRight: "clamp"} as const;

/** 0 → 1 giriş eğrisi. */
export const inAt = (frame: number, delay: number, dur = 20) =>
  interpolate(frame, [delay, delay + dur], [0, 1], {...clamp, easing: ease});

/** Giriş + çıkış (sahne sonunda yumuşak kapanış için). */
export const inOutAt = (frame: number, delay: number, hold: number, dur = 18) =>
  interpolate(frame, [delay, delay + dur, delay + hold, delay + hold + dur], [0, 1, 1, 0], {
    ...clamp,
    easing: ease,
  });

/** Mono etiket stili — veri, kimlik ve ölçü metinleri. */
export const monoLabel = (size = 17, color: string = C.dim) =>
  ({
    fontFamily: FONT.mono,
    fontSize: size,
    letterSpacing: size * 0.13,
    fontWeight: 500,
    color,
  }) as const;
