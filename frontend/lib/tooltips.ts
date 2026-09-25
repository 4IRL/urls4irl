/**
 * The whole desktop hover-tooltip lifecycle lives here:
 *
 * - `initTooltips()` — the one-shot, ready-time sweep that instantiates every
 *   trigger the server (Jinja) rendered.
 * - `applyHoverTooltip()` — creation-time attachment for the TS-rendered
 *   icon-only buttons, which are built and rebuilt long after `ready` and so can
 *   never be reached by that sweep.
 * - `hideTooltip()` — the null-safe hide every "this interaction hides its own
 *   trigger" handler reaches for.
 * - `disposeTooltipsWithin()` / `restoreTooltipIfStillTargeted()` — teardown
 *   before a card/badge is detached, and the restore after a failure that keeps
 *   the button on screen.
 * - `bindManagedTooltipA11yHandlers()` — the accessibility contract Bootstrap
 *   does not provide: Escape dismissal, keyboard (`:focus-visible`) triggering,
 *   and suppression of the duplicate `aria-describedby` announcement.
 *
 * Desktop-only by design: hover tooltips are meaningless on a touch device (and
 * Bootstrap falls back to showing them on tap, which steals the first tap), so
 * nothing is instantiated when `isCoarsePointer()` is true — both entry points
 * honour that gate.
 */
import { $, bootstrap } from "./globals.js";
import { isCoarsePointer } from "../home/mobile.js";

const TOOLTIP_SELECTOR = '[data-bs-toggle="tooltip"]';

// Marker stamped on — and ONLY on — the triggers this module instantiates, i.e.
// the icon-only buttons whose `data-bs-title` is a duplicate of their own
// `aria-label`. Every a11y handler below is delegated through it.
//
// CRITICAL — this is the discriminator that keeps the a11y handlers away from
// the onboarding nudges. `home/onboarding/nudges.ts`'s `showTip()` stamps
// `data-bs-toggle="tooltip"` onto its anchor at RUNTIME, so delegating on the
// Bootstrap attribute would let an Escape press dismiss a live nudge behind
// `nudges.ts`'s back (leaving `_activeTip` non-null, which suppresses every
// remaining tip for the session). Keying off the rendered bubble's
// `data-bs-custom-class` is no safer: the nudge skin is
// `onboarding-nudge-tooltip`, so a `-tooltip` suffix match would catch it too.
// A positive marker only this module writes cannot reach a nudge anchor at all.
const MANAGED_TOOLTIP_ATTRIBUTE = "data-hover-tooltip";
const MANAGED_TOOLTIP_SELECTOR = `[${MANAGED_TOOLTIP_ATTRIBUTE}]`;

// Every jQuery handler here carries this namespace, so the whole set comes off
// with one `.off()`. Adding it to Bootstrap's own event names is safe: jQuery
// fires a handler when the TRIGGERED event's namespaces are a subset of the
// BOUND handler's, so `shown.bs.tooltip.hoverTooltipA11y` still fires for
// Bootstrap's plain `shown.bs.tooltip` (verified on jQuery 3.7.1; same shape as
// `home/utubs/delete.ts`'s `hidden.bs.modal.utubDelete`).
const MANAGED_TOOLTIP_NAMESPACE = ".hoverTooltipA11y";
const SHOW_EVENT = `show.bs.tooltip${MANAGED_TOOLTIP_NAMESPACE}`;
const SHOWN_EVENT = `shown.bs.tooltip${MANAGED_TOOLTIP_NAMESPACE}`;
const HIDE_EVENT = `hide.bs.tooltip${MANAGED_TOOLTIP_NAMESPACE}`;
const FOCUS_VISIBLE_SELECTOR = ":focus-visible";
const HOVER_SELECTOR = ":hover";

// One-shot guard, mirroring `_onboardingInitialized` in `home/onboarding/nudges.ts`.
//
// CRITICAL — this is not merely a double-init nicety. `nudges.ts`'s `showTip()`
// sets `data-bs-toggle="tooltip"` on its anchor buttons at runtime, so a
// re-runnable sweep would later re-catch a nudge anchor and hand it a second,
// hover-triggered instance that collides with the manual-trigger nudge tooltip.
// Keeping this strictly one-shot is what keeps the two systems disjoint — do NOT
// relax it into a re-runnable loop.
let _tooltipsInitialized = false;

// One-shot guard for the delegated a11y handlers. Separate from the sweep guard
// because `applyHoverTooltip()` can run on a page whose `initTooltips()` sweep
// found nothing to instantiate.
let _managedTooltipHandlersBound = false;

