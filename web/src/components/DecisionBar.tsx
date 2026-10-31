import { useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { REVIEW_REASONS, type ReviewReason } from "../api/types";
import type { Decision } from "../lib/useDecision";
import { unitLabel, useCitySettings } from "../lib/useCitySettings";

export function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  return el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName);
}

interface Props {
  onDecide: (d: Decision) => void;
  busy?: boolean;
  /** Listen for A / R / U / W (and 1–7 for reasons) on the whole window. */
  keyboard?: boolean;
  /** Changes when the shown event changes, to reset any open sub-step. */
  resetKey?: string;
}

export function DecisionBar({ onDecide, busy = false, keyboard = false, resetKey }: Props) {
  const { t } = useTranslation();
  const [mode, setMode] = useState<"idle" | "reason" | "workOrder">("idle");

  useEffect(() => setMode("idle"), [resetKey]);

  const decide = (d: Decision) => {
    setMode("idle");
    onDecide(d);
  };

  useEffect(() => {
    if (!keyboard) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTypingTarget(e.target) || busy) return;
      const k = e.key.toLowerCase();
      if (mode === "reason") {
        const n = Number(e.key);
        if (n >= 1 && n <= REVIEW_REASONS.length) {
          e.preventDefault();
          decide({ kind: "falseAlarm", reason: REVIEW_REASONS[n - 1] });
        } else if (k === "escape") {
          setMode("idle");
        } else if (k === "enter" || k === "r") {
          e.preventDefault();
          decide({ kind: "falseAlarm" });
        }
        return;
      }
      if (mode === "workOrder") {
        if (k === "escape") setMode("idle");
        return;
      }
      if (k === "a") decide({ kind: "confirm" });
      else if (k === "r") setMode("reason");
      else if (k === "u") decide({ kind: "unsure" });
      else if (k === "w") {
        e.preventDefault();
        setMode("workOrder");
      } else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [keyboard, mode, busy]);

  return (
    <div className="decision">
      <div className="decision-buttons">
        <button type="button" className="btn btn-confirm" disabled={busy} onClick={() => decide({ kind: "confirm" })}>
          {t("review.actions.confirm")} {keyboard && <kbd>A</kbd>}
        </button>
        <button
          type="button"
          className="btn btn-reject"
          disabled={busy}
          aria-expanded={mode === "reason"}
          onClick={() => setMode(mode === "reason" ? "idle" : "reason")}
        >
          {t("review.actions.falseAlarm")} {keyboard && <kbd>R</kbd>}
        </button>
        <button type="button" className="btn" disabled={busy} onClick={() => decide({ kind: "unsure" })}>
          {t("review.actions.unsure")} {keyboard && <kbd>U</kbd>}
        </button>
        <button type="button" className="btn btn-primary" disabled={busy} onClick={() => setMode("workOrder")}>
          {t("review.actions.workOrder")} {keyboard && <kbd>W</kbd>}
        </button>
      </div>

      {mode === "reason" && (
        <div className="reasons" role="group" aria-label={t("review.reasonPrompt")}>
          <p className="reasons-prompt">{t("review.reasonPrompt")}</p>
          <div className="chips">
            {REVIEW_REASONS.map((r: ReviewReason, i) => (
              <button key={r} type="button" className="chip" disabled={busy} onClick={() => decide({ kind: "falseAlarm", reason: r })}>
                {keyboard && <kbd>{i + 1}</kbd>} {t(`review.reasons.${r}`)}
              </button>
            ))}
            <button type="button" className="chip chip-quiet" disabled={busy} onClick={() => decide({ kind: "falseAlarm" })}>
              {t("review.skipReason")}
            </button>
          </div>
        </div>
      )}

      {mode === "workOrder" && (
        <WorkOrderDialog onCancel={() => setMode("idle")} onSubmit={(unit, note) => decide({ kind: "workOrder", unit, note })} busy={busy} />
      )}
    </div>
  );
}

function WorkOrderDialog({
  onCancel,
  onSubmit,
  busy,
}: {
  onCancel: () => void;
  onSubmit: (unit: string, note: string) => void;
  busy: boolean;
}) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDialogElement>(null);
  const { units } = useCitySettings();
  const [unit, setUnit] = useState<string>(units[0]);
  const [note, setNote] = useState("");

  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
    return () => d?.close();
  }, []);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    onSubmit(unit, note.trim());
  };

  return (
    <dialog ref={ref} className="dialog" onCancel={onCancel} aria-labelledby="wo-title">
      <form onSubmit={submit}>
        <h2 id="wo-title">{t("workOrder.title")}</h2>
        <label className="field">
          <span>{t("workOrder.unit")}</span>
          <select value={unit} onChange={(e) => setUnit(e.target.value)} autoFocus>
            {units.map((u) => (
              <option key={u} value={u}>
                {unitLabel(t, u)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("workOrder.note")}</span>
          <textarea rows={3} value={note} placeholder={t("workOrder.notePlaceholder")} onChange={(e) => setNote(e.target.value)} />
        </label>
        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onCancel}>
            {t("workOrder.cancel")}
          </button>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {t("workOrder.submit")}
          </button>
        </div>
      </form>
    </dialog>
  );
}
