import { useTranslation } from "react-i18next";
import type { CityEvent } from "../api/types";
import { confidenceLevel, statusLabel } from "../lib/format";

export function StatusPill({ status }: { status: string }) {
  const { t } = useTranslation();
  return (
    <span className={`pill pill-status-${status}`}>
      <span className="pill-dot" aria-hidden="true" />
      {statusLabel(t, status)}
    </span>
  );
}

// Text label + bar count, so the level is never shown by colour alone.
export function ConfidenceBadge({ event }: { event: Pick<CityEvent, "confidence" | "confidence_band"> }) {
  const { t } = useTranslation();
  const level = confidenceLevel(event);
  const bars = level === "high" ? 3 : level === "medium" ? 2 : 1;
  const raw = typeof event.confidence === "number" ? t("confidence.raw", { value: event.confidence.toFixed(2) }) : undefined;
  return (
    <span className={`conf conf-${level}`} title={raw}>
      <span className="conf-bars" aria-hidden="true">
        {[1, 2, 3].map((i) => (
          <span key={i} className={i <= bars ? "on" : ""} />
        ))}
      </span>
      <span className="visually-hidden">{t("confidence.label")}: </span>
      {t(`confidence.${level}`)}
    </span>
  );
}