// The managed trigger whose bubble is currently on screen, tracked so Escape can
// dismiss it without querying the DOM for `.tooltip.show` (which would also find
// an onboarding-nudge bubble).
//
// Tracked from `show.bs.tooltip`, NOT `shown.bs.tooltip`: `shown` only fires
// once Bootstrap's 150ms fade-in has finished, and an Escape pressed inside that
// window would then find nothing to dismiss and leave the bubble up for good.
// Measured — the Playwright Escape test hits exactly that window. Cleared on
// `hide.bs.tooltip` (the start of the hide, which needs no transition to have
// run) and on disposal.
let _visibleTooltipTrigger: HTMLElement | null = null;

/**
 * `Element.matches` that reports "no match" instead of throwing on a selector
 * the engine does not know. happy-dom (and older browsers) can reject
 * `:focus-visible` as an unknown pseudo-class with a `SyntaxError`, and
 * accessibility sugar must never take a click handler down with it.
 */
function matchesSelector({
  element,
  selector,
}: {
  element: HTMLElement;
  selector: string;
}): boolean {
  try {
    return element.matches(selector);
  } catch {
    return false;
  }
}

// Tracks the trigger for the Escape handler. See `_visibleTooltipTrigger` for
// why this is `show` and not `shown`.
function handleManagedTooltipShow(event: JQuery.TriggeredEvent): void {
  _visibleTooltipTrigger = event.currentTarget as HTMLElement;
}

/**
 * Bootstrap points the trigger's `aria-describedby` at the bubble it just
 * rendered. Every tooltip this module manages carries a `data-bs-title` that is
 * the same string as the trigger's own `aria-label` (Group D's label is a
 * superset: bubble "Remove tag", label "Remove tag <tagString>"), so leaving
 * that wiring in place makes a screen reader announce the name twice —
 * "Delete UTub, Delete UTub".
 *
 * Drop the description and hide the bubble from the accessibility tree, leaving
 * `aria-label` as the single source of the accessible name. `aria-label` is
 * deliberately kept as the name rather than switching to an `aria-labelledby`
 * pointing at the bubble, which would break every time a per-card button is
 * destroyed and rebuilt.
 *
 * Only ever runs for a trigger that HAS an `aria-label`: the whole premise is
 * that the description is a duplicate of the name, so on a trigger without one
 * the description is the only accessible name there is and stripping it would
 * leave the button anonymous. Every trigger this module marks carries a label
 * today; this guard is what keeps that a safety property rather than a
 * convention a future Jinja button could quietly break.
 *
 * Callable directly (not only from `shown.bs.tooltip`) because a programmatic
 * `show()` sets `aria-describedby` synchronously while `shown` does not fire
 * until the 150ms fade has finished — an assistive technology computing the
 * name inside that window would otherwise still hear the duplicate.
 */
function suppressDuplicateDescription(trigger: HTMLElement): void {
  if (!trigger.hasAttribute("aria-label")) return;

  const bubbleId = trigger.getAttribute("aria-describedby");
  if (bubbleId === null) return;
  trigger.removeAttribute("aria-describedby");
  document.getElementById(bubbleId)?.setAttribute("aria-hidden", "true");
}

function handleManagedTooltipShown(event: JQuery.TriggeredEvent): void {
  suppressDuplicateDescription(event.currentTarget as HTMLElement);
}

function handleManagedTooltipHide(event: JQuery.TriggeredEvent): void {
  if (_visibleTooltipTrigger === event.currentTarget) {
    _visibleTooltipTrigger = null;
  }
}

/**
 * Show the tooltip for a KEYBOARD focus only.
 *
 * `data-bs-trigger` stays `"hover"` everywhere: Bootstrap's own `focus` trigger
 * also fires on click-focus, which strands a bubble after every mouse click —
 * exactly the failure the click-hide guards across the decks exist to prevent.
 * `:focus-visible` is the browser's own "this focus came from the keyboard"
 * heuristic, so gating on it gives sighted keyboard users the label without
 * reintroducing the click-focus bubble.
 */
function handleManagedTooltipFocusIn(event: JQuery.TriggeredEvent): void {
  const trigger = event.currentTarget as HTMLElement;
  if (
    !matchesSelector({ element: trigger, selector: FOCUS_VISIBLE_SELECTOR })
  ) {
    return;
  }
  bootstrap.Tooltip.getInstance(trigger)?.show();
  // Synchronously, not on `shown`: `show()` has already written
  // `aria-describedby`, and this is the exact moment a screen reader announces
  // the newly-focused button.
  suppressDuplicateDescription(trigger);
}

