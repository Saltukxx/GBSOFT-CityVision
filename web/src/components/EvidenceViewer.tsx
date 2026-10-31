import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ImageOff } from "lucide-react";
import type { EventMedia } from "../api/types";

export function EvidenceViewer({ media, alt }: { media: EventMedia[]; alt: string }) {
  const { t } = useTranslation();
  const crop = media.find((m) => m.media_type === "crop" && m.url);
  const frame = media.find((m) => m.media_type === "image" && m.url);
  const clip = media.find((m) => m.media_type === "clip" && m.url);
  const [view, setView] = useState<"crop" | "frame">("frame");
  const [failed, setFailed] = useState<Set<string>>(new Set());

  const shown = (view === "frame" ? frame : crop) ?? frame ?? crop;
  if (!shown && !clip)
    return (
      <div className="evidence-empty">
        <ImageOff size={22} aria-hidden="true" />
        {t("event.noEvidence")}
      </div>
    );

  return (
    <div className="evidence">
      {shown && failed.has(shown.url ?? "") && <div className="evidence-empty"><ImageOff size={22} aria-hidden="true" />{t("event.evidenceFailed")}</div>}
      {shown && !failed.has(shown.url ?? "") && (
        <div className="evidence-image">
          <a href={shown.url} target="_blank" rel="noreferrer">
            <img src={shown.url} alt={alt} onError={() => setFailed((s) => new Set(s).add(shown.url ?? ""))} />
          </a>
          {crop && frame && (
            <div className="segmented" role="group">
              <button type="button" aria-pressed={view === "frame"} onClick={() => setView("frame")}>
                {t("event.showFrame")}
              </button>
              <button type="button" aria-pressed={view === "crop"} onClick={() => setView("crop")}>
                {t("event.showCrop")}
              </button>
            </div>
          )}
        </div>
      )}
      {clip && (
        <details className="evidence-clip">
          <summary>{t("event.clip")}</summary>
          <video src={clip.url} controls playsInline preload="none" />
        </details>
      )}
    </div>
  );
}
