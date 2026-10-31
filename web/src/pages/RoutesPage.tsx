import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowLeftRight,
  Clock,
  Download,
  Eraser,
  FileCode2,
  Pencil,
  Plus,
  Route as RouteIcon,
  Trash2,
  Undo2,
  X,
} from "lucide-react";
import { ApiError, api, downloadAuthed } from "../api/client";
import type { RouteGeo, RoutePlanBody } from "../api/types";
import { useCurrentUser } from "../auth/AuthContext";
import { EventMap, ROUTE_COLOR, TRACK_COLORS } from "../components/EventMap";
import { RouteEditLayer, Swath, type Waypoints } from "../components/RouteEditLayer";
import { Empty, ErrorState, Loading } from "../components/States";
import { useToast } from "../components/Toast";
import { formatDate, formatDuration } from "../lib/format";
import { flightSeconds, formatDistance, lengthM, swathM } from "../lib/geo";

const DEFAULTS = { altitude_m: 60, speed_ms: 5, gimbal_deg: -90 };

function coordsOf(r: RouteGeo | undefined): Waypoints {
  const g = r?.geometry as { type?: string; coordinates?: number[][] } | null | undefined;
  return g?.type === "LineString" && g.coordinates ? g.coordinates.map(([lon, lat]) => [lon, lat] as [number, number]) : [];
}

export function RoutesPage() {
  const { t } = useTranslation();
  const [params, setParams] = useSearchParams();
  const selectedId = params.get("r");
  const [editing, setEditing] = useState<{ route?: RouteGeo } | null>(null);
  const routes = useQuery({ queryKey: ["routes-geo"], queryFn: api.routesGeo });
  const selected = routes.data?.find((r) => r.id === selectedId);
  const flown = useQuery({
    queryKey: ["flight-tracks", "route", selectedId],
    queryFn: () => api.flightTracks(730, selectedId!),
    enabled: !!selectedId && !editing,
  });

  const select = (id: string | null) => setParams(id ? { r: id } : {}, { replace: true });
  const [draft, setDraft] = useState<Waypoints>([]);
  const [params2, setParams2] = useState(DEFAULTS);

  const startEdit = (route?: RouteGeo) => {
    setDraft(coordsOf(route));
    setParams2({
      altitude_m: route?.props?.altitude_m ?? DEFAULTS.altitude_m,
      speed_ms: route?.props?.speed_ms ?? DEFAULTS.speed_ms,
      gimbal_deg: route?.props?.gimbal_deg ?? DEFAULTS.gimbal_deg,
    });
    setEditing({ route });
  };

  const others = (routes.data ?? []).filter((r) => r.id !== editing?.route?.id);

  return (
    <div className="routes-page">
      <aside className="routes-panel">
        {editing ? (
          <RouteEditor
            route={editing.route}
            draft={draft}
            setDraft={setDraft}
            flight={params2}
            setFlight={setParams2}
            onClose={(savedId) => {
              setEditing(null);
              if (savedId) select(savedId);
            }}
          />
        ) : (
          <RouteList routes={routes} selected={selected} onSelect={select} onNew={() => startEdit()} onEdit={startEdit} flown={flown.data ?? []} />
        )}
      </aside>
      <div className="routes-map">
        {routes.isPending ? (
          <Loading />
        ) : (
          <EventMap
            events={[]}
            routes={editing ? others : routes.data}
            selectedRouteId={editing ? null : selectedId}
            onSelectRoute={editing ? undefined : (id) => select(id)}
            tracks={editing ? [] : flown.data}
            className="map-full"
            showFit
          >
            {editing ? (
              <RouteEditLayer points={draft} onChange={setDraft} swathM={swathM(params2.altitude_m)} />
            ) : (
              selected && coordsOf(selected).length > 1 && (
                <Swath latlngs={coordsOf(selected).map(([lon, lat]) => [lat, lon])} widthM={swathM(selected.props?.altitude_m ?? 60)} />
              )
            )}
          </EventMap>
        )}
        {editing && <div className="map-hint">{t("routes.editor.steps")}</div>}
      </div>
    </div>
  );
}

