import { debug } from "../../lib/debug.js";
import { subscribe } from "../../store/app-store.js";
import { applyTagSort } from "../urls/cards/filtering.js";
import { applyTagCountStyleAttribute } from "./deck.js";
import { effectiveTagDisplaySettings } from "./display-settings.js";

const log = debug("tags-display-subscriptions");

/**
 * Applies the sort and count-style settings live: when the resolved value changes
 * (a default or an override saved, or a refresh), re-sorts the deck or rewrites
 * `#TagDeck[data-tag-count-style]`. The match mode and collapsed-tag readers
 * subscribe on their own (`initTagMatchMode`, `initUrlDeckPolicyAttrs`) and the
 * drop toggle is read at drop time. Returns the unsubscribe function.
 */
export function initTagDisplaySubscriptions(): () => void {
  let lastSort = effectiveTagDisplaySettings().tagSort;
  let lastCountStyle = effectiveTagDisplaySettings().tagCountStyle;
  return subscribe((changedKeys) => {
    if (
      !changedKeys.includes("preferences") &&
      !changedKeys.includes("memberSettings")
    ) {
      return;
    }
    const { tagSort, tagCountStyle } = effectiveTagDisplaySettings();
    if (tagCountStyle !== lastCountStyle) {
      lastCountStyle = tagCountStyle;
      log("count style changed", { tagCountStyle });
      applyTagCountStyleAttribute();
    }
    if (tagSort !== lastSort) {
      lastSort = tagSort;
      log("sort changed", { tagSort });
      applyTagSort();
    }
  });
}
