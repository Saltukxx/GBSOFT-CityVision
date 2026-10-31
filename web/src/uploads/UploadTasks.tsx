import { useTranslation } from "react-i18next";
import { formatBytes, formatDuration } from "../lib/format";
import { useUploads, type UploadTask } from "./UploadsContext";

export function UploadTasks() {
  const { t } = useTranslation();
  const { tasks } = useUploads();
  if (!tasks.length) return null;
  const active = tasks.some((x) => ["starting", "uploading", "finishing"].includes(x.status));
  return (
    <section className="card upload-tasks" aria-label={t("flights.task.activeUploads")}>
      <h3>{t("flights.task.activeUploads")}</h3>
      <ul>
        {tasks.map((task) => (
          <TaskRow key={task.key} task={task} />
        ))}
      </ul>
      {active && <p className="muted small">{t("flights.task.leaveWarning")}</p>}
    </section>
  );
}

function TaskRow({ task }: { task: UploadTask }) {
  const { t, i18n } = useTranslation();
  const { pause, resume, cancel, dismiss } = useUploads();
  const lang = i18n.language;
  const pct = task.size ? Math.floor((task.sent / task.size) * 100) : 0;

  let line: string;
  switch (task.status) {
    case "starting":
      line = t("flights.task.starting");
      break;
    case "uploading": {
      line = t("flights.task.uploading", { sent: formatBytes(task.sent, lang), total: formatBytes(task.size, lang) });
      if (task.bytesPerSec && task.bytesPerSec > 0) {
        const eta = (task.size - task.sent) / task.bytesPerSec;
        line += ` · ${t("flights.task.speed", { speed: formatBytes(task.bytesPerSec, lang), eta: formatDuration(eta, lang) })}`;
      }
      break;
    }
    case "paused":
      line = `${t("flights.task.paused")} · ${formatBytes(task.sent, lang)} / ${formatBytes(task.size, lang)}`;
      break;
    case "finishing":
      line = t("flights.task.finishing");
      break;
    case "done":
      line = t("flights.task.done");
      break;
    case "cancelled":
      line = t("flights.task.cancelled");
      break;
    default:
      line = t(`flights.errors.${task.error ?? "server"}`, { defaultValue: t("flights.errors.server") });
  }
  const retrying = task.status === "uploading" && task.error;

  return (
    <li className={`task task-${task.status}`}>
      <div className="task-head">
        <span className="task-name">{task.name}</span>
        <span className="mono small">{pct}%</span>
      </div>
      <div
        className="progress"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        aria-label={task.name}
      >
        <span style={{ width: `${pct}%` }} />
      </div>
      <div className="task-foot">
        <span className={`small ${task.status === "error" ? "text-danger" : "muted"}`} aria-live="polite">
          {retrying ? t(`flights.errors.${task.error}`, { defaultValue: t("flights.errors.retrying") }) : line}
          {task.resumed && task.status === "uploading" && !retrying && ` · ${t("flights.task.resumed")}`}
        </span>
        <span className="task-actions">
          {task.status === "uploading" && (
            <button type="button" className="btn-link" onClick={() => pause(task.key)}>
              {t("flights.task.pause")}
            </button>
          )}
          {(task.status === "paused" || task.status === "error") && (
            <button type="button" className="btn-link" onClick={() => resume(task.key)}>
              {task.status === "error" ? t("flights.task.retry") : t("flights.task.resume")}
            </button>
          )}
          {["starting", "uploading", "paused", "error"].includes(task.status) && (
            <button type="button" className="btn-link btn-link-danger" onClick={() => cancel(task.key)}>
              {t("flights.task.cancel")}
            </button>
          )}
          {["done", "cancelled"].includes(task.status) && (
            <button type="button" className="btn-link" onClick={() => dismiss(task.key)}>
              {t("flights.task.dismiss")}
            </button>
          )}
        </span>
      </div>
    </li>
  );
}
