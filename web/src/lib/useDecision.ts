import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import type { CityEvent, EventStatus, ReviewReason } from "../api/types";
import { useToast } from "../components/Toast";

export type Decision =
  | { kind: "confirm" }
  | { kind: "falseAlarm"; reason?: ReviewReason }
  | { kind: "unsure" }
  | { kind: "workOrder"; unit: string; note: string };

const LABEL = { confirm: "correct", falseAlarm: "wrong", unsure: "unsure", workOrder: "work_order" } as const;

/**
 * Records a review decision, shows a toast and offers undo.
 * Undo restores the previous status; work orders are not undoable here
 * because they create a record the crew may already see.
 */
export function useDecision(onDone?: (ev: CityEvent, d: Decision) => void) {
  const { t } = useTranslation();
  const toast = useToast();
  const qc = useQueryClient();

  const undo = useUndoLast();

  return useMutation({
    mutationFn: async ({ event, decision }: { event: CityEvent; decision: Decision }) => {
      const opts =
        decision.kind === "falseAlarm"
          ? { reason: decision.reason }
          : decision.kind === "workOrder"
            ? { unit: decision.unit, note: decision.note }
            : {};
      return api.review(event.event_id, LABEL[decision.kind], opts);
    },
    onSuccess: (_res, { event, decision }) => {
      const previous = event.status;
      toast.show(t(`review.done.${decision.kind}`), {
        action:
          decision.kind === "workOrder"
            ? undefined
            : { label: t("review.undo"), run: () => undo.mutate({ eventId: event.event_id, status: previous }) },
      });
      void qc.invalidateQueries({ queryKey: ["events"] });
      void qc.invalidateQueries({ queryKey: ["event"] });
      void qc.invalidateQueries({ queryKey: ["kpis"] });
      onDone?.(event, decision);
    },
    onError: () => toast.show(t("review.failed"), { tone: "error" }),
  });
}

// Lets keyboard handlers trigger undo of the most recent decision.
export function useUndoLast() {
  const qc = useQueryClient();
  const toast = useToast();
  const { t } = useTranslation();
  return useMutation({
    mutationFn: ({ eventId, status }: { eventId: string; status: EventStatus }) => api.setStatus(eventId, status),
    onSuccess: () => {
      toast.show(t("review.undone"));
      void qc.invalidateQueries({ queryKey: ["events"] });
      void qc.invalidateQueries({ queryKey: ["event"] });
      void qc.invalidateQueries({ queryKey: ["kpis"] });
    },
    onError: () => toast.show(t("review.failed"), { tone: "error" }),
  });
}
