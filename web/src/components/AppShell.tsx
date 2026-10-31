import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, NavLink, Outlet } from "react-router-dom";
import {
  ClipboardCheck,
  FileBarChart,
  LayoutDashboard,
  LogOut,
  Map,
  PanelLeftClose,
  PanelLeftOpen,
  Plane,
  Route,
  Settings2,
  Tags,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { api } from "../api/client";
import { ACTIVE_FLIGHT_STATUSES, type Flight } from "../api/types";
import { useAuth, useCurrentUser } from "../auth/AuthContext";
import { SUPPORTED_LANGUAGES } from "../i18n";
import { formatNumber } from "../lib/format";
import { useCitySettings } from "../lib/useCitySettings";
import { useUploads } from "../uploads/UploadsContext";
import { BrandMark } from "./Brand";

type Signal = { value: string; tone?: "alert" | "info" | "quiet"; title?: string } | null;

interface NavItem {
  to: string;
  key: string;
  icon: LucideIcon;
  roles?: string[];
}

// Grouped the way the work flows: find it, act on it, learn from it, run the system.
const GROUPS: { key: string; items: NavItem[] }[] = [
  {
    key: "operate",
    items: [
      { to: "/", key: "overview", icon: LayoutDashboard },
      { to: "/review", key: "review", icon: ClipboardCheck },
      { to: "/map", key: "map", icon: Map },
      { to: "/flights", key: "flights", icon: Plane },
      { to: "/routes", key: "routes", icon: Route },
    ],
  },
  {
    key: "act",
    items: [
      { to: "/work-orders", key: "workOrders", icon: Wrench },
      { to: "/reports", key: "reports", icon: FileBarChart },
    ],
  },
  { key: "improve", items: [{ to: "/labelling", key: "labelling", icon: Tags, roles: ["superadmin"] }] },
  { key: "manage", items: [{ to: "/admin", key: "admin", icon: Settings2, roles: ["admin", "superadmin"] }] },
];

const COLLAPSE_KEY = "cv_nav_collapsed";

function initials(name: string): string {
  const parts = name.trim().split(/[\s._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).toUpperCase() || "?";
}

/** Ticking clock in the city's own time zone (the city may not be where you are). */
function useCityClock(timeZone: string | undefined, lang: string) {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), 20_000);
    return () => window.clearInterval(id);
  }, []);
  return useMemo(() => {
    try {
      const fmt = new Intl.DateTimeFormat(lang, { hour: "2-digit", minute: "2-digit", hourCycle: "h23", timeZone, timeZoneName: "shortOffset" });
      const parts = fmt.formatToParts(now);
      const time = parts.filter((p) => ["hour", "minute", "literal"].includes(p.type)).map((p) => p.value).join("").trim();
      const zone = parts.find((p) => p.type === "timeZoneName")?.value ?? "";
      return { time, zone };
    } catch {
      return { time: "", zone: "" };
    }
  }, [now, timeZone, lang]);
}

function relativeTime(iso: string, lang: string): string {
  const diff = (new Date(iso).getTime() - Date.now()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(lang, { numeric: "auto" });
  const abs = Math.abs(diff);
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  return rtf.format(Math.round(diff / 86400), "day");
}

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
}

