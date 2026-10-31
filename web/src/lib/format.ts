import type { TFunction } from "i18next";
import type { CityEvent } from "../api/types";

export type ConfidenceLevel = "high" | "medium" | "low";

// Plain-language confidence. Uses the backend band when present
// (high / probable / manual_review), else the raw score.
export function confidenceLevel(ev: Pick<CityEvent, "confidence" | "confidence_band">): ConfidenceLevel {
  switch (ev.confidence_band) {
    case "high":
      return "high";
    case "probable":
      return "medium";
    case "manual_review":
    case "discard":
      return "low";
  }
  const c = ev.confidence ?? 0;
  if (c >= 0.95) return "high";
  if (c >= 0.85) return "medium";
  return "low";
}

const CONFIDENCE_ORDER: Record<ConfidenceLevel, number> = { high: 0, medium: 1, low: 2 };
export function byConfidenceDesc(a: CityEvent, b: CityEvent): number {
  const d = CONFIDENCE_ORDER[confidenceLevel(a)] - CONFIDENCE_ORDER[confidenceLevel(b)];
  return d !== 0 ? d : (b.confidence ?? 0) - (a.confidence ?? 0);
}

// Unknown codes fall back to a readable version of the code itself.
export function humanize(code: string): string {
  const s = code.replace(/[_-]+/g, " ").trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export function eventTypeLabel(t: TFunction, type: string): string {
  return t(`eventType.${type}`, { defaultValue: humanize(type) });
}

export function statusLabel(t: TFunction, status: string): string {
  return t(`status.${status}`, { defaultValue: humanize(status) });
}

export function formatDateTime(value: string | number | null | undefined, lang: string): string {
  if (value === null || value === undefined || value === "") return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat(lang, { dateStyle: "medium", timeStyle: "short" }).format(d);
}

export function formatNumber(n: number, lang: string): string {
  return new Intl.NumberFormat(lang).format(n);
}

export function formatCoord(lat: number, lon: number, lang: string): string {
  const f = new Intl.NumberFormat(lang, { minimumFractionDigits: 5, maximumFractionDigits: 5 });
  return `${f.format(lat)}, ${f.format(lon)}`;
}

export function seenCount(ev: { observations?: number | unknown[] | null }): number {
  const o = ev.observations;
  if (Array.isArray(o)) return Math.max(1, o.length);
  return typeof o === "number" && o > 0 ? o : 1;
}

export function hasLocation<T extends { lat?: number | null; lon?: number | null }>(ev: T): ev is T & { lat: number; lon: number } {
  return typeof ev.lat === "number" && typeof ev.lon === "number" && !(ev.lat === 0 && ev.lon === 0);
}

const BYTE_UNITS = ["byte", "kilobyte", "megabyte", "gigabyte", "terabyte"] as const;

export function formatBytes(bytes: number | null | undefined, lang: string): string {
  if (bytes === null || bytes === undefined) return "—";
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < BYTE_UNITS.length - 1) {
    value /= 1024;
    unit++;
  }
  return new Intl.NumberFormat(lang, {
    style: "unit",
    unit: BYTE_UNITS[unit],
    unitDisplay: "short",
    maximumFractionDigits: unit >= 2 ? 1 : 0,
  }).format(value);
}

export function formatDuration(seconds: number, lang: string): string {
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const fmt = (v: number, unit: "hour" | "minute" | "second") =>
    new Intl.NumberFormat(lang, { style: "unit", unit, unitDisplay: "short" }).format(v);
  if (h) return `${fmt(h, "hour")} ${fmt(m, "minute")}`;
  if (m) return `${fmt(m, "minute")} ${fmt(s % 60, "second")}`;
  return fmt(s, "second");
}

export function formatDate(value: string | null | undefined, lang: string): string {
  if (!value) return "—";
  const d = new Date(value.length === 10 ? `${value}T00:00:00` : value);
  if (Number.isNaN(d.getTime())) return "—";
  return new Intl.DateTimeFormat(lang, { dateStyle: "medium" }).format(d);
}
