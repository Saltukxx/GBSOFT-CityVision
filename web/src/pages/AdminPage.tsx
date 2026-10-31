import { useEffect, useMemo, useRef, useState, type ChangeEvent, type FormEvent } from "react";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Upload, UserPlus } from "lucide-react";
import { NavLink, Navigate, useParams } from "react-router-dom";
import { GeoJSON, MapContainer, TileLayer } from "react-leaflet";
import { geoJSON as leafletGeoJSON } from "leaflet";
import type { Feature, FeatureCollection, Geometry } from "geojson";
import "leaflet/dist/leaflet.css";
import { ApiError, api } from "../api/client";
import type { AdminUser, AuditEntry, Role } from "../api/types";
import { useCurrentUser } from "../auth/AuthContext";
import { Empty, ErrorState, Loading } from "../components/States";
import { useToast } from "../components/Toast";
import { formatDate, formatDateTime, humanize } from "../lib/format";
import { unitLabel } from "../lib/useCitySettings";
import { MAX_ZOOM, STREETS_LIGHT } from "../lib/mapLayers";

const TABS = ["users", "zones", "models", "settings", "audit"] as const;
type Tab = (typeof TABS)[number];

export function AdminPage() {
  const { t } = useTranslation();
  const { user } = useCurrentUser();
  const { tab } = useParams();
  if (!["admin", "superadmin"].includes(user.role)) {
    return <Empty>{t("admin.forbidden")}</Empty>;
  }
  if (!tab || !TABS.includes(tab as Tab)) return <Navigate to="/admin/users" replace />;

  return (
    <div className="page">
      <header className="page-head">
        <h1>{t("admin.title")}</h1>
      </header>
      <nav className="tabs" aria-label={t("admin.title")}>
        {TABS.map((x) => (
          <NavLink key={x} to={`/admin/${x}`} className="tab">
            {t(`admin.tabs.${x}`)}
          </NavLink>
        ))}
      </nav>
      {tab === "users" && <UsersTab />}
      {tab === "zones" && <ZonesTab />}
      {tab === "models" && <ModelsTab />}
      {tab === "settings" && <SettingsTab />}
      {tab === "audit" && <AuditTab />}
    </div>
  );
}

// ---------------- Users ----------------

const ASSIGNABLE: Role[] = ["viewer", "operator", "admin"];

function generatePassword(): string {
  const alphabet = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = crypto.getRandomValues(new Uint8Array(14));
  return [...bytes].map((b) => alphabet[b % alphabet.length]).join("");
}

function userError(t: (k: string) => string, err: unknown): string {
  const detail = err instanceof ApiError && typeof err.detail === "string" ? err.detail : "";
  const key = `admin.users.errors.${detail}`;
  const msg = detail ? t(key) : "";
  return msg && msg !== key ? msg : t("admin.users.errors.generic");
}

