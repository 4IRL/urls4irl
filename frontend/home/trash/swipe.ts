/**
 * Right-swipe-to-restore gesture for armed `.trashRow` URL rows (mobile/touch
 * only). A sibling of `urls/cards/swipe.ts` (swipe-left-to-delete), which it
 * deliberately does not parametrize: same single-drag-state structure, same
 * `logic/url-swipe-snap.ts` thresholds, same `swipe-dragging` / `swipe-committed`
 * class contract, but rightward motion and `restoreTrashedURL` as the commit.
 *
 * Arming is decided at render time (`render.ts` adds `.trashRowSwipeable` only to
 * rows whose in-place Restore would succeed), so an unarmed row never begins a
 * drag. This module never imports `panel.ts`: `closeTrash()` reaches it through
 * the `TRASH_CLOSED` bus event.
 */
import { on, AppEvents } from "../../lib/event-bus.js";
import { clamp, shouldCommitSwipeGesture } from "../../logic/url-swipe-snap.js";
import { isMobile } from "../mobile.js";
import { restoreTrashedURL } from "./actions.js";
import {
  armTrashClickSuppression,
  clearTrashClickSuppression,
} from "./swipe-click-guard.js";

const SWIPEABLE_ROW_SELECTOR = ".trashRow.trashRowSwipeable";
// A press inside any of these is a button/chip/picker interaction, not a swipe.
const SWIPE_IGNORE_SELECTOR = [
  ".trashBtnRestore",
  ".trashBtnPurge",
  ".chip",
  ".trashDestinationPicker",
].join(", ");
const RESTORE_BUTTON_SELECTOR = ".trashBtnRestore";
const PICKER_SELECTOR = ".trashDestinationPicker";
const CONTENT_SELECTOR = ".trashRowContent";
const REVEAL_SELECTOR = ".trashRowSwipeReveal";
const REVEAL_WIDTH_VAR = "--trash-swipe-reveal-width";
const TRASH_PANEL_SELECTOR = "#TrashPanel";
const SWIPE_DRAGGING_CLASS = "swipe-dragging";
const SWIPE_COMMITTED_CLASS = "swipe-committed";
// Yield to the OS back-swipe: a press this close to the left edge never drags.
const LEFT_EDGE_GUARD_PX = 16;
// Movement (px) below which a press-release is a tap, not a drag.
const TAP_SLOP_PX = 8;
// A drag is vertical/ambiguous (native scroll wins) once the vertical component
// is at least this fraction of the horizontal one.
const VERTICAL_LOCK_RATIO = 1.5;

interface TrashSwipeDragState {
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
  row: JQuery;
  utubID: number;
  utubUrlID: number;
}

// Null between gestures; only one row can be mid-drag at a time.
let _dragState: TrashSwipeDragState | null = null;
let _swipeInitialized = false;
let _unsubscribers: Array<() => void> = [];

function _resetRowVisuals({ row }: { row: JQuery }): void {
  row.removeClass(`${SWIPE_DRAGGING_CLASS} ${SWIPE_COMMITTED_CLASS}`);
  row.find(CONTENT_SELECTOR).css("transform", "");
}

function _teardownDragListeners(state: TrashSwipeDragState): void {
  state.target.removeEventListener("pointermove", _onDragMove);
  state.target.removeEventListener("pointerup", _endDrag);
  state.target.removeEventListener("pointercancel", _cancelDrag);
  state.target.removeEventListener("lostpointercapture", _onLostCapture);
  if (typeof state.target.releasePointerCapture === "function") {
    try {
      state.target.releasePointerCapture(state.pointerId);
    } catch {
      // Capture may already be gone (cancel / lostpointercapture / detached row).
    }
  }
}

/** Drops every trace of a live drag: listeners, classes, inline transform. */
function _clearDragState(state: TrashSwipeDragState): void {
  _teardownDragListeners(state);
  // swipe-dragging (transition: none) is still applied while the inline
  // transform is cleared, so the reset is instant rather than animated.
  _resetRowVisuals({ row: state.row });
  _dragState = null;
}

