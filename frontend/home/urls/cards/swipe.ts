/**
 * Left-swipe-to-delete gesture for `.urlRow` (mobile/touch only). Mirrors
 * `frontend/home/tags/sheet.ts`'s pointer-drag structure: a single module-local
 * `_dragState` (only one row can be mid-drag at a time), dynamic
 * pointermove/pointerup/pointercancel binding on the drag target, and a
 * consume-once click-suppression flag for the trailing click after a commit.
 * Commit-threshold math is pure and lives in `logic/url-swipe-snap.ts`; this
 * module owns only DOM binding and reuses the existing `deleteURLShowModal`
 * confirm flow as the sole commit action — no new AJAX/CSRF logic here.
 */
import { $ } from "../../../lib/globals.js";
import {
  clamp,
  shouldCommitSwipeGesture,
  TAP_SLOP_PX,
} from "../../../logic/url-swipe-snap.js";
import { isCoarsePointer, isMobile } from "../../mobile.js";
import { deleteURLShowModal } from "./delete.js";

// A press starting inside any of these must never begin a swipe: it would
// race the existing tap-to-reveal tag-delete toggle, an open inline-edit
// form's own controls, or the corner-access "go to URL" click handler.
const SWIPE_IGNORE_SELECTOR = [
  ".tagBadge",
  ".urlOptions",
  ".urlTagCombobox",
  ".urlTitleBtnUpdate",
  ".urlStringBtnUpdate",
  ".updateUrlTitleWrap",
  ".updateUrlStringWrap",
  ".goToUrlIcon",
].join(", ");

const URL_ROW_CONTENT_SELECTOR = ".urlRowContent";
const URL_ROW_SWIPE_REVEAL_SELECTOR = ".urlRowSwipeReveal";
const URL_ROW_SWIPE_REVEAL_WIDTH_VAR = "--url-swipe-reveal-width";
const SWIPE_DRAGGING_CLASS = "swipe-dragging";
const SWIPE_COMMITTED_CLASS = "swipe-committed";
// Idempotency marker so a defensive re-bind (e.g. re-render) never double-binds
// the pointerdown listener on the same row.
const SWIPE_GESTURE_BOUND_ATTR = "data-url-swipe-gesture-bound";
// A drag is treated as vertical/ambiguous (native scroll wins) once the
// vertical component is at least this fraction of the horizontal component.
const VERTICAL_LOCK_RATIO = 1.5;
const CONFIRM_MODAL_SELECTOR = "#confirmModal";
const CONFIRM_MODAL_HIDDEN_NAMESPACE = "hidden.bs.modal.urlRowSwipeReset";

const NUDGE_SESSION_STORAGE_KEY = "u4i:urlSwipeNudgeShown";
const NUDGE_PEEK_PX = 12;
const NUDGE_PEEK_DURATION_MS = 400;

interface SwipeDragState {
  pointerId: number;
  startX: number;
  startY: number;
  lastX: number;
  lastT: number;
  velocity: number;
  moved: boolean;
  verticalLocked: boolean;
  revealWidth: number;
  target: HTMLElement;
  urlRow: JQuery;
  utubUrlID: number;
  utubID: number;
}

// In-flight swipe-gesture state. Null between gestures. Module-local (matching
// sheet.ts's single-drag-state-object pattern) — only one row can be mid-drag
// at a time.
let _dragState: SwipeDragState | null = null;
// Set true when a commit fires the confirm modal, so the trailing click does
// not also fire card selection. Consumed (read-and-reset) by selection.ts.
let _suppressSwipeClick = false;

export function _consumeSwipeClickSuppression(): boolean {
  const suppressed = _suppressSwipeClick;
  _suppressSwipeClick = false;
  return suppressed;
}

/**
 * Begin a swipe gesture from a `.urlRow`'s persistent pointerdown listener.
 * Rejects mouse/desktop presses, presses inside an ignored control, and rows
 * whose reveal panel has not been laid out yet (treated as a tap).
 */
