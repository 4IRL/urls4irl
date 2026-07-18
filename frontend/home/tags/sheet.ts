import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { AppEvents, on } from "../../lib/event-bus.js";
import { emit as recordUIEvent } from "../../lib/metrics-client.js";
import { clamp, shouldCommitSheetGesture } from "../../logic/tag-sheet-snap.js";
import { getState } from "../../store/app-store.js";
import {
  TAG_SHEET_TOGGLE_ACTION,
  TAG_SHEET_TOGGLE_TRIGGER,
} from "../../types/metrics-dim-values.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { isCrossUtubSearchActive } from "../search/cross-utub-search.js";
import { isMobile, type MobilePanel } from "../mobile.js";

// Locally-derived alias for the closed set of tag-sheet toggle triggers
// (`metrics-dimensions.d.ts` only carries inline literal unions, no standalone
// Trigger type — mirrors cross-utub-search.ts's TagSheetToggleTrigger pattern).
type TagSheetToggleTrigger =
  (typeof TAG_SHEET_TOGGLE_TRIGGER)[keyof typeof TAG_SHEET_TOGGLE_TRIGGER];

// Module-local open flag — no cross-module reader needs it, so it lives here
// rather than the app store (mirrors `userCollapsedLHS` in left-panel-toggle.ts).
let sheetOpen = false;
// Tracks which element last opened the sheet so focus returns to it on close
// (WCAG 2.4.3).
let _opener: HTMLElement | null = null;

// In-flight swipe-gesture state. Null between gestures. Kept module-local
// (matching the deliberate `sheetOpen` decision) — no cross-module reader needs
// it. `mode` is the gesture direction; positive "progress" always means motion
// toward the committed state.
let _dragState: {
  pointerId: number;
  startY: number;
  lastY: number;
  lastT: number;
  velocity: number;
  moved: boolean;
  mode: "open" | "close";
  // Distance the sheet travels between the collapsed-peek and fully-open
  // detents: sheet height minus the peeking header height. All drag fractions
  // and clamps are relative to this, not the full sheet height.
  travel: number;
  sheet: HTMLElement;
  target: HTMLElement;
} | null = null;
// Set true when a real drag commits, so the element's trailing click does not
// also fire the tap toggle. Consumed (read-and-reset) by the click wrappers.
let _suppressClickAfterDrag = false;

// True while a live pushed/restored history entry exists for the currently-open
// sheet that still needs reconciling on close. Set when the user-action wrapper
// pushes a fresh entry AND when handlePopState restores the sheet onto an
// existing entry (both paths flow through openTagSheet()).
let _openedViaHistoryPush = false;
// The mobile panel the sheet was opened over (always "urls" by construction —
// the sheet only overlays the url-deck). Mirrored module-locally because the
// previous entry's data is gone from window.history.state by the time a popstate
// handler runs, so window-events.ts reads it via getTagSheetOriginPanel().
let _openedOverPanel: MobilePanel | null = null;
// Set by window-events.ts's beginPopstateClose()/endPopstateClose() bracket so a
// close it triggers mid-popstate skips its own history traversal (the popstate
// handler already owns the traversal).
let _closingViaPopstate = false;
// Armed for the single popstate that closeTagSheet()'s own default history.back()
// is about to dispatch (a standalone tap/Escape/backdrop/title-group dismissal, or
// the desktop-relocate close). That traversal exists only to unwind the sheet's
// pushed entry — the underlying UTub and panel are unchanged and the active tag
// filter must survive. window-events.ts's handlePopState consumes-and-resets this
// (getter below) to recognize + swallow that self-close pop so it never rebuilds
// the UTub (buildSelectedUTub resets selectedTagIDs, wiping the filter). The
// mirror image of _closingViaPopstate: that flag flows popstate→close, this one
// flows close→popstate.
let _selfClosingViaBack = false;

function _consumeClickSuppression(): boolean {
  const suppressed = _suppressClickAfterDrag;
  _suppressClickAfterDrag = false;
  return suppressed;
}

