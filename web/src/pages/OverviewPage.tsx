import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { api } from "../api/client";
import type { ReviewStats } from "../api/types";
import { ErrorState, Loading } from "../components/States";
import { eventTypeLabel, formatNumber, statusLabel } from "../lib/format";

// Below this many confirm/reject decisions a percentage is noise, not a result.
const MIN_DECISIONS = 20;

// Pilot acceptance targets from plan.md §7. Only queue precision can be
// measured from review decisions today; the rest need the gold set (phase 4).
const PILOT_TARGETS: { key: string; target: string; measure?: (s: ReviewStats) => number | null; min?: number }[] = [
  { key: "recall", target: "≥ 70%" },
  { key: "queuePrecision", target: "≥ 80%", measure: (s) => s.precision, min: 0.8 },
  { key: "top20", target: "≥ 85%" },
  { key: "falseAlarms", target: "≤ 3" },
];

export function OverviewPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const q = useQuery({ queryKey: ["kpis"], queryFn: api.kpis, refetchInterval: 60_000 });
  const week = useQuery({ queryKey: ["kpis", "review", 7], queryFn: () => api.reviewStats(7), refetchInterval: 120_000 });
  const n = (v: number) => formatNumber(v, lang);
  const pct = (v: number) => new Intl.NumberFormat(lang, { style: "percent", maximumFractionDigits: 0 }).format(v);

  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const k = q.data;

  return (
    <div className="page">
      <header className="page-head">
        <h1>{t("overview.title")}</h1>
      </header>

      <section className={`hero ${k.review_queue ? "" : "hero-clear"}`}>
        <div>
          <p className="hero-title">
            {k.review_queue ? (
              t("overview.hero", { count: k.review_queue })
            ) : (
              <>
                <CheckCircle2 size={20} aria-hidden="true" /> {t("overview.heroEmpty")}
              </>
            )}
          </p>
          <p className="hero-body">{t("overview.heroBody", { today: n(k.today_total), open: n(k.open_work_orders) })}</p>
        </div>
        {k.review_queue > 0 && (
          <Link to="/review" className="btn btn-primary btn-lg">
            {t("overview.startReview")} <ArrowRight size={17} aria-hidden="true" />
          </Link>
        )}
      </section>

      {week.data && <WeekSection s={week.data} />}

      <div className="grid-2">
        <BreakdownCard title={t("overview.byStatus")} rows={Object.entries(k.by_status).map(([s, c]) => [statusLabel(t, s), c])} lang={lang} />
        <BreakdownCard title={t("overview.byType")} rows={Object.entries(k.by_type).map(([ty, c]) => [eventTypeLabel(t, ty), c])} lang={lang} />
      </div>

      <section className="card">
        <div className="card-head">
          <h3>{t("overview.targetsTitle")}</h3>
          <p className="muted small">{t("overview.pilotTargetsNote")}</p>
        </div>
        <table className="table table-plain">
          <thead>
            <tr>
              <th>{t("overview.targetCol.metric")}</th>
              <th className="num">{t("overview.targetCol.target")}</th>
              <th className="num">{t("overview.targetCol.now")}</th>
              <th className="num">{t("overview.targetCol.status")}</th>
            </tr>
          </thead>
          <tbody>
            {PILOT_TARGETS.map((p) => {
              const value = p.measure && week.data ? p.measure(week.data) : null;
              const enough = !!week.data && week.data.confirmed + week.data.false_alarms >= MIN_DECISIONS;
              const state = value == null ? "pending" : !enough ? "few" : value >= (p.min ?? 0) ? "met" : "missed";
              return (
                <tr key={p.key}>
                  <td data-label={t("overview.targetCol.metric")}>{t(`overview.targets.${p.key}`)}</td>
                  <td data-label={t("overview.targetCol.target")} className="num mono">
                    {p.target}
                  </td>
                  <td data-label={t("overview.targetCol.now")} className="num mono">
                    {value != null ? pct(value) : "—"}
                  </td>
                  <td data-label={t("overview.targetCol.status")} className="num">
                    <span className={`target target-${state}`}>{t(`overview.targetStatus.${state}`)}</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function WeekSection({ s }: { s: ReviewStats }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const n = (v: number) => formatNumber(v, lang);
  const enough = s.confirmed + s.false_alarms >= MIN_DECISIONS;
  const pct = s.precision != null ? new Intl.NumberFormat(lang, { style: "percent", maximumFractionDigits: 0 }).format(s.precision) : "—";
  const h = s.median_hours_to_decision;
  const median =
    h == null
      ? "—"
      : h < 1
        ? t("overview.week.minutes", { value: n(Math.round(h * 60)) })
        : h < 48
          ? t("overview.week.hours", { value: n(Math.round(h * 10) / 10) })
          : t("overview.week.days", { value: n(Math.round(h / 24)) });
  const reasons = Object.entries(s.false_alarm_reasons).map(
    ([r, c]) => [r === "unspecified" ? t("overview.week.unspecified") : t(`review.reasons.${r}`, { defaultValue: r }), c] as [string, number],
  );
  const stats: { label: string; value: string; hint?: string; tone?: string }[] = [
    { label: t("overview.week.decisions"), value: n(s.decisions) },
    {
      label: t("overview.week.precision"),
      value: pct,
      hint: t("overview.week.precisionHint"),
      tone: s.precision != null && enough ? (s.precision >= 0.8 ? "text-ok" : "text-warn") : undefined,
    },
    { label: t("overview.week.falseAlarms"), value: n(s.false_alarms) },
    { label: t("overview.week.medianTime"), value: median },
    { label: t("overview.week.flights"), value: n(s.flights) },
  ];
  return (
    <section className="week">
      <h2 className="section-title">{t("overview.week.title")}</h2>
      <div className="card stat-strip">
        {stats.map((x) => (
          <div key={x.label} className="stat" title={x.hint}>
            <span className="stat-label">{x.label}</span>
            <span className={`stat-value ${x.tone ?? ""}`}>{x.value}</span>
          </div>
        ))}
      </div>
      {reasons.length > 0 && <BreakdownCard title={t("overview.week.reasons")} rows={reasons} lang={lang} />}
    </section>
  );
}

function BreakdownCard({ title, rows, lang }: { title: string; rows: [string, number][]; lang: string }) {
  const max = Math.max(1, ...rows.map(([, c]) => c));
  return (
    <section className="card">
      <h3>{title}</h3>
      <ul className="bars">
        {rows
          .sort((a, b) => b[1] - a[1])
          .map(([label, c]) => (
            <li key={label}>
              <span className="bar-label">{label}</span>
              <span className="bar-track" aria-hidden="true">
                <span className="bar-fill" style={{ width: `${(c / max) * 100}%` }} />
              </span>
              <span className="bar-value mono">{formatNumber(c, lang)}</span>
            </li>
          ))}
      </ul>
    </section>
  );
}
