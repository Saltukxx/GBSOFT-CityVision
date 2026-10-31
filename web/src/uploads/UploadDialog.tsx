import { useEffect, useRef, useState, type DragEvent, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import { formatBytes } from "../lib/format";
import { useUploads } from "./UploadsContext";

const VIDEO_EXT = [".mp4", ".mov", ".mkv", ".avi"];
const TELEMETRY_EXT = [".srt", ".jsonl", ".json", ".csv"];

const ext = (name: string) => name.slice(name.lastIndexOf(".")).toLowerCase();
const stem = (name: string) => name.slice(0, name.lastIndexOf(".")) || name;
const today = () => new Date().toISOString().slice(0, 10);

/** Split dropped files into one video + one telemetry file (same-name .SRT preferred). */
function pickFiles(files: File[], current: { video: File | null; telemetry: File | null }) {
  const errors: string[] = [];
  let video = current.video;
  let telemetry = current.telemetry;
  const videos = files.filter((f) => VIDEO_EXT.includes(ext(f.name)));
  const teles = files.filter((f) => TELEMETRY_EXT.includes(ext(f.name)));
  for (const f of files) if (!videos.includes(f) && !teles.includes(f)) errors.push(f.name);
  if (videos.length) video = videos[0];
  if (teles.length) {
    const match = video && teles.find((f) => stem(f.name).toLowerCase() === stem(video!.name).toLowerCase());
    telemetry = match ?? teles[0];
  }
  return { video, telemetry, errors };
}

export function UploadDialog({ onClose }: { onClose: () => void }) {
  const { t, i18n } = useTranslation();
  const { start } = useUploads();
  const ref = useRef<HTMLDialogElement>(null);
  const videoInput = useRef<HTMLInputElement>(null);
  const teleInput = useRef<HTMLInputElement>(null);
  const [video, setVideo] = useState<File | null>(null);
  const [telemetry, setTelemetry] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [nameTouched, setNameTouched] = useState(false);
  const [date, setDate] = useState(today());
  const [routeId, setRouteId] = useState("");
  const [errors, setErrors] = useState<string[]>([]);
  const [dragging, setDragging] = useState(false);
  const routes = useQuery({ queryKey: ["routes"], queryFn: api.routes, staleTime: 300_000 });

  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
    return () => d?.close();
  }, []);

  const accept = (files: File[]) => {
    const picked = pickFiles(files, { video, telemetry });
    setVideo(picked.video);
    setTelemetry(picked.telemetry);
    if (picked.video && !nameTouched) {
      setName(stem(picked.video.name));
      // DJI files carry the capture date; fall back to today.
      setDate(new Date(picked.video.lastModified || Date.now()).toISOString().slice(0, 10));
    }
    setErrors(
      picked.errors.map((n) =>
        TELEMETRY_EXT.includes(ext(n)) ? t("flights.dialog.badTelemetry", { name: n }) : t("flights.dialog.badVideo", { name: n }),
      ),
    );
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    accept([...e.dataTransfer.files]);
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!video) {
      setErrors([t("flights.dialog.needVideo")]);
      return;
    }
    start(video, telemetry, { name: name.trim() || stem(video.name), flight_date: date || undefined, route_id: routeId || undefined });
    onClose();
  };

  return (
    <dialog ref={ref} className="dialog dialog-wide" onCancel={onClose} aria-labelledby="up-title">
      <form onSubmit={submit}>
        <h2 id="up-title">{t("flights.dialog.title")}</h2>

        <div
          className={`dropzone ${dragging ? "dropzone-active" : ""}`}
          onDragOver={(e) => {
            e.preventDefault();
            setDragging(true);
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
        >
          <p>
            {t("flights.dialog.drop")}{" "}
            <button type="button" className="btn-link" onClick={() => videoInput.current?.click()}>
              {t("flights.dialog.browse")}
            </button>
          </p>
          <p className="muted small">{t("flights.dialog.dropHint")}</p>
          <input
            ref={videoInput}
            type="file"
            hidden
            multiple
            accept={[...VIDEO_EXT, ...TELEMETRY_EXT].join(",")}
            onChange={(e) => accept([...(e.target.files ?? [])])}
          />
        </div>

        {(video || telemetry) && (
          <ul className="file-list">
            {video && (
              <li>
                <span className="file-kind">{t("flights.dialog.video")}</span>
                <span className="file-name">{video.name}</span>
                <span className="muted small">{formatBytes(video.size, i18n.language)}</span>
                <button type="button" className="btn-link" onClick={() => setVideo(null)}>
                  {t("flights.dialog.removeFile")}
                </button>
              </li>
            )}
            <li>
              <span className="file-kind">{t("flights.dialog.telemetry")}</span>
              {telemetry ? (
                <>
                  <span className="file-name">{telemetry.name}</span>
                  <span className="muted small">{formatBytes(telemetry.size, i18n.language)}</span>
                  <button type="button" className="btn-link" onClick={() => setTelemetry(null)}>
                    {t("flights.dialog.removeFile")}
                  </button>
                </>
              ) : (
                <button type="button" className="btn-link" onClick={() => teleInput.current?.click()}>
                  {t("flights.dialog.addTelemetry")}
                </button>
              )}
              <input
                ref={teleInput}
                type="file"
                hidden
                accept={TELEMETRY_EXT.join(",")}
                onChange={(e) => accept([...(e.target.files ?? [])])}
              />
            </li>
          </ul>
        )}
        {video && !telemetry && <p className="form-warning">{t("flights.dialog.noTelemetryWarning")}</p>}
        {errors.map((err) => (
          <p key={err} className="form-error" role="alert">
            {err}
          </p>
        ))}

        <div className="form-grid">
          <label className="field">
            <span>{t("flights.dialog.name")}</span>
            <input
              value={name}
              maxLength={120}
              onChange={(e) => {
                setName(e.target.value);
                setNameTouched(true);
              }}
            />
          </label>
          <label className="field">
            <span>{t("flights.dialog.date")}</span>
            <input type="date" value={date} max={today()} onChange={(e) => setDate(e.target.value)} />
          </label>
          {!!routes.data?.length && (
            <label className="field">
              <span>{t("flights.dialog.route")}</span>
              <select value={routeId} onChange={(e) => setRouteId(e.target.value)}>
                <option value="">{t("flights.dialog.noRoute")}</option>
                {routes.data.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.name}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>

        <div className="dialog-actions">
          <button type="button" className="btn" onClick={onClose}>
            {t("flights.dialog.cancel")}
          </button>
          <button type="submit" className="btn btn-primary" disabled={!video}>
            {t("flights.dialog.start")}
          </button>
        </div>
      </form>
    </dialog>
  );
}
