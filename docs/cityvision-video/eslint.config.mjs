import {config} from "@remotion/eslint-config-flat";
import globals from "globals";

export default [
  ...(Array.isArray(config) ? config : [config]),
  {
    // QA / yardımcı betikler Node ortamında çalışır.
    files: ["scripts/**/*.mjs"],
    languageOptions: {globals: globals.node},
  },
];
