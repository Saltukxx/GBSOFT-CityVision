import type { Geometry } from "geojson";

export type EventStatus =
  | "under_review"
  | "confirmed"
  | "false_positive"
  | "work_order_created"
  | "resolved"
  | "archived";

export type Role = "viewer" | "operator" | "admin" | "superadmin";

export interface User {
  username: string;
  display_name?: string | null;
  role: Role;
  city_id?: string | null;
}

export interface AuthConfig {
  login_enabled: boolean;
  auth_required: boolean;
}

export interface CityEvent {
  id: number;
  event_id: string;
  run_id?: string | null;
  type: string;
  lat?: number | null;
  lon?: number | null;
  severity?: string | null;
  confidence?: number | null;
  confidence_band?: string | null;
  observations?: number | null;
  status: EventStatus;
  model_version?: string | null;
  zone_id?: string | null;
  first_seen_ms?: number | null;
  last_seen_ms?: number | null;
  city_id?: string | null;
  created_at?: string;
  updated_at?: string;
  thumb_url?: string | null;
}

export interface EventMedia {
  id: number;
  event_id: string;
  media_type: "image" | "crop" | "clip" | "json" | string;
  content_type?: string | null;
  url?: string;
}

export interface Review {
  id: number;
  event_id: string;
  label: string;
  reason?: string | null;
  note?: string | null;
  reviewer: string;
  created_at: string;
}

// GET /events/{id} replaces the `observations` count with the observation rows.
export interface EventDetail extends Omit<CityEvent, "observations"> {
  observations?: number | unknown[] | null;
  media: EventMedia[];
  reviews: Review[];
}

export type ReviewLabel = "correct" | "wrong" | "unsure" | "work_order";

export const REVIEW_REASONS = [
  "manhole",
  "shadow",
  "vehicle",
  "marking",
  "vegetation",
  "duplicate",
  "other",
] as const;
export type ReviewReason = (typeof REVIEW_REASONS)[number];

export interface Kpis {
  events_total: number;
  review_queue: number;
  by_type: Record<string, number>;
  by_status: Record<string, number>;
  today_total: number;
  today_by_type: Record<string, number>;
  open_work_orders: number;
}

export type FlightStatus =
  | "uploading"
  | "received"
  | "queued"
  | "analyzing"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "duplicate";

export const ACTIVE_FLIGHT_STATUSES: FlightStatus[] = ["uploading", "received", "queued", "analyzing"];

export interface Flight {
  id: string;
  name: string;
  filename?: string | null;
  source: "upload" | "flighthub" | "device";
  device_name?: string | null;
  city_id?: string | null;
  route_id?: string | null;
  flight_date?: string | null;
  uploaded_by?: string | null;
  bytes?: number | null;
  status: FlightStatus;
  progress?: number | null;
  error?: string | null;
  has_telemetry: boolean;
  trajectory_warning?: string | null;
  duplicate_of?: string | null;
  candidates: number;
  holdout: boolean;
  run_id?: number | null;
  created_at: string;
  updated_at: string;
  processing_started_at?: string | null;
  processing_finished_at?: string | null;
  upload?: { chunk_size: number; chunks: number; received: number[] };
}

export interface FlightDetail extends Flight {
  track: [number, number][];
  event_ids: string[];
  adherence?: Adherence | null;
}

export interface Route {
  id: string;
  name: string;
}

export type WorkOrderStatus = "created" | "assigned" | "in_progress" | "resolved" | "cancelled";
export const WORK_ORDER_COLUMNS: WorkOrderStatus[] = ["created", "assigned", "in_progress", "resolved", "cancelled"];

export interface WorkOrder {
  id: number;
  event_id: string;
  unit: string;
  note?: string | null;
  status: WorkOrderStatus;
  assignee?: string | null;
  due_date?: string | null;
  created_at: string;
  updated_at: string;
  city_id?: string | null;
  event_type: string;
  lat?: number | null;
  lon?: number | null;
  confidence?: number | null;
  confidence_band?: string | null;
  thumb_url?: string | null;
}

export interface WorkOrderPatch {
  status?: WorkOrderStatus;
  note?: string;
  assignee?: string;
  unit?: string;
  due_date?: string;
  clear_due_date?: boolean;
}

