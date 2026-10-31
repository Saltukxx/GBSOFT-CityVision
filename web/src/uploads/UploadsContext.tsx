import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ApiError, api } from "../api/client";
import type { Flight } from "../api/types";

/**
 * Resumable flight uploads that keep running while the user moves around the app.
 *
 * The server knows which chunks it has, so resuming = asking for the flight and
 * sending what is missing. Browsers can't keep a File across reloads, so after a
 * reload the user picks the same file again; we match it by name + size + date
 * (stored in localStorage) and continue the existing upload.
 */

export type UploadStatus = "starting" | "uploading" | "paused" | "finishing" | "done" | "error" | "cancelled";

export interface UploadTask {
  key: string;
  flightId?: string;
  name: string;
  fileName: string;
  size: number;
  sent: number;
  status: UploadStatus;
  /** i18n key suffix under flights.errors.* */
  error?: string;
  bytesPerSec?: number;
  resumed: boolean;
}

export interface UploadMeta {
  name?: string;
  route_id?: string;
  flight_date?: string;
}

interface UploadsApi {
  tasks: UploadTask[];
  start: (video: File, telemetry: File | null, meta: UploadMeta) => void;
  pause: (key: string) => void;
  resume: (key: string) => void;
  cancel: (key: string) => void;
  dismiss: (key: string) => void;
}

const UploadsContext = createContext<UploadsApi | null>(null);

const PARALLEL = 3;
const MAX_RETRIES = 6;
const RESUME_KEY = "cv_flight_uploads";

function fingerprint(f: File): string {
  return `${f.name}|${f.size}|${f.lastModified}`;
}

function readResumeMap(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(RESUME_KEY) || "{}") as Record<string, string>;
  } catch {
    return {};
  }
}

function writeResumeMap(fp: string, flightId: string | null): void {
  try {
    const map = readResumeMap();
    if (flightId) map[fp] = flightId;
    else delete map[fp];
    localStorage.setItem(RESUME_KEY, JSON.stringify(map));
  } catch {
    /* storage unavailable: resume after reload won't work, uploads still do */
  }
}

/** Flight ids this browser started and has not finished. */
export function pendingUploadIds(): Set<string> {
  return new Set(Object.values(readResumeMap()));
}

function errorCode(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 401) return "signedOut";
    if (err.status === 403) return "forbidden";
    if (err.status === 413) return "tooLarge";
    if (typeof err.detail === "string" && /^[a-z_]+$/.test(err.detail)) return err.detail;
    return "server";
  }
  return "network";
}

const sleep = (ms: number, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    const t = window.setTimeout(resolve, ms);
    signal.addEventListener("abort", () => {
      window.clearTimeout(t);
      reject(new DOMException("aborted", "AbortError"));
    });
  });

interface Runtime {
  video: File;
  telemetry: File | null;
  meta: UploadMeta;
  controller: AbortController | null;
  chunkSize: number;
  received: Set<number>;
  telemetrySent: boolean;
  samples: { t: number; sent: number }[];
}

