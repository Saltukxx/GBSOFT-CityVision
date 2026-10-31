import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";

// English only at launch. To add a language: create locales/xx.json with the
// same keys, register it in `resources` and in SUPPORTED_LANGUAGES.
export const SUPPORTED_LANGUAGES = [{ code: "en", label: "English" }] as const;

const LANG_KEY = "cv_lang";

function initialLanguage(): string {
  try {
    const saved = localStorage.getItem(LANG_KEY);
    if (saved && SUPPORTED_LANGUAGES.some((l) => l.code === saved)) return saved;
  } catch {
    /* storage unavailable */
  }
  return "en";
}

void i18n.use(initReactI18next).init({
  resources: { en: { translation: en } },
  lng: initialLanguage(),
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  returnNull: false,
});

i18n.on("languageChanged", (lng) => {
  document.documentElement.lang = lng;
  try {
    localStorage.setItem(LANG_KEY, lng);
  } catch {
    /* ignore */
  }
});

export default i18n;