function _beginDrag({
  event,
  urlRow,
  utubUrlID,
  utubID,
}: {
  event: PointerEvent;
  urlRow: JQuery;
  utubUrlID: number;
  utubID: number;
}): void {
  // Reject a secondary pointer while a drag is already live (a second finger
  // would orphan the first pointer's listeners by overwriting _dragState).
  if (_dragState !== null) return;
  if (event.button !== 0) return;
  // Mouse users keep tap-to-select/click-delete; touch/pen primary drags proceed.
  if (!isMobile() || event.pointerType === "mouse") return;

  const eventTarget = event.target as HTMLElement | null;
  if (eventTarget?.closest(SWIPE_IGNORE_SELECTOR)) return;

  const revealWidth = urlRow
    .find(URL_ROW_SWIPE_REVEAL_SELECTOR)[0]
    ?.getBoundingClientRect().width;
  // A non-positive width (row not laid out, or canDelete false so no reveal
  // panel exists) would make every fraction/velocity division degenerate.
  // Treat that press as a tap, not a drag.
  if (!revealWidth || revealWidth <= 0) return;

  urlRow.css(URL_ROW_SWIPE_REVEAL_WIDTH_VAR, `${revealWidth}px`);

  const target = event.currentTarget as HTMLElement;
  _dragState = {
    pointerId: event.pointerId,
    startX: event.clientX,
    startY: event.clientY,
    lastX: event.clientX,
    lastT: performance.now(),
    velocity: 0,
    moved: false,
    verticalLocked: false,
    revealWidth,
    target,
    urlRow,
    utubUrlID,
    utubID,
  };

  if (typeof target.setPointerCapture === "function") {
    try {
      target.setPointerCapture(event.pointerId);
    } catch {
      // Pointer capture is best-effort; absence is non-fatal.
    }
  }
  target.addEventListener("pointermove", _onDragMove);
  target.addEventListener("pointerup", _endDrag);
  target.addEventListener("pointercancel", _cancelDrag);
}

/**
 * Track the finger while dragging: lock to vertical scroll if the gesture
 * reads as vertical/ambiguous past the tap slop, otherwise move the content
 * layer 1:1 (left-only, clamped to the reveal panel's width) and sample
 * velocity for the release commit decision.
 */
function _onDragMove(event: PointerEvent): void {
  if (_dragState === null) return;
  // Ignore a stray second pointer if capture silently failed (try/catch).
  if (event.pointerId !== _dragState.pointerId) return;
  // Native vertical scroll already owns this pointer sequence — never fight
  // it mid-gesture, and never re-evaluate direction until the next pointerdown.
  if (_dragState.verticalLocked) return;

  const deltaX = event.clientX - _dragState.startX;
  const deltaY = event.clientY - _dragState.startY;

  if (!_dragState.moved) {
    // Sub-slop jitter (or a plain tap) falls through to the existing click
    // handlers untouched. Only gates the initial tap-vs-drag transition —
    // once moved is true, every subsequent move applies unconditionally
    // below (a finger drifting back within the slop band mid-drag must not
    // freeze the transform or skip a velocity sample).
    if (Math.abs(deltaX) <= TAP_SLOP_PX) return;

    if (Math.abs(deltaX) <= VERTICAL_LOCK_RATIO * Math.abs(deltaY)) {
      _dragState.verticalLocked = true;
      return;
    }
    _dragState.moved = true;
    _dragState.urlRow.addClass(SWIPE_DRAGGING_CLASS);
  }

  event.preventDefault();
  const clampedDeltaX = clamp({
    value: deltaX,
    min: -_dragState.revealWidth,
    max: 0,
  });
  _dragState.urlRow
    .find(URL_ROW_CONTENT_SELECTOR)
    .css("transform", `translateX(${clampedDeltaX}px)`);

  const now = performance.now();
  const elapsedMs = now - _dragState.lastT;
  if (elapsedMs > 0) {
    // Positive = motion toward commit (leftward).
    _dragState.velocity = (_dragState.lastX - event.clientX) / elapsedMs;
  }
  _dragState.lastX = event.clientX;
  _dragState.lastT = now;
}

