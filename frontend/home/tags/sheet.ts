import { $ } from "../../lib/globals.js";
import { KEYS } from "../../lib/constants.js";
import { AppEvents, on } from "../../lib/event-bus.js";
import { emit as recordUIEvent } from "../../lib/metrics-client.js";
import { clamp, shouldCommitSheetGesture } from "../../logic/tag-sheet-snap.js";
import { TAG_SHEET_TOGGLE_ACTION } from "../../types/metrics-dim-values.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { isCrossUtubSearchActive } from "../search/cross-utub-search.js";
import { isMobile } from "../mobile.js";

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
  sheetHeight: number;
  sheet: HTMLElement;
  target: HTMLElement;
} | null = null;
// Set true when a real drag commits, so the element's trailing click does not
// also fire the tap toggle. Consumed (read-and-reset) by the click wrappers.
let _suppressClickAfterDrag = false;

function _consumeClickSuppression(): boolean {
  const suppressed = _suppressClickAfterDrag;
  _suppressClickAfterDrag = false;
  return suppressed;
}

const SHEET_SELECTOR = "#tagDeckSheet";
const SHEET_BODY_SELECTOR = "#tagSheetBody";
const BACKDROP_SELECTOR = "#tagSheetBackdrop";
const HANDLE_ID = "tagSheetHandle";
const HANDLE_SELECTOR = `#${HANDLE_ID}`;
const HANDLE_COUNT_SELECTOR = "#tagSheetHandleCount";
const GRABBER_ID = "tagSheetGrabber";
const GRABBER_SELECTOR = `#${GRABBER_ID}`;
// Left half of the tag deck's title row — a secondary, larger close target
// (the grabber bar alone is an awkward touch target). Sized to 50% width in
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
// Siblings of these two are made inert while the sheet is open; the pair is
// excluded so the sheet and its backdrop remain interactive.
const INERT_EXCLUDE_SELECTOR = `${SHEET_SELECTOR}, ${BACKDROP_SELECTOR}`;

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
 * The handle shows only when mobile + a UTub is selected + the URL deck is
 * showing + cross-search is not open. Exported so mobile-state subscribers can
 * re-sync it after a deck transition.
 */
export function refreshTagSheetHandleVisibility(): void {
  const utubSelected = $(".UTubSelector.active").length > 0;
  const urlDeckShowing = $(".panel#centerPanel").hasClass("visible-flex");
  const shouldShow =
    isMobile() && utubSelected && urlDeckShowing && !isCrossUtubSearchActive();
  $(HANDLE_SELECTOR).toggleClass(HIDDEN_CLASS, !shouldShow);
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
    // Close first (the handle's JS hidden-state must also reset), then refresh
    // handle visibility so a later return to mobile re-shows it correctly.
    closeTagSheet({ returnFocus: false });
    refreshTagSheetHandleVisibility();
  }
}

