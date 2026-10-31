import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { MapPinOff, Upload } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { ACTIVE_FLIGHT_STATUSES, type Flight } from "../api/types";
import { useCurrentUser } from "../auth/AuthContext";
import { FlightStatus } from "../components/FlightStatus";
import { Empty, ErrorState, Loading } from "../components/States";
import { formatBytes, formatDate } from "../lib/format";
import { UploadDialog } from "../uploads/UploadDialog";
import { UploadTasks } from "../uploads/UploadTasks";
import { pendingUploadIds, useUploads } from "../uploads/UploadsContext";

export function FlightsPage() {
  const { t } = useTranslation();
  const { canDecide } = useCurrentUser();
  const [uploading, setUploading] = useState(false);

  const q = useQuery({
    queryKey: ["flights"],
    queryFn: api.flights,
    // Poll quickly while something is moving, slowly otherwise.
    refetchInterval: (query) =>
      query.state.data?.some((f) => ACTIVE_FLIGHT_STATUSES.includes(f.status)) ? 4000 : 60_000,
  });

  const flights = q.data ?? [];
  // Uploads this browser started earlier but is not sending right now.
  const { tasks } = useUploads();
  const runningHere = new Set(tasks.map((x) => x.flightId).filter(Boolean));
  const interrupted = new Set([...pendingUploadIds()].filter((id) => !runningHere.has(id)));

  return (
    <div className="page">
      <header className="page-head page-head-actions">
        <div>
          <h1>{t("flights.title")}</h1>
          {q.data && <span className="muted">{t("flights.count", { count: flights.length })}</span>}
        </div>
        {canDecide && (
          <button type="button" className="btn btn-primary" onClick={() => setUploading(true)}>
            <Upload size={17} aria-hidden="true" /> {t("flights.upload")}
          </button>
        )}
      </header>

      <UploadTasks />

      {q.isPending ? (
        <Loading />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : flights.length === 0 ? (
        <Empty>{t("flights.empty")}</Empty>
      ) : (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>{t("flights.columns.flight")}</th>
                <th>{t("flights.columns.date")}</th>
                <th>{t("flights.columns.source")}</th>
                <th>{t("flights.columns.status")}</th>
                <th className="num">{t("flights.columns.candidates")}</th>
                <th className="num">{t("flights.columns.size")}</th>
              </tr>
            </thead>
            <tbody>
              {flights.map((f) => (
                <FlightRow key={f.id} flight={f} interruptedHere={f.status === "uploading" && interrupted.has(f.id)} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {uploading && <UploadDialog onClose={() => setUploading(false)} />}
    </div>
  );
}

function FlightRow({ flight: f, interruptedHere }: { flight: Flight; interruptedHere: boolean }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  return (
    <tr>
      <td data-label={t("flights.columns.flight")}>
        <Link to={`/flights/${f.id}`} className="table-link">
          {f.name}
        </Link>
        {!f.has_telemetry && f.status !== "uploading" && (
          <span className="flag" title={t("flights.noTelemetry")}>
            <MapPinOff size={15} aria-hidden="true" />
            <span className="visually-hidden">{t("flights.noTelemetry")}</span>
          </span>
        )}
        {interruptedHere && <p className="muted small">{t("flights.resumeHint")}</p>}
      </td>
      <td data-label={t("flights.columns.date")}>{formatDate(f.flight_date || f.created_at, lang)}</td>
      <td data-label={t("flights.columns.source")}>{t(`flights.source.${f.source}`)}</td>
      <td data-label={t("flights.columns.status")}>
        <FlightStatus flight={f} showBar />
      </td>
      <td data-label={t("flights.columns.candidates")} className="num">
        {f.status === "succeeded" ? f.candidates : "—"}
      </td>
      <td data-label={t("flights.columns.size")} className="num muted">
        {formatBytes(f.bytes, lang)}
      </td>
    </tr>
  );
}