/**
 * Release listeners and pointer capture bound during `_beginDrag`. Shared by
 * `_endDrag` and `_cancelDrag` so both teardown paths stay in sync.
 */
function _teardownDragListeners(state: SwipeDragState): void {
  if (typeof state.target.releasePointerCapture === "function") {
    try {
      state.target.releasePointerCapture(state.pointerId);
    } catch {
      // Capture may already be released (cancel/lostpointercapture).
    }
  }
  state.target.removeEventListener("pointermove", _onDragMove);
  state.target.removeEventListener("pointerup", _endDrag);
  state.target.removeEventListener("pointercancel", _cancelDrag);
}

/**
 * Release handler (pointerup): a non-moved release is a tap (native click
 * drives card selection normally). A moved release decides commit-or-snap-back
 * via the pure threshold math, and on commit opens the existing confirm-delete
 * modal exactly as `.urlBtnDelete` would.
 */
function _endDrag(event: PointerEvent): void {
  if (_dragState === null) return;
  // Ignore a stray second pointer if capture silently failed (try/catch).
  if (event.pointerId !== _dragState.pointerId) return;
  const state = _dragState;

  _teardownDragListeners(state);

  if (!state.moved) {
    _dragState = null;
    return;
  }

  const { startX, lastX, revealWidth, velocity, urlRow, utubUrlID, utubID } =
    state;
  const deltaX = lastX - startX;
  const draggedFraction = Math.abs(deltaX) / revealWidth;
  const commit = shouldCommitSwipeGesture({ draggedFraction, velocity });

  // Null BEFORE routing so a re-entrant force-close/reset never operates on
  // stale state, mirroring sheet.ts's _endDrag.
  _dragState = null;

  if (!commit) {
    urlRow.removeClass(SWIPE_DRAGGING_CLASS);
    urlRow.find(URL_ROW_CONTENT_SELECTOR).css("transform", "");
    return;
  }

  _suppressSwipeClick = true;
  urlRow.addClass(SWIPE_COMMITTED_CLASS).removeClass(SWIPE_DRAGGING_CLASS);
  // The class-driven committed transform would otherwise be masked by the
  // higher-specificity inline style _onDragMove just set.
  urlRow.find(URL_ROW_CONTENT_SELECTOR).css("transform", "");

  // Self-removing: fires on cancel, dismiss, success, and the stale-404
  // auto-delete path alike, since every modal-close route in delete.ts goes
  // through Bootstrap's native .modal("hide") transition.
  $(CONFIRM_MODAL_SELECTOR)
    .off(CONFIRM_MODAL_HIDDEN_NAMESPACE)
    .one(CONFIRM_MODAL_HIDDEN_NAMESPACE, () => {
      urlRow.removeClass(`${SWIPE_COMMITTED_CLASS} ${SWIPE_DRAGGING_CLASS}`);
      urlRow.find(URL_ROW_CONTENT_SELECTOR).css("transform", "");
      urlRow.trigger("focus");
    });

  // Focus the row before the modal opens so it already has focus (WCAG 2.4.3).
  urlRow.trigger("focus");
  deleteURLShowModal(utubUrlID, urlRow, utubID);
}

/**
 * Cancel handler (pointercancel): instantly reset the row with no transition
 * and null drag state. Guarded so it is safe to call redundantly after
 * `_endDrag` already nulled state, matching sheet.ts's `_cancelDrag`.
 */