function RouteList({
  routes,
  selected,
  onSelect,
  onNew,
  onEdit,
  flown,
}: {
  routes: ReturnType<typeof useQuery<RouteGeo[]>>;
  selected?: RouteGeo;
  onSelect: (id: string | null) => void;
  onNew: () => void;
  onEdit: (r: RouteGeo) => void;
  flown: { id: string; name: string | null; created_at: string; candidates: number }[];
}) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const { canDecide, user } = useCurrentUser();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const qc = useQueryClient();
  const toast = useToast();
  const del = useMutation({
    mutationFn: (id: string) => api.deleteRoute(id),
    onSuccess: () => {
      toast.show(t("routes.deleted"));
      void qc.invalidateQueries({ queryKey: ["routes-geo"] });
      void qc.invalidateQueries({ queryKey: ["routes"] });
      onSelect(null);
    },
  });

  if (routes.isPending) return <Loading />;
  if (routes.isError) return <ErrorState error={routes.error} onRetry={() => routes.refetch()} />;
  const list = routes.data ?? [];

  return (
    <>
      <header className="routes-head">
        <div>
          <h1>{t("routes.title")}</h1>
          <p className="muted small">{t("routes.subtitle")}</p>
        </div>
        {canDecide && (
          <button type="button" className="btn btn-primary" onClick={onNew}>
            <Plus size={16} aria-hidden="true" /> {t("routes.new")}
          </button>
        )}
      </header>

      {list.length === 0 ? (
        <Empty icon={RouteIcon}>{t("routes.empty")}</Empty>
      ) : (
        <ul className="route-list">
          {list.map((r) => {
            const coords = coordsOf(r);
            const len = r.length_m ?? lengthM(coords);
            const sel = r.id === selected?.id;
            const speed = r.props?.speed_ms ?? DEFAULTS.speed_ms;
            return (
              <li key={r.id} className={`route-card ${sel ? "route-card-selected" : ""}`}>
                <button type="button" className="route-card-main" onClick={() => onSelect(sel ? null : r.id)}>
                  <span className="route-swatch" aria-hidden="true" />
                  <span className="route-card-body">
                    <span className="route-name">{r.name}</span>
                    <span className="route-meta">
                      <span>{formatDistance(len, lang)}</span>
                      <span>{formatDuration(flightSeconds(coords, speed), lang)}</span>
                      {r.props?.altitude_m != null && <span>{t("routes.units.agl", { v: r.props.altitude_m })}</span>}
                    </span>
                  </span>
                  <span className="route-flights" title={t("routes.stats.flights")}>
                    {r.flights ?? 0}
                  </span>
                </button>

                {sel && (
                  <div className="route-detail">
                    <dl className="route-stats">
                      <div>
                        <dt>{t("routes.stats.waypoints")}</dt>
                        <dd>{coords.length}</dd>
                      </div>
                      <div>
                        <dt>{t("routes.stats.speed")}</dt>
                        <dd>{t("routes.units.speed", { v: speed })}</dd>
                      </div>
                      <div>
                        <dt>{t("routes.stats.gimbal")}</dt>
                        <dd>
                          {t("routes.units.gimbal", { v: r.props?.gimbal_deg ?? -90 })}
                          {(r.props?.gimbal_deg ?? -90) === -90 && <span className="muted"> · {t("routes.nadir")}</span>}
                        </dd>
                      </div>
                      <div>
                        <dt>{t("routes.stats.swath")}</dt>
                        <dd>{t("routes.units.swath", { v: Math.round(swathM(r.props?.altitude_m ?? 60)) })}</dd>
                      </div>
                      <div>
                        <dt>{t("routes.stats.lastFlown")}</dt>
                        <dd>{r.last_flown ? formatDate(r.last_flown, lang) : t("routes.stats.never")}</dd>
                      </div>
                    </dl>
                    {r.props?.preferred_time && (
                      <p className="small route-time">
                        <Clock size={13} aria-hidden="true" /> {r.props.preferred_time}
                      </p>
                    )}
                    {r.props?.notes && <p className="small route-notes">{r.props.notes}</p>}

                    <div className="route-actions">
                      {canDecide && (
                        <button type="button" className="btn btn-sm" onClick={() => onEdit(r)}>
                          <Pencil size={14} aria-hidden="true" /> {t("routes.edit")}
                        </button>
                      )}
                      <button type="button" className="btn btn-sm" onClick={() => void downloadAuthed(`/api/routes/${encodeURIComponent(r.id)}/export.kml`, `${r.id}.kml`)}>
                        <Download size={14} aria-hidden="true" /> {t("routes.exportKml")}
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm btn-ghost"
                        onClick={() => void downloadAuthed(`/api/routes/${encodeURIComponent(r.id)}/export.geojson`, `${r.id}.geojson`)}
                      >
                        <FileCode2 size={14} aria-hidden="true" /> {t("routes.exportGeojson")}
                      </button>
                      {["admin", "superadmin"].includes(user.role) && (
                        <button type="button" className="btn btn-sm btn-ghost text-danger" onClick={() => setConfirmDelete(true)}>
                          <Trash2 size={14} aria-hidden="true" /> {t("routes.delete")}
                        </button>
                      )}
                    </div>

                    <h3 className="route-sub">{t("routes.flightsTitle")}</h3>
                    {flown.length === 0 ? (
                      <p className="muted small">{t("routes.noFlights")}</p>
                    ) : (
                      <ul className="route-flown">
                        {flown.map((f, i) => (
                          <li key={f.id}>
                            <span className="track-swatch" style={{ background: TRACK_COLORS[i % TRACK_COLORS.length] }} aria-hidden="true" />
                            <Link to={`/flights/${f.id}`}>{f.name ?? f.id.slice(0, 8)}</Link>
                            <span className="muted small">{formatDate(f.created_at, lang)}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {confirmDelete && selected && (
        <ConfirmDialog
          title={t("routes.deleteTitle", { name: selected.name })}
          body={t("routes.deleteBody")}
          confirmLabel={t("routes.delete")}
          onCancel={() => setConfirmDelete(false)}
          onConfirm={() => {
            setConfirmDelete(false);
            del.mutate(selected.id);
          }}
        />
      )}
    </>
  );
}

function RouteEditor({
  route,
  draft,
  setDraft,
  flight,
  setFlight,
  onClose,
}: {
  route?: RouteGeo;
  draft: Waypoints;
  setDraft: (p: Waypoints) => void;
  flight: typeof DEFAULTS;
  setFlight: (f: typeof DEFAULTS) => void;
  onClose: (savedId?: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const qc = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState(route?.name ?? "");
  const [time, setTime] = useState(route?.props?.preferred_time ?? "");
  const [notes, setNotes] = useState(route?.props?.notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const history = useRef<Waypoints[]>([]);

  // Keep an undo stack of waypoint edits.
  const prev = useRef(draft);
  useEffect(() => {
    if (prev.current !== draft) {
      history.current = [...history.current.slice(-49), prev.current];
      prev.current = draft;
    }
  }, [draft]);
  const undo = () => {
    const last = history.current.pop();
    if (last) {
      prev.current = last;
      setDraft(last);
    }
  };

  const len = useMemo(() => lengthM(draft), [draft]);
  const secs = flightSeconds(draft, flight.speed_ms);

  const save = useMutation({
    mutationFn: () => {
      const body: RoutePlanBody = { name: name.trim(), coordinates: draft, ...flight, preferred_time: time.trim() || null, notes: notes.trim() || null };
      return route ? api.updateRoute(route.id, body) : api.createRoute(body);
    },
    onSuccess: (saved) => {
      toast.show(t("routes.editor.saved"));
      void qc.invalidateQueries({ queryKey: ["routes-geo"] });
      void qc.invalidateQueries({ queryKey: ["routes"] });
      onClose(saved.id);
    },
    onError: (err) => setError(err instanceof ApiError && typeof err.detail === "string" ? err.detail : t("routes.editor.failed")),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    if (!name.trim()) return setError(t("routes.editor.needName"));
    if (draft.length < 2) return setError(t("routes.editor.needPoints"));
    save.mutate();
  };

  // Keyboard: Ctrl/Cmd+Z undo while editing (not inside text fields).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName)) return;
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "z") {
        e.preventDefault();
        undo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <form className="route-editor" onSubmit={submit}>
      <header className="routes-head">
        <h1>{route ? t("routes.editor.editTitle") : t("routes.editor.newTitle")}</h1>
        <button type="button" className="icon-btn" onClick={() => onClose()} aria-label={t("routes.editor.cancel")}>
          <X size={18} aria-hidden="true" />
        </button>
      </header>

      <div className="route-summary">
        <div>
          <span className="stat-label">{t("routes.stats.distance")}</span>
          <span className="route-summary-value">{formatDistance(len, lang)}</span>
        </div>
        <div>
          <span className="stat-label">{t("routes.stats.time")}</span>
          <span className="route-summary-value">{secs ? formatDuration(secs, lang) : "—"}</span>
        </div>
        <div>
          <span className="stat-label">{t("routes.stats.swath")}</span>
          <span className="route-summary-value">≈ {Math.round(swathM(flight.altitude_m))} m</span>
        </div>
      </div>

      <label className="field">
        <span>{t("routes.editor.name")}</span>
        <input value={name} maxLength={120} placeholder={t("routes.editor.namePlaceholder")} onChange={(e) => setName(e.target.value)} autoFocus />
      </label>
      <div className="form-grid form-grid-3">
        <label className="field">
          <span>{t("routes.editor.altitude")}</span>
          <input type="number" min={5} max={500} step={5} value={flight.altitude_m} onChange={(e) => setFlight({ ...flight, altitude_m: Number(e.target.value) })} />
        </label>
        <label className="field">
          <span>{t("routes.editor.speed")}</span>
          <input type="number" min={0.5} max={25} step={0.5} value={flight.speed_ms} onChange={(e) => setFlight({ ...flight, speed_ms: Number(e.target.value) })} />
        </label>
        <label className="field">
          <span>{t("routes.editor.gimbal")}</span>
          <input type="number" min={-90} max={0} step={5} value={flight.gimbal_deg} onChange={(e) => setFlight({ ...flight, gimbal_deg: Number(e.target.value) })} />
        </label>
      </div>
      <p className="muted small">{t("routes.editor.gimbalHint")}</p>
      {flight.altitude_m > 120 && <p className="form-warning">{t("routes.editor.altitudeWarn")}</p>}

      <div className="waypoints-head">
        <h3>
          {t("routes.editor.waypoints")} <span className="muted">· {draft.length}</span>
        </h3>
        <span className="toolbar">
          <button type="button" className="icon-btn icon-btn-bordered" title={t("routes.editor.undo")} aria-label={t("routes.editor.undo")} onClick={undo}>
            <Undo2 size={15} aria-hidden="true" />
          </button>
          <button
            type="button"
            className="icon-btn icon-btn-bordered"
            title={t("routes.editor.reverse")}
            aria-label={t("routes.editor.reverse")}
            onClick={() => setDraft([...draft].reverse())}
            disabled={draft.length < 2}
          >
            <ArrowLeftRight size={15} aria-hidden="true" />
          </button>
          <button type="button" className="icon-btn icon-btn-bordered" title={t("routes.editor.clear")} aria-label={t("routes.editor.clear")} onClick={() => setDraft([])} disabled={!draft.length}>
            <Eraser size={15} aria-hidden="true" />
          </button>
        </span>
      </div>
      {draft.length === 0 ? (
        <p className="muted small waypoints-empty">{t("routes.editor.noWaypoints")}</p>
      ) : (
        <ol className="waypoints">
          {draft.map((p, i) => (
            <li key={i}>
              <span className={`wp-num ${i === 0 ? "wp-num-start" : i === draft.length - 1 ? "wp-num-end" : ""}`}>{i === 0 ? "S" : i + 1}</span>
              <span className="mono small">
                {p[1].toFixed(5)}, {p[0].toFixed(5)}
              </span>
              {i > 0 && <span className="muted small wp-leg">+{formatDistance(lengthM([draft[i - 1], p]), lang)}</span>}
              <button type="button" className="icon-btn wp-remove" aria-label={t("routes.delete")} onClick={() => setDraft(draft.filter((_, j) => j !== i))}>
                <X size={14} aria-hidden="true" />
              </button>
            </li>
          ))}
        </ol>
      )}

      <label className="field">
        <span>{t("routes.editor.time")}</span>
        <input value={time} maxLength={40} placeholder={t("routes.editor.timePlaceholder")} onChange={(e) => setTime(e.target.value)} />
      </label>
      <label className="field">
        <span>{t("routes.editor.notes")}</span>
        <textarea rows={3} value={notes} maxLength={2000} onChange={(e) => setNotes(e.target.value)} />
      </label>

      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      <div className="route-editor-actions">
        <button type="button" className="btn" onClick={() => onClose()}>
          {t("routes.editor.cancel")}
        </button>
        <button type="submit" className="btn btn-primary" disabled={save.isPending}>
          {save.isPending ? t("routes.editor.saving") : t("routes.editor.save")}
        </button>
      </div>
      <span className="route-color-key" style={{ background: ROUTE_COLOR }} aria-hidden="true" />
    </form>
  );
}

function ConfirmDialog({
  title,
  body,
  confirmLabel,
  onCancel,
  onConfirm,
}: {
  title: string;
  body: string;
  confirmLabel: string;
  onCancel: () => void;
  onConfirm: () => void;
}) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
    return () => d?.close();
  }, []);
  return (
    <dialog ref={ref} className="dialog" onCancel={onCancel} aria-labelledby="confirm-title">
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onConfirm();
        }}
      >
        <h2 id="confirm-title">{title}</h2>
        <p className="muted">{body}</p>
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onCancel}>
            {t("routes.editor.cancel")}
          </button>
          <button type="submit" className="btn btn-danger">
            {confirmLabel}
          </button>
        </div>
      </form>
    </dialog>
  );
}