const SHEET_SELECTOR = "#tagDeckSheet";
const SHEET_VIEWPORT_SELECTOR = "#tagSheetViewport";
const SHEET_BODY_SELECTOR = "#tagSheetBody";
const BACKDROP_SELECTOR = "#tagSheetBackdrop";
const HANDLE_ID = "tagSheetHandle";
const HANDLE_SELECTOR = `#${HANDLE_ID}`;
const HANDLE_COUNT_SELECTOR = "#tagSheetHandleCount";
// Left half of the tag deck's title row — a secondary, larger close target
// (the header lip alone is an awkward touch target). Sized to 50% width in
// tag-sheet.css so the action buttons on the right half stay tappable.
const TITLE_GROUP_SELECTOR = "#TagDeckTitleGroup";
const EMPTY_STATE_SELECTOR = "#tagSheetEmpty";
const MAIN_PANEL_SELECTOR = "#mainPanel";
const TAG_DECK_SELECTOR = "#TagDeck";
const LIST_TAGS_SELECTOR = "#listTags";
const TAG_FILTER_SELECTOR = ".tagFilter";
const SHEET_OPEN_CLASS = "tag-sheet-open";
const SHEET_DRAGGING_CLASS = "tag-sheet-dragging";
const BACKDROP_SHOW_CLASS = "tag-sheet-backdrop-show";
const HIDDEN_CLASS = "hidden";
const ESCAPE_KEYDOWN_NAMESPACE = "keydown.tagSheetEscape";
// Movement (px) below which a press-release is treated as a tap, not a drag.
const TAP_SLOP_PX = 8;
// Idempotency marker so re-running initTagSheet() never double-binds the drag.
const GESTURE_BOUND_ATTR = "data-tag-sheet-gesture-bound";
// #mainPanel children other than these are made inert while the sheet is open.
// The sheet's clipping viewport (which contains the sheet) and the backdrop are
// excluded so they remain interactive.
const INERT_EXCLUDE_SELECTOR = `${SHEET_VIEWPORT_SELECTOR}, ${BACKDROP_SELECTOR}`;

/**
 * Toggle the inline empty-state message based on the current `#listTags` child
 * count. Reads only the DOM; independent of `sheetOpen`. The "No tags in this
 * UTub." literal lives in the Jinja template (TS only toggles `.hidden`), so no
 * APP_CONFIG bridge is warranted.
 */
function _updateEmptyState(): void {
  const hasTags =
    $(LIST_TAGS_SELECTOR).children(TAG_FILTER_SELECTOR).length > 0;
  $(EMPTY_STATE_SELECTOR).toggleClass(HIDDEN_CLASS, hasTags);
}

/**
 * The whole sheet (its peeking header included) is present only when mobile + a
 * UTub is selected + the URL deck is showing + cross-search is not open;
 * otherwise it is fully hidden via `.hidden`. Exported so mobile-state
 * subscribers can re-sync it after a deck transition.
 */
export function refreshTagSheetAvailability(): void {
  const utubSelected = $(".UTubSelector.active").length > 0;
  const urlDeckShowing = $(".panel#centerPanel").hasClass("visible-flex");
  const shouldShow =
    isMobile() && utubSelected && urlDeckShowing && !isCrossUtubSearchActive();
  $(SHEET_SELECTOR).toggleClass(HIDDEN_CLASS, !shouldShow);
}

/**
 * Move `#TagDeck` into the sheet on mobile and back into `#leftPanel` (as the
 * 3rd child, after `#MemberDeck`) on desktop. Moving the whole node keeps
 * `#listTags` + its `.tagFilter` children intact so `sortTagFiltersInPlace`
 * stays valid.
 */
export function relocateTagDeckForViewport(): void {
  const tagDeckInSheet =
    $(`${SHEET_BODY_SELECTOR} ${TAG_DECK_SELECTOR}`).length > 0;

  if (isMobile()) {
    if (!tagDeckInSheet) {
      $(TAG_DECK_SELECTOR).appendTo(SHEET_BODY_SELECTOR);
    }
    _updateEmptyState();
    return;
  }

  if (tagDeckInSheet) {
    $(TAG_DECK_SELECTOR).insertAfter("#leftPanel #MemberDeck");
    // Close first (the sheet's open/inert state must reset), then refresh
    // availability so a later return to mobile re-shows the peek correctly.
    // Default (standalone) reconciliation — NOT viaDeckSwitch (DD-21): a resize
    // into desktop has no caller-owned push burying the entry, so history.back()
    // must consume it (openTagSheet()'s isMobile() guard no-ops the restore).
    closeTagSheet({
      returnFocus: false,
      trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP,
    });
    refreshTagSheetAvailability();
  }
}

