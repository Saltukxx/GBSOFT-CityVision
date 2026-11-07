import React from "react";
import {AbsoluteFill, Img, staticFile} from "remotion";

/** Bakes an SVG map to PNG (rendered with renderStill by scripts/bake-maps.mjs). */
export const MapBake: React.FC<{src: string}> = ({src}) => (
  <AbsoluteFill>
    <Img src={staticFile(src)} style={{width: "100%", height: "100%"}} />
  </AbsoluteFill>
);
