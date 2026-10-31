import { useTranslation } from "react-i18next";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";
import { EventPanel } from "../components/EventPanel";
import { useDecision } from "../lib/useDecision";

export function EventPage() {
  const { t } = useTranslation();
  const { eventId = "" } = useParams();
  const decision = useDecision();

  return (
    <div className="page page-narrow">
      <Link to="/review" className="btn btn-ghost">
        <ArrowLeft size={16} aria-hidden="true" /> {t("event.back")}
      </Link>
      <EventPanel
        eventId={eventId}
        variant="full"
        busy={decision.isPending}
        onDecide={(event, d) => decision.mutate({ event, decision: d })}
      />
    </div>
  );
}