function _isBusy({ row }: { row: JQuery }): boolean {
  return row.find(RESTORE_BUTTON_SELECTOR).attr("aria-disabled") === "true";
}

function _beginDrag(event: PointerEvent): void {
  // A drag whose row was detached never sees its pointerup (the listeners live
  // on the detached row), so drop it here instead of blocking every later swipe.
  if (_dragState !== null && !_dragState.target.isConnected) {
    _clearDragState(_dragState);
  }
  // A second pointer while a drag is live would orphan the first one's listeners.
  if (_dragState !== null) return;
  if (event.button !== 0) return;
  if (!isMobile() || event.pointerType === "mouse") return;
  if (event.clientX < LEFT_EDGE_GUARD_PX) return;

  const eventTarget = event.target as HTMLElement | null;
  const rowElement = eventTarget?.closest<HTMLElement>(SWIPEABLE_ROW_SELECTOR);
  if (!rowElement) return;
  if (eventTarget?.closest(SWIPE_IGNORE_SELECTOR)) return;

  const row = $(rowElement);
  if (_isBusy({ row })) return;
  if (row.find(PICKER_SELECTOR).length > 0) return;

  const utubID = Number(rowElement.getAttribute("data-utub-id"));
  const utubUrlID = Number(rowElement.getAttribute("data-utub-url-id"));
  if (!Number.isFinite(utubID) || !Number.isFinite(utubUrlID)) return;

  const revealWidth = row
    .find(REVEAL_SELECTOR)[0]
    ?.getBoundingClientRect().width;
  // A non-positive width (row not laid out) would make the fraction/velocity
  // math degenerate: treat the press as a tap.
  if (!revealWidth || revealWidth <= 0) return;

  row.css(REVEAL_WIDTH_VAR, `${revealWidth}px`);

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
    target: rowElement,
    row,
    utubID,
    utubUrlID,
  };

  if (typeof rowElement.setPointerCapture === "function") {
    try {
      rowElement.setPointerCapture(event.pointerId);
    } catch {
      // Pointer capture is best-effort; absence is non-fatal.
    }
  }
  rowElement.addEventListener("pointermove", _onDragMove);
  rowElement.addEventListener("pointerup", _endDrag);
  rowElement.addEventListener("pointercancel", _cancelDrag);
  rowElement.addEventListener("lostpointercapture", _onLostCapture);
}

function _onDragMove(event: PointerEvent): void {
  if (_dragState === null) return;
  if (event.pointerId !== _dragState.pointerId) return;
  // A row removed mid-drag (list reload, restore elsewhere) ends the gesture.
  if (!_dragState.target.isConnected) {
    _clearDragState(_dragState);
    return;
  }
  if (_dragState.verticalLocked) return;

  const deltaX = event.clientX - _dragState.startX;
  const deltaY = event.clientY - _dragState.startY;

  if (!_dragState.moved) {
    if (Math.abs(deltaX) <= TAP_SLOP_PX) return;
    if (Math.abs(deltaX) <= VERTICAL_LOCK_RATIO * Math.abs(deltaY)) {
      _dragState.verticalLocked = true;
      return;
    }
    _dragState.moved = true;
    _dragState.row.addClass(SWIPE_DRAGGING_CLASS);
  }

  event.preventDefault();
  const clampedDeltaX = clamp({
    value: deltaX,
    min: 0,
    max: _dragState.revealWidth,
  });
  _dragState.row
    .find(CONTENT_SELECTOR)
    .css("transform", `translateX(${clampedDeltaX}px)`);

  const now = performance.now();
  const elapsedMs = now - _dragState.lastT;
  if (elapsedMs > 0) {
    // Positive = motion toward commit (rightward).
    _dragState.velocity = (event.clientX - _dragState.lastX) / elapsedMs;
  }
  _dragState.lastX = event.clientX;
  _dragState.lastT = now;
}

