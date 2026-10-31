import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Brand } from "../components/Brand";

export function LoginPage({ expired }: { expired?: boolean }) {
  const { t } = useTranslation();
  const { signIn } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(expired ? t("auth.expired") : null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(username.trim(), password);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? t("auth.invalid") : t("auth.unavailable"));
      setBusy(false);
    }
  };

  const points = t("auth.panelPoints", { returnObjects: true }) as string[];
  return (
    <main className="login">
      <section className="login-panel" aria-hidden="true">
        <Brand large />
        <div className="login-pitch">
          <h2>{t("auth.panelTitle")}</h2>
          <p>{t("auth.panelBody")}</p>
          <ul>
            {points.map((p) => (
              <li key={p}>{p}</li>
            ))}
          </ul>
        </div>
        <svg className="login-grid" viewBox="0 0 400 300" preserveAspectRatio="xMidYMid slice">
          <path d="M-10 214 C 90 192, 140 122, 220 128 S 340 72, 410 58" />
          <path d="M150 -10 C 160 80, 120 180, 150 310" className="mid" />
          <path d="M30 310 L 112 -10 M 205 310 L 262 -10 M 318 310 L 352 -10 M -10 88 L 410 150 M -10 252 L 410 232 M -10 40 L 410 70" className="thin" />
          <g className="blocks">
            <rect x="62" y="104" width="34" height="22" rx="2" /><rect x="168" y="168" width="28" height="30" rx="2" />
            <rect x="272" y="168" width="40" height="24" rx="2" /><rect x="228" y="40" width="24" height="20" rx="2" />
            <rect x="330" y="96" width="30" height="26" rx="2" /><rect x="84" y="236" width="40" height="20" rx="2" />
          </g>
          <rect x="203" y="111" width="34" height="34" rx="3" className="target" />
          <circle cx="220" cy="128" r="3.5" className="dot" />
          <rect x="300" y="196" width="26" height="26" rx="3" className="target target-2" />
          <circle cx="313" cy="209" r="3" className="dot dot-2" />
        </svg>
      </section>
      <section className="login-form-wrap">
        <form className="login-card" onSubmit={submit}>
          <div className="login-brand-small">
            <Brand />
          </div>
          <h1>{t("auth.title")}</h1>
          <p className="muted">{t("auth.subtitle")}</p>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <label className="field">
            <span>{t("auth.username")}</span>
            <input autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} required autoFocus />
          </label>
          <label className="field">
            <span>{t("auth.password")}</span>
            <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          </label>
          <button type="submit" className="btn btn-primary btn-block btn-lg" disabled={busy}>
            {busy ? t("auth.submitting") : t("auth.submit")}
          </button>
        </form>
      </section>
    </main>
  );
}