export function UploadsProvider({ children }: { children: ReactNode }) {
  const [tasks, setTasks] = useState<UploadTask[]>([]);
  const runtimes = useRef(new Map<string, Runtime>());
  const qc = useQueryClient();

  const patch = useCallback((key: string, p: Partial<UploadTask>) => {
    setTasks((list) => list.map((t) => (t.key === key ? { ...t, ...p } : t)));
  }, []);

  const refreshFlights = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ["flights"] });
    void qc.invalidateQueries({ queryKey: ["flight"] });
  }, [qc]);

  const run = useCallback(
    async (key: string, flightIdIn?: string) => {
      const rt = runtimes.current.get(key);
      if (!rt) return;
      const controller = new AbortController();
      rt.controller = controller;
      const { signal } = controller;
      let flightId = flightIdIn;

      try {
        // 1. Find or create the server-side upload.
        if (!flightId) {
          const fp = fingerprint(rt.video);
          const previous = readResumeMap()[fp];
          let existing: Flight | null = null;
          if (previous) {
            try {
              existing = await api.flight(previous);
            } catch {
              existing = null;
            }
          }
          if (existing && existing.status === "uploading" && existing.upload) {
            flightId = existing.id;
            patch(key, { resumed: true, name: existing.name });
          } else {
            const created = await api.createUpload({
              filename: rt.video.name,
              size: rt.video.size,
              ...rt.meta,
            });
            flightId = created.id;
            writeResumeMap(fp, flightId);
          }
          patch(key, { flightId });
          refreshFlights();
        }

        const state = await api.flight(flightId);
        if (state.status !== "uploading" || !state.upload) {
          patch(key, { status: "done", sent: rt.video.size });
          writeResumeMap(fingerprint(rt.video), null);
          return;
        }
        rt.chunkSize = state.upload.chunk_size;
        rt.received = new Set(state.upload.received);
        const total = state.upload.chunks;
        const sentBytes = () =>
          [...rt.received].reduce((sum, i) => sum + Math.min(rt.chunkSize, rt.video.size - i * rt.chunkSize), 0);
        patch(key, { status: "uploading", sent: sentBytes(), error: undefined });

        // 2. Telemetry (small, one request).
        if (rt.telemetry && !rt.telemetrySent) {
          await api.putTelemetry(flightId, rt.telemetry);
          rt.telemetrySent = true;
        }

        // 3. Missing chunks, a few in parallel, each retried with backoff.
        const queue = Array.from({ length: total }, (_, i) => i).filter((i) => !rt.received.has(i));
        const sendOne = async (index: number) => {
          for (let attempt = 0; ; attempt++) {
            if (signal.aborted) throw new DOMException("aborted", "AbortError");
            const start = index * rt.chunkSize;
            const blob = rt.video.slice(start, Math.min(start + rt.chunkSize, rt.video.size));
            try {
              await api.putChunk(flightId!, index, blob, signal);
              rt.received.add(index);
              const sent = sentBytes();
              const now = performance.now();
              rt.samples = [...rt.samples.filter((s) => now - s.t < 10_000), { t: now, sent }];
              const first = rt.samples[0];
              const bytesPerSec = now > first.t ? ((sent - first.sent) / (now - first.t)) * 1000 : undefined;
              patch(key, { sent, bytesPerSec });
              return;
            } catch (err) {
              if (signal.aborted || (err instanceof DOMException && err.name === "AbortError")) throw err;
              const code = errorCode(err);
              const fatal = err instanceof ApiError && [401, 403, 404, 409, 413].includes(err.status);
              if (fatal || attempt >= MAX_RETRIES) throw err;
              patch(key, { error: code === "network" ? "retrying" : code });
              await sleep(Math.min(30_000, 1000 * 2 ** attempt), signal);
              patch(key, { error: undefined });
            }
          }
        };
        const workers = Array.from({ length: Math.min(PARALLEL, queue.length) }, async () => {
          while (queue.length) {
            const next = queue.shift();
            if (next !== undefined) await sendOne(next);
          }
        });
        await Promise.all(workers);

        // 4. Tell the server we're done; it starts processing.
        patch(key, { status: "finishing" });
        await api.completeUpload(flightId);
        writeResumeMap(fingerprint(rt.video), null);
        patch(key, { status: "done", sent: rt.video.size, bytesPerSec: undefined });
        runtimes.current.delete(key);
        refreshFlights();
      } catch (err) {
        if (signal.aborted || (err instanceof DOMException && err.name === "AbortError")) return; // paused / cancelled
        patch(key, { status: "error", error: errorCode(err), bytesPerSec: undefined });
        refreshFlights();
      } finally {
        if (rt.controller === controller) rt.controller = null;
      }
    },
    [patch, refreshFlights],
  );

  const start = useCallback<UploadsApi["start"]>(
    (video, telemetry, meta) => {
      const key = crypto.randomUUID();
      runtimes.current.set(key, {
        video,
        telemetry,
        meta,
        controller: null,
        chunkSize: 0,
        received: new Set(),
        telemetrySent: false,
        samples: [],
      });
      setTasks((list) => [
        ...list,
        {
          key,
          name: meta.name || video.name,
          fileName: video.name,
          size: video.size,
          sent: 0,
          status: "starting",
          resumed: false,
        },
      ]);
      void run(key);
    },
    [run],
  );

  const pause = useCallback(
    (key: string) => {
      runtimes.current.get(key)?.controller?.abort();
      patch(key, { status: "paused", bytesPerSec: undefined });
    },
    [patch],
  );

  const resume = useCallback(
    (key: string) => {
      const task = tasks.find((t) => t.key === key);
      if (!task) return;
      patch(key, { status: "uploading", error: undefined });
      void run(key, task.flightId);
    },
    [tasks, patch, run],
  );

  const cancel = useCallback(
    (key: string) => {
      const rt = runtimes.current.get(key);
      rt?.controller?.abort();
      const task = tasks.find((t) => t.key === key);
      patch(key, { status: "cancelled", bytesPerSec: undefined });
      if (rt) writeResumeMap(fingerprint(rt.video), null);
      runtimes.current.delete(key);
      if (task?.flightId) void api.cancelUpload(task.flightId).catch(() => undefined).finally(refreshFlights);
    },
    [tasks, patch, refreshFlights],
  );

  const dismiss = useCallback((key: string) => {
    runtimes.current.delete(key);
    setTasks((list) => list.filter((t) => t.key !== key));
  }, []);

  // Warn before closing the tab while bytes are still moving.
  const busy = tasks.some((t) => ["starting", "uploading", "finishing"].includes(t.status));
  useEffect(() => {
    if (!busy) return;
    const onBeforeUnload = (e: BeforeUnloadEvent) => {
      e.preventDefault();
    };
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, [busy]);

  const value = useMemo(() => ({ tasks, start, pause, resume, cancel, dismiss }), [tasks, start, pause, resume, cancel, dismiss]);
  return <UploadsContext.Provider value={value}>{children}</UploadsContext.Provider>;
}

export function useUploads(): UploadsApi {
  const ctx = useContext(UploadsContext);
  if (!ctx) throw new Error("useUploads must be used inside UploadsProvider");
  return ctx;
}
