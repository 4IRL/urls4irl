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
