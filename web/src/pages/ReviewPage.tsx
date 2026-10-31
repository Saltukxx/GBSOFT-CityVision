import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { ArrowLeft } from "lucide-react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { CityEvent, EventStatus } from "../api/types";
import { ConfidenceBadge, StatusPill } from "../components/Badges";
import { isTypingTarget } from "../components/DecisionBar";
import { EventPanel } from "../components/EventPanel";
import { FilterBar, applyConfidenceFilter, useEventFilters } from "../components/FilterBar";
import { Empty, ErrorState, Loading } from "../components/States";
import { Thumb } from "../components/Thumb";
import { byConfidenceDesc, eventTypeLabel, formatDateTime, seenCount } from "../lib/format";
import { useDecision, useUndoLast } from "../lib/useDecision";

export function ReviewPage() {
  const { t, i18n } = useTranslation();
  const [params, setParams] = useSearchParams();
  const filters = useEventFilters("under_review");
  const selectedId = params.get("e");

  const q = useQuery({
    queryKey: ["events", filters.status, filters.type],
    queryFn: () => api.events({ status: filters.status || undefined, type: filters.type || undefined }),
    refetchInterval: 60_000,
  });

  const list = useMemo(
    () => applyConfidenceFilter(q.data ?? [], filters.conf).sort(byConfidenceDesc),
    [q.data, filters.conf],
  );

  const select = useCallback(
    (id: string | null) => {
      setParams(
        (p) => {
          const next = new URLSearchParams(p);
          if (id) next.set("e", id);
          else next.delete("e");
          return next;
        },
        { replace: true },
      );
    },
    [setParams],
  );

  // On desktop, open the first event when nothing is selected.
  const isWide = useIsWide();
  useEffect(() => {
    if (isWide && !selectedId && list.length) select(list[0].event_id);
  }, [isWide, list, selectedId, select]);

  const lastDecision = useRef<{ eventId: string; status: EventStatus } | null>(null);
  const undoLast = useUndoLast();

  const decision = useDecision((ev) => {
    lastDecision.current = { eventId: ev.event_id, status: ev.status };
    const idx = list.findIndex((e) => e.event_id === ev.event_id);
    const next = list[idx + 1] ?? list[idx - 1] ?? null;
    select(next ? next.event_id : null);
  });

  // J / K to move, Z to undo the last decision.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTypingTarget(e.target)) return;
      if (document.querySelector("dialog[open]")) return;
      const k = e.key.toLowerCase();
      if (k === "j" || k === "k") {
        e.preventDefault();
        const idx = list.findIndex((x) => x.event_id === selectedId);
        const target = k === "j" ? list[Math.min(idx + 1, list.length - 1)] : list[Math.max(idx - 1, 0)];
        if (target) select(target.event_id);
      } else if (k === "z" && lastDecision.current) {
        e.preventDefault();
        undoLast.mutate(lastDecision.current);
        select(lastDecision.current.eventId);
        lastDecision.current = null;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [list, selectedId, select, undoLast]);

  // Keep the selected row visible while moving with J / K.
  useEffect(() => {
    if (!selectedId) return;
    document.getElementById(`row-${selectedId}`)?.scrollIntoView({ block: "nearest" });
  }, [selectedId]);

  // The selected event may briefly be outside the list (just decided / undone);
  // the panel loads it by id, so keep showing it.
  const selected = selectedId;

  return (
    <div className={`review ${selected ? "has-selection" : ""}`}>
      <section className="review-list" aria-label={t("review.title")}>
        <header className="page-head">
          <h1>{t("review.title")}</h1>
          {q.data && <span className="muted">{t("review.count", { count: list.length })}</span>}
        </header>
        <FilterBar filters={filters} events={q.data ?? []} />
        {q.isPending ? (
          <Loading />
        ) : q.isError ? (
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        ) : list.length === 0 ? (
          <Empty>{filters.isDefault ? t("review.empty") : t("review.emptyFiltered")}</Empty>
        ) : (
          <ul className="rows" role="listbox" aria-label={t("review.title")}>
            {list.map((ev) => (
              <EventRow key={ev.event_id} ev={ev} selected={ev.event_id === selected} onSelect={() => select(ev.event_id)} lang={i18n.language} />
            ))}
          </ul>
        )}
        <p className="shortcuts muted small">{t("review.shortcuts")}</p>
      </section>

      <section className="review-detail">
        {selected ? (
          <>
            <button type="button" className="btn btn-ghost back-mobile" onClick={() => select(null)}>
              <ArrowLeft size={16} aria-hidden="true" /> {t("event.back")}
            </button>
            <EventPanel
              key={selected}
              eventId={selected}
              variant="compact"
              keyboard
              busy={decision.isPending}
              onDecide={(event, d) => decision.mutate({ event, decision: d })}
            />
          </>
        ) : (
          <Empty>{list.length ? t("review.selectHint") : null}</Empty>
        )}
      </section>
    </div>
  );
}

function EventRow({ ev, selected, onSelect, lang }: { ev: CityEvent; selected: boolean; onSelect: () => void; lang: string }) {
  const { t } = useTranslation();
  return (
    <li id={`row-${ev.event_id}`} role="option" aria-selected={selected}>
      <button type="button" className={`row ${selected ? "row-selected" : ""}`} onClick={onSelect}>
        <Thumb src={ev.thumb_url} />
        <span className="row-body">
          <span className="row-title">{eventTypeLabel(t, ev.type)}</span>
          <span className="row-meta">
            <ConfidenceBadge event={ev} />
            <span className="muted small">{t("review.seen", { count: seenCount(ev) })}</span>
          </span>
          <span className="row-meta">
            <StatusPill status={ev.status} />
            <span className="muted small">{formatDateTime(ev.created_at, lang)}</span>
          </span>
        </span>
      </button>
    </li>
  );
}

function useIsWide(): boolean {
  const query = "(min-width: 900px)";
  const [wide, setWide] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const m = window.matchMedia(query);
    const on = () => setWide(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return wide;
}
