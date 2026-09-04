/**
 * Core onboarding-nudge engine: show a manual-trigger Bootstrap tooltip anchored
 * to a key home-page button, and dismiss it via an act-or-tap-away model with
 * **mark-seen-on-dismissal** (never on show). At most one tip is visible at a
 * time.
 *
 * Reuses the existing programmatic Bootstrap-tooltip lifecycle from
 * `urls/cards/copy.ts` (`getOrCreateInstance` + `setContent` + `show`/`hide`)
 * but drops the auto-hide timer. Because `showTip()` rebuilds a fresh, enabled
 * instance via `getOrCreateInstance(anchor)` on every call, teardown is
 * `hide(); dispose();` (a one-shot) rather than the `hide(); disable();`
 * precedent in the edit flows (`update-string.ts`, `tags/create.ts`,
 * `tags/combobox.ts`), which reuse one persistent instance across repeated
 * edit-toggle cycles and therefore must stay re-enable-able.
 *
 * The registry, eligibility gating, contextual sequencing, and init wiring live
 * in Step 6; the metrics hooks live in Step 5. This module owns only the
 * show/dismiss primitive and its accessibility announcement.
 */
import { $, bootstrap } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import {
  _resetOnboardingStorageForTests,
  markTipSeen,
} from "./nudge-storage.js";

const log = debug("onboarding");

// The single source of truth for tip identifiers, threaded through showTip's
// `tipId`, `_activeTipId`, and (Step 6) `NUDGE_REGISTRY`.
export type TipId = "createUtub" | "addUrl";

// Real, styled tooltip skin defined in `styles/home/onboarding-nudges.css`.
const NUDGE_CUSTOM_CLASS = "onboarding-nudge-tooltip";
const CLICK_NAMESPACE = "click.onboardingNudge";
const KEYDOWN_NAMESPACE = "keydown.onboardingNudge";
// Shared visually-hidden aria-live region (see `pages/home.html`).
const ANNOUNCER_SELECTOR = "#onboardingNudgeAnnouncement";

// Module-local single-active-tip state (only one nudge shows at a time).
let _activeTip: ReturnType<
  typeof bootstrap.Tooltip.getOrCreateInstance
> | null = null;
let _activeTipId: TipId | null = null;
// Id of the one-tick deferred listener-bind timer, so a dismiss fired before
// the bind executes can cancel it outright (no orphaned document handlers).
let _pendingBindTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * Dismiss the currently-active tip, if any: hide + dispose the tooltip, remove
 * the document click/Escape handlers, cancel a still-pending listener bind, and
 * — only when `markSeen` is true (user-driven act / tap-away / Escape) — persist
 * the seen flag. Environment-driven teardown (Step 6) passes `markSeen: false`.
 *
 * The `tipId` capture-and-guard at the top narrows `_activeTipId` from
 * `TipId | null` to `TipId` for the rest of the function (guard-clause idiom,
 * matching `swipe.ts`), so `markTipSeen(tipId)` type-checks under strict mode.
 */
export function dismissActiveTip({ markSeen }: { markSeen: boolean }): void {
  const tipId = _activeTipId;
  if (_activeTip === null || tipId === null) return;

  _activeTip.hide();
  _activeTip.dispose();
  log("tip dismissed", { tipId, markSeen });

  _activeTip = null;
  _activeTipId = null;

  if (_pendingBindTimer !== null) {
    clearTimeout(_pendingBindTimer);
    _pendingBindTimer = null;
  }
  $(document).off(CLICK_NAMESPACE);
  $(document).off(KEYDOWN_NAMESPACE);

  // Mark seen ONLY here (on dismissal), never on show.
  if (markSeen) markTipSeen(tipId);
}

// Any click that survives the one-tick deferral is a real user interaction:
// both the act path (a click on/within the anchor) and the tap-away path (a
// click elsewhere) dismiss with markSeen:true. The act path is not
// special-cased because we never `preventDefault`/`stopPropagation`, so the
// anchor's own click handler still runs and opens its form as usual.
function handleDocumentClick(): void {
  dismissActiveTip({ markSeen: true });
}

function handleDocumentKeydown(event: JQuery.TriggeredEvent): void {
  if (event.key === "Escape") dismissActiveTip({ markSeen: true });
}

/**
 * Show a single onboarding tip anchored to `anchorSelector`. No-ops if the
 * anchor is not in the DOM (visibility/eligibility gating is Step 6). Binding of
 * the act-or-tap-away listeners is deferred one tick so the interaction that
 * triggered the show can never immediately self-dismiss the tip.
 */
export function showTip({
  tipId,
  anchorSelector,
  titleKey,
  bodyKey,
}: {
  tipId: TipId;
  anchorSelector: string;
  titleKey: string;
  bodyKey: string;
}): void {
  const anchor = document.querySelector<HTMLElement>(anchorSelector);
  if (anchor === null) return;

  // Self-enforce the single-active-tip invariant: if a tip is somehow already
  // live (defensive — Step 6's maybeShowNextTip is the caller-side gate), tear
  // it down first WITHOUT marking it seen so it can re-show later when eligible.
  if (_activeTip !== null) dismissActiveTip({ markSeen: false });

  anchor.setAttribute("data-bs-toggle", "tooltip");
  anchor.setAttribute("data-bs-custom-class", NUDGE_CUSTOM_CLASS);
  anchor.setAttribute("data-bs-placement", "bottom");
  anchor.setAttribute("data-bs-trigger", "manual");
  // Render the title/body markup as real elements so Step 3's
  // `.onboarding-nudge-title`/`.onboarding-nudge-body` rules apply. Bootstrap's
  // default sanitizer (sanitize:true) permits `div`/`class`, and the strings are
  // developer-authored bridged constants, so this stays XSS-safe.
  anchor.setAttribute("data-bs-html", "true");

  const title = APP_CONFIG.strings[titleKey];
  const body = APP_CONFIG.strings[bodyKey];

  const tip = bootstrap.Tooltip.getOrCreateInstance(anchor);
  tip.setContent({
    ".tooltip-inner": `<div class="onboarding-nudge-title">${title}</div><div class="onboarding-nudge-body">${body}</div>`,
  });
  tip.show();

  _activeTip = tip;
  _activeTipId = tipId;

  // Announce for screen readers via the shared visually-hidden live region.
  // Do NOT move focus to the bubble (non-modal informational tip).
  $(ANNOUNCER_SELECTOR).text(`${title}. ${body}`);

  log("tip shown", { tipId });

  // Defer the act-or-tap-away bind one tick so the triggering click does not
  // self-dismiss. dismissActiveTip clears this timer if it fires first.
  _pendingBindTimer = setTimeout(() => {
    _pendingBindTimer = null;
    $(document).offAndOnExact(CLICK_NAMESPACE, handleDocumentClick);
    $(document).offAndOnExact(KEYDOWN_NAMESPACE, handleDocumentKeydown);
  }, 0);
}

/**
 * Test-only reset: clear the active tip, cancel any pending bind, remove the
 * document handlers, and reset persisted seen state (mirrors `swipe.ts`'s
 * `_resetURLSwipeGestureForTests`). Step 6's `_onboardingInitialized` idempotency
 * guard will be added to this reset when that step lands.
 */
export function _resetOnboardingNudgesForTests(): void {
  if (_pendingBindTimer !== null) {
    clearTimeout(_pendingBindTimer);
    _pendingBindTimer = null;
  }
  _activeTip = null;
  _activeTipId = null;
  $(document).off(CLICK_NAMESPACE);
  $(document).off(KEYDOWN_NAMESPACE);
  _resetOnboardingStorageForTests();
}