export function openTagSheet({
  trigger,
}: {
  trigger: TagSheetToggleTrigger;
}): void {
  if (!isMobile()) return;

  // Capture the element that had focus at open time so focus can be returned to
  // it on close (covers both #toTags and #tagSheetHandle openers; WCAG 2.4.3).
  _opener = document.activeElement as HTMLElement | null;

  // The section is never aria-hidden: the handle (now the sheet's header/peek
  // lip) must stay reachable when collapsed. Modal semantics live on the body
  // instead — aria-modal is set only while open, and the body's inert/aria-hidden
  // are cleared here.
  $(SHEET_SELECTOR).addClass(SHEET_OPEN_CLASS).attr("aria-modal", "true");
  $(SHEET_BODY_SELECTOR).prop("inert", false).attr("aria-hidden", "false");
  // Defer the backdrop class one tick so the CSS opacity transition fires. Also
  // clear any inline opacity set mid-drag so the committed-open gesture does not
  // flash the backdrop down to its CSS base before the class transition runs.
  setTimeout(() => {
    $(BACKDROP_SELECTOR).addClass(BACKDROP_SHOW_CLASS).css("opacity", "");
  }, 0);
  $(HANDLE_SELECTOR).attr("aria-expanded", "true");
  sheetOpen = true;

  // Trap focus: mark every #mainPanel direct child inert except the sheet and
  // its backdrop. Native inert focus containment needs no custom Tab interceptor
  // (Chrome 120+, Firefox 121+, Safari 16+).
  $(MAIN_PANEL_SELECTOR)
    .children()
    .not(INERT_EXCLUDE_SELECTOR)
    .prop("inert", true);

  document.getElementById(HANDLE_ID)?.focus();

  $(document).on(ESCAPE_KEYDOWN_NAMESPACE, (event: JQuery.TriggeredEvent) => {
    if (event.key !== KEYS.ESCAPE) return;
    closeTagSheet({ trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP });
  });

  _updateEmptyState();

  recordUIEvent({
    event: UI_EVENTS.UI_TAG_SHEET_TOGGLE,
    action: TAG_SHEET_TOGGLE_ACTION.OPEN,
    trigger,
  });

  // A live history entry now exists for this open sheet — freshly pushed by the
  // openTagSheetFromUserAction() wrapper, or restored onto an existing entry by
  // handlePopState — that must be reconciled on close.
  _openedViaHistoryPush = true;
  // The sheet only ever overlays the url-deck by construction, so its origin
  // panel is always "urls". Set here so the popstate-restore path (bare
  // openTagSheet, no pushTagSheetHistoryState) also tracks the origin for the
  // DD-31 same-panel-vs-cross-panel focus decision.
  _openedOverPanel = "urls";

  // Announce only the non-visually-obvious history-nav open (Back/Forward);
  // tap-driven opens are already visible to a sighted user.
  if (trigger === TAG_SHEET_TOGGLE_TRIGGER.HISTORY_NAV) {
    $("#TagSheetAnnouncement").text(
      APP_CONFIG.strings.TAG_SHEET_ANNOUNCEMENT_OPEN,
    );
  }
}

/**
 * Push the sheet's own session-only history entry so Back closes the sheet
 * first. Call-site-owned (per DD-7) — never invoked from inside openTagSheet().
 * Keeps the URL on the url-deck (no `?panel=tags`); the entry is reconciled by
 * closeTagSheet()'s three-way logic. No-op on desktop or with no active UTub.
 */
