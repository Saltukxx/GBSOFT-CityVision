import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { WORK_ORDER_COLUMNS, type WorkOrder, type WorkOrderPatch, type WorkOrderStatus } from "../api/types";
import { useCurrentUser } from "../auth/AuthContext";
import { Empty, ErrorState, Loading } from "../components/States";
import { Thumb } from "../components/Thumb";
import { useToast } from "../components/Toast";
import { eventTypeLabel, formatDate } from "../lib/format";
import { unitLabel, useCitySettings } from "../lib/useCitySettings";

const today = () => new Date().toISOString().slice(0, 10);
const isOverdue = (w: WorkOrder) =>
  !!w.due_date && w.due_date < today() && w.status !== "resolved" && w.status !== "cancelled";

function useUpdateWorkOrder() {
  const qc = useQueryClient();
  const toast = useToast();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: WorkOrderPatch }) => api.patchWorkOrder(id, patch),
    // Optimistic: the card moves at once, rolls back if the server says no.
    onMutate: async ({ id, patch }) => {
      await qc.cancelQueries({ queryKey: ["work-orders"] });
      const prev = qc.getQueryData<WorkOrder[]>(["work-orders"]);
      qc.setQueryData<WorkOrder[]>(["work-orders"], (list) =>
        list?.map((w) =>
          w.id === id ? { ...w, ...patch, due_date: patch.clear_due_date ? null : patch.due_date ?? w.due_date } : w,
        ),
      );
      return { prev };
    },
    onError: (_e, _v, ctx) => {
      if (ctx?.prev) qc.setQueryData(["work-orders"], ctx.prev);
      toast.show(t("workOrders.edit.failed"), { tone: "error" });
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: ["work-orders"] });
      void qc.invalidateQueries({ queryKey: ["events"] });
      void qc.invalidateQueries({ queryKey: ["kpis"] });
    },
  });
}

