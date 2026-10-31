import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

/** Confirmation for destructive actions (never the browser's confirm()). */
export function ConfirmDialog({
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
            {t("common.cancel")}
          </button>
          <button type="submit" className="btn btn-danger">
            {confirmLabel}
          </button>
        </div>
      </form>
    </dialog>
  );
}