export function pushTagSheetHistoryState(): void {
  if (!isMobile()) return;
  const activeUTubID = getState().activeUTubID;
  if (activeUTubID === null) return;
  window.history.pushState(
    { UTubID: activeUTubID, mobilePanel: "urls", tagSheetOpen: true },
    "",
    location.href,
  );
  _openedOverPanel = "urls";
}

/**
 * The mobile panel the sheet was opened over, or null when no sheet entry is
 * live. window-events.ts reads this to decide the Back-driven close's focus
 * target (the previous entry's panel is gone from history.state by then).
 */
export function getTagSheetOriginPanel(): MobilePanel | null {
  return _openedOverPanel;
}

/**
 * The single site that pairs a tap-driven open with its history push, so
 * `_openedViaHistoryPush` and the pushed entry can never drift (DD-27). Routed
 * through by all three user-tap open sites (navbar #toTags, drag-commit,
 * handle-tap). Bare openTagSheet() stays reserved for handlePopState's restore.
 */
export function openTagSheetFromUserAction(): void {
  openTagSheet({ trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP });
  pushTagSheetHistoryState();
}

/**
 * Popstate-close bracket: window-events.ts wraps its whole handlePopState
 * invocation in begin/end so any closeTagSheet() it triggers (directly or via a
 * synchronous UTUB_SELECTED listener) skips its own history traversal — the
 * popstate handler already owns it.
 */
export function beginPopstateClose(): void {
  _closingViaPopstate = true;
}

export function endPopstateClose(): void {
  _closingViaPopstate = false;
}

/**
 * Consume-and-reset the self-close flag armed just before closeTagSheet()'s own
 * default history.back(). window-events.ts's handlePopState calls this first: a
 * true result means the incoming popstate is that self-initiated entry
 * consumption (underlying UTub/panel unchanged, active tag filter must survive),
 * so the handler swallows it without rebuilding the UTub. Genuine Back/Forward
 * navigations leave it false and fall through to the normal reconciliation.
 */
export function consumeTagSheetSelfBackClose(): boolean {
  const wasSelfClosing = _selfClosingViaBack;
  _selfClosingViaBack = false;
  return wasSelfClosing;
}

