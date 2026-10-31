import { useState } from "react";
import { Image } from "lucide-react";

/** Small evidence thumbnail; hides itself if the image can't load. */
export function Thumb({ src, size = "md" }: { src?: string | null; size?: "sm" | "md" }) {
  const [failed, setFailed] = useState(false);
  return (
    <span className={`row-thumb ${size === "sm" ? "row-thumb-sm" : ""}`}>
      {src && !failed ? <img src={src} alt="" loading="lazy" onError={() => setFailed(true)} /> : <Image size={size === "sm" ? 16 : 20} strokeWidth={1.5} aria-hidden="true" />}
    </span>
  );
}