export function WorkOrdersPage() {
  const { t } = useTranslation();
  const { canDecide } = useCurrentUser();
  const [params, setParams] = useSearchParams();
  const unit = params.get("unit") ?? "";
  const overdueOnly = params.get("overdue") === "1";
  const [search, setSearch] = useState("");
  const [editing, setEditing] = useState<number | null>(null);
  // Phones show one column at a time.
  const [mobileCol, setMobileCol] = useState<WorkOrderStatus>("created");
  const { units } = useCitySettings();

  const q = useQuery({ queryKey: ["work-orders"], queryFn: api.workOrders, refetchInterval: 60_000 });
  const update = useUpdateWorkOrder();
  const toast = useToast();

  const setParam = (k: string, v: string) =>
    setParams(
      (p) => {
        const n = new URLSearchParams(p);
        if (v) n.set(k, v);
        else n.delete(k);
        return n;
      },
      { replace: true },
    );

  const filtered = useMemo(() => {
    const s = search.trim().toLowerCase();
    return (q.data ?? []).filter(
      (w) =>
        (!unit || w.unit === unit) &&
        (!overdueOnly || isOverdue(w)) &&
        (!s || (w.assignee ?? "").toLowerCase().includes(s) || (w.note ?? "").toLowerCase().includes(s)),
    );
  }, [q.data, unit, overdueOnly, search]);

  // Open the phone view on the first column that has something in it.
  const pickedCol = useRef(false);
  useEffect(() => {
    if (pickedCol.current || !q.data?.length) return;
    pickedCol.current = true;
    const first = WORK_ORDER_COLUMNS.find((c) => q.data.some((w) => w.status === c));
    if (first) setMobileCol(first);
  }, [q.data]);

  const allUnits = useMemo(() => [...new Set([...units, ...(q.data ?? []).map((w) => w.unit)])], [units, q.data]);
  const move = (w: WorkOrder, status: WorkOrderStatus) => {
    update.mutate({ id: w.id, patch: { status } });
    toast.show(t("workOrders.moved", { status: t(`workOrders.status.${status}`) }));
  };
  const current = q.data?.find((w) => w.id === editing) ?? null;

  return (
    <div className="page page-wide">
      <header className="page-head page-head-actions">
        <div>
          <h1>{t("workOrders.title")}</h1>
          {q.data && <span className="muted">{t("workOrders.count", { count: filtered.length })}</span>}
        </div>
        <div className="filters">
          <label className="filter">
            <span className="filter-label">{t("workOrders.filters.unit")}</span>
            <select value={unit} onChange={(e) => setParam("unit", e.target.value)}>
              <option value="">{t("workOrders.filters.allUnits")}</option>
              {allUnits.map((u) => (
                <option key={u} value={u}>
                  {unitLabel(t, u)}
                </option>
              ))}
            </select>
          </label>
          <label className="check">
            <input type="checkbox" checked={overdueOnly} onChange={(e) => setParam("overdue", e.target.checked ? "1" : "")} />
            {t("workOrders.filters.overdue")}
          </label>
          <input
            className="search"
            type="search"
            placeholder={t("workOrders.filters.search")}
            aria-label={t("workOrders.filters.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </header>

      {q.isPending ? (
        <Loading />
      ) : q.isError ? (
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      ) : !q.data.length ? (
        <Empty>{t("workOrders.empty")}</Empty>
      ) : (
        <>
        <div className="board-tabs" role="tablist" aria-label={t("workOrders.title")}>
          {WORK_ORDER_COLUMNS.map((col) => (
            <button
              key={col}
              type="button"
              role="tab"
              aria-selected={mobileCol === col}
              className="board-tab"
              onClick={() => setMobileCol(col)}
            >
              {t(`workOrders.status.${col}`)} <span className="board-count">{filtered.filter((w) => w.status === col).length}</span>
            </button>
          ))}
        </div>
        <div className="board">
          {WORK_ORDER_COLUMNS.map((col) => {
            const cards = filtered.filter((w) => w.status === col);
            return (
              <section
                key={col}
                className={`board-col board-col-${col} ${mobileCol === col ? "board-col-current" : ""}`}
                aria-label={t(`workOrders.status.${col}`)}
              >
                <header className="board-col-head">
                  <h2>{t(`workOrders.status.${col}`)}</h2>
                  <span className="board-count">{cards.length}</span>
                </header>
                {cards.length === 0 ? (
                  <p className="muted small board-empty">{t("workOrders.columnEmpty")}</p>
                ) : (
                  <ul className="board-cards">
                    {cards.map((w) => (
                      <WorkOrderCard key={w.id} w={w} canEdit={canDecide} onOpen={() => setEditing(w.id)} onMove={(s) => move(w, s)} />
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
        </div>
        </>
      )}

      {current && (
        <WorkOrderDialog
          w={current}
          units={allUnits}
          canEdit={canDecide}
          onClose={() => setEditing(null)}
          onSave={(patch) =>
            update.mutate(
              { id: current.id, patch },
              { onSuccess: () => toast.show(t("workOrders.edit.saved")) },
            )
          }
        />
      )}
    </div>
  );
}

function WorkOrderCard({
  w,
  canEdit,
  onOpen,
  onMove,
}: {
  w: WorkOrder;
  canEdit: boolean;
  onOpen: () => void;
  onMove: (s: WorkOrderStatus) => void;
}) {
  const { t, i18n } = useTranslation();
  const overdue = isOverdue(w);
  return (
    <li className={`wo-card ${overdue ? "wo-overdue" : ""}`}>
      <button type="button" className="wo-main" onClick={onOpen}>
        <Thumb src={w.thumb_url} size="sm" />
        <span className="wo-body">
          <span className="row-title">
            {eventTypeLabel(t, w.event_type)} <span className="muted mono small">#{w.id}</span>
          </span>
          <span className="small">{unitLabel(t, w.unit)} · {w.assignee || <span className="muted">{t("workOrders.unassigned")}</span>}</span>
          {w.due_date ? (
            <span className={`small ${overdue ? "text-danger" : "muted"}`}>
              {overdue ? t("workOrders.overdue", { date: formatDate(w.due_date, i18n.language) }) : t("workOrders.due", { date: formatDate(w.due_date, i18n.language) })}
            </span>
          ) : (
            <span className="muted small">{t("workOrders.opened", { date: formatDate(w.created_at, i18n.language) })}</span>
          )}
        </span>
      </button>
      {canEdit && (
        <label className="wo-move">
          <span className="visually-hidden">{t("workOrders.moveTo")}</span>
          <select value="" onChange={(e) => e.target.value && onMove(e.target.value as WorkOrderStatus)}>
            <option value="">{t("workOrders.moveTo")}…</option>
            {WORK_ORDER_COLUMNS.filter((s) => s !== w.status).map((s) => (
              <option key={s} value={s}>
                {t(`workOrders.status.${s}`)}
              </option>
            ))}
          </select>
        </label>
      )}
    </li>
  );
}

function WorkOrderDialog({
  w,
  units,
  canEdit,
  onClose,
  onSave,
}: {
  w: WorkOrder;
  units: string[];
  canEdit: boolean;
  onClose: () => void;
  onSave: (patch: WorkOrderPatch) => void;
}) {
  const { t } = useTranslation();
  const ref = useRef<HTMLDialogElement>(null);
  const [assignee, setAssignee] = useState(w.assignee ?? "");
  const [unit, setUnit] = useState(w.unit);
  const [due, setDue] = useState(w.due_date ?? "");
  const [note, setNote] = useState(w.note ?? "");
  const [status, setStatus] = useState<WorkOrderStatus>(w.status);

  useEffect(() => {
    const d = ref.current;
    if (d && !d.open) d.showModal();
    return () => d?.close();
  }, []);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const patch: WorkOrderPatch = {};
    if (assignee !== (w.assignee ?? "")) patch.assignee = assignee.trim();
    if (unit !== w.unit) patch.unit = unit;
    if (note !== (w.note ?? "")) patch.note = note;
    if (status !== w.status) patch.status = status;
    if (due !== (w.due_date ?? "")) {
      if (due) patch.due_date = due;
      else patch.clear_due_date = true;
    }
    if (Object.keys(patch).length) onSave(patch);
    onClose();
  };

  return (
    <dialog ref={ref} className="dialog dialog-wide" onCancel={onClose} aria-labelledby="wo-edit-title">
      <form onSubmit={submit}>
        <h2 id="wo-edit-title">
          {t("workOrders.edit.title", { id: w.id })} · {eventTypeLabel(t, w.event_type)}
        </h2>
        {w.thumb_url && <img className="wo-dialog-img" src={w.thumb_url} alt="" />}
        <fieldset disabled={!canEdit} className="form-grid">
          <label className="field">
            <span>{t("workOrders.edit.status")}</span>
            <select value={status} onChange={(e) => setStatus(e.target.value as WorkOrderStatus)}>
              {WORK_ORDER_COLUMNS.map((s) => (
                <option key={s} value={s}>
                  {t(`workOrders.status.${s}`)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{t("workOrders.edit.unit")}</span>
            <select value={unit} onChange={(e) => setUnit(e.target.value)}>
              {units.map((u) => (
                <option key={u} value={u}>
                  {unitLabel(t, u)}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>{t("workOrders.edit.assignee")}</span>
            <input value={assignee} maxLength={120} placeholder={t("workOrders.edit.assigneePlaceholder")} onChange={(e) => setAssignee(e.target.value)} />
          </label>
          <label className="field">
            <span>{t("workOrders.edit.due")}</span>
            <input type="date" value={due} onChange={(e) => setDue(e.target.value)} />
          </label>
        </fieldset>
        <label className="field">
          <span>{t("workOrders.edit.note")}</span>
          <textarea rows={3} value={note} maxLength={2000} disabled={!canEdit} onChange={(e) => setNote(e.target.value)} />
        </label>
        <div className="dialog-actions dialog-actions-split">
          <Link className="btn btn-ghost" to={`/events/${encodeURIComponent(w.event_id)}`}>
            {t("workOrders.edit.openEvent")}
          </Link>
          <span>
            <button type="button" className="btn" onClick={onClose}>
              {t("workOrders.edit.cancel")}
            </button>{" "}
            {canEdit && (
              <button type="submit" className="btn btn-primary">
                {t("workOrders.edit.save")}
              </button>
            )}
          </span>
        </div>
      </form>
    </dialog>
  );
}