/**
 * Losing keyboard focus hides the bubble the focus raised — unless the pointer
 * is on the button, in which case the hover that is still in effect owns the
 * bubble and Bootstrap's own `mouseleave` will hide it later.
 *
 * Note this is NOT the backstop for a trigger that its own activation DETACHES:
 * removing a focused element does not reliably fire `focusout`. That case is
 * covered by `disposeTooltipsWithin`/`disposeTooltipsWithinAfterHide`, which
 * dispose the instance and take the bubble with it. Focusout does cover the
 * triggers that merely get hidden or covered (a modal opening over them, a
 * button given `.hidden` by its own click), where the browser does move focus.
 */
function handleManagedTooltipFocusOut(event: JQuery.TriggeredEvent): void {
  const trigger = event.currentTarget as HTMLElement;
  if (matchesSelector({ element: trigger, selector: HOVER_SELECTOR })) return;
  hideTooltip(trigger);
}

/**
 * WCAG 2.1 SC 1.4.13 "Dismissible": content shown on hover or focus must be
 * dismissible without moving the pointer. Bootstrap does not do this for
 * tooltips, so hide the visible managed bubble on Escape.
 *
 * Deliberately does NOT `preventDefault()`/`stopPropagation()`: `nudges.ts` and
 * Bootstrap's modals bind their own document-level Escape handling, and this
 * handler must not swallow either. It also only ever touches the trigger tracked
 * from a managed `show.bs.tooltip`, so an onboarding nudge is unreachable from
 * here even while its anchor is carrying `data-bs-toggle="tooltip"`.
 *
 * Bound natively in the CAPTURE phase rather than through jQuery, because
 * components that own Escape stop it propagating — `urls/tags/combobox.ts` and
 * `lib/roving-listbox.ts` both do — which would otherwise starve this handler
 * and leave a visible bubble undismissable while those widgets hold focus.
 * Capture runs before any of them, and since nothing is prevented or stopped
 * here they still receive the key exactly as before.
 *
 * No `isConnected` guard: the bubble is a `document.body` child, so a trigger
 * detached without being disposed leaves the bubble on screen and this is the
 * one thing that can still clear it. `hide()` on a detached element is safe —
 * Bootstrap keys its instance map by element, not by attachment.
 */
function handleManagedTooltipKeydown(event: KeyboardEvent): void {
  if (event.key !== "Escape") return;

  const trigger = _visibleTooltipTrigger;
  if (trigger === null) return;
  _visibleTooltipTrigger = null;
  hideTooltip(trigger);
}

/**
 * Bind the delegated accessibility handlers once, on `document`. Delegation is
 * what makes this work for the per-card triggers that are created and destroyed
 * long after any binding pass.
 *
 * Both entry points call it, and both are already behind the `isCoarsePointer()`
 * gate — keyboard focus and Escape are desktop concerns, and the mobile
 * suppression contract is that a touch device instantiates no tooltip at all.
 */
function bindManagedTooltipA11yHandlers(): void {
  if (_managedTooltipHandlersBound) return;
  _managedTooltipHandlersBound = true;

  $(document)
    .on(SHOW_EVENT, MANAGED_TOOLTIP_SELECTOR, handleManagedTooltipShow)
    .on(SHOWN_EVENT, MANAGED_TOOLTIP_SELECTOR, handleManagedTooltipShown)
    .on(HIDE_EVENT, MANAGED_TOOLTIP_SELECTOR, handleManagedTooltipHide)
    .on(
      `focusin${MANAGED_TOOLTIP_NAMESPACE}`,
      MANAGED_TOOLTIP_SELECTOR,
      handleManagedTooltipFocusIn,
    )
    .on(
      `focusout${MANAGED_TOOLTIP_NAMESPACE}`,
      MANAGED_TOOLTIP_SELECTOR,
      handleManagedTooltipFocusOut,
    );

  document.addEventListener("keydown", handleManagedTooltipKeydown, true);
}

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
      tooltipElement.setAttribute(MANAGED_TOOLTIP_ATTRIBUTE, "");
      // `getOrCreateInstance`, never `new bootstrap.Tooltip(el)`: Bootstrap
      // 5.2.3's `Data.set` silently overwrites a same-key instance while leaving
      // the replaced one's listeners bound to the element.
      bootstrap.Tooltip.getOrCreateInstance(tooltipElement);
    });

  bindManagedTooltipA11yHandlers();
}

/**
 * Hide the hover tooltip on `element`, if it has a live instance.
 *
 * The one-liner every "this interaction hides/covers/detaches its own trigger"
 * call site needs: hiding an element the cursor is still over never fires the
 * `mouseleave` Bootstrap waits for, so the bubble — a `document.body` child —
 * would linger on screen with nothing left to dismiss it.
 *
 * The loose parameter type is load-bearing, not defensive noise: call sites
 * reach for their element through `$(selector)[0]` / `.get(0)`, which yields
 * `undefined` when the selector matched nothing. The optional chain covers the
 * other half — a trigger can legitimately have no instance, since coarse
 * pointers instantiate none at all.
 *
 * Safe on an element that has already been detached — Bootstrap keys its
 * instance map by element, not by attachment.
 */
