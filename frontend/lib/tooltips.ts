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

/**
 * Test-only: clear the one-shot guard so each test starts from an uninitialized
 * module (mirrors `_resetOnboardingNudgesForTests`).
 */
export function _resetTooltipsForTests(): void {
  _tooltipsInitialized = false;
}