export function closeTagSheet({
  returnFocus = true,
  viaDeckSwitch = false,
  viaReplace = false,
  focusLandmark = false,
  suppressAnnouncement = false,
  trigger,
}: {
  returnFocus?: boolean;
  viaDeckSwitch?: boolean;
  viaReplace?: boolean;
  focusLandmark?: boolean;
  suppressAnnouncement?: boolean;
  trigger: TagSheetToggleTrigger;
}): void {
  // Cancel any in-flight swipe so the four force-close AppEvents plus
  // Escape/backdrop/title-group all tear down a live drag. On the committed-close
  // path _endDrag has already nulled _dragState, so this is a guard-protected
  // no-op there and click-suppression survives.
  _cancelDrag();

  // Capture prior-open state so the CLOSE metric only fires for a real
  // open→close transition. Several programmatic callers (deck-switch, desktop
  // relocate) invoke this on an already-closed sheet; emitting there would
  // inflate close counts with no matching open.
  const wasOpen = sheetOpen;

  $(SHEET_SELECTOR).removeClass(SHEET_OPEN_CLASS).removeAttr("aria-modal");
  $(SHEET_BODY_SELECTOR).prop("inert", true).attr("aria-hidden", "true");
  $(BACKDROP_SELECTOR).removeClass(BACKDROP_SHOW_CLASS);
  $(document).off(ESCAPE_KEYDOWN_NAMESPACE);

  // Unconditional removal is safe: no #mainPanel child carries independent inert state.
  // If that changes, snapshot which siblings were already inert in openTagSheet and restore selectively.
  $(MAIN_PANEL_SELECTOR)
    .children()
    .not(INERT_EXCLUDE_SELECTOR)
    .prop("inert", false);

  $(HANDLE_SELECTOR).attr("aria-expanded", "false");
  sheetOpen = false;

  if (returnFocus) {
    // Require the opener to also be visible/focusable (offsetParent !== null):
    // a Back that closes the sheet AND hides #toTags under a new panel would
    // otherwise .focus() a display:none element and silently drop focus.
    if (
      _opener !== null &&
      document.contains(_opener) &&
      _opener.offsetParent !== null
    ) {
      _opener.focus();
    } else {
      document.getElementById(HANDLE_ID)?.focus();
    }
  } else if (focusLandmark) {
    // Cross-panel Back close: neither the opener (#toTags, scoped to the
    // collapsible dropdown) nor the handle (scoped to the now-hidden url-deck)
    // is guaranteed visible. Fall back to the always-visible hamburger landmark.
    document.querySelector<HTMLElement>(".navbar-toggler")?.focus();
  }
  _opener = null;

  // Three-way reconciliation of the sheet's own history entry. Mirrors the
  // null-first-line re-entrancy-guard style of _cancelDrag/_endDrag.
  if (_closingViaPopstate) {
    // window-events.ts already owns the traversal — skip all history work.
    _openedViaHistoryPush = false;
    _openedOverPanel = null;
  } else if (_openedViaHistoryPush) {
    if (viaDeckSwitch) {
      // The caller's own same-stack push buries this entry one level deeper;
      // traversing here would fire a stale popstate. Skip back() (DD-21 detail).
    } else if (viaReplace) {
      // Consume the entry via replaceState instead of back() so no popstate is
      // dispatched (would self-cancel the cross-UTub search overlay opening now).
      window.history.replaceState(
        { UTubID: getState().activeUTubID },
        "",
        location.href,
      );
    } else {
      // Default/standalone: consume the sheet's entry with a real traversal.
      // Arm the self-close flag so the popstate this back() dispatches is
      // swallowed by handlePopState instead of rebuilding the underlying UTub —
      // a rebuild would reset selectedTagIDs and wipe the active tag filter that
      // must persist behind the now-collapsed sheet.
      _selfClosingViaBack = true;
      window.history.back();
    }
    _openedViaHistoryPush = false;
    _openedOverPanel = null;
  }

  if (wasOpen) {
    recordUIEvent({
      event: UI_EVENTS.UI_TAG_SHEET_TOGGLE,
      action: TAG_SHEET_TOGGLE_ACTION.CLOSE,
      trigger,
    });
    // Announce only the non-visually-obvious history-nav close, and only when a
    // competing #MobilePanelAnnouncement is not firing in the same invocation
    // (DD-32 — the panel-change announcement is the more informative one).
    if (
      trigger === TAG_SHEET_TOGGLE_TRIGGER.HISTORY_NAV &&
      !suppressAnnouncement
    ) {
      $("#TagSheetAnnouncement").text(
        APP_CONFIG.strings.TAG_SHEET_ANNOUNCEMENT_CLOSE,
      );
    }
  }
}

export function toggleTagSheet(): void {
  if (sheetOpen) {
    closeTagSheet({ trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP });
  } else {
    openTagSheetFromUserAction();
  }
}

export function isTagSheetOpen(): boolean {
  return sheetOpen;
}

/**
 * Resolve the collapsed peek height (px) from the `--tag-sheet-peek` CSS var so
 * the drag math is independent of the handle's rendered height (which shrinks in
 * the open state). Supports rem/px var units; falls back to the given element's
 * measured height when the var is unavailable (e.g. happy-dom unit tests stub the
 * handle's getBoundingClientRect).
 *
 * @example _collapsedPeekPx({ sheet, fallback: handle }) === 48  // "3rem" @ 16px root
 */
function _collapsedPeekPx({
  sheet,
  fallback,
}: {
  sheet: HTMLElement;
  fallback: HTMLElement;
}): number {
  const raw = getComputedStyle(sheet)
    .getPropertyValue("--tag-sheet-peek")
    .trim();
  if (raw.endsWith("rem")) {
    const rootFontPx =
      parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    const peekPx = parseFloat(raw) * rootFontPx;
    if (Number.isFinite(peekPx) && peekPx > 0) return peekPx;
  } else if (raw.endsWith("px")) {
    const peekPx = parseFloat(raw);
    if (Number.isFinite(peekPx) && peekPx > 0) return peekPx;
  }
  return fallback.getBoundingClientRect().height;
}

