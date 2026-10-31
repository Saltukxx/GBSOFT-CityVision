/** Small geodesy helpers for route planning. Coordinates are [lon, lat]. */

const R = 6_371_008.8; // mean Earth radius, metres
const rad = (d: number) => (d * Math.PI) / 180;

export function distanceM(a: [number, number], b: [number, number]): number {
  const dLat = rad(b[1] - a[1]);
  const dLon = rad(b[0] - a[0]);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a[1])) * Math.cos(rad(b[1])) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export function lengthM(coords: [number, number][]): number {
  let total = 0;
  for (let i = 1; i < coords.length; i++) total += distanceM(coords[i - 1], coords[i]);
  return total;
}

// Each waypoint costs a slow-down, turn and re-accelerate.
const TURN_SECONDS = 4;

/** Rough flight time for a route at a cruise speed (no wind, no take-off/landing). */
export function flightSeconds(coords: [number, number][], speedMs: number): number {
  if (coords.length < 2 || speedMs <= 0) return 0;
  return lengthM(coords) / speedMs + Math.max(0, coords.length - 2) * TURN_SECONDS;
}

export function formatDistance(m: number, lang: string): string {
  if (m < 1000) return `${new Intl.NumberFormat(lang, { maximumFractionDigits: 0 }).format(m)} m`;
  return `${new Intl.NumberFormat(lang, { maximumFractionDigits: 2 }).format(m / 1000)} km`;
}

/** Footprint width on the ground for a nadir camera: 2·h·tan(HFOV/2). Default HFOV fits DJI M3E/M30. */
export function swathM(altitudeM: number, hfovDeg = 73): number {
  return 2 * altitudeM * Math.tan(rad(hfovDeg / 2));
}
