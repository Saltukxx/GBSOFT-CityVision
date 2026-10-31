import { Fragment, useMemo, useState } from "react";
import { Marker, Polyline, Tooltip, useMap, useMapEvents } from "react-leaflet";
import L from "leaflet";
import { useTranslation } from "react-i18next";
import { ROUTE_COLOR } from "./EventMap";

/** [lon, lat] waypoints, GeoJSON order. */
export type Waypoints = [number, number][];

function waypointIcon(n: number, kind: "start" | "end" | "mid"): L.DivIcon {
  return L.divIcon({
    className: `cv-wp cv-wp-${kind}`,
    html: `<span>${kind === "start" ? "S" : n}</span>`,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
}

const insertIcon = L.divIcon({ className: "cv-wp-insert", html: "<span>+</span>", iconSize: [18, 18], iconAnchor: [9, 9] });

/**
 * Edit a route on the map: click to append, drag to move, drag a "+" between two
 * points to insert one, right-click a point to remove it.
 */
export function RouteEditLayer({ points, onChange, swathM }: { points: Waypoints; onChange: (p: Waypoints) => void; swathM?: number }) {
  const { t } = useTranslation();
  useMapEvents({
    click: (e) => onChange([...points, [round(e.latlng.lng), round(e.latlng.lat)]]),
  });
  const latlngs = useMemo(() => points.map(([lon, lat]) => [lat, lon] as [number, number]), [points]);

  return (
    <>
      {swathM && latlngs.length > 1 && <Swath latlngs={latlngs} widthM={swathM} />}
      {latlngs.length > 1 && (
        <>
          <Polyline positions={latlngs} pathOptions={{ color: "#ffffff", weight: 7, opacity: 0.85 }} interactive={false} />
          <Polyline positions={latlngs} pathOptions={{ color: ROUTE_COLOR, weight: 3.5, opacity: 1 }} interactive={false} />
        </>
      )}
      {latlngs.slice(1).map((b, i) => {
        const a = latlngs[i];
        const mid: [number, number] = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
        return (
          <Marker
            key={`ins-${i}-${mid.join(",")}`}
            position={mid}
            icon={insertIcon}
            draggable
            eventHandlers={{
              click: (e) => L.DomEvent.stopPropagation(e),
              dragend: (e) => {
                const ll = (e.target as L.Marker).getLatLng();
                const next = [...points];
                next.splice(i + 1, 0, [round(ll.lng), round(ll.lat)]);
                onChange(next);
              },
            }}
          >
            <Tooltip direction="top" offset={[0, -8]}>
              {t("routes.editor.insertHint")}
            </Tooltip>
          </Marker>
        );
      })}
      {latlngs.map((p, i) => (
        <Fragment key={`wp-${i}`}>
          <Marker
            position={p}
            icon={waypointIcon(i + 1, i === 0 ? "start" : i === latlngs.length - 1 ? "end" : "mid")}
            draggable
            zIndexOffset={500}
            eventHandlers={{
              click: (e) => L.DomEvent.stopPropagation(e),
              contextmenu: (e) => {
                L.DomEvent.stopPropagation(e);
                onChange(points.filter((_, j) => j !== i));
              },
              dragend: (e) => {
                const ll = (e.target as L.Marker).getLatLng();
                onChange(points.map((q, j) => (j === i ? [round(ll.lng), round(ll.lat)] : q)));
              },
            }}
          >
            <Tooltip direction="top" offset={[0, -12]}>
              {t("routes.editor.waypoint", { n: i + 1 })} · {t("routes.editor.removeHint")}
            </Tooltip>
          </Marker>
        </Fragment>
      ))}
    </>
  );
}

/** Camera footprint along the route: a translucent band `widthM` wide on the ground. */
export function Swath({ latlngs, widthM }: { latlngs: [number, number][]; widthM: number }) {
  const map = useMap();
  const [zoom, setZoom] = useState(map.getZoom());
  useMapEvents({ zoomend: () => setZoom(map.getZoom()) });
  const lat = latlngs[0][0];
  const metresPerPixel = (156543.03392 * Math.cos((lat * Math.PI) / 180)) / 2 ** zoom;
  const weight = Math.max(2, widthM / metresPerPixel);
  return (
    <Polyline
      positions={latlngs}
      pathOptions={{ color: ROUTE_COLOR, weight, opacity: 0.14, lineCap: "butt", lineJoin: "round" }}
      interactive={false}
    />
  );
}

const round = (v: number) => Math.round(v * 1e7) / 1e7;
