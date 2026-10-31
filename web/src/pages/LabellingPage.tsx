import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { Ban, Download, FlaskConical, SkipForward, Trash2, Check } from "lucide-react";
import { ApiError, api, downloadAuthed } from "../api/client";
import type { LabelBox, LabelItem, LabelKind } from "../api/types";
import { useCurrentUser } from "../auth/AuthContext";
import { BoxEditor, CLASS_COLORS } from "../components/BoxEditor";
import { isTypingTarget } from "../components/DecisionBar";
import { Empty, ErrorState, Loading } from "../components/States";
import { Thumb } from "../components/Thumb";
import { useToast } from "../components/Toast";
import { eventTypeLabel, formatDateTime } from "../lib/format";

const CONFIRMED = new Set(["correct", "confirmed", "work_order"]);

export function LabellingPage() {
  const { t, i18n } = useTranslation();
  const { user } = useCurrentUser();
  const [params, setParams] = useSearchParams();
  const done = params.get("tab") === "done";
  const selectedId = params.get("e");
  const toast = useToast();
  const [exporting, setExporting] = useState(false);

  const queue = useQuery({ queryKey: ["labelling", done], queryFn: () => api.labellingQueue(done), enabled: user.role === "superadmin" });
  const classes = useQuery({ queryKey: ["labelling-classes"], queryFn: api.labellingClasses, staleTime: Infinity, enabled: user.role === "superadmin" });
  const items = useMemo(() => queue.data?.items ?? [], [queue.data]);

  const select = useCallback(
    (id: string | null) =>
      setParams(
        (p) => {
          const n = new URLSearchParams(p);
          if (id) n.set("e", id);
          else n.delete("e");
          return n;
        },
        { replace: true },
      ),
    [setParams],
  );
  const setTab = (tab: "todo" | "done") => setParams(tab === "done" ? { tab } : {}, { replace: true });

  useEffect(() => {
    if (!selectedId && items.length) select(items[0].event_id);
  }, [selectedId, items, select]);

  if (user.role !== "superadmin") return <Empty>{t("admin.forbidden")}</Empty>;

  const counts = queue.data?.counts;
  const exportSet = async () => {
    setExporting(true);
    try {
      await downloadAuthed("/api/labelling/export.zip", "cityvision-labels.zip");
      toast.show(t("labelling.exported"));
    } catch (err) {
      toast.show(err instanceof ApiError && err.status === 404 ? t("labelling.exportEmpty") : t("labelling.exportFailed"), { tone: "error" });
    } finally {
      setExporting(false);
    }
  };

  const next = (id: string) => {
    const idx = items.findIndex((x) => x.event_id === id);
    const n = done ? items[idx + 1] : items.filter((x) => x.event_id !== id)[idx] ?? items[idx - 1];
    select(n && n.event_id !== id ? n.event_id : null);
  };

  return (
    <div className="review labelling">
      <section className="review-list">
        <header className="page-head page-head-actions">
          <div>
            <h1>{t("labelling.title")}</h1>
            {counts && (
              <span className="muted small">
                {t("labelling.stats", { todo: counts.todo, pos: counts.by_kind.positive ?? 0, neg: counts.by_kind.negative ?? 0 })}
              </span>
            )}
          </div>
        </header>
        <button type="button" className="btn" onClick={() => void exportSet()} disabled={exporting}>
          <Download size={16} aria-hidden="true" /> {exporting ? t("labelling.exporting") : t("labelling.export")}
        </button>
        <div className="segmented-tabs" role="tablist">
          <button type="button" role="tab" aria-selected={!done} onClick={() => setTab("todo")}>
            {t("labelling.tabs.todo")} {counts ? <span className="board-count">{counts.todo}</span> : null}
          </button>
          <button type="button" role="tab" aria-selected={done} onClick={() => setTab("done")}>
            {t("labelling.tabs.done")}
          </button>
        </div>
        {queue.isPending ? (
          <Loading />
        ) : queue.isError ? (
          <ErrorState error={queue.error} onRetry={() => queue.refetch()} />
        ) : items.length === 0 ? (
          <Empty>{done ? t("labelling.emptyDone") : t("labelling.empty")}</Empty>
        ) : (
          <ul className="rows" role="listbox">
            {items.map((it) => (
              <QueueRow key={it.event_id} it={it} selected={it.event_id === selectedId} onSelect={() => select(it.event_id)} lang={i18n.language} />
            ))}
          </ul>
        )}
        <p className="shortcuts muted small">{t("labelling.shortcuts")}</p>
      </section>
      <section className="review-detail">
        {selectedId && classes.data ? (
          <Editor key={selectedId} eventId={selectedId} classes={classes.data} onDone={() => next(selectedId)} />
        ) : (
          <Empty>{items.length ? t("labelling.select") : null}</Empty>
        )}
      </section>
    </div>
  );
}

