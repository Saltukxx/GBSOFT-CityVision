import {loadFont as loadMono} from "@remotion/google-fonts/IBMPlexMono";
import {loadFont as loadSans} from "@remotion/google-fonts/InterTight";
import {continueRender, delayRender} from "remotion";

// Türkçe diyakritikler (ğ ı İ ş ç ö ü) latin-ext alt kümesinde.
const sans = loadSans("normal", {weights: ["400", "500", "600", "700"], subsets: ["latin", "latin-ext"]});
const mono = loadMono("normal", {weights: ["400", "500", "600"], subsets: ["latin", "latin-ext"]});

// Yazı tipleri inmeden kare basılırsa metrikler kayar; render'ı bekletiyoruz.
const handle = delayRender("Yazı tipleri yükleniyor");
Promise.all([sans.waitUntilDone(), mono.waitUntilDone()])
  .then(() => continueRender(handle))
  .catch(() => continueRender(handle));

export const sansFamily = sans.fontFamily;
export const monoFamily = mono.fontFamily;
