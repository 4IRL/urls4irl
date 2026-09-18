/**
 * One-shot initializer for the static, Jinja-rendered hover tooltips, plus the
 * teardown helper for TS-rendered ones.
 *
 * Desktop-only by design: hover tooltips are meaningless on a touch device (and
 * Bootstrap falls back to showing them on tap, which steals the first tap), so
 * nothing is instantiated when `isCoarsePointer()` is true. Tooltips attached at
 * creation time by the TS card/badge renderers are not this module's concern —
 * it only sweeps what the server rendered.
 */
import { bootstrap } from "./globals.js";
import { isCoarsePointer } from "../home/mobile.js";

const TOOLTIP_SELECTOR = '[data-bs-toggle="tooltip"]';

// One-shot guard, mirroring `_onboardingInitialized` in `home/onboarding/nudges.ts`.
//
// CRITICAL — this is not merely a double-init nicety. `nudges.ts`'s `showTip()`
// sets `data-bs-toggle="tooltip"` on its anchor buttons at runtime, so a
// re-runnable sweep would later re-catch a nudge anchor and hand it a second,
// hover-triggered instance that collides with the manual-trigger nudge tooltip.
// Keeping this strictly one-shot is what keeps the two systems disjoint — do NOT
// relax it into a re-runnable loop.
let _tooltipsInitialized = false;

/**
 * Instantiate a Bootstrap tooltip for every element the server rendered with
 * `data-bs-toggle="tooltip"`. Call once, from `$(document).ready`.
 */
export function initTooltips(): void {
  if (isCoarsePointer()) return;
  if (_tooltipsInitialized) return;
  _tooltipsInitialized = true;

  document
    .querySelectorAll<HTMLElement>(TOOLTIP_SELECTOR)
    .forEach((tooltipElement) => {
      // `getOrCreateInstance`, never `new bootstrap.Tooltip(el)`: Bootstrap
      // 5.2.3's `Data.set` silently overwrites a same-key instance while leaving
      // the replaced one's listeners bound to the element.
      bootstrap.Tooltip.getOrCreateInstance(tooltipElement);
    });
}

/**
 * Dispose every live tooltip instance inside `container`. Used before a subtree
 * of TS-rendered cards/badges is torn down (UTub switch, deck reset) so their
 * per-element instances and listeners do not leak.
 */
export function disposeTooltipsWithin(container: JQuery<HTMLElement>): void {
  container.find(TOOLTIP_SELECTOR).each((_index, tooltipElement) => {
    bootstrap.Tooltip.getInstance(tooltipElement)?.dispose();
  });
}

// Bootstrap's `$tooltip-transition` fade is 150ms; pad it so the restore below
// lands after `hide()`'s queued teardown has run.
export const TOOLTIP_RESTORE_DELAY_MS = 200;

// Per-button pending restore timer, so a resubmit can cancel the previous one.
// WeakMap keeps no reference to a card that has since been torn down.
const _pendingRestoreTimers = new WeakMap<HTMLElement, number>();

/**
 * Re-show the hover tooltip on a submit button whose click handler hid it, after
 * the request failed in a way that keeps the form (and the button) on screen.
 *
 * Two guards, both load-bearing and both measured live against Bootstrap 5.2.3:
 *
 * 1. `:hover` — the same failure is reachable from the Enter-key/modal submit
 *    paths, where no `mouseenter` ever fired. Bootstrap only fires the matching
 *    `_leave()` after a real `mouseenter`, so a force-shown bubble there has
 *    nothing to dismiss it and strands over the deck (the tip is a
 *    `document.body` child, so it outlives the form closing). Checked twice:
 *    once now, to skip scheduling at all, and again when the timer fires,
 *    because the pointer may have moved on during the delay.
 * 2. The delay — `hide()` clears every `_activeTrigger` flag and queues a
 *    `complete()` that disposes the popper after the fade. A `show()` inside
 *    that window builds a tip the queued `complete()` immediately tears back
 *    down. This is not theoretical: a real backend 400 measured ~75ms end to
 *    end, well inside the 150ms fade, and an undeferred restore left no bubble
 *    at all with the cursor still on the button.
 */
export function restoreTooltipIfHovered(
  element: HTMLElement | undefined,
): void {
  if (!element?.matches(":hover")) return;

  // One pending restore per button. A resubmit hides the tooltip again and
  // schedules its own restore; without this, the earlier timer could still fire
  // mid-flight of the second request and force the bubble back while it is
  // deliberately hidden.
  const pendingRestore = _pendingRestoreTimers.get(element);
  if (pendingRestore !== undefined) window.clearTimeout(pendingRestore);

  _pendingRestoreTimers.set(
    element,
    window.setTimeout(() => {
      _pendingRestoreTimers.delete(element);
      if (!element.matches(":hover")) return;
      bootstrap.Tooltip.getInstance(element)?.show();
    }, TOOLTIP_RESTORE_DELAY_MS),
  );
}

/**
 * Test-only: clear the one-shot guard so each test starts from an uninitialized
 * module (mirrors `_resetOnboardingNudgesForTests`).
 */
export function _resetTooltipsForTests(): void {
  _tooltipsInitialized = false;
}
