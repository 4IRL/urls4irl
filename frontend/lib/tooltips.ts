/**
 * The whole desktop hover-tooltip lifecycle lives here:
 *
 * - `initTooltips()` — the one-shot, ready-time sweep that instantiates every
 *   trigger the server (Jinja) rendered.
 * - `applyHoverTooltip()` — creation-time attachment for the TS-rendered
 *   icon-only buttons, which are built and rebuilt long after `ready` and so can
 *   never be reached by that sweep.
 * - `disposeTooltipsWithin()` / `restoreTooltipIfHovered()` — teardown before a
 *   card/badge is detached, and the restore after a failure that keeps the
 *   button on screen.
 *
 * Desktop-only by design: hover tooltips are meaningless on a touch device (and
 * Bootstrap falls back to showing them on tap, which steals the first tap), so
 * nothing is instantiated when `isCoarsePointer()` is true — both entry points
 * honour that gate.
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
 * Dispose every live tooltip instance on `container` itself AND on its
 * descendants. Used before TS-rendered cards/badges are torn down (UTub switch,
 * deck reset, a single tag badge removed) so their per-element instances and
 * listeners do not leak.
 *
 * `addBack` is load-bearing: call sites pass either a subtree (a `.urlRow`,
 * whose triggers are descendants) or a single trigger (a `.urlTagBtnDelete`
 * badge wrapper, or the button itself). A descendants-only sweep would silently
 * dispose nothing for the latter.
 */
export function disposeTooltipsWithin(container: JQuery<HTMLElement>): void {
  container
    .find(TOOLTIP_SELECTOR)
    .addBack(TOOLTIP_SELECTOR)
    .each((_index, tooltipElement) => {
      bootstrap.Tooltip.getInstance(tooltipElement)?.dispose();
    });
}

// Bootstrap's `$tooltip-transition` fade is 150ms; pad it so a teardown queued
// behind a `hide()` lands after that hide's own callback has run.
export const TOOLTIP_DISPOSE_DELAY_MS = 200;

/**
 * `disposeTooltipsWithin`, deferred past Bootstrap's hide transition. Use this —
 * never the bare version — when the same interaction that tears the element down
 * ALSO called `hide()` on its tooltip.
 *
 * Why: `hide()` queues its teardown through `executeAfterTransition`, and
 * `BaseComponent.dispose()` synchronously nulls every own property on the
 * instance. A dispose landing inside the fade window leaves the queued callback
 * to reach `_isWithActiveTrigger()` → `Object.values(this._activeTrigger)` with
 * `_activeTrigger` already `null`, throwing "Cannot convert undefined or null to
 * object". Measured live on the tag-delete path (click-hide, then dispose on a
 * ~60ms AJAX success) — the same race Step 2 diagnosed in `nudges.ts`, which
 * fixes it the same way.
 *
 * Disposing after the element has already been detached is fine: Bootstrap keys
 * its instance map by element, not by attachment.
 */
export function disposeTooltipsWithinAfterHide(
  container: JQuery<HTMLElement>,
): void {
  window.setTimeout(
    () => disposeTooltipsWithin(container),
    TOOLTIP_DISPOSE_DELAY_MS,
  );
}

// Title and custom class travel together — a tooltip is never half-configured,
// so the pair is one object rather than independent optionals. `ariaLabel`
// defaults to the title and is only worth passing when the accessible name must
// be more specific than the shared bubble text (e.g. a per-tag delete button,
// where every badge would otherwise announce the identical "Remove tag").
export interface HoverTooltipOptions {
  title: string;
  customClass: string;
  ariaLabel?: string;
}

/**
 * Apply the shared desktop hover-tooltip contract to a TS-rendered icon-only
 * button. These buttons are re-created per card/badge, so they can never be
 * reached by `initTooltips()`'s ready-time sweep — attachment has to happen at
 * creation time, here.
 *
 * The `aria-label` is set regardless of pointer type (an icon-only button needs
 * an accessible name on touch too, mirroring the Jinja-rendered deck buttons,
 * which render theirs unconditionally); only the visual tooltip and its
 * Bootstrap instance are gated behind `isCoarsePointer()`, matching
 * `initTooltips()`'s own coarse-pointer early return.
 *
 * Call it AFTER the button's markup is in place, so the instance is created on a
 * fully-built element — the invariant every existing call site already follows.
 */
export function applyHoverTooltip({
  btn,
  tooltip,
}: {
  btn: JQuery<HTMLElement>;
  tooltip: HoverTooltipOptions | undefined;
}): void {
  if (!tooltip) return;

  btn.attr("aria-label", tooltip.ariaLabel ?? tooltip.title);

  if (isCoarsePointer()) return;

  btn.attr({
    "data-bs-toggle": "tooltip",
    "data-bs-custom-class": tooltip.customClass,
    "data-bs-placement": "top",
    "data-bs-trigger": "hover",
    "data-bs-title": tooltip.title,
  });
  // `getOrCreateInstance`, never `new bootstrap.Tooltip(el)` — see initTooltips().
  bootstrap.Tooltip.getOrCreateInstance(btn[0]);
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
