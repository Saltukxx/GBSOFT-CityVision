import { useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { useTranslation } from "react-i18next";
import type { LabelBox } from "../api/types";

// One colour per training class, readable on aerial imagery.
export const CLASS_COLORS: Record<string, string> = {
  pothole: "#f59e0b",
  road_crack: "#38bdf8",
  road_damage: "#f472b6",
  overflowing_container: "#a3e635",
  street_waste: "#c084fc",
};

interface Props {
  src: string;
  boxes: LabelBox[];
  onChange: (boxes: LabelBox[]) => void;
  selected: number | null;
  onSelect: (i: number | null) => void;
  drawClass: string;
  onImageSize?: (w: number, h: number) => void;
}

type Drag =
  | { mode: "draw"; x0: number; y0: number; x1: number; y1: number }
  | { mode: "move"; index: number; dx: number; dy: number; start: LabelBox };

const clamp = (v: number) => Math.min(1, Math.max(0, v));

/** Draw and adjust boxes on an image. Coordinates are 0..1 of the image, top-left origin. */
export function BoxEditor({ src, boxes, onChange, selected, onSelect, drawClass, onImageSize }: Props) {
  const { t } = useTranslation();
  const wrap = useRef<HTMLDivElement>(null);
  const [drag, setDrag] = useState<Drag | null>(null);

  const point = (e: ReactPointerEvent) => {
    const r = wrap.current!.getBoundingClientRect();
    return { x: clamp((e.clientX - r.left) / r.width), y: clamp((e.clientY - r.top) / r.height) };
  };

  const hitTest = (x: number, y: number) => {
    // Topmost (last drawn) box wins.
    for (let i = boxes.length - 1; i >= 0; i--) {
      const b = boxes[i];
      if (x >= b.x && x <= b.x + b.w && y >= b.y && y <= b.y + b.h) return i;
    }
    return null;
  };

  const onDown = (e: ReactPointerEvent) => {
    if (e.button !== 0) return;
    const p = point(e);
    const hit = hitTest(p.x, p.y);
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    if (hit !== null) {
      onSelect(hit);
      setDrag({ mode: "move", index: hit, dx: p.x - boxes[hit].x, dy: p.y - boxes[hit].y, start: boxes[hit] });
    } else {
      onSelect(null);
      setDrag({ mode: "draw", x0: p.x, y0: p.y, x1: p.x, y1: p.y });
    }
  };

  const onMove = (e: ReactPointerEvent) => {
    if (!drag) return;
    const p = point(e);
    if (drag.mode === "draw") setDrag({ ...drag, x1: p.x, y1: p.y });
    else {
      const b = drag.start;
      const x = Math.min(1 - b.w, Math.max(0, p.x - drag.dx));
      const y = Math.min(1 - b.h, Math.max(0, p.y - drag.dy));
      onChange(boxes.map((bx, i) => (i === drag.index ? { ...bx, x, y } : bx)));
    }
  };

  const onUp = () => {
    if (drag?.mode === "draw") {
      const x = Math.min(drag.x0, drag.x1);
      const y = Math.min(drag.y0, drag.y1);
      const w = Math.abs(drag.x1 - drag.x0);
      const h = Math.abs(drag.y1 - drag.y0);
      // Ignore clicks and slivers.
      if (w > 0.008 && h > 0.008) {
        onChange([...boxes, { cls: drawClass, x, y, w, h }]);
        onSelect(boxes.length);
      }
    }
    setDrag(null);
  };

  const preview =
    drag?.mode === "draw"
      ? { x: Math.min(drag.x0, drag.x1), y: Math.min(drag.y0, drag.y1), w: Math.abs(drag.x1 - drag.x0), h: Math.abs(drag.y1 - drag.y0) }
      : null;

  return (
    <div className="box-editor">
      <div
        ref={wrap}
        className="box-canvas"
        onPointerDown={onDown}
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={() => setDrag(null)}
      >
        <img
          src={src}
          alt=""
          draggable={false}
          onLoad={(e) => onImageSize?.(e.currentTarget.naturalWidth, e.currentTarget.naturalHeight)}
        />
        {boxes.map((b, i) => (
          <div
            key={i}
            className={`box ${i === selected ? "box-selected" : ""}`}
            style={{
              left: `${b.x * 100}%`,
              top: `${b.y * 100}%`,
              width: `${b.w * 100}%`,
              height: `${b.h * 100}%`,
              ["--box" as string]: CLASS_COLORS[b.cls] ?? "#fff",
            }}
          >
            <span className="box-tag">{t(`labelling.classes.${b.cls}`, { defaultValue: b.cls })}</span>
          </div>
        ))}
        {preview && (
          <div
            className="box box-preview"
            style={{
              left: `${preview.x * 100}%`,
              top: `${preview.y * 100}%`,
              width: `${preview.w * 100}%`,
              height: `${preview.h * 100}%`,
              ["--box" as string]: CLASS_COLORS[drawClass] ?? "#fff",
            }}
          />
        )}
      </div>
    </div>
  );
}