/**
 * Begin a swipe gesture from the handle (drag up opens, down closes). Captures
 * the sheet element and pointer once, then streams move/up/cancel on the target.
 */
function _beginDrag({
  event,
  mode,
}: {
  event: PointerEvent;
  mode: "open" | "close";
}): void {
  // Reject a secondary pointer while a drag is already live (a second finger
  // would orphan the first pointer's listeners by overwriting _dragState).
  if (_dragState !== null) return;
  if (event.button !== 0) return;
  // Mouse users keep click-to-toggle; touch/pen primary drags proceed.
  if (!isMobile() || event.pointerType === "mouse") return;
  if (mode === "open" && isTagSheetOpen()) return;
  if (mode === "close" && !isTagSheetOpen()) return;

  _suppressClickAfterDrag = false;

  // currentTarget is the handle (the sheet's header lip). The sheet itself is
  // the ancestor element captured here, never from the event.
  const sheet = document.querySelector(SHEET_SELECTOR) as HTMLElement | null;
  if (sheet === null) return;
  const target = event.currentTarget as HTMLElement;
  // The sheet travels by (height - peek): the peeking header stays on screen in
  // the collapsed detent. Peek is read from the --tag-sheet-peek CSS var, not the
  // handle's current height, because the handle is slimmed in the open state — a
  // close-drag must still measure travel against the full collapsed peek.
  const peek = _collapsedPeekPx({ sheet, fallback: target });
  const travel = sheet.getBoundingClientRect().height - peek;
  // A non-positive travel (sheet not laid out, or peek >= height) would make
  // every fraction/velocity division degenerate (Infinity/NaN). Treat that
  // press as a tap, not a drag.
  if (travel <= 0) return;

  _dragState = {
    pointerId: event.pointerId,
    startY: event.clientY,
    lastY: event.clientY,
    lastT: performance.now(),
    velocity: 0,
    moved: false,
    mode,
    travel,
    sheet,
    target,
  };

  if (typeof target.setPointerCapture === "function") {
    try {
      target.setPointerCapture(event.pointerId);
    } catch {
      // Pointer capture is best-effort; absence is non-fatal in happy-dom.
    }
  }
  target.addEventListener("pointermove", _onDragMove);
  target.addEventListener("pointerup", _endDrag);
  target.addEventListener("pointercancel", _endDrag);
}

/**
 * Track the finger while dragging: move the sheet 1:1 (once past the tap slop),
 * interpolate the backdrop on open, and sample velocity for the release snap.
 */
function _onDragMove(event: PointerEvent): void {
  if (_dragState === null) return;
  // Ignore a stray second pointer if capture silently failed (try/catch).
  if (event.pointerId !== _dragState.pointerId) return;

  const deltaY = event.clientY - _dragState.startY;
  // Positive = motion toward commit (open = upward/negative deltaY, close = down).
  const progress = _dragState.mode === "open" ? -deltaY : deltaY;

  if (!_dragState.moved && Math.abs(deltaY) >= TAP_SLOP_PX) {
    _dragState.moved = true;
    _dragState.sheet.classList.add(SHEET_DRAGGING_CLASS);
  }

  if (_dragState.moved) {
    event.preventDefault();
    const offset =
      _dragState.mode === "open"
        ? clamp({
            value: _dragState.travel - Math.max(progress, 0),
            min: 0,
            max: _dragState.travel,
          })
        : clamp({
            value: Math.max(progress, 0),
            min: 0,
            max: _dragState.travel,
          });
    _dragState.sheet.style.transform = `translateY(${offset}px)`;

    if (_dragState.mode === "open") {
      const backdrop = document.querySelector(
        BACKDROP_SELECTOR,
      ) as HTMLElement | null;
      if (backdrop) {
        backdrop.style.opacity = String(
          Math.min(Math.max(progress / _dragState.travel, 0), 1),
        );
      }
    }
  }

  const now = performance.now();
  const elapsedMs = now - _dragState.lastT;
  if (elapsedMs > 0) {
    const sampleDelta =
      _dragState.mode === "open"
        ? -(event.clientY - _dragState.lastY)
        : event.clientY - _dragState.lastY;
    _dragState.velocity = sampleDelta / elapsedMs;
  }
  _dragState.lastY = event.clientY;
  _dragState.lastT = now;
}

