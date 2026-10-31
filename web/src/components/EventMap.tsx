import { Fragment, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { GeoJSON, MapContainer, Polyline, TileLayer, Tooltip, useMap } from "react-leaflet";
import L, { latLngBounds, type LatLngTuple } from "leaflet";
import "leaflet/dist/leaflet.css";
import "leaflet.markercluster";
import "leaflet.markercluster/dist/MarkerCluster.css";
import type { FeatureCollection } from "geojson";
import { useTranslation } from "react-i18next";
import { Layers, Maximize, Satellite, Map as MapIcon } from "lucide-react";
import type { CityEvent, FlightTrack, RouteGeo } from "../api/types";
import { eventTypeLabel, hasLocation, statusLabel } from "../lib/format";
import {
  MAX_ZOOM,
  SATELLITE,
  SATELLITE_LABELS,
  STREETS_DARK,
  STREETS_DARK_LABELS,
  STREETS_LIGHT,
  type TileSource,
  saveBaseLayer,
  savedBaseLayer,
  type BaseLayerId,
} from "../lib/mapLayers";

// Marker colours follow the status tokens in styles.css.
export const STATUS_COLOR: Record<string, string> = {
  under_review: "#d97706",
  confirmed: "#059669",
  work_order_created: "#2563eb",
  false_positive: "#6b7280",
  resolved: "#64748b",
  archived: "#94a3b8",
};

// Small glyphs drawn inside markers: waste vs road surface vs anything else.
const WASTE = new Set(["overflowing_container", "street_waste", "waste", "illegal_dumping"]);
const ROAD = new Set(["pothole", "road_crack", "road_damage"]);
const GLYPH_WASTE =
  '<path d="M4 7h16M9 7V4.5h6V7M6.5 7l1 12.5h9l1-12.5" fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>';
const GLYPH_ROAD =
  '<path d="M12 4 21 19H3Z" fill="none" stroke="#fff" stroke-width="2.2" stroke-linejoin="round"/><path d="M12 10v4" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/>';
const GLYPH_DOT = '<circle cx="12" cy="12" r="3.2" fill="#fff"/>';

type MapEvent = Pick<CityEvent, "event_id" | "type" | "lat" | "lon" | "status">;

function markerIcon(ev: MapEvent, selected: boolean): L.DivIcon {
  const color = STATUS_COLOR[ev.status] ?? "#6b7280";
  const glyph = WASTE.has(ev.type) ? GLYPH_WASTE : ROAD.has(ev.type) ? GLYPH_ROAD : GLYPH_DOT;
  const size = selected ? 34 : 26;
  const g = Math.round(size * 0.55);
  return L.divIcon({
    className: `cv-marker${selected ? " cv-marker-selected" : ""}`,
    html: `<span style="--c:${color}"><svg viewBox="0 0 24 24" width="${g}" height="${g}">${glyph}</svg></span>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  });
}

function clusterIcon(cluster: L.MarkerCluster): L.DivIcon {
  const pending = cluster.getAllChildMarkers().some((m) => (m.options as { status?: string }).status === "under_review");
  const n = cluster.getChildCount();
  const size = n < 10 ? 34 : n < 100 ? 40 : 46;
  return L.divIcon({
    className: `cv-cluster${pending ? " cv-cluster-pending" : ""}`,
    html: `<span>${n}</span>`,
    iconSize: [size, size],
  });
}

/** Points in the main group: within 40 km of the median, so one stray point on
 *  another continent doesn't zoom the whole city out to a world view. */
function mainCluster(points: LatLngTuple[]): LatLngTuple[] {
  if (points.length < 3) return points;
  const med = (xs: number[]) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];
  const c = L.latLng(med(points.map((p) => p[0])), med(points.map((p) => p[1])));
  const near = points.filter((p) => c.distanceTo(p) < 40_000);
  return near.length ? near : points;
}

function useDarkScheme(): boolean {
  const q = "(prefers-color-scheme: dark)";
  const [dark, setDark] = useState(() => window.matchMedia(q).matches);
  useEffect(() => {
    const m = window.matchMedia(q);
    const on = () => setDark(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return dark;
}

function Markers({
  events,
  selectedId,
  onSelect,
  cluster,
}: {
  events: (MapEvent & { lat: number; lon: number })[];
  selectedId?: string | null;
  onSelect?: (id: string) => void;
  cluster: boolean;
}) {
  const map = useMap();
  const { t } = useTranslation();
  const group = useRef<L.LayerGroup | null>(null);

  useEffect(() => {
    const g: L.LayerGroup = cluster
      ? L.markerClusterGroup({
          iconCreateFunction: clusterIcon,
          showCoverageOnHover: false,
          spiderfyOnMaxZoom: true,
          maxClusterRadius: 48,
          disableClusteringAtZoom: 18,
        })
      : L.layerGroup();
    g.addTo(map);
    group.current = g;
    return () => {
      g.remove();
      group.current = null;
    };
  }, [map, cluster]);

  useEffect(() => {
    const g = group.current;
    if (!g) return;
    g.clearLayers();
    for (const ev of events) {
      const selected = ev.event_id === selectedId;
      const label = `${eventTypeLabel(t, ev.type)} · ${statusLabel(t, ev.status)}`;
      const m = L.marker([ev.lat, ev.lon], {
        icon: markerIcon(ev, selected),
        zIndexOffset: selected ? 1000 : 0,
        keyboard: true,
        alt: label,
        // Read by the cluster icon to colour groups that still need review.
        status: ev.status,
      } as L.MarkerOptions & { status: string });
      if (onSelect) m.on("click", () => onSelect(ev.event_id));
      m.bindTooltip(label, { direction: "top", offset: [0, -14] });
      g.addLayer(m);
    }
  }, [events, selectedId, onSelect, t, cluster]);

  return null;
}

function FitBounds({ points, single, fitKey }: { points: LatLngTuple[]; single: boolean; fitKey: number }) {
  const map = useMap();
  const key = points.map((p) => p.join(",")).join("|");
  useEffect(() => {
    if (!points.length) return;
    if (single || points.length === 1) map.setView(points[0], 18);
    else map.fitBounds(latLngBounds(mainCluster(points)), { padding: [48, 48], maxZoom: 18 });
    // Refit only when the set of points changes or the user asks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, single, map, fitKey]);
  return null;
}

/** Keep tiles filling the box when its size changes (e.g. the menu collapses). */
function AutoResize() {
  const map = useMap();
  useEffect(() => {
    const ro = new ResizeObserver(() => map.invalidateSize({ animate: false }));
    ro.observe(map.getContainer());
    return () => ro.disconnect();
  }, [map]);
  return null;
}

/** Drop the "Leaflet" flag from the attribution line; the data credits stay. */
function NoAttributionPrefix() {
  const map = useMap();
  useEffect(() => {
    map.attributionControl?.setPrefix(false);
  }, [map]);
  return null;
}

function PanToSelected({ point }: { point: LatLngTuple | null }) {
  const map = useMap();
  const key = point ? point.join(",") : "";
  useEffect(() => {
    if (point && !map.getBounds().pad(-0.15).contains(point)) map.panTo(point, { animate: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, map]);
  return null;
}

// Distinct but calm colours for overlapping flight paths.
export const TRACK_COLORS = ["#0ea5e9", "#14b8a6", "#6366f1", "#22c55e", "#f472b6", "#eab308"];
export const ROUTE_COLOR = "#7c3aed";

function routeLatLngs(r: RouteGeo): LatLngTuple[] {
  const g = r.geometry as { type?: string; coordinates?: number[][] } | null | undefined;
  return g?.type === "LineString" && g.coordinates ? g.coordinates.map(([lon, lat]) => [lat, lon] as LatLngTuple) : [];
}

interface Props {
  events: MapEvent[];
  /** Flown GPS tracks to draw (flight-path layer). */
  tracks?: FlightTrack[];
  selectedTrackId?: string | null;
  onSelectTrack?: (id: string) => void;
  /** Planned routes to draw (dashed). */
  routes?: RouteGeo[];
  selectedRouteId?: string | null;
  onSelectRoute?: (id: string) => void;
  /** Extra layers drawn inside the map (e.g. the route editor). */
  children?: ReactNode;
  selectedId?: string | null;
  onSelect?: (eventId: string) => void;
  /** Single-event mini map: fixed close zoom, no clustering. */
  single?: boolean;
  className?: string;
  /** Flight path as [lon, lat] pairs (GeoJSON order). */
  track?: [number, number][];
  zones?: FeatureCollection | null;
  /** Show the fit-to-events button (full maps). */
  showFit?: boolean;
}

export function EventMap({
  events,
  selectedId,
  onSelect,
  single = false,
  className,
  track,
  zones,
  showFit = false,
  tracks,
  selectedTrackId,
  onSelectTrack,
  routes,
  selectedRouteId,
  onSelectRoute,
  children,
}: Props) {
  const { t } = useTranslation();
  const dark = useDarkScheme();
  const scope = single ? "mini" : "full";
  const [base, setBase] = useState<BaseLayerId>(() => savedBaseLayer(scope, single ? "satellite" : "streets"));
  const [fitKey, setFitKey] = useState(0);

  const located = useMemo(() => events.filter(hasLocation), [events]);
  const path = useMemo(() => (track ?? []).map(([lon, lat]) => [lat, lon] as LatLngTuple), [track]);
  const routeLines = useMemo(() => (routes ?? []).map((r) => ({ r, pts: routeLatLngs(r) })).filter((x) => x.pts.length > 1), [routes]);
  const trackLines = useMemo(
    () => (tracks ?? []).map((tr, i) => ({ tr, color: TRACK_COLORS[i % TRACK_COLORS.length], pts: tr.track.map(([lon, lat]) => [lat, lon] as LatLngTuple) })),
    [tracks],
  );
  // Frame events first; with no events, frame the paths and routes shown.
  const points = useMemo(() => {
    const own = [...located.map((e) => [e.lat, e.lon] as LatLngTuple), ...path];
    if (own.length) return own;
    return [...trackLines.flatMap((x) => x.pts), ...routeLines.flatMap((x) => x.pts)];
  }, [located, path, trackLines, routeLines]);
  const center: LatLngTuple = points[0] ?? [39.0, 35.0];
  const selected = located.find((e) => e.event_id === selectedId);

  const tile = (src: TileSource, key: string) => (
    <TileLayer key={key} url={src.url} attribution={src.attribution} maxNativeZoom={src.maxNativeZoom} maxZoom={MAX_ZOOM} />
  );
  const chooseBase = (id: BaseLayerId) => {
    setBase(id);
    saveBaseLayer(scope, id);
  };

  return (
    <div className={`map-shell ${single ? "map-shell-mini" : ""} ${className ?? ""}`}>
      <MapContainer center={center} zoom={points.length ? 16 : 5} maxZoom={MAX_ZOOM} className="map" scrollWheelZoom={!single} zoomControl={!single} attributionControl>
        {base === "satellite"
          ? [tile(SATELLITE, "sat"), tile(SATELLITE_LABELS, "sat-labels")]
          : dark
            ? [tile(STREETS_DARK, "dark"), tile(STREETS_DARK_LABELS, "dark-labels")]
            : tile(STREETS_LIGHT, "light")}
        {zones && zones.features.length > 0 && (
          <GeoJSON
            key={zones.features.length}
            data={zones}
            style={{ color: "#c2410c", weight: 2, fillColor: "#f59e0b", fillOpacity: 0.12, dashArray: "5 4" }}
            onEachFeature={(f, layer) => {
              if (f.properties?.name) layer.bindTooltip(String(f.properties.name), { sticky: true });
            }}
          />
        )}
        {routeLines.map(({ r, pts }) => {
          const sel = r.id === selectedRouteId;
          return (
            <Fragment key={`route-${r.id}`}>
              <Polyline positions={pts} pathOptions={{ color: "#ffffff", weight: sel ? 9 : 6, opacity: 0.7 }} interactive={false} />
              <Polyline
                positions={pts}
                pathOptions={{ color: ROUTE_COLOR, weight: sel ? 4.5 : 3, opacity: sel ? 1 : 0.8, dashArray: "10 7" }}
                eventHandlers={onSelectRoute ? { click: () => onSelectRoute(r.id) } : undefined}
              >
                <Tooltip sticky>{r.name}</Tooltip>
              </Polyline>
            </Fragment>
          );
        })}
        {trackLines.map(({ tr, color, pts }) => {
          const sel = tr.id === selectedTrackId;
          const dim = !!selectedTrackId && !sel;
          return (
            <Fragment key={`track-${tr.id}`}>
              {sel && <Polyline positions={pts} pathOptions={{ color: "#ffffff", weight: 8, opacity: 0.85 }} interactive={false} />}
              <Polyline
                positions={pts}
                pathOptions={{ color, weight: sel ? 4.5 : 3, opacity: dim ? 0.3 : 0.9 }}
                eventHandlers={onSelectTrack ? { click: () => onSelectTrack(tr.id) } : undefined}
              >
                <Tooltip sticky>{tr.name ?? tr.id.slice(0, 8)}</Tooltip>
              </Polyline>
            </Fragment>
          );
        })}
        {path.length > 1 && (
          <>
            <Polyline positions={path} pathOptions={{ color: "#ffffff", weight: 7, opacity: 0.75 }} />
            <Polyline positions={path} pathOptions={{ color: "#0b6e84", weight: 3.5, opacity: 1 }} />
          </>
        )}
        <Markers events={located} selectedId={selectedId} onSelect={onSelect} cluster={!single && located.length > 1} />
        <FitBounds points={points} single={single} fitKey={fitKey} />
        <NoAttributionPrefix />
        <AutoResize />
        {children}
        {!single && <PanToSelected point={selected ? [selected.lat, selected.lon] : null} />}
      </MapContainer>

      <div className="map-tools" role="group" aria-label={t("map.layers")}>
        <Layers className="map-tools-icon" size={14} aria-hidden="true" />
        <button type="button" aria-pressed={base === "streets"} onClick={() => chooseBase("streets")} title={t("map.streets")}>
          <MapIcon size={14} aria-hidden="true" />
          <span>{t("map.streets")}</span>
        </button>
        <button type="button" aria-pressed={base === "satellite"} onClick={() => chooseBase("satellite")} title={t("map.satellite")}>
          <Satellite size={14} aria-hidden="true" />
          <span>{t("map.satellite")}</span>
        </button>
      </div>
      {showFit && points.length > 0 && (
        <button type="button" className="map-fit" onClick={() => setFitKey((k) => k + 1)} title={t("map.fit")} aria-label={t("map.fit")}>
          <Maximize size={16} aria-hidden="true" />
        </button>
      )}
    </div>
  );
}
