import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ACTIVE_FLIGHT_STATUSES } from "../api/types";
import { useCurrentUser } from "../auth/AuthContext";
import type { Adherence } from "../api/types";
import { formatDistance } from "../lib/geo";
import { ConfidenceBadge, StatusPill } from "../components/Badges";
import { EventMap } from "../components/EventMap";
import { FlightStatus } from "../components/FlightStatus";
import { Empty, ErrorState, Loading } from "../components/States";
import { Thumb } from "../components/Thumb";
import { eventTypeLabel, formatBytes, formatDate, formatDateTime, formatDuration } from "../lib/format";

export function FlightDetailPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const { flightId = "" } = useParams();

  const q = useQuery({
    queryKey: ["flight", flightId],
    queryFn: () => api.flight(flightId),
    refetchInterval: (query) => (query.state.data && ACTIVE_FLIGHT_STATUSES.includes(query.state.data.status) ? 3000 : false),
  });
  const routes = useQuery({ queryKey: ["routes"], queryFn: api.routes, staleTime: 300_000 });
  const routeGeos = useQuery({ queryKey: ["routes-geo"], queryFn: api.routesGeo, staleTime: 300_000 });
  const assign = useMutation({
    mutationFn: (routeId: string | null) => api.assignRoute(flightId, routeId),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: ["flight", flightId] });
      void qc.invalidateQueries({ queryKey: ["routes-geo"] });
      void qc.invalidateQueries({ queryKey: ["flight-tracks"] });
    },
  });
  const { user, canDecide } = useCurrentUser();
  const qc = useQueryClient();
  // Shown value flips on click; cleared once the server's copy is back.
  const [holdoutShown, setHoldoutShown] = useState<boolean | null>(null);
  const holdout = useMutation({
    mutationFn: (value: boolean) => api.setHoldout(flightId, value),
    onSettled: async () => {
      await qc.invalidateQueries({ queryKey: ["flight", flightId] });
      void qc.invalidateQueries({ queryKey: ["labelling"] });
      setHoldoutShown(null);
    },
  });

  const eventIds = useMemo(() => q.data?.event_ids ?? [], [q.data]);
  const events = useQuery({
    queryKey: ["events", "flight", flightId, eventIds.length],
    queryFn: () => api.events({ limit: 2000 }),
    enabled: eventIds.length > 0,
  });
  const flightEvents = useMemo(() => {
    const ids = new Set(eventIds);
    return (events.data ?? []).filter((e) => ids.has(e.event_id));
  }, [events.data, eventIds]);

  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} notFoundText={t("flights.notFound")} />;
  const f = q.data;

  const routeName = f.route_id ? routes.data?.find((r) => r.id === f.route_id)?.name ?? f.route_id : null;
  const plannedRoute = f.route_id ? routeGeos.data?.find((r) => r.id === f.route_id) : undefined;
  const ended = f.status === "duplicate" || f.status === "cancelled";
  const processingSecs =
    !ended && f.processing_started_at && f.processing_finished_at
      ? (new Date(f.processing_finished_at).getTime() - new Date(f.processing_started_at).getTime()) / 1000
      : null;
  const pending = flightEvents.filter((e) => e.status === "under_review").length;

  const rows: [string, string][] = [
    [t("flights.flightDate"), formatDate(f.flight_date, lang)],
    [t("flights.columns.source"), f.device_name && f.source !== "upload" ? `${t(`flights.source.${f.source}`)} · ${f.device_name}` : t(`flights.source.${f.source}`)],
    [t("flights.fileName"), f.filename || "—"],
    [t("flights.columns.size"), formatBytes(f.bytes, lang)],
    [t("flights.uploadedBy"), f.uploaded_by || "—"],
    [t("flights.uploadedAt"), formatDateTime(f.created_at, lang)],
    [t("flights.route"), routeName || "—"],
    [t("flights.processingTime"), processingSecs != null ? formatDuration(processingSecs, lang) : "—"],
  ];

  return (
    <div className="page">
      <Link to="/flights" className="btn btn-ghost back-link">
        <ArrowLeft size={16} aria-hidden="true" /> {t("flights.back")}
      </Link>
      <header className="page-head page-head-actions">
        <div>
          <h1>{f.name}</h1>
          <div className="event-meta">
            <FlightStatus flight={f} showBar />
            {f.status === "succeeded" && <span className="muted">{t("flights.candidates", { count: f.candidates })}</span>}
          </div>
        </div>
        {pending > 0 && (
          <Link className="btn btn-primary" to="/review">
            {t("flights.openQueue")} ({pending})
          </Link>
        )}
      </header>

      {f.status === "failed" && f.error && (
        <p className="form-error" role="alert">
          {f.error}
        </p>
      )}
      {f.status === "duplicate" && (
        <p className="form-warning">
          {t("flights.duplicateOf")}{" "}
          {f.duplicate_of && <Link to={`/flights/${f.duplicate_of}`}>{t("flights.openOriginal")}</Link>}
        </p>
      )}
      {f.status === "uploading" && <p className="form-warning">{t("flights.resumeHint")}</p>}
      {!f.has_telemetry && f.status !== "uploading" && <p className="form-warning">{t("flights.noTelemetry")}</p>}
      {f.trajectory_warning && <p className="form-warning">{f.trajectory_warning}</p>}
      {user.role === "superadmin" && f.status === "succeeded" && (
        <label className="card holdout-toggle">
          <input
            type="checkbox"
            checked={holdoutShown ?? f.holdout}
            onChange={(e) => {
              setHoldoutShown(e.target.checked);
              holdout.mutate(e.target.checked);
            }}
          />
          <span>
            <strong>{t("flights.holdoutToggle")}</strong>
            <span className="muted small">{t("flights.holdoutHint")}</span>
          </span>
        </label>
      )}

      <div className="grid-2 grid-2-wide">
        {!ended && (
          <section className="card">
            <h3>{t("flights.track")}</h3>
            {f.track.length || flightEvents.some((e) => e.lat) ? (
              <>
                <EventMap events={flightEvents} track={f.track} routes={plannedRoute ? [plannedRoute] : []} className="map-flight" />
                {plannedRoute && (
                  <p className="route-legend small muted">
                    <span className="legend-line legend-line-plan" aria-hidden="true" /> {t("flights.routeLegendPlan")}
                    <span className="legend-line legend-line-flown" aria-hidden="true" /> {t("flights.routeLegendFlown")}
                  </p>
                )}
              </>
            ) : (
              <p className="muted">{t("flights.noTrack")}</p>
            )}
          </section>
        )}
        <section className="card">
          <h3>{t("flights.details")}</h3>
          <dl className="dl">
            {rows.map(([k, v]) => (
              <div key={k}>
                <dt>{k}</dt>
                <dd>{v}</dd>
              </div>
            ))}
          </dl>
        </section>
      </div>

      {f.status === "succeeded" && (
        <section className="card route-card-flight">
          <div className="route-flight-head">
            <h3>{t("flights.routeTitle")}</h3>
            {canDecide ? (
              <label className="filter">
                <span className="filter-label">{t("flights.routeAssign")}</span>
                <select value={f.route_id ?? ""} disabled={assign.isPending} onChange={(e) => assign.mutate(e.target.value || null)}>
                  <option value="">{t("flights.routeNone")}</option>
                  {(routeGeos.data ?? []).map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              <span className="muted">{routeName ?? t("flights.routeNone")}</span>
            )}
          </div>
          {f.adherence && <AdherenceStats a={f.adherence} lang={lang} />}
        </section>
      )}

      {f.status === "succeeded" && (
        <section className="card">
          <h3>{t("flights.events")}</h3>
          {events.isPending && eventIds.length > 0 ? (
            <Loading />
          ) : flightEvents.length === 0 ? (
            <Empty>{t("flights.noEvents")}</Empty>
          ) : (
            <ul className="event-list">
              {flightEvents.map((e) => (
                <li key={e.event_id}>
                  <Link to={`/events/${encodeURIComponent(e.event_id)}`} className="event-list-row">
                    <Thumb src={e.thumb_url} size="sm" />
                    <span className="row-title">{eventTypeLabel(t, e.type)}</span>
                    <ConfidenceBadge event={e} />
                    <StatusPill status={e.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}

function AdherenceStats({ a, lang }: { a: Adherence; lang: string }) {
  const { t } = useTranslation();
  const pct = (v: number) => new Intl.NumberFormat(lang, { style: "percent", maximumFractionDigits: 0 }).format(v);
  const verdict = a.coverage >= 0.9 && a.off_route <= 0.1 ? "good" : a.coverage >= 0.6 ? "partial" : "poor";
  return (
    <div className="adherence">
      <div className={`adherence-verdict adherence-${verdict}`}>
        <span className="adherence-ring" style={{ ["--p" as string]: `${Math.round(a.coverage * 100)}` }}>
          <span>{pct(a.coverage)}</span>
        </span>
        <span>
          <strong>{t(`flights.adherence.${verdict}`)}</strong>
          <span className="muted small">{t("flights.adherence.within", { m: a.tolerance_m })}</span>
        </span>
      </div>
      <dl className="adherence-stats">
        <div>
          <dt>{t("flights.adherence.coverage")}</dt>
          <dd>{pct(a.coverage)}</dd>
        </div>
        <div>
          <dt>{t("flights.adherence.offRoute")}</dt>
          <dd>{pct(a.off_route)}</dd>
        </div>
        <div>
          <dt>{t("flights.adherence.maxDev")}</dt>
          <dd>{formatDistance(a.max_deviation_m, lang)}</dd>
        </div>
      </dl>
    </div>
  );
}
