/**
 * Basemap tile sources (Esri, no API key needed for display).
 *
 * NOTE for production: Esri's terms expect an ArcGIS account/API key for
 * commercial apps. Before a paid rollout, add a key (or switch to another
 * keyed provider such as MapTiler or Mapbox) — only this file changes.
 */
export type BaseLayerId = "streets" | "satellite";

export interface TileSource {
  url: string;
  attribution: string;
  /** Highest zoom the server has tiles for; above this, tiles are scaled up. */
  maxNativeZoom: number;
}

const ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services";
export const MAX_ZOOM = 20;

export const STREETS_LIGHT: TileSource = {
  url: `${ESRI}/World_Street_Map/MapServer/tile/{z}/{y}/{x}`,
  attribution: "Map &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors",
  maxNativeZoom: 19,
};

export const STREETS_DARK: TileSource = {
  url: `${ESRI}/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}`,
  attribution: "Map &copy; Esri, HERE, Garmin, &copy; OpenStreetMap contributors",
  maxNativeZoom: 16,
};

/** Street and place names drawn over the dark base. */
export const STREETS_DARK_LABELS: TileSource = {
  url: `${ESRI}/Canvas/World_Dark_Gray_Reference/MapServer/tile/{z}/{y}/{x}`,
  attribution: "",
  maxNativeZoom: 16,
};

export const SATELLITE: TileSource = {
  url: `${ESRI}/World_Imagery/MapServer/tile/{z}/{y}/{x}`,
  attribution: "Imagery &copy; Esri, Maxar, Earthstar Geographics",
  maxNativeZoom: 19,
};

/** Place names on top of satellite imagery. */
export const SATELLITE_LABELS: TileSource = {
  url: `${ESRI}/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}`,
  attribution: "",
  maxNativeZoom: 19,
};

// Full maps and the small per-event map remember their layer separately:
// satellite suits checking one spot, streets suit finding your way around.
const layerKey = (scope: string) => `cv_base_layer_${scope}`;

export function savedBaseLayer(scope: string, fallback: BaseLayerId): BaseLayerId {
  try {
    const v = localStorage.getItem(layerKey(scope));
    return v === "streets" || v === "satellite" ? v : fallback;
  } catch {
    return fallback;
  }
}

export function saveBaseLayer(scope: string, id: BaseLayerId): void {
  try {
    localStorage.setItem(layerKey(scope), id);
  } catch {
    /* per-browser convenience only */
  }
}
