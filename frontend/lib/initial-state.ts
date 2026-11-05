import { debug } from "./debug.js";
import { getState, setState } from "../store/app-store.js";
import type {
  DateFormatValue,
  DensityValue,
  SortOrderValue,
  ThemeValue,
  ViewModeValue,
} from "../types/preferences.js";
import {
  isCollapsedTagsStyleValue,
  isMemberSortValue,
  isTagCountStyleValue,
  isTagMatchModeValue,
  isTagSortValue,
  isUtubSortValue,
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
  display_utub_sort?: unknown;
  display_member_sort?: unknown;
  display_show_row_counts?: unknown;
  display_show_list_totals?: unknown;
  display_tag_sort?: unknown;
  display_tag_match_mode?: unknown;
  display_tag_count_style?: unknown;
  display_show_tags_on_collapsed?: unknown;
  display_collapsed_tags_style?: unknown;
  display_tag_drop_opens_url?: unknown;
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
  const defaults = getState().preferences;
  setState({
    preferences: {
      ...defaults,
      // Fail closed to today's look: an unknown sort or a non-boolean toggle
      // keeps the default.
      utubSort: isUtubSortValue(context.display_utub_sort)
        ? context.display_utub_sort
        : defaults.utubSort,
      memberSort: isMemberSortValue(context.display_member_sort)
        ? context.display_member_sort
        : defaults.memberSort,
      showRowCounts:
        typeof context.display_show_row_counts === "boolean"
          ? context.display_show_row_counts
          : defaults.showRowCounts,
      showListTotals:
        typeof context.display_show_list_totals === "boolean"
          ? context.display_show_list_totals
          : defaults.showListTotals,
      tagSort: isTagSortValue(context.display_tag_sort)
        ? context.display_tag_sort
        : defaults.tagSort,
      tagMatchMode: isTagMatchModeValue(context.display_tag_match_mode)
        ? context.display_tag_match_mode
        : defaults.tagMatchMode,
      tagCountStyle: isTagCountStyleValue(context.display_tag_count_style)
        ? context.display_tag_count_style
        : defaults.tagCountStyle,
      showTagsOnCollapsed:
        typeof context.display_show_tags_on_collapsed === "boolean"
          ? context.display_show_tags_on_collapsed
          : defaults.showTagsOnCollapsed,
      collapsedTagsStyle: isCollapsedTagsStyleValue(
        context.display_collapsed_tags_style,
      )
        ? context.display_collapsed_tags_style
        : defaults.collapsedTagsStyle,
      tagDropOpensUrl:
        typeof context.display_tag_drop_opens_url === "boolean"
          ? context.display_tag_drop_opens_url
          : defaults.tagDropOpensUrl,
      theme: context.display_theme,
      defaultView: context.display_default_view,
      defaultSort: context.display_default_sort,
      density: context.display_density,
      dateFormat: context.display_date_format,
    },
  });
}