function _endDrag(event: PointerEvent): void {
  if (_dragState === null) return;
  if (event.pointerId !== _dragState.pointerId) return;
  const state = _dragState;

  if (!state.target.isConnected) {
    _clearDragState(state);
    return;
  }

  _teardownDragListeners(state);

  if (!state.moved) {
    _dragState = null;
    return;
  }

  const { startX, lastX, revealWidth, velocity, row, utubID, utubUrlID } =
    state;
  const deltaX = lastX - startX;
  // Only a rightward drag reveals the restore panel; a net-leftward release must
  // never satisfy the distance threshold.
  const draggedFraction =
    deltaX > 0 ? clamp({ value: deltaX / revealWidth, min: 0, max: 1 }) : 0;
  // A net-leftward release never commits, whatever the last velocity sample was.
  const commit =
    deltaX > 0 && shouldCommitSwipeGesture({ draggedFraction, velocity });

  // Null BEFORE routing so a re-entrant reset never operates on stale state.
  _dragState = null;

  if (!commit) {
    _resetRowVisuals({ row });
    return;
  }

  // The finger lifts over whatever is under it; that click must not also fire
  // Restore / Delete forever.
  armTrashClickSuppression();
  row.addClass(SWIPE_COMMITTED_CLASS).removeClass(SWIPE_DRAGGING_CLASS);
  // The class-driven committed transform would otherwise be masked by the
  // higher-specificity inline style _onDragMove just set.
  row.find(CONTENT_SELECTOR).css("transform", "");

  void restoreTrashedURL({
    utubID,
    utubUrlID,
    destUtubID: undefined,
    viaSwipe: true,
  }).then((restored) => {
    if (restored) return;
    // Every failure leaves the row (or a reloaded replacement) in place; snap
    // back only if this row is still in the document.
    if (!row[0]?.isConnected) return;
    _resetRowVisuals({ row });
  });
}

function _cancelDrag(event: PointerEvent): void {
  if (_dragState === null) return;
  if (event.pointerId !== _dragState.pointerId) return;
  _clearDragState(_dragState);
}

function _onLostCapture(event: PointerEvent): void {
  if (_dragState === null) return;
  if (event.pointerId !== _dragState.pointerId) return;
  _clearDragState(_dragState);
}

/** Tears down a live drag when its context goes away (deck switch, Trash closed). */
export function resetTrashSwipeState(): void {
  if (_dragState === null) return;
  _clearDragState(_dragState);
}

function _onPanelPointerDown(event: PointerEvent): void {
  const target = event.target as HTMLElement | null;
  if (!target?.closest(TRASH_PANEL_SELECTOR)) return;
  // Any new press means the previous swipe's trailing click is long gone.
  clearTrashClickSuppression();
}

function _onPanelKeyDown(event: KeyboardEvent): void {
  const target = event.target as HTMLElement | null;
  if (!target?.closest(TRASH_PANEL_SELECTOR)) return;
  // A keyboard Enter/Space activation must never be swallowed by a stale flag.
  clearTrashClickSuppression();
}

/**
 * Idempotent. Delegates pointerdown from the document so re-rendered rows need
 * no per-row binding; the clearing listeners run in the capture phase so they
 * precede any row handler.
 */
export function initTrashSwipe(): void {
  if (_swipeInitialized) return;
  _swipeInitialized = true;
  document.addEventListener("pointerdown", _onPanelPointerDown, true);
  document.addEventListener("pointerdown", _beginDrag);
  document.addEventListener("keydown", _onPanelKeyDown, true);
  _unsubscribers = [
    on(AppEvents.MOBILE_DECK_SWITCHED, resetTrashSwipeState),
    on(AppEvents.TRASH_CLOSED, resetTrashSwipeState),
  ];
}

/** Test-only: clear drag state, suppression and the init guard between tests. */
export function _resetTrashSwipeForTests(): void {
  if (_dragState !== null) _clearDragState(_dragState);
  _dragState = null;
  clearTrashClickSuppression();
  document.removeEventListener("pointerdown", _onPanelPointerDown, true);
  document.removeEventListener("pointerdown", _beginDrag);
  document.removeEventListener("keydown", _onPanelKeyDown, true);
  _unsubscribers.forEach((unsubscribe) => unsubscribe());
  _unsubscribers = [];
  _swipeInitialized = false;
}
