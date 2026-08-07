import { debug } from "./debug.js";
import { getState, setState } from "../store/app-store.js";
import type {
  DateFormatValue,
  DensityValue,
  SortOrderValue,
  ThemeValue,
  ViewModeValue,
} from "../types/preferences.js";
import type { UtubSummaryItem } from "../types/utub.js";

const log = debug("init");

// Flat, `display_`-prefixed shape emitted by the backend's
// `build_display_preferences_context()` and rendered into #user-preferences-data.
interface PreferencesContext {
  display_theme: ThemeValue;
  display_default_view: ViewModeValue;
  display_default_sort: SortOrderValue;
  display_density: DensityValue;
  display_date_format: DateFormatValue;
}

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

// Seeds the store's `preferences` slice from the server-rendered
// #user-preferences-data script tag, mapping the flat `display_*` context keys
// into the store's `{ theme, defaultView, ... }` shape. Falls back to the store's
// existing (createInitialState) defaults when the tag is missing or empty.
export function loadInitialPreferencesState(): void {
  const preferencesScript = document.getElementById("user-preferences-data");
  if (!preferencesScript) {
    log(
      "user-preferences-data element missing — store keeps default preferences",
    );
    return;
  }
  const raw = preferencesScript.textContent?.trim();
  if (!raw || raw === "null") {
    log("user-preferences-data empty — store keeps default preferences");
    return;
  }
  const context = JSON.parse(raw) as PreferencesContext;
  setState({
    preferences: {
      ...getState().preferences,
      theme: context.display_theme,
      defaultView: context.display_default_view,
      defaultSort: context.display_default_sort,
      density: context.display_density,
      dateFormat: context.display_date_format,
    },
  });
}
