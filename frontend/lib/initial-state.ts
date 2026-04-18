import { setState } from "../store/app-store.js";
import type { UtubSummaryItem } from "../types/utub.js";

export function loadInitialUtubState(): void {
  const utubsScript = document.getElementById("utubs-data");
  if (utubsScript)
    setState({
      utubs: JSON.parse(utubsScript.textContent ?? "[]") as UtubSummaryItem[],
    });
}