function UsersTab() {
  const { t } = useTranslation();
  const { user: me } = useCurrentUser();
  const q = useQuery({ queryKey: ["users"], queryFn: api.users });
  const [dialog, setDialog] = useState<{ mode: "add" } | { mode: "edit"; user: AdminUser } | null>(null);

  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const users = [...q.data].sort((a, b) => Number(b.active) - Number(a.active) || a.username.localeCompare(b.username));

  return (
    <>
      <div className="toolbar">
        <button type="button" className="btn btn-primary" onClick={() => setDialog({ mode: "add" })}>
          <UserPlus size={17} aria-hidden="true" /> {t("admin.users.add")}
        </button>
      </div>
      {users.length === 0 ? (
        <Empty>{t("admin.users.empty")}</Empty>
      ) : (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>{t("admin.users.name")}</th>
                <th>{t("admin.users.username")}</th>
                <th>{t("admin.users.role")}</th>
                <th>{t("admin.users.status")}</th>
                <th aria-label={t("admin.users.edit")} />
              </tr>
            </thead>
            <tbody>
              {users.map((u) => (
                <tr key={u.username} className={u.active ? "" : "row-inactive"}>
                  <td data-label={t("admin.users.name")}>
                    <span className="user-cell">
                      <span className="avatar avatar-sm" aria-hidden="true">
                        {(u.display_name || u.username)
                          .split(/[\s._-]+/)
                          .filter(Boolean)
                          .slice(0, 2)
                          .map((p) => p[0]?.toUpperCase())
                          .join("")}
                      </span>
                      <strong>{u.display_name || u.username}</strong>
                    </span>
                    {u.username === me.username && <span className="tag">{t("admin.users.you")}</span>}
                  </td>
                  <td data-label={t("admin.users.username")} className="mono small">
                    {u.username}
                  </td>
                  <td data-label={t("admin.users.role")}>{t(`roles.${u.role}`)}</td>
                  <td data-label={t("admin.users.status")}>
                    <span className={`pill ${u.active ? "pill-flight-ok" : "pill-flight-muted"}`}>
                      <span className="pill-dot" aria-hidden="true" />
                      {u.active ? t("admin.users.active") : t("admin.users.inactive")}
                    </span>
                  </td>
                  <td className="num">
                    <button type="button" className="btn-link" onClick={() => setDialog({ mode: "edit", user: u })}>
                      {t("admin.users.edit")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {dialog && <UserDialog key={dialog.mode === "edit" ? dialog.user.username : "add"} state={dialog} onClose={() => setDialog(null)} />}
    </>
  );
}

function UserDialog({ state, onClose }: { state: { mode: "add" } | { mode: "edit"; user: AdminUser }; onClose: () => void }) {
  const { t } = useTranslation();
  const { user: me } = useCurrentUser();
  const qc = useQueryClient();
  const toast = useToast();
  const ref = useRef<HTMLDialogElement>(null);
  const editing = state.mode === "edit" ? state.user : null;
  const isSelf = editing?.username === me.username;
  const [username, setUsername] = useState("");
  const [displayName, setDisplayName] = useState(editing?.display_name ?? "");
  const [role, setRole] = useState<Role>(editing?.role ?? "operator");
  const [password, setPassword] = useState(editing ? "" : generatePassword());
  const [active, setActive] = useState(editing?.active ?? true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
    return () => d?.close();
  }, []);

  const save = useMutation({
    mutationFn: async () => {
      if (!editing) {
        // The create endpoint also updates existing users; never overwrite someone by accident.
        const existing = qc.getQueryData<AdminUser[]>(["users"]) ?? [];
        if (existing.some((u) => u.username.toLowerCase() === username.trim().toLowerCase())) {
          throw new ApiError(409, "username already taken", "username already taken");
        }
        return api.createUser({ username: username.trim(), display_name: displayName.trim(), role, password });
      }
      const body: { display_name?: string; role?: string; active?: boolean; password?: string } = {};
      if (displayName !== (editing.display_name ?? "")) body.display_name = displayName.trim();
      if (role !== editing.role) body.role = role;
      if (active !== editing.active) body.active = active;
      if (password) body.password = password;
      return api.patchUser(editing.username, body);
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["users"] });
      toast.show(editing ? t("admin.users.saved") : t("admin.users.created"));
      onClose();
    },
    onError: (err) => setError(userError(t, err)),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    save.mutate();
  };
  const roles = me.role === "superadmin" ? [...ASSIGNABLE, "superadmin" as Role] : ASSIGNABLE;
  const lockedSuper = editing?.role === "superadmin" && me.role !== "superadmin";

  return (
    <dialog ref={ref} className="dialog dialog-wide" onCancel={onClose} aria-labelledby="user-title">
      <form onSubmit={submit}>
        <h2 id="user-title">
          {editing ? t("admin.users.dialogEdit", { name: editing.display_name || editing.username }) : t("admin.users.dialogAdd")}
        </h2>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <fieldset className="form-grid" disabled={lockedSuper}>
          {!editing && (
            <label className="field">
              <span>{t("admin.users.username")}</span>
              <input value={username} onChange={(e) => setUsername(e.target.value)} required minLength={2} maxLength={60} pattern="[A-Za-z0-9._\-]+" autoFocus />
            </label>
          )}
          <label className="field">
            <span>{t("admin.users.displayName")}</span>
            <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} maxLength={120} />
          </label>
          <label className="field">
            <span>{t("admin.users.role")}</span>
            <select value={role} onChange={(e) => setRole(e.target.value as Role)} disabled={isSelf}>
              {roles.map((r) => (
                <option key={r} value={r}>
                  {t(`roles.${r}`)}
                </option>
              ))}
            </select>
          </label>
        </fieldset>
        <p className="muted small">{t(`admin.users.roleHelp.${role}`)}</p>

        <label className="field">
          <span>{editing ? t("admin.users.resetPassword") : t("admin.users.password")}</span>
          <span className="input-row">
            <input
              className="mono"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              required={!editing}
              disabled={lockedSuper}
              autoComplete="new-password"
            />
            <button type="button" className="btn" onClick={() => setPassword(generatePassword())} disabled={lockedSuper}>
              {t("admin.users.generate")}
            </button>
          </span>
        </label>
        <p className="muted small">{editing ? t("admin.users.resetHint") : t("admin.users.passwordHint")}</p>

        {editing && !isSelf && !lockedSuper && (
          <div className="danger-zone">
            <label className="check">
              <input type="checkbox" checked={!active} onChange={(e) => setActive(!e.target.checked)} />
              {editing.active ? t("admin.users.deactivate") : t("admin.users.reactivate")}
            </label>
            <p className="muted small">{t("admin.users.deactivateHint")}</p>
          </div>
        )}

        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose}>
            {t("admin.users.cancel")}
          </button>
          <button type="submit" className="btn btn-primary" disabled={save.isPending || lockedSuper}>
            {editing ? t("admin.users.save") : t("admin.users.create")}
          </button>
        </div>
      </form>
    </dialog>
  );
}

// ---------------- Zones & routes ----------------

function ZonesTab() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const toast = useToast();
  const zones = useQuery({ queryKey: ["zones"], queryFn: api.zones });
  const routes = useQuery({ queryKey: ["routes-geo"], queryFn: api.routesGeo });

  const collection = useMemo<FeatureCollection>(() => {
    const features: Feature<Geometry>[] = [];
    zones.data?.forEach((z) => z.geometry && features.push({ type: "Feature", properties: { kind: "zone", name: z.name }, geometry: z.geometry }));
    routes.data?.forEach((r) => r.geometry && features.push({ type: "Feature", properties: { kind: "route", name: r.name }, geometry: r.geometry }));
    return { type: "FeatureCollection", features };
  }, [zones.data, routes.data]);

  const upload = async (kind: "zones" | "routes", e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    let data: unknown;
    try {
      data = JSON.parse(await file.text());
    } catch {
      toast.show(t("admin.zones.badFile"), { tone: "error" });
      return;
    }
    if (!data || (data as { type?: string }).type !== "FeatureCollection") {
      toast.show(t("admin.zones.badFile"), { tone: "error" });
      return;
    }
    try {
      const res = kind === "zones" ? await api.uploadZones(data) : await api.uploadRoutes(data);
      const count = res.zones_upserted ?? res.routes_upserted ?? 0;
      toast.show(t("admin.zones.uploaded", { count, skipped: res.skipped }));
      void qc.invalidateQueries({ queryKey: ["zones"] });
      void qc.invalidateQueries({ queryKey: ["routes-geo"] });
      void qc.invalidateQueries({ queryKey: ["routes"] });
    } catch {
      toast.show(t("admin.zones.failed"), { tone: "error" });
    }
  };

  if (zones.isPending || routes.isPending) return <Loading />;
  if (zones.isError) return <ErrorState error={zones.error} onRetry={() => zones.refetch()} />;

  return (
    <>
      <div className="toolbar">
        <label className="btn">
          <Upload size={16} aria-hidden="true" /> {t("admin.zones.uploadZones")}
          <input type="file" accept=".geojson,.json,application/geo+json,application/json" hidden onChange={(e) => void upload("zones", e)} />
        </label>
        <label className="btn">
          <Upload size={16} aria-hidden="true" /> {t("admin.zones.uploadRoutes")}
          <input type="file" accept=".geojson,.json,application/geo+json,application/json" hidden onChange={(e) => void upload("routes", e)} />
        </label>
      </div>
      <p className="muted small">{t("admin.zones.hint")}</p>
      <div className="grid-2 grid-2-wide">
        <section className="card">
          <GeoMap data={collection} />
        </section>
        <section className="card">
          <h3>{t("admin.zones.zones")}</h3>
          {zones.data.length ? (
            <ul className="plain-list">
              {zones.data.map((z) => (
                <li key={z.zone_id}>
                  <span className="legend-swatch legend-zone" aria-hidden="true" /> {z.name}{" "}
                  <span className="muted small">· {humanize(z.zone_type)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">{t("admin.zones.noZones")}</p>
          )}
          <h3 className="mt">{t("admin.zones.routes")}</h3>
          {routes.data?.length ? (
            <ul className="plain-list">
              {routes.data.map((r) => (
                <li key={r.id}>
                  <span className="legend-swatch legend-route" aria-hidden="true" /> {r.name} <span className="muted mono small">{r.id}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">{t("admin.zones.noRoutes")}</p>
          )}
        </section>
      </div>
    </>
  );
}

function GeoMap({ data }: { data: FeatureCollection }) {
  const bounds = data.features.length ? leafletGeoJSON(data).getBounds() : null;
  return (
    <MapContainer
      key={JSON.stringify(bounds)}
      bounds={bounds && bounds.isValid() ? bounds.pad(0.1) : undefined}
      center={bounds && bounds.isValid() ? undefined : [39.9, 41.27]}
      zoom={bounds && bounds.isValid() ? undefined : 12}
      className="map map-flight"
    >
      <TileLayer url={STREETS_LIGHT.url} attribution={STREETS_LIGHT.attribution} maxNativeZoom={STREETS_LIGHT.maxNativeZoom} maxZoom={MAX_ZOOM} />
      <GeoJSON
        key={data.features.length}
        data={data}
        style={(f) =>
          f?.properties?.kind === "route"
            ? { color: "#0e7490", weight: 4 }
            : { color: "#b45309", weight: 2, fillOpacity: 0.15 }
        }
        onEachFeature={(f, layer) => f.properties?.name && layer.bindTooltip(String(f.properties.name))}
      />
    </MapContainer>
  );
}

// ---------------- Models ----------------

function ModelsTab() {
  const { t, i18n } = useTranslation();
  const q = useQuery({ queryKey: ["model-performance"], queryFn: api.modelPerformance });
  if (q.isPending) return <Loading />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const lang = i18n.language;
  const pct = (v: number | null) => (v == null ? "—" : new Intl.NumberFormat(lang, { style: "percent", maximumFractionDigits: 0 }).format(v));
  return (
    <>
      <p className="muted">{t("admin.models.intro")}</p>
      {q.data.length === 0 ? (
        <Empty>{t("admin.models.empty")}</Empty>
      ) : (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>{t("admin.models.version")}</th>
                <th>{t("admin.models.period")}</th>
                <th className="num">{t("admin.models.events")}</th>
                <th className="num">{t("admin.models.confirmed")}</th>
                <th className="num">{t("admin.models.falseAlarms")}</th>
                <th className="num">{t("admin.models.pending")}</th>
                <th className="num">{t("admin.models.precision")}</th>
                <th>{t("admin.models.topReason")}</th>
              </tr>
            </thead>
            <tbody>
              {q.data.map((m) => {
                const top = Object.entries(m.false_alarm_reasons).sort((a, b) => b[1] - a[1])[0];
                const decided = m.confirmed + m.false_alarms;
                return (
                  <tr key={m.model_version}>
                    <td data-label={t("admin.models.version")} className="mono">
                      {m.model_version === "unknown" ? <span className="muted">{t("admin.models.unknown")}</span> : m.model_version}
                    </td>
                    <td data-label={t("admin.models.period")} className="small nowrap">
                      {formatDate(m.first_seen, lang)} – {formatDate(m.last_seen, lang)}
                    </td>
                    <td data-label={t("admin.models.events")} className="num">{m.events}</td>
                    <td data-label={t("admin.models.confirmed")} className="num">{m.confirmed}</td>
                    <td data-label={t("admin.models.falseAlarms")} className="num">{m.false_alarms}</td>
                    <td data-label={t("admin.models.pending")} className="num muted">{m.pending}</td>
                    <td data-label={t("admin.models.precision")} className="num">
                      <span className={decided >= 20 ? (m.precision != null && m.precision >= 0.8 ? "text-ok" : "text-warn") : "muted"}>{pct(m.precision)}</span>
                    </td>
                    <td data-label={t("admin.models.topReason")} className="small">
                      {top ? `${top[0] === "unspecified" ? t("overview.week.unspecified") : t(`review.reasons.${top[0]}`, { defaultValue: top[0] })} (${top[1]})` : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}

// ---------------- Settings ----------------

function SettingsTab() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["city-settings"], queryFn: api.citySettings });
  const [form, setForm] = useState<{ name: string; timezone: string; language: string; units: string } | null>(null);

  useEffect(() => {
    if (q.data && !form)
      setForm({ name: q.data.name, timezone: q.data.timezone, language: q.data.language, units: q.data.work_order_units.join("\n") });
  }, [q.data, form]);

  const zonesList = useMemo(() => {
    try {
      return (Intl as unknown as { supportedValuesOf: (k: string) => string[] }).supportedValuesOf("timeZone");
    } catch {
      return [];
    }
  }, []);

  const save = useMutation({
    mutationFn: () =>
      api.patchCitySettings({
        name: form!.name.trim(),
        timezone: form!.timezone,
        language: form!.language,
        work_order_units: form!.units.split("\n").map((u) => u.trim()).filter(Boolean),
      }),
    onSuccess: (data) => {
      qc.setQueryData(["city-settings"], data);
      setForm({ name: data.name, timezone: data.timezone, language: data.language, units: data.work_order_units.join("\n") });
      toast.show(t("admin.settings.saved"));
    },
    onError: () => toast.show(t("admin.settings.failed"), { tone: "error" }),
  });

  if (q.isPending || !form) return <Loading />;
  if (q.isError) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;

  return (
    <form
      className="card settings-form"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div className="form-grid">
        <label className="field">
          <span>{t("admin.settings.cityName")}</span>
          <input value={form.name} required maxLength={120} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </label>
        <label className="field">
          <span>{t("admin.settings.timezone")}</span>
          {zonesList.length ? (
            <select value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })}>
              {!zonesList.includes(form.timezone) && <option value={form.timezone}>{form.timezone}</option>}
              {zonesList.map((z) => (
                <option key={z} value={z}>
                  {z}
                </option>
              ))}
            </select>
          ) : (
            <input value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
          )}
        </label>
        <label className="field">
          <span>{t("admin.settings.language")}</span>
          <select value={form.language} onChange={(e) => setForm({ ...form, language: e.target.value })}>
            {q.data.languages.map((l) => (
              <option key={l} value={l}>
                {new Intl.DisplayNames([l], { type: "language" }).of(l) ?? l}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="field">
        <span>{t("admin.settings.units")}</span>
        <textarea rows={5} value={form.units} onChange={(e) => setForm({ ...form, units: e.target.value })} />
      </label>
      <p className="muted small">
        {t("admin.settings.unitsHint")}{" "}
        {form.units
          .split("\n")
          .map((u) => u.trim())
          .filter(Boolean)
          .map((u) => unitLabel(t, u))
          .join(" · ")}
      </p>
      <p className="muted small">{t("admin.settings.notYet")}</p>
      <div>
        <button type="submit" className="btn btn-primary" disabled={save.isPending}>
          {t("admin.settings.save")}
        </button>
      </div>
    </form>
  );
}

// ---------------- Audit ----------------

const PAGE = 50;

function AuditTab() {
  const { t, i18n } = useTranslation();
  const [action, setAction] = useState("");
  const [actor, setActor] = useState("");
  const [actorFilter, setActorFilter] = useState("");
  const actions = useMemo(() => Object.keys(t("admin.audit.actions", { returnObjects: true }) as Record<string, string>), [t]);

  const q = useInfiniteQuery({
    queryKey: ["audit", action, actorFilter],
    queryFn: ({ pageParam }) => api.audit({ action, actor: actorFilter, before_id: pageParam, limit: PAGE }),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (last) => (last.length === PAGE ? last[last.length - 1].id : undefined),
  });
  const rows = q.data?.pages.flat() ?? [];

  return (
    <>
      <form
        className="filters toolbar"
        onSubmit={(e) => {
          e.preventDefault();
          setActorFilter(actor.trim());
        }}
      >
        <select className="search" value={action} onChange={(e) => setAction(e.target.value)} aria-label={t("admin.audit.what")}>
          <option value="">{t("admin.audit.allActions")}</option>
          {actions.map((a) => (
            <option key={a} value={a}>
              {t(`admin.audit.actions.${a}`)}
            </option>
          ))}
        </select>
        <input
          className="search"
          type="search"
          placeholder={t("admin.audit.actor")}
          aria-label={t("admin.audit.actor")}
          value={actor}
          onChange={(e) => setActor(e.target.value)}
          onBlur={() => setActorFilter(actor.trim())}
        />
      </form>
      {q.isPending ? (
        <Loading />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : rows.length === 0 ? (
        <Empty>{t("admin.audit.empty")}</Empty>
      ) : (
        <div className="card table-card">
          <table className="table">
            <thead>
              <tr>
                <th>{t("admin.audit.when")}</th>
                <th>{t("admin.audit.who")}</th>
                <th>{t("admin.audit.what")}</th>
                <th>{t("admin.audit.details")}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td data-label={t("admin.audit.when")} className="nowrap small">
                    {formatDateTime(r.created_at, i18n.language)}
                  </td>
                  <td data-label={t("admin.audit.who")}>{r.actor}</td>
                  <td data-label={t("admin.audit.what")}>{t(`admin.audit.actions.${r.action}`, { defaultValue: humanize(r.action) })}</td>
                  <td data-label={t("admin.audit.details")} className="small muted audit-detail">
                    {describeDetail(r)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {q.hasNextPage && (
        <button type="button" className="btn" onClick={() => void q.fetchNextPage()} disabled={q.isFetchingNextPage}>
          {t("admin.audit.loadMore")}
        </button>
      )}
    </>
  );
}

/** Short, readable summary of an audit entry's details. */
function describeDetail(r: AuditEntry): string {
  const parts: string[] = [];
  if (r.entity_id && r.entity_type !== "user") parts.push(`${humanize(r.entity_type)} ${r.entity_id}`);
  for (const [k, v] of Object.entries(r.detail ?? {})) {
    if (v === null || v === undefined || v === "" || typeof v === "object") continue;
    parts.push(`${humanize(k)}: ${String(v)}`);
  }
  return parts.join(" · ") || "—";
}
