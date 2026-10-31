import { useQuery } from "@tanstack/react-query";
import type { TFunction } from "i18next";
import { api } from "../api/client";

const FALLBACK_UNITS = ["roads", "sanitation", "parks", "other"];

/** City settings every screen may need (units, language). Cached for the session. */
export function useCitySettings() {
  const q = useQuery({ queryKey: ["city-settings"], queryFn: api.citySettings, staleTime: 10 * 60_000 });
  return { ...q, units: q.data?.work_order_units ?? FALLBACK_UNITS };
}

/** Built-in unit codes are translated; units a city typed in are shown as written. */
export function unitLabel(t: TFunction, unit: string): string {
  return t(`workOrder.units.${unit}`, { defaultValue: unit });
}
