import { debug } from "./debug.js";
import { setState } from "../store/app-store.js";
import type { UtubSummaryItem } from "../types/utub.js";

const log = debug("init");

export function loadInitialUtubState(): void {
  const utubsScript = document.getElementById("utubs-data");
  if (utubsScript) {
    setState({
      utubs: JSON.parse(utubsScript.textContent ?? "[]") as UtubSummaryItem[],
    });
  } else {
    log("utubs-data element missing — store starts empty");
  }
}