export function hideTooltip(element: HTMLElement | undefined | null): void {
  if (!element) return;
  bootstrap.Tooltip.getInstance(element)?.hide();
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
  // Deliberately sweeps `data-bs-toggle`, NOT the managed marker: the five
  // pre-existing URL-card option buttons (`options/*.ts`) create their own
  // instances without going through this module, and they live inside exactly
  // the cards these callers tear down — a marker-only sweep would leak them.
  // The marker exists to keep the a11y HANDLERS off an onboarding-nudge anchor;
  // disposal has no such hazard, because no call site ever passes a container
  // holding one (the anchors are deck headers, the containers are URL rows and
  // tag badges).
  container
    .find(TOOLTIP_SELECTOR)
    .addBack(TOOLTIP_SELECTOR)
    .each((_index, tooltipElement) => {
      // Disposal fires no `hide.bs.tooltip`, so the Escape handler's tracked
      // trigger has to be cleared here or it would point at a dead instance.
      if (_visibleTooltipTrigger === tooltipElement) {
        _visibleTooltipTrigger = null;
      }
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
    [MANAGED_TOOLTIP_ATTRIBUTE]: "",
  });
  // `getOrCreateInstance`, never `new bootstrap.Tooltip(el)` — see initTooltips().
  bootstrap.Tooltip.getOrCreateInstance(btn[0]);
  // These buttons are built after `ready`, and a page may have had nothing for
  // the sweep to instantiate, so bind here too (idempotent).
  bindManagedTooltipA11yHandlers();
}

// Bootstrap's `$tooltip-transition` fade is 150ms; pad it so the restore below
// lands after `hide()`'s queued teardown has run.
export const TOOLTIP_RESTORE_DELAY_MS = 200;

// Per-button pending restore timer, so a resubmit can cancel the previous one.
// WeakMap keeps no reference to a card that has since been torn down.
const _pendingRestoreTimers = new WeakMap<HTMLElement, number>();

/**
 * Re-show the tooltip on a submit button whose click handler hid it, after the
 * request failed in a way that keeps the form (and the button) on screen.
 *
 * Two guards, both load-bearing and both measured live against Bootstrap 5.2.3:
 *
 * 1. Still-targeted — the button must still be under the pointer (`:hover`) or
 *    still hold keyboard focus (`:focus-visible`). The same failure is reachable
 *    from paths that never targeted the button at all: the Enter-key submit
 *    (focus is on the text input, not the button) and the same-name confirmation
 *    modal (focus is on `#modalSubmit`). Bootstrap only fires the matching
 *    `_leave()` after a real `mouseenter`, so a force-shown bubble on those
 *    paths has nothing to dismiss it and strands over the deck (the tip is a
 *    `document.body` child, so it outlives the form closing). Checked twice:
 *    once now, to skip scheduling at all, and again when the timer fires,
 *    because the pointer or focus may have moved on during the delay.
 *
 *    `:focus-visible` is included so the keyboard path matches the pointer one:
 *    once a bubble can be raised by keyboard focus, a keyboard user who presses
 *    Enter on the button and gets a keep-open 400 would otherwise be left with
 *    the label silently gone while the button is still focused, with no
 *    `focusin` left to fire. It stays narrow enough to leave the two guarded
 *    paths above untouched — neither of them leaves focus on the button.
 * 2. The delay — `hide()` clears every `_activeTrigger` flag and queues a
 *    `complete()` that disposes the popper after the fade. A `show()` inside
 *    that window builds a tip the queued `complete()` immediately tears back
 *    down. This is not theoretical: a real backend 400 measured ~75ms end to
 *    end, well inside the 150ms fade, and an undeferred restore left no bubble
 *    at all with the cursor still on the button.
 */
function isStillTargeted(element: HTMLElement): boolean {
  return (
    matchesSelector({ element, selector: HOVER_SELECTOR }) ||
    matchesSelector({ element, selector: FOCUS_VISIBLE_SELECTOR })
  );
}

export function restoreTooltipIfStillTargeted(
  element: HTMLElement | undefined,
): void {
  if (element === undefined || !isStillTargeted(element)) return;

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
      if (!isStillTargeted(element)) return;
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
  _managedTooltipHandlersBound = false;
  _visibleTooltipTrigger = null;
  // `document` is shared across every test in a file, so the delegated handlers
  // have to come off or they would stack up run after run.
  $(document).off(MANAGED_TOOLTIP_NAMESPACE);
  document.removeEventListener("keydown", handleManagedTooltipKeydown, true);
}