export interface AdminUser {
  id: number;
  username: string;
  display_name?: string | null;
  role: Role;
  active: boolean;
  city_id?: string | null;
  created_at?: string;
}

export interface CitySettings {
  id: string;
  name: string;
  timezone: string;
  language: string;
  work_order_units: string[];
  languages: string[];
}

export interface AuditEntry {
  id: number;
  actor: string;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  detail: Record<string, unknown>;
  city_id?: string | null;
  created_at: string;
}

export interface ReviewStats {
  days: number;
  decisions: number;
  confirmed: number;
  false_alarms: number;
  unsure: number;
  precision: number | null;
  false_alarm_reasons: Record<string, number>;
  by_reviewer: Record<string, number>;
  median_hours_to_decision: number | null;
  flights: number;
}

export interface Zone {
  zone_id: string;
  name: string;
  zone_type: string;
  city_id?: string | null;
  geometry: Geometry;
}

export interface RouteProps {
  altitude_m?: number;
  speed_ms?: number;
  gimbal_deg?: number;
  preferred_time?: string | null;
  notes?: string | null;
  planned?: boolean;
}

export interface RouteGeo {
  id: string;
  name: string;
  city_id?: string | null;
  geometry?: Geometry | null;
  props?: RouteProps;
  length_m?: number | null;
  flights?: number;
  last_flown?: string | null;
  created_by?: string | null;
  updated_at?: string;
}

export interface RoutePlanBody {
  name: string;
  coordinates: [number, number][];
  altitude_m: number;
  speed_ms: number;
  gimbal_deg: number;
  preferred_time?: string | null;
  notes?: string | null;
}

export interface FlightTrack {
  id: string;
  name: string | null;
  flight_date?: string | null;
  created_at: string;
  route_id?: string | null;
  status: string;
  candidates: number;
  track: [number, number][];
}

export interface Adherence {
  tolerance_m: number;
  route_m: number;
  coverage: number;
  off_route: number;
  max_deviation_m: number;
}

export interface GeoUploadResult {
  zones_upserted?: number;
  routes_upserted?: number;
  skipped: number;
}

export interface LabelBox {
  cls: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export type LabelKind = "positive" | "negative" | "skip";

export interface LabelItem {
  event_id: string;
  type: string;
  confidence?: number | null;
  confidence_band?: string | null;
  model_version?: string | null;
  city_id?: string | null;
  review_label: string;
  review_reason?: string | null;
  reviewer: string;
  reviewed_at: string;
  flight_id?: string | null;
  flight_name?: string | null;
  holdout: boolean;
  label_kind?: LabelKind | null;
  label_boxes?: LabelBox[] | null;
  labeller?: string | null;
  labelled_at?: string | null;
  has_clean_frame: boolean;
  thumb_url?: string | null;
}

export interface LabelItemDetail extends LabelItem {
  frame: { id: number; url: string } | null;
  annotated_url?: string | null;
  sample_bbox?: [number, number, number, number] | null;
}

export interface LabelCounts {
  todo: number;
  by_kind: Partial<Record<LabelKind, number>>;
  boxes_by_class: Record<string, number>;
}

export interface ModelPerformance {
  model_version: string;
  events: number;
  runs: number;
  first_seen: string;
  last_seen: string;
  confirmed: number;
  false_alarms: number;
  pending: number;
  precision: number | null;
  false_alarm_reasons: Record<string, number>;
}

export interface WeeklyReport {
  start: string;
  end: string;
  city: { id: string | null; name: string | null };
  flights: { flights: number; bytes: number; processed: number };
  new_candidates: number;
  new_by_type: Record<string, number>;
  decisions: number;
  confirmed: number;
  false_alarms: number;
  unsure: number;
  precision: number | null;
  false_alarm_reasons: Record<string, number>;
  work_orders: { opened: number; resolved: number; open_now: number; overdue: number };
  confirmed_events: (Pick<CityEvent, "event_id" | "type" | "lat" | "lon" | "status" | "confidence" | "confidence_band"> & { decided_at: string })[];
  model_versions: string[];
  previous: { new_candidates: number; decisions: number; confirmed: number; false_alarms: number; precision: number | null; flights: number };
}
