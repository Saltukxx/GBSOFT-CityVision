import type {
  FlightTrack,
  RoutePlanBody,
  LabelBox,
  LabelCounts,
  LabelItem,
  LabelItemDetail,
  LabelKind,
  ModelPerformance,
  WeeklyReport,
  AdminUser,
  AuditEntry,
  CitySettings,
  GeoUploadResult,
  ReviewStats,
  RouteGeo,
  WorkOrder,
  WorkOrderPatch,
  Zone,
  AuthConfig,
  Flight,
  FlightDetail,
  Route,
  CityEvent,
  EventDetail,
  EventStatus,
  Kpis,
  ReviewLabel,
  ReviewReason,
  User,
} from "./types";

const TOKEN_KEY = "cv_token";

export function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable — session lasts until reload */
  }
}

export class ApiError extends Error {
  readonly status: number;
  /** Raw `detail` from the API (string code or object). */
  readonly detail: unknown;
  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

// Called on any 401 so the app can send the user back to sign-in.
let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null): void {
  onUnauthorized = fn;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const res = await fetch(path, { ...init, headers });
  if (!res.ok) {
    let detail = res.statusText;
    let raw: unknown;
    try {
      const body = await res.json();
      raw = body?.detail;
      if (typeof raw === "string") detail = raw;
    } catch {
      /* not JSON */
    }
    if (res.status === 401 && path !== "/api/auth/login") onUnauthorized?.();
    throw new ApiError(res.status, detail, raw);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export interface EventFilters {
  status?: string;
  type?: string;
  limit?: number;
}

export const api = {
  authConfig: () => request<AuthConfig>("/api/auth/config"),

  login: (username: string, password: string) =>
    request<{ access_token: string; user: User }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),

  me: () => request<User>("/api/auth/me"),

  events: (f: EventFilters = {}) => {
    const q = new URLSearchParams({ thumbs: "true", limit: String(f.limit ?? 500) });
    if (f.status) q.set("status", f.status);
    if (f.type) q.set("type", f.type);
    return request<CityEvent[]>(`/api/events?${q}`);
  },

  event: (eventId: string) =>
    request<EventDetail>(`/api/events/${encodeURIComponent(eventId)}`),

  review: (eventId: string, label: ReviewLabel, opts: { reason?: ReviewReason; note?: string; unit?: string } = {}) =>
    request<{ status: EventStatus; work_order_id: number | null }>(
      `/api/events/${encodeURIComponent(eventId)}/review`,
      { method: "POST", body: JSON.stringify({ label, ...opts }) },
    ),

  setStatus: (eventId: string, status: EventStatus) =>
    request<CityEvent>(`/api/events/${encodeURIComponent(eventId)}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),

  kpis: () => request<Kpis>("/api/kpis"),

  routes: () => request<Route[]>("/api/routes"),

  flights: () => request<Flight[]>("/api/flights"),

  flight: (id: string) => request<FlightDetail>(`/api/flights/${encodeURIComponent(id)}`),

  createUpload: (body: { filename: string; size: number; name?: string; route_id?: string; flight_date?: string }) =>
    request<Flight>("/api/flights/uploads", { method: "POST", body: JSON.stringify(body) }),

  putChunk: (id: string, index: number, blob: Blob, signal?: AbortSignal) =>
    request<{ index: number }>(`/api/flights/uploads/${encodeURIComponent(id)}/chunks/${index}`, {
      method: "PUT",
      body: blob,
      headers: { "Content-Type": "application/octet-stream" },
      signal,
    }),

  putTelemetry: (id: string, file: File) =>
    request<{ telemetry: boolean }>(
      `/api/flights/uploads/${encodeURIComponent(id)}/telemetry?filename=${encodeURIComponent(file.name)}`,
      { method: "PUT", body: file, headers: { "Content-Type": "application/octet-stream" } },
    ),

  completeUpload: (id: string) =>
    request<Flight>(`/api/flights/uploads/${encodeURIComponent(id)}/complete`, { method: "POST" }),

  workOrders: () => request<WorkOrder[]>("/api/work-orders/board"),

  patchWorkOrder: (id: number, body: WorkOrderPatch) =>
    request<WorkOrder>(`/api/work-orders/${id}/board`, { method: "PATCH", body: JSON.stringify(body) }),

  citySettings: () => request<CitySettings>("/api/city-settings"),

  patchCitySettings: (body: Partial<Pick<CitySettings, "name" | "timezone" | "language" | "work_order_units">>) =>
    request<CitySettings>("/api/city-settings", { method: "PATCH", body: JSON.stringify(body) }),

  users: () => request<AdminUser[]>("/api/users"),

  createUser: (body: { username: string; display_name: string; role: string; password: string }) =>
    request<{ id: number; username: string }>("/api/auth/users", { method: "POST", body: JSON.stringify(body) }),

  patchUser: (username: string, body: { display_name?: string; role?: string; active?: boolean; password?: string }) =>
    request<AdminUser>(`/api/users/${encodeURIComponent(username)}`, { method: "PATCH", body: JSON.stringify(body) }),

  zones: () => request<Zone[]>("/api/zones"),

  routesGeo: () => request<RouteGeo[]>("/api/routes"),

  route: (id: string) => request<RouteGeo>(`/api/routes/${encodeURIComponent(id)}`),

  createRoute: (body: RoutePlanBody) => request<RouteGeo>("/api/routes/plan", { method: "POST", body: JSON.stringify(body) }),

  updateRoute: (id: string, body: RoutePlanBody) =>
    request<RouteGeo>(`/api/routes/${encodeURIComponent(id)}/plan`, { method: "PUT", body: JSON.stringify(body) }),

  deleteRoute: (id: string) => request<void>(`/api/routes/${encodeURIComponent(id)}`, { method: "DELETE" }),

  flightTracks: (days = 30, routeId?: string) =>
    request<FlightTrack[]>(`/api/flights/tracks?days=${days}${routeId ? `&route_id=${encodeURIComponent(routeId)}` : ""}`),

  assignRoute: (flightId: string, routeId: string | null) =>
    request<{ route_id: string | null }>(`/api/flights/${encodeURIComponent(flightId)}/route`, {
      method: "PATCH",
      body: JSON.stringify({ route_id: routeId }),
    }),

  uploadZones: (geojson: unknown) =>
    request<GeoUploadResult>("/api/zones/upload", { method: "POST", body: JSON.stringify(geojson) }),

  uploadRoutes: (geojson: unknown) =>
    request<GeoUploadResult>("/api/routes/upload", { method: "POST", body: JSON.stringify(geojson) }),

  audit: (params: { actor?: string; action?: string; before_id?: number; limit?: number }) => {
    const q = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => v !== undefined && v !== "" && q.set(k, String(v)));
    return request<AuditEntry[]>(`/api/audit/search?${q}`);
  },

  reviewStats: (days = 7) => request<ReviewStats>(`/api/kpis/review?days=${days}`),

  labellingQueue: (done: boolean, limit = 200) =>
    request<{ items: LabelItem[]; counts: LabelCounts }>(`/api/labelling/queue?done=${done}&limit=${limit}`),

  labellingClasses: () => request<string[]>("/api/labelling/classes"),

  labellingItem: (eventId: string) => request<LabelItemDetail>(`/api/labelling/items/${encodeURIComponent(eventId)}`),

  saveLabel: (eventId: string, kind: LabelKind, boxes: LabelBox[]) =>
    request<unknown>(`/api/labelling/items/${encodeURIComponent(eventId)}`, {
      method: "PUT",
      body: JSON.stringify({ kind, boxes }),
    }),

  setHoldout: (flightId: string, holdout: boolean) =>
    request<{ holdout: boolean }>(`/api/flights/${encodeURIComponent(flightId)}/holdout`, {
      method: "PATCH",
      body: JSON.stringify({ holdout }),
    }),

  modelPerformance: () => request<ModelPerformance[]>("/api/models/performance"),

  weeklyReport: (start?: string) => request<WeeklyReport>(`/api/reports/weekly${start ? `?start=${start}` : ""}`),

  cancelUpload: (id: string) =>
    request<void>(`/api/flights/uploads/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

/** Download a file from an authenticated endpoint (a plain <a href> can't send the token). */
export async function downloadAuthed(path: string, fallbackName: string): Promise<void> {
  const headers = new Headers();
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(path, { headers });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = (await res.json())?.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, typeof detail === "string" ? detail : res.statusText, detail);
  }
  const name = /filename="?([^";]+)"?/.exec(res.headers.get("Content-Disposition") ?? "")?.[1] ?? fallbackName;
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
