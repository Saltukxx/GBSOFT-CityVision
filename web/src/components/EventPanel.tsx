import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Maximize2 } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { CityEvent, EventDetail } from "../api/types";
import { useCurrentUser } from "../auth/AuthContext";
import { eventTypeLabel, formatCoord, formatDateTime, hasLocation, seenCount } from "../lib/format";
import type { Decision } from "../lib/useDecision";
import { ConfidenceBadge, StatusPill } from "./Badges";
import { DecisionBar } from "./DecisionBar";
import { EventMap } from "./EventMap";
import { EvidenceViewer } from "./EvidenceViewer";
import { ErrorState, Loading } from "./States";

interface Props {
  eventId: string;
  onDecide: (ev: CityEvent, d: Decision) => void;
  busy: boolean;
  keyboard?: boolean;
  /** Compact = inside the review queue; full = standalone event page. */
  variant: "compact" | "full";
}

export function EventPanel({ eventId, onDecide, busy, keyboard = false, variant }: Props) {
  const { t } = useTranslation();
  const { canDecide } = useCurrentUser();
  const q = useQuery({ queryKey: ["event", eventId], queryFn: () => api.event(eventId) });

  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} notFoundText={t("event.notFound")} />;
  const ev = q.data;
  const title = eventTypeLabel(t, ev.type);

  return (
    <article className={`event-panel event-panel-${variant}`}>
      <header className="event-head">
        <div>
          <h2 className="event-title">{title}</h2>
          <div className="event-meta">
            <StatusPill status={ev.status} />
            <ConfidenceBadge event={ev} />
            <span className="muted">{t("review.seen", { count: seenCount(ev) })}</span>
          </div>
        </div>
        {variant === "compact" && (
          <Link className="btn btn-ghost btn-sm" to={`/events/${encodeURIComponent(ev.event_id)}`}>
            <Maximize2 size={15} aria-hidden="true" /> {t("review.openFull")}
          </Link>
        )}
      </header>

      <EvidenceViewer media={ev.media ?? []} alt={title} />

      {canDecide ? (
        <section className="event-decision" aria-label={t("event.decision")}>
          <DecisionBar onDecide={(d) => onDecide({ ...ev, observations: seenCount(ev) }, d)} busy={busy} keyboard={keyboard} resetKey={ev.event_id} />
        </section>
      ) : (
        <p className="muted">{t("review.readOnly")}</p>
      )}

      <div className={variant === "full" ? "event-grid" : "event-stack"}>
        <Location ev={ev} />
        <Details ev={ev} />
        {variant === "full" && <History ev={ev} />}
      </div>
    </article>
  );
}

function Location({ ev }: { ev: EventDetail }) {
  const { t, i18n } = useTranslation();
  return (
    <section className="card">
      <h3>{t("event.location")}</h3>
      {hasLocation(ev) ? (
        <>
          <EventMap events={[ev]} selectedId={ev.event_id} single className="map-mini" />
          <p className="mono small">{formatCoord(ev.lat, ev.lon, i18n.language)}</p>
          <p className="muted small">{t("event.locationNote")}</p>
        </>
      ) : (
        <p className="muted">{t("event.noLocation")}</p>
      )}
    </section>
  );
}

function Details({ ev }: { ev: EventDetail }) {
  const { t, i18n } = useTranslation();
  const rows: [string, string][] = [
    [t("event.firstSeen"), formatDateTime(ev.created_at, i18n.language)],
    [t("event.lastSeen"), formatDateTime(ev.updated_at, i18n.language)],
    [t("event.observations"), String(seenCount(ev))],
    [t("event.zone"), ev.zone_id || t("common.none")],
    [t("event.model"), ev.model_version || t("common.none")],
    [t("event.eventId"), ev.event_id],
  ];
  return (
    <section className="card">
      <h3>{t("event.details")}</h3>
      <dl className="dl">
        {rows.map(([k, v]) => (
          <div key={k}>
            <dt>{k}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

const LABEL_TO_KEY: Record<string, string> = {
  correct: "review.done.confirm",
  confirmed: "review.done.confirm",
  wrong: "review.done.falseAlarm",
  false_positive: "review.done.falseAlarm",
  unsure: "review.done.unsure",
  work_order: "review.done.workOrder",
};

function History({ ev }: { ev: EventDetail }) {
  const { t, i18n } = useTranslation();
  return (
    <section className="card">
      <h3>{t("event.history")}</h3>
      {ev.reviews?.length ? (
        <ol className="history">
          {ev.reviews.map((r) => {
            const what = LABEL_TO_KEY[r.label] ? t(LABEL_TO_KEY[r.label]) : r.label;
            const reason = r.reason ? ` · ${t(`review.reasons.${r.reason}`, { defaultValue: r.reason })}` : "";
            return (
              <li key={r.id}>
                <span>{t("event.historyEntry", { who: r.reviewer, what: what + reason })}</span>
                <time className="muted small">{formatDateTime(r.created_at, i18n.language)}</time>
                {r.note && <p className="small">{r.note}</p>}
              </li>
            );
          })}
        </ol>
      ) : (
        <p className="muted">{t("event.noHistory")}</p>
      )}
    </section>
  );
}
