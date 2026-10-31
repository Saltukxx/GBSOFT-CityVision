import { useTranslation } from "react-i18next";
import { Inbox, type LucideIcon } from "lucide-react";
import { ApiError } from "../api/client";

export function Loading() {
  const { t } = useTranslation();
  return (
    <div className="state" role="status">
      <span className="spinner" aria-hidden="true" />
      {t("common.loading")}
    </div>
  );
}

export function ErrorState({ error, onRetry, notFoundText }: { error: unknown; onRetry?: () => void; notFoundText?: string }) {
  const { t } = useTranslation();
  const notFound = error instanceof ApiError && error.status === 404;
  return (
    <div className="state state-error" role="alert">
      <p>{notFound && notFoundText ? notFoundText : t("common.error")}</p>
      {!notFound && onRetry && (
        <button type="button" className="btn" onClick={onRetry}>
          {t("common.retry")}
        </button>
      )}
    </div>
  );
}

export function Empty({ children, icon: Icon = Inbox }: { children: React.ReactNode; icon?: LucideIcon }) {
  return (
    <div className="state state-empty">
      {children ? <Icon size={26} strokeWidth={1.6} aria-hidden="true" /> : null}
      {children}
    </div>
  );
}
