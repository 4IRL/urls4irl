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
import { on, AppEvents } from "../../lib/event-bus.js";
import { emit as emitMetric } from "../../lib/metrics-client.js";
import { getOpenForm } from "../../lib/modal-tracking.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { getState } from "../../store/app-store.js";
import { isCrossUtubSearchActive } from "../search/cross-utub-search.js";
import { isUTubSearchActive } from "../utubs/search.js";
import {
  _resetOnboardingStorageForTests,
  hasSeenTip,
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
// Guards initOnboardingNudges against double-binding its event-bus
// subscriptions on a repeated call (subscriptions accumulate otherwise),
// mirroring swipe.ts's `_swipeInitialized` idempotency guard.
let _onboardingInitialized = false;

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

  // Emit the dismissed metric ONLY on user-driven dismissal (markSeen: true —
  // act / tap-away / Escape). Environment-driven teardown (markSeen: false)
  // intentionally does not emit, keeping this a pure user-outcome signal. The
  // narrowed local `tipId` (TipId, not TipId | null) type-checks against the
  // matching Literal `tip_id` dimension with no cast.
  if (markSeen) {
    emitMetric({ event: UI_EVENTS.UI_ONBOARDING_TIP_DISMISSED, tip_id: tipId });
  }

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

  // `tipId` is typed `TipId`, which matches the codegen's UI_ONBOARDING_TIP_SHOWN
  // `tip_id` Literal dimension, so this emit type-checks with no cast.
  emitMetric({ event: UI_EVENTS.UI_ONBOARDING_TIP_SHOWN, tip_id: tipId });

  // Defer the act-or-tap-away bind one tick so the triggering click does not
  // self-dismiss. dismissActiveTip clears this timer if it fires first.
  _pendingBindTimer = setTimeout(() => {
    _pendingBindTimer = null;
    $(document).offAndOnExact(CLICK_NAMESPACE, handleDocumentClick);
    $(document).offAndOnExact(KEYDOWN_NAMESPACE, handleDocumentKeydown);
  }, 0);
}

// A single curated tip: its identity, the anchor button it points at, the
// bridged title/body string keys, and an eligibility predicate over app-store
// state. Walked in priority order by `maybeShowNextTip`.
interface NudgeConfig {
  tipId: TipId;
  anchorSelector: string;
  titleKey: string;
  bodyKey: string;
  isEligible(): boolean;
}

// The curated, contextually-sequenced tip set. Order is priority order: the
// Create-UTub tip precedes the Add-URL tip, so a brand-new user is guided to
// create their first UTub before being nudged to add a URL to it. Each nudge
// anchors to its deck's header "+" button (never the empty-state CTA) for
// anchor-consistency across the set.
const NUDGE_REGISTRY: readonly NudgeConfig[] = [
  {
    tipId: "createUtub",
    anchorSelector: "#utubBtnCreate",
    titleKey: "ONBOARDING_CREATE_UTUB_TIP_TITLE",
    bodyKey: "ONBOARDING_CREATE_UTUB_TIP_BODY",
    isEligible: (): boolean => getState().utubs.length === 0,
  },
  {
    tipId: "addUrl",
    anchorSelector: "#urlBtnCreate",
    titleKey: "ONBOARDING_ADD_URL_TIP_TITLE",
    bodyKey: "ONBOARDING_ADD_URL_TIP_BODY",
    isEligible: (): boolean =>
      getState().activeUTubID !== null &&
      getState().urls.length === 0 &&
      !getState().multiSelectMode,
  },
];

/**
 * A tip is only worth showing when its anchor is actually rendered-visible.
 * `offsetParent === null` is true for an element inside a `.hidden` ancestor
 * (e.g. a mobile panel that is not the current deck), matching the same
 * opener-visibility check `tags/sheet.ts` uses. Inherently correct on both
 * desktop (both panels visible) and mobile (off-panel anchors are hidden).
 */
function isAnchorVisible(anchorSelector: string): boolean {
  const anchor = document.querySelector<HTMLElement>(anchorSelector);
  return anchor !== null && anchor.offsetParent !== null;
}

/**
 * Show the highest-priority eligible tip, or nothing. Suppressed entirely while
 * a conflicting home UI owns the space the bubble would occupy (an open form,
 * an active UTub-name/cross-UTub search, or multi-select mode) — in which case
 * any currently-active tip is also torn down WITHOUT marking it seen, so it can
 * re-show once the conflicting UI closes. Otherwise walks the registry in
 * priority order and shows the first tip that is unseen, eligible, and whose
 * anchor is visible. At most one tip is ever shown.
 */
export function maybeShowNextTip(): void {
  const suppressed =
    getOpenForm() !== null ||
    getState().multiSelectMode ||
    isUTubSearchActive() ||
    isCrossUtubSearchActive();
  if (suppressed) {
    if (_activeTip !== null) dismissActiveTip({ markSeen: false });
    return;
  }

  // A tip is already visible — never stack a second one.
  if (_activeTip !== null) return;

  for (const nudge of NUDGE_REGISTRY) {
    if (hasSeenTip(nudge.tipId)) continue;
    if (!nudge.isEligible()) continue;
    if (!isAnchorVisible(nudge.anchorSelector)) continue;
    showTip({
      tipId: nudge.tipId,
      anchorSelector: nudge.anchorSelector,
      titleKey: nudge.titleKey,
      bodyKey: nudge.bodyKey,
    });
    return;
  }
}

/**
 * Initialize the onboarding-nudge system exactly once. Wires the event-bus
 * subscriptions that drive contextual sequencing and mobile-panel teardown,
 * then evaluates the initial (server-rendered) page state so the zero-UTub
 * Create tip fires on first load when applicable.
 *
 * - `UTUB_SELECTED`: after the first UTub is created and auto-selected, advance
 *   from the (now-seen/ineligible) Create-UTub tip to the Add-URL tip.
 * - `MOBILE_DECK_SWITCHED`: tear down an active tip whose anchor is no longer
 *   visible (environment-driven, `markSeen: false`), THEN re-evaluate so an
 *   eligible tip can (re)show on the now-current panel. Teardown must precede
 *   re-evaluation, else `maybeShowNextTip`'s single-active-tip guard would skip
 *   the new panel's eligible tip.
 */
export function initOnboardingNudges(): void {
  if (_onboardingInitialized) return;
  _onboardingInitialized = true;

  on(AppEvents.UTUB_SELECTED, () => maybeShowNextTip());
  on(AppEvents.MOBILE_DECK_SWITCHED, () => {
    if (_activeTipId !== null) {
      const activeConfig = NUDGE_REGISTRY.find(
        (nudge) => nudge.tipId === _activeTipId,
      );
      if (
        activeConfig !== undefined &&
        !isAnchorVisible(activeConfig.anchorSelector)
      ) {
        dismissActiveTip({ markSeen: false });
      }
    }
    maybeShowNextTip();
  });

  maybeShowNextTip();
}

/**
 * Test-only reset: clear the active tip, cancel any pending bind, remove the
 * document handlers, reset the init guard, and reset persisted seen state
 * (mirrors `swipe.ts`'s `_resetURLSwipeGestureForTests`).
 */
export function _resetOnboardingNudgesForTests(): void {
  if (_pendingBindTimer !== null) {
    clearTimeout(_pendingBindTimer);
    _pendingBindTimer = null;
  }
  _activeTip = null;
  _activeTipId = null;
  _onboardingInitialized = false;
  $(document).off(CLICK_NAMESPACE);
  $(document).off(KEYDOWN_NAMESPACE);
  _resetOnboardingStorageForTests();
}