export function openTagSheet(): void {
  if (!isMobile()) return;

  // Capture the element that had focus at open time so focus can be returned to
  // it on close (covers both #toTags and #tagSheetHandle openers; WCAG 2.4.3).
  _opener = document.activeElement as HTMLElement | null;

  $(SHEET_SELECTOR).addClass(SHEET_OPEN_CLASS).attr("aria-hidden", "false");
  // Defer the backdrop class one tick so the CSS opacity transition fires. Also
  // clear any inline opacity set mid-drag so the committed-open gesture does not
  // flash the backdrop down to its CSS base before the class transition runs.
  setTimeout(() => {
    $(BACKDROP_SELECTOR).addClass(BACKDROP_SHOW_CLASS);
    const backdrop = document.querySelector(
      BACKDROP_SELECTOR,
    ) as HTMLElement | null;
    if (backdrop) backdrop.style.opacity = "";
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

  document.getElementById(GRABBER_ID)?.focus();

  $(document).on(ESCAPE_KEYDOWN_NAMESPACE, (event: JQuery.TriggeredEvent) => {
    if (event.key !== KEYS.ESCAPE) return;
    closeTagSheet();
  });

  _updateEmptyState();

  recordUIEvent({
    event: UI_EVENTS.UI_TAG_SHEET_TOGGLE,
    action: TAG_SHEET_TOGGLE_ACTION.OPEN,
  });
}

export function closeTagSheet({
  returnFocus = true,
}: { returnFocus?: boolean } = {}): void {
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

  $(SHEET_SELECTOR).removeClass(SHEET_OPEN_CLASS).attr("aria-hidden", "true");
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
    if (_opener !== null && document.contains(_opener)) {
      _opener.focus();
    } else {
      document.getElementById(HANDLE_ID)?.focus();
    }
  }
  _opener = null;

  if (wasOpen) {
    recordUIEvent({
      event: UI_EVENTS.UI_TAG_SHEET_TOGGLE,
      action: TAG_SHEET_TOGGLE_ACTION.CLOSE,
    });
  }
}

export function toggleTagSheet(): void {
  if (sheetOpen) {
    closeTagSheet();
  } else {
    openTagSheet();
  }
}

export function isTagSheetOpen(): boolean {
  return sheetOpen;
}

/**
 * Begin a swipe gesture from the handle (open) or grabber (close). Captures the
 * sheet element and pointer once, then streams move/up/cancel on the target.
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

  // currentTarget is the handle/grabber (a child of the sheet). The sheet itself
  // is a separate element captured here, never from the event.
  const sheet = document.querySelector(SHEET_SELECTOR) as HTMLElement | null;
  if (sheet === null) return;
  const target = event.currentTarget as HTMLElement;
  const sheetHeight = sheet.getBoundingClientRect().height;
  // A zero-height sheet (not laid out) would make every fraction/velocity
  // division degenerate (Infinity/NaN). Treat that press as a tap, not a drag.
  if (sheetHeight <= 0) return;

  _dragState = {
    pointerId: event.pointerId,
    startY: event.clientY,
    lastY: event.clientY,
    lastT: performance.now(),
    velocity: 0,
    moved: false,
    mode,
    sheetHeight,
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
            value: _dragState.sheetHeight - Math.max(progress, 0),
            min: 0,
            max: _dragState.sheetHeight,
          })
        : clamp({
            value: Math.max(progress, 0),
            min: 0,
            max: _dragState.sheetHeight,
          });
    _dragState.sheet.style.transform = `translateY(${offset}px)`;

    if (_dragState.mode === "open") {
      const backdrop = document.querySelector(
        BACKDROP_SELECTOR,
      ) as HTMLElement | null;
      if (backdrop) {
        backdrop.style.opacity = String(
          Math.min(progress / _dragState.sheetHeight, 1),
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
    value: Math.max(finalProgress, 0) / state.sheetHeight,
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
      openTagSheet();
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
  if (commit) closeTagSheet();
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

  $(HANDLE_SELECTOR).on("click", () => {
    if (_consumeClickSuppression()) return;
    toggleTagSheet();
  });
  $(GRABBER_SELECTOR).on("click", () => {
    if (_consumeClickSuppression()) return;
    closeTagSheet();
  });
  $(BACKDROP_SELECTOR).on("click", () => closeTagSheet());

  // Native pointer-drag: up from the handle opens, down from the grabber closes.
  // Guarded by GESTURE_BOUND_ATTR so re-init never double-binds.
  const handle = document.getElementById(HANDLE_ID);
  if (handle && !handle.hasAttribute(GESTURE_BOUND_ATTR)) {
    handle.setAttribute(GESTURE_BOUND_ATTR, "true");
    handle.addEventListener("pointerdown", (event: PointerEvent) => {
      _beginDrag({ event, mode: "open" });
    });
  }
  const grabber = document.getElementById(GRABBER_ID);
  if (grabber && !grabber.hasAttribute(GESTURE_BOUND_ATTR)) {
    grabber.setAttribute(GESTURE_BOUND_ATTR, "true");
    grabber.addEventListener("pointerdown", (event: PointerEvent) => {
      _beginDrag({ event, mode: "close" });
    });
  }

  // Tapping the title group (left half of the tag deck header) closes the sheet
  // — a larger touch target than the grabber. Mobile + open only: on desktop the
  // same element drives the caret collapse (collapsible-decks.ts), which already
  // no-ops on mobile, so the two handlers never conflict.
  $(TITLE_GROUP_SELECTOR).on("click", () => {
    if (isMobile() && sheetOpen) closeTagSheet();
  });

  on(AppEvents.UTUB_SELECTED, () => {
    if (sheetOpen) closeTagSheet({ returnFocus: false });
    refreshTagSheetHandleVisibility();
    _updateEmptyState();
  });

  on(AppEvents.UTUB_DELETED, () => {
    if (sheetOpen) closeTagSheet({ returnFocus: false });
    refreshTagSheetHandleVisibility();
  });

  on(AppEvents.CROSS_UTUB_SEARCH_VISIBILITY_CHANGED, ({ active }) => {
    if (active) closeTagSheet({ returnFocus: false });
    refreshTagSheetHandleVisibility();
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
    closeTagSheet({ returnFocus: false });
    refreshTagSheetHandleVisibility();
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