function _cancelDrag(event: PointerEvent): void {
  if (_dragState === null) return;
  if (event.pointerId !== _dragState.pointerId) return;
  const state = _dragState;

  _teardownDragListeners(state);

  // Clear the inline transform while swipe-dragging (transition: none) is
  // still applied, so the reset is instant rather than animated by
  // .urlRowContent's 0.3s transition — then remove the state classes.
  state.urlRow.find(URL_ROW_CONTENT_SELECTOR).css("transform", "");
  state.urlRow.removeClass(`${SWIPE_DRAGGING_CLASS} ${SWIPE_COMMITTED_CLASS}`);

  _dragState = null;
}

/**
 * Bind the swipe gesture to a single `.urlRow`. Idempotent via
 * `SWIPE_GESTURE_BOUND_ATTR` (defensive re-render safety even though each
 * `.urlRow` is normally a fresh DOM node). Only `pointerdown` is bound here;
 * `pointermove`/`pointerup`/`pointercancel` are added/removed dynamically per
 * drag in `_beginDrag`/`_endDrag`/`_cancelDrag`.
 */
export function bindURLRowSwipeGesture({
  urlRow,
  utubUrlID,
  utubID,
}: {
  urlRow: JQuery;
  utubUrlID: number;
  utubID: number;
}): void {
  const rowElement = urlRow[0];
  if (!rowElement || rowElement.hasAttribute(SWIPE_GESTURE_BOUND_ATTR)) return;
  rowElement.setAttribute(SWIPE_GESTURE_BOUND_ATTR, "true");

  rowElement.addEventListener("pointerdown", (event: PointerEvent) => {
    _beginDrag({ event, urlRow, utubUrlID, utubID });
  });
}

/**
 * One-time onboarding nudge: auto-peek `.urlRowContent` a few px so a mobile
 * user discovers the swipe affordance without swiping first. Must be called
 * from the DOM-attachment call site (deck.ts/create.ts) after a
 * `createURLBlock()`-returned row is appended to the document — never from
 * `bindURLRowSwipeGesture` itself, which runs before attachment and would
 * measure a detached/zero-sized row.
 *
 * Gates, in order: mobile + coarse pointer, the session flag not already set,
 * the row actually has a reveal panel (canDelete was true), and the row is
 * within the viewport at attachment time. The flag is set immediately once all
 * gates pass, regardless of whether the peek animation itself ran, so a fast
 * reload within the same session never re-triggers it.
 */
export function triggerURLSwipeNudgeIfEligible({
  urlRow,
}: {
  urlRow: JQuery;
}): void {
  if (!isMobile() || !isCoarsePointer()) return;

  let alreadyShown = false;
  try {
    alreadyShown = sessionStorage.getItem(NUDGE_SESSION_STORAGE_KEY) !== null;
  } catch {
    // Storage may be unavailable (e.g. private browsing); best-effort only.
  }
  if (alreadyShown) return;

  if (urlRow.find(URL_ROW_SWIPE_REVEAL_SELECTOR).length === 0) return;

  const rowElement = urlRow[0];
  if (!rowElement) return;
  if (rowElement.getBoundingClientRect().top >= window.innerHeight) return;

  const reducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)",
  ).matches;
  if (!reducedMotion) {
    const content = urlRow.find(URL_ROW_CONTENT_SELECTOR);
    content.css("transform", `translateX(-${NUDGE_PEEK_PX}px)`);
    setTimeout(() => {
      content.css("transform", "");
    }, NUDGE_PEEK_DURATION_MS);
  }

  try {
    sessionStorage.setItem(NUDGE_SESSION_STORAGE_KEY, "true");
  } catch {
    // Best-effort; a failed write just means the nudge may repeat next load.
  }
}

/**
 * Test-only helper: clear in-flight drag state and suppression so an
 * interrupted-drag test never leaks state into the next test (mirrors
 * `_resetTagSheetGestureForTests`).
 */
export function _resetURLSwipeGestureForTests(): void {
  _dragState = null;
  _suppressSwipeClick = false;
}
