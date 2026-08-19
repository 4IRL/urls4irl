/**
 * Shared per-card bulk-result cue helper (extracted from bulk-tag.ts — DD-16).
 *
 * Both bulk-tag and bulk-copy flash a transient, self-fading chip on each
 * targeted URL card after a bulk action: bulk-tag flashes "Tagged"/"At tag
 * limit"; bulk-copy flashes "Copied"/"Already there". The hold/fade/DOM-lookup
 * mechanics are identical, so they live here once and the caller supplies the
 * variant (drives the `.bulkCardResultCue--${variant}` colour class) and the
 * static label per card.
 *
 * Cues are `aria-hidden`; the result banner carries the screen-reader summary.
 * This is what lets the banner stay a concise count instead of listing every
 * card by title (unbounded on a large batch) — and it never surfaces a
 * user-controlled title (XSS-safe: the label is a static bridged string).
 */

import { $ } from "../../../lib/globals.js";

/** How long a per-card result cue stays fully visible before it fades. */
const CARD_CUE_HOLD_MS = 2400;
/** Fade duration — mirrors the CSS transition on `.bulkCardResultCue--fading`. */
const CARD_CUE_FADE_MS = 600;

/**
 * Flash a self-fading cue chip on each targeted URL card. For every entry,
 * resolves the `.urlRow[utuburlid=…]`, strips any lingering cue so nothing
 * stacks, appends a fresh `aria-hidden` chip, and schedules the hold → fade →
 * remove timers.
 */
export function flashCardResultCues({
  cues,
}: {
  cues: Array<{ utubUrlID: number; variant: string; label: string }>;
}): void {
  cues.forEach(({ utubUrlID, variant, label }) => {
    const urlCard = $(`.urlRow[utuburlid=${utubUrlID}]`);
    if (urlCard.length === 0) return;

    // Replace any lingering cue from a prior action so nothing stacks/duplicates.
    urlCard.find(".bulkCardResultCue").remove();

    const cue = $(document.createElement("span"))
      .addClass(`bulkCardResultCue bulkCardResultCue--${variant}`)
      .attr({ "aria-hidden": "true" })
      .text(label);
    urlCard.append(cue);

    // Hold, then fade (CSS transition), then remove from the DOM.
    window.setTimeout(
      () => cue.addClass("bulkCardResultCue--fading"),
      CARD_CUE_HOLD_MS,
    );
    window.setTimeout(() => cue.remove(), CARD_CUE_HOLD_MS + CARD_CUE_FADE_MS);
  });
}