/**
 * Release handler shared by pointerup/pointercancel: tear down listeners, then
 * decide whether to commit (route through open/close) or snap back.
 */
function _endDrag(event: PointerEvent): void {
  if (_dragState === null) return;
  // Ignore a stray second pointer if capture silently failed (try/catch).
  if (event.pointerId !== _dragState.pointerId) return;
  const state = _dragState;
  const { pointerId, mode, startY, lastY, sheet } = state;

  // Unconditional teardown from captured locals (never _cancelDrag here — it
  // would double-tear-down and reset suppression on the committed-close path).
  if (typeof state.target.releasePointerCapture === "function") {
    try {
      state.target.releasePointerCapture(pointerId);
    } catch {
      // Capture may already be released (cancel/lostpointercapture).
    }
  }
  state.target.removeEventListener("pointermove", _onDragMove);
  state.target.removeEventListener("pointerup", _endDrag);
  state.target.removeEventListener("pointercancel", _endDrag);
  sheet.classList.remove(SHEET_DRAGGING_CLASS);
  sheet.style.transform = "";

  // Cancel or non-moved release: a tap (native click drives the existing toggle)
  // or a cancel snaps back to the class-driven state. Clear backdrop, do not route.
  if (event.type === "pointercancel" || !state.moved) {
    const backdrop = document.querySelector(
      BACKDROP_SELECTOR,
    ) as HTMLElement | null;
    if (backdrop) backdrop.style.opacity = "";
    _dragState = null;
    return;
  }

  const finalProgress = mode === "open" ? startY - lastY : lastY - startY;
  const draggedFraction = clamp({
    value: Math.max(finalProgress, 0) / state.travel,
    min: 0,
    max: 1,
  });
  const commit = shouldCommitSheetGesture({
    draggedFraction,
    velocity: state.velocity,
  });

  if (commit) _suppressClickAfterDrag = true;

  // Null BEFORE routing: the re-entrant _cancelDrag() from closeTagSheet() then
  // hits its null-guard as a pure no-op, preserving _suppressClickAfterDrag on
  // the committed-close path.
  _dragState = null;

  if (mode === "open") {
    if (commit) {
      // Focus the handle so openTagSheet() captures it as _opener (it reads
      // document.activeElement at its first line). The handle is not yet inert.
      document.getElementById(HANDLE_ID)?.focus();
      openTagSheetFromUserAction();
      // openTagSheet() clears inline backdrop opacity in its timer callback.
    } else {
      const backdrop = document.querySelector(
        BACKDROP_SELECTOR,
      ) as HTMLElement | null;
      if (backdrop) backdrop.style.opacity = "";
    }
    return;
  }

  // close mode: commit closes; snap-back leaves .tag-sheet-open in place. The
  // open-only backdrop interpolation means no inline opacity clear is needed.
  if (commit) closeTagSheet({ trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP });
}

/**
 * Centralized drag teardown for every force-close path. The null-guard first
 * line is the re-entrancy key: on the committed-close path _endDrag has already
 * nulled _dragState, so this returns as a pure no-op and click-suppression
 * survives. On live-drag force-closes it performs a full teardown.
 */
function _cancelDrag(): void {
  if (_dragState === null) return;

  _dragState.target.removeEventListener("pointermove", _onDragMove);
  _dragState.target.removeEventListener("pointerup", _endDrag);
  _dragState.target.removeEventListener("pointercancel", _endDrag);
  if (typeof _dragState.target.releasePointerCapture === "function") {
    try {
      _dragState.target.releasePointerCapture(_dragState.pointerId);
    } catch {
      // already released
    }
  }
  _dragState.sheet.classList.remove(SHEET_DRAGGING_CLASS);
  _dragState.sheet.style.transform = "";
  const backdrop = document.querySelector(
    BACKDROP_SELECTOR,
  ) as HTMLElement | null;
  if (backdrop) backdrop.style.opacity = "";
  _suppressClickAfterDrag = false;
  _dragState = null;
}