function QueueRow({ it, selected, onSelect, lang }: { it: LabelItem; selected: boolean; onSelect: () => void; lang: string }) {
  const { t } = useTranslation();
  const review = t(`labelling.review.${it.review_label}`, { defaultValue: it.review_label });
  const reason = it.review_reason ? ` · ${t(`review.reasons.${it.review_reason}`, { defaultValue: it.review_reason })}` : "";
  return (
    <li role="option" aria-selected={selected}>
      <button type="button" className={`row ${selected ? "row-selected" : ""}`} onClick={onSelect}>
        <Thumb src={it.thumb_url} />
        <span className="row-body">
          <span className="row-title">{eventTypeLabel(t, it.type)}</span>
          <span className="small">
            <span className={`review-tag review-tag-${CONFIRMED.has(it.review_label) ? "yes" : it.review_label === "unsure" ? "maybe" : "no"}`}>{review}</span>
            <span className="muted">{reason}</span>
          </span>
          <span className="row-meta muted small">
            {it.label_kind ? t(`labelling.actions.${it.label_kind === "positive" ? "save" : it.label_kind}`) : formatDateTime(it.reviewed_at, lang)}
            {it.holdout && (
              <span className="pill pill-flight-active">
                <FlaskConical size={12} aria-hidden="true" /> {t("labelling.holdout")}
              </span>
            )}
          </span>
        </span>
      </button>
    </li>
  );
}

