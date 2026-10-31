import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { ArrowRight, Maximize2, Plane, Route as RouteIcon, Shapes, X } from "lucide-react";
import type { FeatureCollection } from "geojson";
import { api } from "../api/client";
import { ConfidenceBadge, StatusPill } from "../components/Badges";
import { EventMap, STATUS_COLOR } from "../components/EventMap";
import { FilterBar, applyConfidenceFilter, useEventFilters } from "../components/FilterBar";
import { Empty, ErrorState, Loading } from "../components/States";
import { Thumb } from "../components/Thumb";
import { eventTypeLabel, formatDateTime, hasLocation, seenCount, statusLabel } from "../lib/format";

const STATUS_ORDER = ["under_review", "confirmed", "work_order_created", "false_positive", "resolved", "archived"];

export function MapPage() {
  const { t, i18n } = useTranslation();
  const filters = useEventFilters("");
  const [params] = useSearchParams();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [showZones, setShowZones] = useState(true);
  const [showTracks, setShowTracks] = useState(true);
  const [showRoutes, setShowRoutes] = useState(true);
  const [selectedTrack, setSelectedTrack] = useState<string | null>(null);

  const q = useQuery({
    queryKey: ["events", filters.status, filters.type, "map"],
    queryFn: () => api.events({ status: filters.status || undefined, type: filters.type || undefined, limit: 2000 }),
    refetchInterval: 60_000,
  });
  const zones = useQuery({ queryKey: ["zones"], queryFn: api.zones, staleTime: 300_000 });
  const tracks = useQuery({ queryKey: ["flight-tracks", 30], queryFn: () => api.flightTracks(30), staleTime: 60_000 });
  const routes = useQuery({ queryKey: ["routes-geo"], queryFn: api.routesGeo, staleTime: 300_000 });
  const track = tracks.data?.find((x) => x.id === selectedTrack);
  const trackRoute = track?.route_id ? routes.data?.find((r) => r.id === track.route_id) : undefined;

  const events = useMemo(() => applyConfidenceFilter(q.data ?? [], filters.conf), [q.data, filters.conf]);
  const located = useMemo(() => events.filter(hasLocation), [events]);
  const visible = useMemo(() => located.filter((e) => !hidden.has(e.status)), [located, hidden]);
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    located.forEach((e) => (c[e.status] = (c[e.status] ?? 0) + 1));
    return c;
  }, [located]);
  const zoneCollection = useMemo<FeatureCollection | null>(
    () =>
      zones.data?.length
        ? {
            type: "FeatureCollection",
            features: zones.data.map((z) => ({ type: "Feature", properties: { name: z.name }, geometry: z.geometry })),
          }
        : null,
    [zones.data],
  );
  const selected = events.find((e) => e.event_id === selectedId);
  const missing = events.length - located.length;

  const toggle = (s: string) =>
    setHidden((h) => {
      const n = new Set(h);
      if (n.has(s)) n.delete(s);
      else n.add(s);
      return n;
    });

  // "Open" keeps the current filters when jumping to the queue.
  const reviewLink = (id: string, status: string) => {
    const p = new URLSearchParams(params);
    p.set("e", id);
    p.set("status", status);
    return `/review?${p}`;
  };

  return (
    <div className="map-page">
      <header className="page-head map-head">
        <h1>{t("map.title")}</h1>
        <FilterBar filters={filters} events={q.data ?? []} />
        {q.data && (
          <span className="muted small map-count">
            {t("map.showing", { shown: visible.length, total: events.length })}
            {missing > 0 && ` · ${t("map.noLocation", { count: missing })}`}
          </span>
        )}
      </header>
      <div className="map-wrap">
        {q.isPending ? (
          <Loading />
        ) : q.isError ? (
          <ErrorState error={q.error} onRetry={() => q.refetch()} />
        ) : (
          <>
            <EventMap
              events={visible}
              selectedId={selectedId}
              onSelect={(id) => {
                setSelectedId(id);
                setSelectedTrack(null);
              }}
              tracks={showTracks ? tracks.data : []}
              selectedTrackId={selectedTrack}
              onSelectTrack={(id) => {
                setSelectedTrack(id);
                setSelectedId(null);
              }}
              routes={showRoutes ? routes.data : []}
              selectedRouteId={trackRoute?.id}
              zones={showZones ? zoneCollection : null}
              className="map-full"
              showFit
            />
            {located.length === 0 && (
              <div className="map-overlay">
                <Empty>{t("map.noLocated")}</Empty>
              </div>
            )}
            <aside className="map-legend" aria-label={t("map.legend")}>
              <p className="map-legend-title">{t("map.legend")}</p>
              {STATUS_ORDER.filter((s) => counts[s]).map((s) => (
                <button key={s} type="button" className="legend-row" aria-pressed={!hidden.has(s)} onClick={() => toggle(s)} title={t("map.legendHint")}>
                  <i style={{ background: STATUS_COLOR[s] }} aria-hidden="true" />
                  <span>{statusLabel(t, s)}</span>
                  <span className="legend-count">{counts[s]}</span>
                </button>
              ))}
              {!!tracks.data?.length && (
                <button type="button" className="legend-row legend-layer legend-tracks" aria-pressed={showTracks} onClick={() => setShowTracks((v) => !v)}>
                  <Plane size={13} aria-hidden="true" />
                  <span>{t("map.flightPaths")}</span>
                  <span className="legend-count">{tracks.data.length}</span>
                </button>
              )}
              {!!routes.data?.length && (
                <button type="button" className="legend-row legend-layer legend-routes" aria-pressed={showRoutes} onClick={() => setShowRoutes((v) => !v)}>
                  <RouteIcon size={13} aria-hidden="true" />
                  <span>{t("map.routes")}</span>
                  <span className="legend-count">{routes.data.length}</span>
                </button>
              )}
              {zoneCollection && (
                <button type="button" className="legend-row legend-zones" aria-pressed={showZones} onClick={() => setShowZones((v) => !v)}>
                  <Shapes size={13} aria-hidden="true" />
                  <span>{t("map.zones")}</span>
                  <span className="legend-count">{zones.data?.length}</span>
                </button>
              )}
            </aside>
            {track && !selected && (
              <aside className="map-drawer" aria-label={track.name ?? ""}>
                <div className="map-drawer-body">
                  <div className="drawer-title-row">
                    <h2>
                      <Plane size={17} aria-hidden="true" /> {track.name ?? track.id.slice(0, 8)}
                    </h2>
                    <button type="button" className="icon-btn" onClick={() => setSelectedTrack(null)} aria-label={t("common.close")}>
                      <X size={18} aria-hidden="true" />
                    </button>
                  </div>
                  <p className="muted small">
                    {t("map.flightPanel.date")} {formatDateTime(track.created_at, i18n.language)} · {t("map.flightPanel.candidates", { count: track.candidates })}
                  </p>
                  {trackRoute && (
                    <p className="small">
                      <RouteIcon size={13} aria-hidden="true" className="inline-icon" /> {t("map.flightPanel.route")}:{" "}
                      <Link to={`/routes?r=${encodeURIComponent(trackRoute.id)}`}>{trackRoute.name}</Link>
                    </p>
                  )}
                  <div className="drawer-actions">
                    <Link className="btn btn-primary" to={`/flights/${track.id}`}>
                      {t("map.flightPanel.open")} <ArrowRight size={16} aria-hidden="true" />
                    </Link>
                  </div>
                </div>
              </aside>
            )}
            {selected && (
              <aside className="map-drawer" aria-label={eventTypeLabel(t, selected.type)}>
                <div className="map-drawer-media">
                  <Thumb src={selected.thumb_url} />
                  <button type="button" className="icon-btn map-drawer-close" onClick={() => setSelectedId(null)} aria-label={t("common.close")}>
                    <X size={18} aria-hidden="true" />
                  </button>
                </div>
                <div className="map-drawer-body">
                  <h2>{eventTypeLabel(t, selected.type)}</h2>
                  <div className="event-meta">
                    <StatusPill status={selected.status} />
                    <ConfidenceBadge event={selected} />
                  </div>
                  <p className="muted small">
                    {t("map.seen", { count: seenCount(selected) })} · {formatDateTime(selected.created_at, i18n.language)}
                  </p>
                  <div className="drawer-actions">
                    <Link className="btn btn-primary" to={reviewLink(selected.event_id, selected.status)}>
                      {t("map.openInReview")} <ArrowRight size={16} aria-hidden="true" />
                    </Link>
                    <Link className="btn" to={`/events/${encodeURIComponent(selected.event_id)}`} title={t("map.openEvent")} aria-label={t("map.openEvent")}>
                      <Maximize2 size={16} aria-hidden="true" />
                    </Link>
                  </div>
                </div>
              </aside>
            )}
          </>
        )}
      </div>
    </div>
  );
}
