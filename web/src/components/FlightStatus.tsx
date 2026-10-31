import { useTranslation } from "react-i18next";
import type { Flight } from "../api/types";

const TONE: Record<string, string> = {
  uploading: "active",
  received: "active",
  queued: "waiting",
  analyzing: "active",
  succeeded: "ok",
  failed: "bad",
  cancelled: "muted",
  duplicate: "muted",
};

export function FlightStatus({ flight, showBar = false }: { flight: Pick<Flight, "status" | "progress">; showBar?: boolean }) {
  const { t } = useTranslation();
  const pct = flight.progress != null ? Math.round(flight.progress * 100) : null;
  const label =
    flight.status === "analyzing" && pct != null
      ? t("flights.processing", { percent: pct })
      : t(`flights.status.${flight.status}`, { defaultValue: flight.status });
  return (
    <span className="flight-status">
      <span className={`pill pill-flight-${TONE[flight.status] ?? "muted"}`}>
        <span className="pill-dot" aria-hidden="true" />
        {label}
      </span>
      {showBar && (flight.status === "analyzing" || flight.status === "received") && (
        <span className="progress progress-sm" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct ?? 0} aria-label={label}>
          <span style={{ width: `${pct ?? 0}%` }} />
        </span>
      )}
    </span>
  );
}