function Editor({ eventId, classes, onDone }: { eventId: string; classes: string[]; onDone: () => void }) {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({ queryKey: ["labelling-item", eventId], queryFn: () => api.labellingItem(eventId) });
  const [boxes, setBoxes] = useState<LabelBox[] | null>(null);
  const [selected, setSelected] = useState<number | null>(null);
  const [drawClass, setDrawClass] = useState<string>(classes[0]);
  const [imgSize, setImgSize] = useState<{ w: number; h: number } | null>(null);
  const [showDetector, setShowDetector] = useState(false);

  // Start from the saved label, else the detector's own box (for confirmed candidates).
  const item = q.data;
  useEffect(() => {
    if (!item || boxes !== null) return;
    const defaultCls = classes.includes(item.type) ? item.type : classes[0];
    setDrawClass(defaultCls);
    if (item.label_boxes?.length) {
      setBoxes(item.label_boxes);
      return;
    }
    if (item.label_kind) {
      setBoxes([]);
      return;
    }
    if (!imgSize) return;
    const sb = item.sample_bbox;
    if (sb && CONFIRMED.has(item.review_label)) {
      const [x1, y1, x2, y2] = sb;
      setBoxes([{ cls: defaultCls, x: x1 / imgSize.w, y: y1 / imgSize.h, w: (x2 - x1) / imgSize.w, h: (y2 - y1) / imgSize.h }]);
    } else setBoxes([]);
  }, [item, imgSize, boxes, classes]);

  const save = useMutation({
    mutationFn: ({ kind, list }: { kind: LabelKind; list: LabelBox[] }) => api.saveLabel(eventId, kind, list),
    onSuccess: (_r, { kind }) => {
      toast.show(kind === "positive" ? t("labelling.saved") : kind === "negative" ? t("labelling.savedNegative") : t("labelling.skipped"));
      void qc.invalidateQueries({ queryKey: ["labelling"] });
      void qc.invalidateQueries({ queryKey: ["labelling-item", eventId] });
      onDone();
    },
    onError: (err) =>
      toast.show(err instanceof ApiError && typeof err.detail === "string" && err.detail === "no_clean_frame" ? t("labelling.noCleanFrame") : t("labelling.failed"), {
        tone: "error",
      }),
  });

  const list = useMemo(() => boxes ?? [], [boxes]);
  const canLabel = !!item?.frame;

  // Keyboard: 1–5 class, Delete box, Enter save, N negative, S skip.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || isTypingTarget(e.target) || save.isPending) return;
      const n = Number(e.key);
      if (n >= 1 && n <= classes.length) {
        const cls = classes[n - 1];
        setDrawClass(cls);
        if (selected !== null) setBoxes(list.map((b, i) => (i === selected ? { ...b, cls } : b)));
      } else if ((e.key === "Delete" || e.key === "Backspace") && selected !== null) {
        setBoxes(list.filter((_, i) => i !== selected));
        setSelected(null);
      } else if (e.key === "Enter" && canLabel && list.length) save.mutate({ kind: "positive", list });
      else if (e.key.toLowerCase() === "n" && canLabel) save.mutate({ kind: "negative", list: [] });
      else if (e.key.toLowerCase() === "s") save.mutate({ kind: "skip", list: [] });
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [classes, selected, list, canLabel, save]);

  if (q.isPending) return <Loading />;
  if (q.isError || !item) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;

  const image = showDetector ? item.annotated_url : item.frame?.url ?? item.annotated_url;
  return (
    <article className="event-panel label-editor">
      <header className="event-head">
        <div>
          <h2 className="event-title">{eventTypeLabel(t, item.type)}</h2>
          <div className="event-meta">
            <span className="muted small">{t("labelling.reviewer")}:</span>
            <span className={`review-tag review-tag-${CONFIRMED.has(item.review_label) ? "yes" : item.review_label === "unsure" ? "maybe" : "no"}`}>
              {t(`labelling.review.${item.review_label}`, { defaultValue: item.review_label })}
              {item.review_reason ? ` · ${t(`review.reasons.${item.review_reason}`, { defaultValue: item.review_reason })}` : ""}
            </span>
            <span className="muted small">
              {item.reviewer} · {formatDateTime(item.reviewed_at, i18n.language)}
            </span>
            {item.flight_id && (
              <Link to={`/flights/${item.flight_id}`} className="small">
                {t("labelling.flight")}: {item.flight_name || item.flight_id.slice(0, 8)}
              </Link>
            )}
            {item.holdout && (
              <span className="pill pill-flight-active" title={t("labelling.holdoutHint")}>
                <FlaskConical size={12} aria-hidden="true" /> {t("labelling.holdout")}
              </span>
            )}
          </div>
        </div>
        {item.annotated_url && item.frame && (
          <label className="check">
            <input type="checkbox" checked={showDetector} onChange={(e) => setShowDetector(e.target.checked)} />
            {t("labelling.detectorView")}
          </label>
        )}
      </header>

      {!canLabel && <p className="form-warning">{t("labelling.noCleanFrame")}</p>}

      {image ? (
        showDetector || !canLabel ? (
          <div className="evidence-image">
            <img src={image} alt="" />
          </div>
        ) : (
          <BoxEditor
            src={image}
            boxes={list}
            onChange={setBoxes}
            selected={selected}
            onSelect={setSelected}
            drawClass={drawClass}
            onImageSize={(w, h) => setImgSize({ w, h })}
          />
        )
      ) : (
        <Empty>{t("event.noEvidence")}</Empty>
      )}

      {canLabel && (
        <div className="label-toolbar">
          <div className="class-picker" role="radiogroup" aria-label={t("labelling.class")}>
            {classes.map((c, i) => {
              const active = selected !== null ? list[selected]?.cls === c : drawClass === c;
              return (
                <button
                  key={c}
                  type="button"
                  role="radio"
                  aria-checked={active}
                  className="class-chip"
                  style={{ ["--box" as string]: CLASS_COLORS[c] }}
                  onClick={() => {
                    setDrawClass(c);
                    if (selected !== null) setBoxes(list.map((b, j) => (j === selected ? { ...b, cls: c } : b)));
                  }}
                >
                  <kbd>{i + 1}</kbd> {t(`labelling.classes.${c}`, { defaultValue: c })}
                </button>
              );
            })}
            {selected !== null && (
              <button
                type="button"
                className="icon-btn icon-btn-bordered"
                title={t("labelling.deleteBox")}
                aria-label={t("labelling.deleteBox")}
                onClick={() => {
                  setBoxes(list.filter((_, i) => i !== selected));
                  setSelected(null);
                }}
              >
                <Trash2 size={16} aria-hidden="true" />
              </button>
            )}
          </div>
          <p className="muted small">{t("labelling.classHint")}</p>
        </div>
      )}

      <div className="decision-buttons label-actions">
        <button type="button" className="btn" disabled={save.isPending} onClick={() => save.mutate({ kind: "skip", list: [] })}>
          <SkipForward size={16} aria-hidden="true" /> {t("labelling.actions.skip")} <kbd>S</kbd>
        </button>
        {canLabel && (
          <button type="button" className="btn" disabled={save.isPending} title={t("labelling.negativeHint")} onClick={() => save.mutate({ kind: "negative", list: [] })}>
            <Ban size={16} aria-hidden="true" /> {t("labelling.actions.negative")} <kbd>N</kbd>
          </button>
        )}
        {canLabel && (
          <button type="button" className="btn btn-primary" disabled={save.isPending || !list.length} onClick={() => save.mutate({ kind: "positive", list })}>
            <Check size={16} aria-hidden="true" /> {t("labelling.actions.save")} · {t("labelling.boxes", { count: list.length })} <kbd>↵</kbd>
          </button>
        )}
      </div>
      {canLabel && <p className="muted small">{t("labelling.negativeHint")}</p>}
    </article>
  );
}

