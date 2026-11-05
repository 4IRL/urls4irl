import { APP_CONFIG } from "../../lib/config.js";
import { getState } from "../../store/app-store.js";
import type { TagMatchModeValue } from "../../types/preferences.js";

export interface TagCount {
  inView: number;
  total: number;
}

/**
 * Reads a tag chip's "in view / total" count from its two number spans.
 *
 * The count is structured markup (`.tagCountInView`, `.tagCountSep`,
 * `.tagCountTotal` inside `.tagAppliedToUrlsCount`) so CSS can show it as
 * "3 / 7", "7" or nothing without any code parsing the rendered text.
 *
 * @param chip - the `.tagFilter` element.
 * @returns the counts, or `null` when the chip has no (or a malformed) count.
 */
export function readTagCount(chip: JQuery): TagCount | null {
  const inViewText = chip.find(".tagCountInView").first().text();
  const totalText = chip.find(".tagCountTotal").first().text();
  const inView = parseInt(inViewText, 10);
  const total = parseInt(totalText, 10);
  if (Number.isNaN(inView) || Number.isNaN(total)) return null;
  return { inView, total };
}

/**
 * Writes both numbers of a tag chip's count. Always updates the in-view span,
 * even when the count style hides it, because "Most in view" sorting reads it.
 *
 * @param chip - the `.tagFilter` element.
 * @param inView - the in-view number to write.
 * @param total - the UTub-wide total to write.
 */
export function writeTagCount({
  chip,
  inView,
  total,
}: { chip: JQuery } & TagCount): void {
  chip.find(".tagCountInView").first().text(String(inView));
  chip.find(".tagCountTotal").first().text(String(total));
}

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
export function tagFilterPillLabel({
  count,
  mode,
}: {
  count: number;
  mode: TagMatchModeValue;
}): string {
  if (count === 0) return "";
  const label = APP_CONFIG.strings.TAG_FILTER_PILL_COUNT.replace(
    "{n}",
    String(count),
  );
  return isAnyModeWithSeveralTags({ count, mode })
    ? label + APP_CONFIG.strings.TAG_FILTER_PILL_ANY_SUFFIX
    : label;
}

/** The match-mode cue and the "any" wording appear only for "any" with 2+ tags. */
export function isAnyModeWithSeveralTags({
  count,
  mode,
}: {
  count: number;
  mode: TagMatchModeValue;
}): boolean {
  return mode === "any" && count >= 2;
}

/**
 * Sentence for how many URLs match after a match-mode change, e.g.
 * "3 URLs shown, matching any selected tags". `count === 1` picks the singular
 * string (no placeholder), otherwise the plural string with `{n}` replaced
 * (0 reads "0 URLs shown").
 */
export function tagFilterResultAnnouncement({
  count,
  mode,
}: {
  count: number;
  mode: TagMatchModeValue;
}): string {
  const strings = APP_CONFIG.strings;
  if (count === 1) {
    return mode === "any"
      ? strings.TAG_FILTER_RESULT_ANY_ONE
      : strings.TAG_FILTER_RESULT_ALL_ONE;
  }
  const template =
    mode === "any"
      ? strings.TAG_FILTER_RESULT_ANY
      : strings.TAG_FILTER_RESULT_ALL;
  return template.replace("{n}", String(count));
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
export function collapsedTagFilterAnnouncement({
  count,
  mode,
}: {
  count: number;
  mode: TagMatchModeValue;
}): string {
  if (count === 0) return "";
  const sentence =
    count === 1
      ? APP_CONFIG.strings.TAG_FILTER_ANNOUNCEMENT_COUNT_ONE
      : APP_CONFIG.strings.TAG_FILTER_ANNOUNCEMENT_COUNT.replace(
          "{n}",
          String(count),
        );
  return isAnyModeWithSeveralTags({ count, mode })
    ? sentence + APP_CONFIG.strings.TAG_FILTER_ANNOUNCEMENT_ANY_SUFFIX
    : sentence;
}