export function AppShell() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const { signOut } = useAuth();
  const { user, devMode } = useCurrentUser();
  const city = useCitySettings();
  const [collapsed, setCollapsed] = useState(readCollapsed);

  const kpis = useQuery({ queryKey: ["kpis"], queryFn: api.kpis, refetchInterval: 60_000 });
  const flights = useQuery({
    queryKey: ["flights"],
    queryFn: api.flights,
    refetchInterval: (q) => (q.state.data?.some((f) => ACTIVE_FLIGHT_STATUSES.includes(f.status)) ? 5000 : 120_000),
  });
  const labelling = useQuery({
    queryKey: ["labelling", "count"],
    queryFn: () => api.labellingQueue(false, 1),
    enabled: user.role === "superadmin",
    refetchInterval: 120_000,
  });
  const { tasks } = useUploads();
  const clock = useCityClock(city.data?.timezone, lang);

  const moving = tasks.filter((x) => ["starting", "uploading", "finishing"].includes(x.status));
  const uploadPct = moving.length
    ? Math.floor((moving.reduce((s, x) => s + x.sent, 0) / Math.max(1, moving.reduce((s, x) => s + x.size, 0))) * 100)
    : null;
  const pending = kpis.data?.review_queue ?? 0;
  const openOrders = kpis.data?.open_work_orders ?? 0;
  const latest: Flight | undefined = flights.data?.find((f) => !["cancelled", "duplicate"].includes(f.status));

  const signals: Record<string, Signal> = {
    review: pending ? { value: formatNumber(pending, lang), tone: "alert", title: t("nav.waiting", { count: pending }) } : null,
    flights: uploadPct !== null ? { value: `${uploadPct}%`, tone: "info", title: t("flights.task.activeUploads") } : null,
    workOrders: openOrders ? { value: formatNumber(openOrders, lang), tone: "quiet", title: t("nav.openOrders", { count: openOrders }) } : null,
    labelling: labelling.data?.counts.todo ? { value: formatNumber(labelling.data.counts.todo, lang), tone: "quiet" } : null,
  };

  const toggle = () => {
    setCollapsed((c) => {
      try {
        localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1");
      } catch {
        /* per-browser convenience only */
      }
      return !c;
    });
  };

  const name = devMode ? t("auth.localUser") : user.display_name || user.username;
  const cityName = city.data?.name ?? user.city_id ?? "";

  return (
    <div className={`shell ${collapsed ? "shell-collapsed" : ""}`}>
      <aside className="sidebar">
        <header className="deck">
          <svg className="deck-topo" viewBox="0 0 240 120" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
            <path d="M-10 92c40-18 70-6 104-24s60-40 104-30 50 8 52 8" />
            <path d="M-10 108c46-14 80-2 118-20s58-34 98-26 40 10 44 10" />
            <path d="M-10 76c34-20 66-12 96-30s64-38 108-30 40 6 56 6" />
            <path d="M40 130c10-30 40-42 70-44s56-24 64-50" />
            <path d="M-10 60c30-16 52-14 80-30S120-2 150 4" />
          </svg>
          <div className="deck-top">
            <Link to="/" className="brand" aria-label="CityVision">
              <BrandMark size={22} />
              <span className="brand-name">
                City<span>Vision</span>
              </span>
            </Link>
            <button type="button" className="icon-btn deck-collapse" onClick={toggle} title={collapsed ? t("nav.expand") : t("nav.collapse")} aria-label={collapsed ? t("nav.expand") : t("nav.collapse")}>
              {collapsed ? <PanelLeftOpen size={17} aria-hidden="true" /> : <PanelLeftClose size={17} aria-hidden="true" />}
            </button>
          </div>
          {cityName && (
            <div className="deck-city" title={t("nav.localTime", { city: cityName })}>
              <span className="deck-city-name">{cityName}</span>
              {clock.time && (
                <span className="deck-clock">
                  <span className="mono">{clock.time}</span>
                  <span className="deck-zone">{clock.zone}</span>
                </span>
              )}
            </div>
          )}
        </header>

        <nav className="nav" aria-label={t("nav.main")}>
          {GROUPS.map((g) => {
            const items = g.items.filter((n) => !n.roles || n.roles.includes(user.role));
            if (!items.length) return null;
            return (
              <div key={g.key} className="nav-group">
                <p className="nav-group-label">{t(`nav.groups.${g.key}`)}</p>
                <ul>
                  {items.map((n) => {
                    const sig = signals[n.key];
                    return (
                      <li key={n.key}>
                        <NavLink to={n.to} end={n.to === "/"} className="nav-item" title={collapsed ? t(`nav.${n.key}`) : undefined}>
                          <span className="nav-frame" aria-hidden="true" />
                          <n.icon className="nav-icon" size={18} strokeWidth={1.8} aria-hidden="true" />
                          <span className="nav-label">{t(`nav.${n.key}`)}</span>
                          {sig && (
                            <span className={`nav-signal nav-signal-${sig.tone}`} title={sig.title}>
                              {sig.tone === "alert" && <span className="nav-pulse" aria-hidden="true" />}
                              {sig.value}
                            </span>
                          )}
                        </NavLink>
                      </li>
                    );
                  })}
                </ul>
              </div>
            );
          })}
        </nav>

        <div className="sidebar-foot">
          <Link to={latest ? `/flights/${latest.id}` : "/flights"} className="telemetry">
            <span className="telemetry-head">
              <span className={`telemetry-dot ${latest && ACTIVE_FLIGHT_STATUSES.includes(latest.status) ? "telemetry-dot-live" : ""}`} aria-hidden="true" />
              {t("nav.lastFlight")}
              {latest && <span className="telemetry-when">{relativeTime(latest.created_at, lang)}</span>}
            </span>
            {latest ? (
              <>
                <span className="telemetry-name">{latest.name}</span>
                {latest.status === "analyzing" || latest.status === "received" ? (
                  <span className="telemetry-bar" role="progressbar" aria-valuenow={Math.round((latest.progress ?? 0) * 100)} aria-valuemin={0} aria-valuemax={100}>
                    <span style={{ width: `${Math.round((latest.progress ?? 0) * 100)}%` }} />
                  </span>
                ) : (
                  <span className="telemetry-sub">
                    {latest.status === "succeeded"
                      ? t("flights.candidates", { count: latest.candidates })
                      : latest.status === "uploading"
                        ? t("nav.uploading")
                        : t(`flights.status.${latest.status}`)}
                  </span>
                )}
              </>
            ) : (
              <span className="telemetry-sub">{t("nav.noFlights")}</span>
            )}
          </Link>

          {SUPPORTED_LANGUAGES.length > 1 && (
            <label className="field field-inline">
              <span>{t("common.language")}</span>
              <select value={i18n.language} onChange={(e) => void i18n.changeLanguage(e.target.value)}>
                {SUPPORTED_LANGUAGES.map((l) => (
                  <option key={l.code} value={l.code}>
                    {l.label}
                  </option>
                ))}
              </select>
            </label>
          )}
          <div className="user">
            <span className="avatar" aria-hidden="true">
              {initials(name)}
            </span>
            <span className="user-text">
              <span className="user-name">{name}</span>
              <span className="user-role">{t(`roles.${user.role}`)}</span>
            </span>
            {!devMode && (
              <button type="button" className="icon-btn" onClick={() => signOut()} title={t("auth.signOut")} aria-label={t("auth.signOut")}>
                <LogOut size={16} aria-hidden="true" />
              </button>
            )}
          </div>
        </div>
      </aside>
      <main className="main">
        {devMode && <div className="banner">{t("auth.devMode")}</div>}
        <Outlet />
      </main>
    </div>
  );
}
