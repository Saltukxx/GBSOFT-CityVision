import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router-dom";
import type { CityEvent } from "../api/types";
import { confidenceLevel, eventTypeLabel, statusLabel, type ConfidenceLevel } from "../lib/format";

const STATUSES = ["under_review", "confirmed", "work_order_created", "false_positive", "resolved", "archived"];
const LEVELS: ConfidenceLevel[] = ["high", "medium", "low"];

export interface EventFiltersState {
  status: string;
  type: string;
  conf: string;
  isDefault: boolean;
  set: (key: "status" | "type" | "conf", value: string) => void;
  clear: () => void;
}

/** Filters live in the URL so the queue and map share links and survive reloads. */
export function useEventFilters(defaultStatus: string): EventFiltersState {
  const [params, setParams] = useSearchParams();
  const status = params.has("status") ? params.get("status") ?? "" : defaultStatus;
  const type = params.get("type") ?? "";
  const conf = params.get("conf") ?? "";

  return {
    status,
    type,
    conf,
    isDefault: status === defaultStatus && !type && !conf,
    set: (key, value) =>
      setParams(
        (p) => {
          const next = new URLSearchParams(p);
          next.set(key, value);
          if (key !== "status" && !value) next.delete(key);
          next.delete("e");
          return next;
        },
        { replace: true },
      ),
    clear: () => setParams(new URLSearchParams(), { replace: true }),
  };
}

export function applyConfidenceFilter(events: CityEvent[], conf: string): CityEvent[] {
  return conf ? events.filter((e) => confidenceLevel(e) === conf) : [...events];
}

export function FilterBar({ filters, events }: { filters: EventFiltersState; events: CityEvent[] }) {
  const { t } = useTranslation();
  const types = useMemo(() => {
    const s = new Set(events.map((e) => e.type).filter(Boolean));
    if (filters.type) s.add(filters.type);
    return [...s].sort();
  }, [events, filters.type]);

  return (
    <div className="filters">
      <label className="filter">
        <span className="filter-label">{t("filters.status")}</span>
        <select value={filters.status} onChange={(e) => filters.set("status", e.target.value)}>
          <option value="">{t("filters.allStatuses")}</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {statusLabel(t, s)}
            </option>
          ))}
        </select>
      </label>
      <label className="filter">
        <span className="filter-label">{t("filters.type")}</span>
        <select value={filters.type} onChange={(e) => filters.set("type", e.target.value)}>
          <option value="">{t("filters.allTypes")}</option>
          {types.map((ty) => (
            <option key={ty} value={ty}>
              {eventTypeLabel(t, ty)}
            </option>
          ))}
        </select>
      </label>
      <label className="filter">
        <span className="filter-label">{t("filters.confidence")}</span>
        <select value={filters.conf} onChange={(e) => filters.set("conf", e.target.value)}>
          <option value="">{t("filters.anyConfidence")}</option>
          {LEVELS.map((l) => (
            <option key={l} value={l}>
              {t(`confidence.${l}`)}
            </option>
          ))}
        </select>
      </label>
      {!filters.isDefault && (
        <button type="button" className="btn btn-link" onClick={filters.clear}>
          {t("filters.clear")}
        </button>
      )}
    </div>
  );
}
