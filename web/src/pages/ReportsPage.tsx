import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { ChevronLeft, ChevronRight, Printer } from "lucide-react";
import { api } from "../api/client";
import type { WeeklyReport } from "../api/types";
import { BrandMark } from "../components/Brand";
import { EventMap } from "../components/EventMap";
import { ErrorState, Loading } from "../components/States";
import { eventTypeLabel, formatDate, formatDateTime, formatNumber, hasLocation } from "../lib/format";

const iso = (d: Date) => d.toISOString().slice(0, 10);
function shift(start: string, days: number): string {
  const d = new Date(`${start}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return iso(d);
}

export function ReportsPage() {
  const { t, i18n } = useTranslation();
  const [params, setParams] = useSearchParams();
  const start = params.get("week") ?? undefined;
  const q = useQuery({ queryKey: ["report", start ?? "current"], queryFn: () => api.weeklyReport(start) });

  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const r = q.data;
  const isCurrent = r.end > iso(new Date());

  return (
    <div className="page report-page">
      <header className="page-head page-head-actions no-print">
        <div>
          <h1>{t("reports.title")}</h1>
        </div>
        <div className="toolbar">
          <button type="button" className="btn" onClick={() => setParams({ week: shift(r.start, -7) })}>
            <ChevronLeft size={16} aria-hidden="true" /> {t("reports.prev")}
          </button>
          {!isCurrent && (
            <>
              <button type="button" className="btn" onClick={() => setParams({ week: shift(r.start, 7) })}>
                {t("reports.next")} <ChevronRight size={16} aria-hidden="true" />
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => setParams({})}>
                {t("reports.thisWeek")}
              </button>
            </>
          )}
          <button type="button" className="btn btn-primary" onClick={() => window.print()} title={t("reports.downloadHint")}>
            <Printer size={16} aria-hidden="true" /> {t("reports.download")}
          </button>
        </div>
      </header>

      <Report r={r} lang={i18n.language} />
    </div>
  );
}

function Delta({ now, before, lang }: { now: number; before: number; lang: string }) {
  const { t } = useTranslation();
  const d = now - before;
  if (!before && !now) return null;
  const txt = `${d > 0 ? "+" : ""}${formatNumber(d, lang)}`;
  return <span className={`delta ${d > 0 ? "delta-up" : d < 0 ? "delta-down" : ""}`}>{t("reports.vsPrev", { delta: txt })}</span>;
}

function Report({ r, lang }: { r: WeeklyReport; lang: string }) {
  const { t } = useTranslation();
  const n = (v: number) => formatNumber(v, lang);
  const pct = (v: number | null) => (v == null ? "—" : new Intl.NumberFormat(lang, { style: "percent", maximumFractionDigits: 0 }).format(v));
  const endInclusive = shift(r.end, -1);
  const located = r.confirmed_events.filter(hasLocation);
  const reasons = Object.entries(r.false_alarm_reasons).sort((a, b) => b[1] - a[1]);
  const types = Object.entries(r.new_by_type).sort((a, b) => b[1] - a[1]);
  const max = (rows: [string, number][]) => Math.max(1, ...rows.map(([, c]) => c));

  return (
    <article className="report">
      <header className="report-head">
        <div className="report-brand">
          <BrandMark size={26} />
          <div>
            <p className="report-city">{r.city.name}</p>
            <h2>
              {t("reports.title")} · {formatDate(r.start, lang)} – {formatDate(endInclusive, lang)}
            </h2>
          </div>
        </div>
        <p className="muted small">{t("reports.generated", { date: formatDateTime(new Date().toISOString(), lang) })}</p>
      </header>

      <p className="report-summary">
        {[
          t("reports.summaryFlights", { count: r.flights.flights }),
          t("reports.summaryCandidates", { count: r.new_candidates }),
          t("reports.summaryDecisions", { count: r.decisions }),
        ].join(" · ")}
      </p>

      <div className="card stat-strip">
        <div className="stat">
          <span className="stat-label">{t("reports.flights")}</span>
          <span className="stat-value">{n(r.flights.flights)}</span>
          <Delta now={r.flights.flights} before={r.previous.flights} lang={lang} />
        </div>
        <div className="stat">
          <span className="stat-label">{t("reports.candidates")}</span>
          <span className="stat-value">{n(r.new_candidates)}</span>
          <Delta now={r.new_candidates} before={r.previous.new_candidates} lang={lang} />
        </div>
        <div className="stat">
          <span className="stat-label">{t("reports.decisions")}</span>
          <span className="stat-value">{n(r.decisions)}</span>
          <Delta now={r.decisions} before={r.previous.decisions} lang={lang} />
        </div>
        <div className="stat">
          <span className="stat-label">{t("reports.confirmedShare")}</span>
          <span className="stat-value">{pct(r.precision)}</span>
          <span className="muted small">
            {n(r.confirmed)} / {n(r.confirmed + r.false_alarms)}
          </span>
        </div>
      </div>

      <div className="grid-2">
        <section className="card">
          <h3>{t("reports.workOrders")}</h3>
          <dl className="dl">
            {(
              [
                ["opened", r.work_orders.opened],
                ["resolved", r.work_orders.resolved],
                ["openNow", r.work_orders.open_now],
                ["overdue", r.work_orders.overdue],
              ] as [string, number][]
            ).map(([k, v]) => (
              <div key={k}>
                <dt>{t(`reports.${k}`)}</dt>
                <dd className={`mono ${k === "overdue" && v > 0 ? "text-danger" : ""}`}>{n(v)}</dd>
              </div>
            ))}
          </dl>
        </section>
        <section className="card">
          <h3>{t("reports.reasons")}</h3>
          {reasons.length ? (
            <ul className="bars">
              {reasons.map(([k, c]) => (
                <li key={k}>
                  <span className="bar-label">{k === "unspecified" ? t("overview.week.unspecified") : t(`review.reasons.${k}`, { defaultValue: k })}</span>
                  <span className="bar-track">
                    <span className="bar-fill" style={{ width: `${(c / max(reasons)) * 100}%` }} />
                  </span>
                  <span className="bar-value mono">{n(c)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">{t("reports.noReasons")}</p>
          )}
        </section>
      </div>

      {types.length > 0 && (
        <section className="card">
          <h3>{t("reports.byType")}</h3>
          <ul className="bars">
            {types.map(([k, c]) => (
              <li key={k}>
                <span className="bar-label">{eventTypeLabel(t, k)}</span>
                <span className="bar-track">
                  <span className="bar-fill" style={{ width: `${(c / max(types)) * 100}%` }} />
                </span>
                <span className="bar-value mono">{n(c)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="card report-confirmed">
        <h3>
          {t("reports.confirmedMap")} · {n(r.confirmed_events.length)}
        </h3>
        {r.confirmed_events.length === 0 ? (
          <p className="muted">{t("reports.noConfirmed")}</p>
        ) : (
          <div className="report-map-grid">
            {located.length > 0 && <EventMap events={located} className="map-report" />}
            <ol className="report-events">
              {r.confirmed_events.slice(0, 12).map((e) => (
                <li key={e.event_id}>
                  <Link to={`/events/${encodeURIComponent(e.event_id)}`}>{eventTypeLabel(t, e.type)}</Link>
                  <span className="muted small mono">{e.event_id}</span>
                </li>
              ))}
            </ol>
          </div>
        )}
      </section>

      {r.model_versions.length > 0 && (
        <p className="muted small">
          {t("reports.models")}: <span className="mono">{r.model_versions.join(", ")}</span>
        </p>
      )}
    </article>
  );
}
