import { APP_CONFIG } from "../../lib/config.js";
import { getState } from "../../store/app-store.js";

// Returns tag IDs currently in the store
export function currentTagDeckIDs(): number[] {
  return getState().tags.map((tag) => tag.id);
}

export function isTagInUTubTagDeck(utubTagID: number): boolean {
  return currentTagDeckIDs().includes(utubTagID);
}

export function isATagSelected(): boolean {
  return getState().selectedTagIDs.length > 0;
}

/**
 * Visible label for the collapsed Tag deck's filter pill, e.g. "3 filtered".
 *
 * @param count - how many tag filters are currently applied.
 * @returns the label, or `""` when nothing is filtered (the pill is unlabeled
 *          as well as unmarked, so a stale count can never flash on re-show).
 */
export function tagFilterPillLabel(count: number): string {
  if (count === 0) return "";
  return APP_CONFIG.strings.TAG_FILTER_PILL_COUNT.replace("{n}", String(count));
}

/**
 * Spoken form of that same pill, e.g. "3 tags filtered" / "1 tag filtered".
 *
 * Lives here, in the tag domain's leaf util module, because BOTH writers need
 * it: `tags/deck.ts`'s TAG_FILTER_CHANGED subscriber and `collapsible-decks.ts`'s
 * Tag-collapse branch (the collapse click emits no TAG_FILTER_CHANGED, so it
 * cannot route through the subscriber). Importing `tags/deck.js` from
 * `collapsible-decks.ts` instead would pull deck.ts's module-scope
 * UTUB_SELECTED subscription into that module's evaluation graph.
 *
 * @param count - how many tag filters are currently applied.
 * @returns the sentence to announce, or `""` when nothing is filtered.
 */
export function collapsedTagFilterAnnouncement(count: number): string {
  if (count === 0) return "";
  return count === 1
    ? APP_CONFIG.strings.TAG_FILTER_ANNOUNCEMENT_COUNT_ONE
    : APP_CONFIG.strings.TAG_FILTER_ANNOUNCEMENT_COUNT.replace(
        "{n}",
        String(count),
      );
}