/**
 * Test-only helper: clear in-flight drag state so an interrupted-drag test never
 * leaks state into the next test (mirrors _resetPaneResizersForTests).
 */
export function _resetTagSheetGestureForTests(): void {
  _dragState = null;
  _suppressClickAfterDrag = false;
}

export function initTagSheet(): void {
  // Place #TagDeck correctly for the load-time viewport (one-shot; viewport
  // crossings are owned by initMobileLayout's matchMedia listener in mobile.ts).
  relocateTagDeckForViewport();

  // The handle is the sheet's header/peek lip: tapping it toggles, and it is the
  // single drag target for both directions (drag up to open, down to close).
  $(HANDLE_SELECTOR).on("click", () => {
    if (_consumeClickSuppression()) return;
    toggleTagSheet();
  });
  $(BACKDROP_SELECTOR).on("click", () =>
    closeTagSheet({ trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP }),
  );

  // Native pointer-drag bound once on the handle; the direction is derived from
  // the current open state at press time. Guarded by GESTURE_BOUND_ATTR so
  // re-init never double-binds.
  const handle = document.getElementById(HANDLE_ID);
  if (handle && !handle.hasAttribute(GESTURE_BOUND_ATTR)) {
    handle.setAttribute(GESTURE_BOUND_ATTR, "true");
    handle.addEventListener("pointerdown", (event: PointerEvent) => {
      _beginDrag({ event, mode: isTagSheetOpen() ? "close" : "open" });
    });
  }

  // Tapping the title group (left half of the tag deck header) closes the sheet
  // — a larger touch target than the header lip. Mobile + open only: on desktop the
  // same element drives the caret collapse (collapsible-decks.ts), which already
  // no-ops on mobile, so the two handlers never conflict.
  $(TITLE_GROUP_SELECTOR).on("click", () => {
    if (isMobile() && sheetOpen)
      closeTagSheet({ trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP });
  });

  on(AppEvents.UTUB_SELECTED, () => {
    if (sheetOpen)
      closeTagSheet({
        returnFocus: false,
        trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP,
      });
    refreshTagSheetAvailability();
    _updateEmptyState();
  });

  on(AppEvents.UTUB_DELETED, () => {
    if (sheetOpen)
      closeTagSheet({
        returnFocus: false,
        trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP,
      });
    refreshTagSheetAvailability();
  });

  on(AppEvents.CROSS_UTUB_SEARCH_VISIBILITY_CHANGED, ({ active }) => {
    // Consume the sheet's entry via replaceState (viaReplace), not back():
    // a popstate here would self-cancel the cross-UTub search overlay opening.
    if (active)
      closeTagSheet({
        returnFocus: false,
        viaReplace: true,
        trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP,
      });
    refreshTagSheetAvailability();
  });

  on(AppEvents.MOBILE_DECK_SWITCHED, ({ target }) => {
    if (target === "desktop") {
      relocateTagDeckForViewport();
      return;
    }
    // Any explicit mobile deck navigation dismisses an open sheet — including
    // navigating (back) to the URL deck via the navbar. closeTagSheet is a safe
    // no-op when the sheet is already closed (the common UTub-select path), so
    // the url-deck target is no longer special-cased: leaving it open would keep
    // #mainPanel siblings inert and break navbar re-open over the URL deck.
    // viaDeckSwitch: the tap handler's own pushMobilePanelHistoryState runs in
    // the same call stack and buries the sheet's entry, so skip history.back().
    closeTagSheet({
      returnFocus: false,
      viaDeckSwitch: true,
      trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP,
    });
    refreshTagSheetAvailability();
  });

  // Stateless show/hide of the handle's count badge from selectedTagIDs.length.
  // Registered once permanently — no per-UTub teardown (unlike deck.ts), so it
  // never accumulates duplicates across UTub changes.
  on(AppEvents.TAG_FILTER_CHANGED, ({ selectedTagIDs }) => {
    const count = selectedTagIDs.length;
    $(HANDLE_COUNT_SELECTOR)
      .toggleClass(HIDDEN_CLASS, count === 0)
      .text(count > 0 ? String(count) : "");
  });
}
