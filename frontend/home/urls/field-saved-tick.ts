/**
 * Shared "Saved ✓" acknowledgment helper for the mobile consolidated edit
 * panels (UTub header name/description + URL card title/string).
 *
 * On a successful per-field save while a panel stays open, a transient
 * "Saved ✓" tick fades in beside the field and auto-fades after ~1.5s while a
 * polite aria-live announcer states which field was saved. This module lives
 * in a neutral location and imports ONLY `APP_CONFIG` (operating on the jQuery
 * objects handed to it by callers) — nothing from the field/panel modules — so
 * it introduces no import cycle with the mutually-importing
 * `update-name`/`update-description` and `update-string`/`update-url-panel`
 * pairs.
 */

import { APP_CONFIG } from "../../lib/config.js";

// Inline `bi-check` SVG for the "Saved ✓" tick. This project ships no
// bootstrap-icons font, so a font-based `<i class="bi bi-check">` renders as
// empty space — every icon in this codebase is an inline SVG instead. Shared
// here (the canonical field-saved-tick module) so both card call sites
// (url-title.ts, url-string.ts) reuse one copy. `fill="currentColor"` inherits
// the tick's green color; aria-hidden since the "Saved" text conveys meaning.
export const FIELD_SAVED_CHECK_SVG =
  '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-check" viewBox="0 0 16 16" aria-hidden="true"><path d="M10.97 4.97a.75.75 0 0 1 1.07 1.05l-3.99 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425a.267.267 0 0 1 .02-.022z"/></svg>';

// Dwell time before the tick fades back out. Mirrors the ~1.5s transient-ack
// dwell used by the "Copied!" tooltip (cards/copy.ts).
const FIELD_SAVED_TICK_DWELL_MS = 1500;

// Pending fade timers keyed by the tick's DOM node, so a rapid second save on
// the same field cancels/restarts its own timer (no premature fade) and panel
// teardown can force-clear a pending timer via clearFieldSavedTick.
const savedTickTimers = new WeakMap<
  HTMLElement,
  ReturnType<typeof setTimeout>
>();

/**
 * Show the "Saved" tick for a field and announce it politely, then fade it
 * back out after ~1.5s. A second call before the timer fires cancels the prior
 * timer and restarts the dwell.
 */
export function showFieldSavedTick({
  tick,
  announce,
  label,
}: {
  tick: JQuery;
  announce?: JQuery;
  label: string;
}): void {
  const tickElement = tick.get(0);
  if (!tickElement) return;

  const pendingTimer = savedTickTimers.get(tickElement);
  if (pendingTimer !== undefined) {
    clearTimeout(pendingTimer);
    savedTickTimers.delete(tickElement);
  }

  const announcementMessage = `${label} ${APP_CONFIG.strings.FIELD_SAVED}`;
  tick.removeClass("opa-0").addClass("opa-1");
  if (announce && announce.length > 0) {
    announce.text(announcementMessage);
  }

  const fadeTimer = setTimeout(() => {
    tick.removeClass("opa-1").addClass("opa-0");
    // Only clear the shared announcer if this field is still its last writer.
    // With both UTub header fields editable at once, a second field can announce
    // within this field's ~1.5s dwell; leaving a newer message intact lets its
    // own fade timer clear it rather than blanking it early.
    if (
      announce &&
      announce.length > 0 &&
      announce.text() === announcementMessage
    ) {
      announce.text("");
    }
    savedTickTimers.delete(tickElement);
  }, FIELD_SAVED_TICK_DWELL_MS);

  savedTickTimers.set(tickElement, fadeTimer);
}

/**
 * Cancel any pending fade timer for a tick and force it back to hidden. Used by
 * the panel teardown functions so a stale timer never mutates a torn-down field.
 */
export function clearFieldSavedTick(tick: JQuery): void {
  const tickElement = tick.get(0);
  if (!tickElement) return;

  const pendingTimer = savedTickTimers.get(tickElement);
  if (pendingTimer !== undefined) {
    clearTimeout(pendingTimer);
    savedTickTimers.delete(tickElement);
  }

  tick.removeClass("opa-1").addClass("opa-0");
}
