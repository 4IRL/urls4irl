import { debug } from "../../lib/debug.js";
import {
  clamp,
  resolveExpandableSheetRelease,
} from "../../logic/tag-sheet-snap.js";
import { isTagSheetSelfBackPending } from "../tags/sheet.js";

// The mobile bottom-sheet chrome for the panel settings shell: backdrop, sheet,
// inert background and drag-to-dismiss. It knows nothing about sections; the
// shell (popover.ts) renders into the body this module returns and registers
// the close handler every user-initiated close routes through. This module
// never imports popover.ts.

const log = debug("panel-settings");

export type CloseKind = "user" | "popstate" | "forced";

const ROOT_SELECTOR = "#panelSettingsRoot";
const SHEET_SELECTOR = "#panelSettingsSheet";
const BACKDROP_SELECTOR = "#panelSettingsBackdrop";
const TITLE_SELECTOR = "#panelSettingsSheetTitle";
const BODY_SELECTOR = "#panelSettingsSheetBody";
const CLOSE_SELECTOR = "#panelSettingsSheetClose";
const GRABBER_SELECTOR = "#panelSettingsSheetGrabber";
const HEADER_SELECTOR = "#panelSettingsSheetHeader";
const INTERACTIVE_SELECTOR = "button, a, input, select, textarea";

const HIDDEN_CLASS = "hidden";
const ROOT_SHEET_CLASS = "panelSettingsRoot--sheet";
const SHEET_OPEN_CLASS = "panelSettingsSheet--open";
const SHEET_DRAGGING_CLASS = "panelSettingsSheet--dragging";
const SHEET_EXPANDED_CLASS = "panelSettingsSheet--expanded";
const BACKDROP_SHOW_CLASS = "panelSettingsBackdrop--show";
const BOUND_ATTRIBUTE = "data-sheet-bound";
const INERT_ATTRIBUTE = "inert";
const NON_INERT_TAGS: ReadonlySet<string> = new Set([
  "SCRIPT",
  "STYLE",
  "TEMPLATE",
]);
const SETTINGS_HISTORY_KEY = "panelSettingsSheetOpen";
export const SELF_BACK_TIMEOUT_MS = 1500;
// Movement below this is a tap, not a drag.
export const TAP_SLOP_PX = 6;
// The expanded detent's height as a fraction of the viewport (mirrors the
// 95dvh of .panelSettingsSheet--expanded).
export const EXPANDED_HEIGHT_FRACTION = 0.95;
// Fallback to drop the settle's inline height when no transition runs
// (reduced motion); a little over the 0.3s CSS transition.
export const SETTLE_MS = 350;

interface InertRecord {
  element: Element;
  wasInert: boolean;
}

interface DragState {
  pointerId: number;
  target: HTMLElement;
  startY: number;
  lastY: number;
  lastTime: number;
  velocity: number;
  // Sheet height at the press, and the two detent heights the drag moves between.
  startHeight: number;
  defaultHeight: number;
  expandedHeight: number;
  expandedAtStart: boolean;
  moved: boolean;
}

type CloseHandler = (kind: CloseKind) => void;

let _closeHandler: CloseHandler | null = null;
let _inertRecords: InertRecord[] = [];
let _drag: DragState | null = null;
let _baseState: unknown = null;
let _selfClosingViaBack = false;
let _selfBackTimer: ReturnType<typeof setTimeout> | null = null;
// Snap state: reset to the default detent every time the sheet opens.
let _expanded = false;
let _defaultHeight = 0;
let _settleTimer: ReturnType<typeof setTimeout> | null = null;

function currentHistoryState(): Record<string, unknown> | null {
  const state: unknown = history.state;
  return typeof state === "object" && state !== null
    ? (state as Record<string, unknown>)
    : null;
}

function clearSelfBackFlag(): void {
  _selfClosingViaBack = false;
  if (_selfBackTimer !== null) clearTimeout(_selfBackTimer);
  _selfBackTimer = null;
}

// A back() that never produces a popstate must not wedge the sheet.
function startSelfBackTimer(): void {
  if (_selfBackTimer !== null) clearTimeout(_selfBackTimer);
  _selfBackTimer = setTimeout(() => {
    _selfBackTimer = null;
    _selfClosingViaBack = false;
  }, SELF_BACK_TIMEOUT_MS);
}

// ---------------------------------------------------------------- elements

function sheetElement(): HTMLElement | null {
  return document.querySelector<HTMLElement>(SHEET_SELECTOR);
}

function backdropElement(): HTMLElement | null {
  return document.querySelector<HTMLElement>(BACKDROP_SELECTOR);
}

function rootElement(): HTMLElement | null {
  return document.querySelector<HTMLElement>(ROOT_SELECTOR);
}

// ------------------------------------------------------------------- inert

function applyInert(): void {
  const root = rootElement();
  if (_inertRecords.length > 0) return;
  for (const child of Array.from(document.body.children)) {
    if (child === root || NON_INERT_TAGS.has(child.tagName)) continue;
    _inertRecords.push({
      element: child,
      wasInert: child.hasAttribute(INERT_ATTRIBUTE),
    });
    child.setAttribute(INERT_ATTRIBUTE, "");
  }
}

// Reverse order of application: restores exactly each element's prior state.
function restoreInert(): void {
  for (const record of _inertRecords.reverse()) {
    if (record.wasInert) {
      record.element.setAttribute(INERT_ATTRIBUTE, "");
    } else {
      record.element.removeAttribute(INERT_ATTRIBUTE);
    }
  }
  _inertRecords = [];
}

// -------------------------------------------------------------------- drag

function endDragListeners(): void {
  const state = _drag;
  if (state === null) return;
  state.target.removeEventListener("pointermove", onDragMove);
  state.target.removeEventListener("pointerup", onDragEnd);
  state.target.removeEventListener("pointercancel", onDragEnd);
  try {
    if (state.target.hasPointerCapture?.(state.pointerId)) {
      state.target.releasePointerCapture(state.pointerId);
    }
  } catch {
    // Capture may already be released.
  }
  _drag = null;
}

/** Drops the inline height a drag/settle set, so the CSS state governs again. */
function finishSettle(): void {
  if (_settleTimer !== null) clearTimeout(_settleTimer);
  _settleTimer = null;
  const sheet = sheetElement();
  if (sheet === null) return;
  sheet.style.removeProperty("height");
  sheet.style.removeProperty("max-height");
}

function clearDragVisuals(): void {
  finishSettle();
  const sheet = sheetElement();
  if (sheet === null) return;
  sheet.classList.remove(SHEET_DRAGGING_CLASS);
  sheet.style.removeProperty("transform");
}

function resetExpansion(): void {
  _expanded = false;
  sheetElement()?.classList.remove(SHEET_EXPANDED_CLASS);
}

/**
 * Animates the sheet from its dragged pose to a detent: the inline height
 * transitions to the detent's pixel height, then the CSS state takes over.
 */
function settleTo({
  detent,
  defaultHeight,
  expandedHeight,
}: {
  detent: "default" | "expanded";
  defaultHeight: number;
  expandedHeight: number;
}): void {
  const sheet = sheetElement();
  if (sheet === null) return;
  _expanded = detent === "expanded";
  sheet.classList.toggle(SHEET_EXPANDED_CLASS, _expanded);
  sheet.classList.remove(SHEET_DRAGGING_CLASS);
  sheet.style.setProperty("max-height", "none");
  sheet.style.setProperty(
    "height",
    `${_expanded ? expandedHeight : defaultHeight}px`,
  );
  sheet.style.removeProperty("transform");
  if (_settleTimer !== null) clearTimeout(_settleTimer);
  _settleTimer = setTimeout(finishSettle, SETTLE_MS);
}

/** Null-guarded teardown run by every close path and by the reset. */
function teardownDrag(): void {
  endDragListeners();
  clearDragVisuals();
  resetExpansion();
}

function onDragStart(event: PointerEvent): void {
  if (event.pointerType === "mouse") return;
  if (_drag !== null || !isSettingsSheetOpen()) return;
  const target = event.currentTarget;
  if (!(target instanceof HTMLElement)) return;
  // The close button (or any interactive header child) is a tap, not a drag
  // start: capturing the pointer here would swallow its click.
  if (
    event.target instanceof Element &&
    event.target.closest(INTERACTIVE_SELECTOR) !== null
  ) {
    return;
  }
  const sheet = sheetElement();
  if (sheet === null) return;
  // A press mid-settle takes over from the CSS state, not the inline pose.
  finishSettle();
  const height = sheet.getBoundingClientRect().height;
  if (height <= 0) return;
  // The content-sized height is only measurable from the default detent.
  if (!_expanded || _defaultHeight <= 0) _defaultHeight = height;
  const expandedHeight = Math.max(
    window.innerHeight * EXPANDED_HEIGHT_FRACTION,
    _defaultHeight,
  );

  _drag = {
    pointerId: event.pointerId,
    target,
    startY: event.clientY,
    lastY: event.clientY,
    lastTime: performance.now(),
    velocity: 0,
    startHeight: height,
    defaultHeight: _defaultHeight,
    expandedHeight,
    expandedAtStart: _expanded,
    moved: false,
  };
  if (typeof target.setPointerCapture === "function") {
    try {
      target.setPointerCapture(event.pointerId);
    } catch {
      // Capture is best effort; listeners on the target still receive events.
    }
  }
  target.addEventListener("pointermove", onDragMove);
  target.addEventListener("pointerup", onDragEnd);
  target.addEventListener("pointercancel", onDragEnd);
}

function onDragMove(event: PointerEvent): void {
  const state = _drag;
  const sheet = sheetElement();
  if (state === null || sheet === null) return;
  if (event.pointerId !== state.pointerId) return;
  const delta = event.clientY - state.startY;
  if (!state.moved && Math.abs(delta) < TAP_SLOP_PX) return;
  state.moved = true;

  const now = performance.now();
  const elapsed = now - state.lastTime;
  if (elapsed > 0) {
    state.velocity = (event.clientY - state.lastY) / elapsed;
  }
  state.lastY = event.clientY;
  state.lastTime = now;

  sheet.classList.add(SHEET_DRAGGING_CLASS);
  // Dragging up grows the sheet between the detents; dragging below the default
  // detent slides the whole sheet down (toward dismissal).
  const wanted = state.startHeight - delta;
  const height = clamp({
    value: wanted,
    min: state.defaultHeight,
    max: state.expandedHeight,
  });
  const offset = clamp({
    value: state.defaultHeight - wanted,
    min: 0,
    max: state.defaultHeight,
  });
  sheet.style.setProperty("max-height", "none");
  sheet.style.setProperty("height", `${height}px`);
  sheet.style.transform = `translateY(${offset}px)`;
}

function onDragEnd(event: PointerEvent): void {
  const state = _drag;
  if (state === null || event.pointerId !== state.pointerId) return;
  const { moved, velocity, startY, defaultHeight, expandedHeight } = state;
  const delta = event.clientY - startY;
  endDragListeners();

  if (!moved) {
    clearDragVisuals();
    return;
  }
  if (event.type === "pointercancel") {
    settleTo({
      detent: state.expandedAtStart ? "expanded" : "default",
      defaultHeight,
      expandedHeight,
    });
    return;
  }
  const outcome = resolveExpandableSheetRelease({
    expanded: state.expandedAtStart,
    delta,
    velocity,
    defaultHeight,
    expandedHeight,
  });
  if (outcome === "dismiss") {
    // The close hides the sheet at the dragged offset first, then clears the
    // inline transform (see closeSettingsSheet), so it never flashes open.
    requestUserClose();
    return;
  }
  settleTo({ detent: outcome, defaultHeight, expandedHeight });
}

// ---------------------------------------------------------------- closing

function requestUserClose(): void {
  // Fail closed: without the shell's handler a close would hide the sheet but
  // leave the shell's state (current panel, aria-expanded, queue) stale.
  if (_closeHandler === null) {
    log("user close ignored: no close handler registered");
    return;
  }
  _closeHandler("user");
}

function bindListeners(sheet: HTMLElement): void {
  if (sheet.hasAttribute(BOUND_ATTRIBUTE)) return;
  sheet.setAttribute(BOUND_ATTRIBUTE, "true");

  backdropElement()?.addEventListener("click", requestUserClose);
  sheet
    .querySelector<HTMLElement>(CLOSE_SELECTOR)
    ?.addEventListener("click", requestUserClose);
  for (const selector of [GRABBER_SELECTOR, HEADER_SELECTOR]) {
    sheet
      .querySelector<HTMLElement>(selector)
      ?.addEventListener("pointerdown", onDragStart);
  }
}

// -------------------------------------------------------------- public API

/**
 * Registers the shell's close function, the single entry used by the close
 * button, the backdrop and a committed drag. Also binds the sheet listeners
 * once (idempotent per sheet element).
 */
export function registerSettingsSheetCloseHandler(
  handler: (kind: CloseKind) => void,
): void {
  const sheet = sheetElement();
  if (sheet !== null) bindListeners(sheet);
  _closeHandler = handler;
}

export function isSettingsSheetOpen(): boolean {
  const sheet = sheetElement();
  return sheet !== null && !sheet.classList.contains(HIDDEN_CLASS);
}

/** Shows the backdrop and sheet, inerts the page and returns the body to fill. */
export function openSettingsSheet({ title }: { title: string }): HTMLElement {
  const sheet = sheetElement();
  const body = sheet?.querySelector<HTMLElement>(BODY_SELECTOR) ?? null;
  if (sheet === null || body === null) {
    throw new Error("panel settings sheet markup is missing");
  }
  bindListeners(sheet);
  teardownDrag();

  const titleElement = sheet.querySelector<HTMLElement>(TITLE_SELECTOR);
  if (titleElement) titleElement.textContent = title;

  _baseState = history.state;
  history.pushState(
    { ...currentHistoryState(), [SETTINGS_HISTORY_KEY]: true },
    "",
    location.href,
  );

  applyInert();
  rootElement()?.classList.add(ROOT_SHEET_CLASS);

  const backdrop = backdropElement();
  backdrop?.classList.remove(HIDDEN_CLASS);
  sheet.classList.remove(HIDDEN_CLASS);
  // Commit the resting (off-screen) styles so the next class change transitions.
  void sheet.offsetHeight;
  backdrop?.classList.add(BACKDROP_SHOW_CLASS);
  sheet.classList.add(SHEET_OPEN_CLASS);
  return body;
}

/**
 * Hides the surface. The sheet hides instantly (no exit animation): the inline
 * drag transform and dragging class are cleared only after it is hidden, so a
 * dismissed drag never flashes back to its open position.
 */
function hideSurface(): void {
  const sheet = sheetElement();
  if (sheet !== null) {
    sheet.classList.remove(SHEET_OPEN_CLASS);
    sheet.classList.add(HIDDEN_CLASS);
  }
  const backdrop = backdropElement();
  backdrop?.classList.remove(BACKDROP_SHOW_CLASS);
  backdrop?.classList.add(HIDDEN_CLASS);
  teardownDrag();
  restoreInert();
  rootElement()?.classList.remove(ROOT_SHEET_CLASS);
}

function hasSettingsKey(): boolean {
  return currentHistoryState()?.[SETTINGS_HISTORY_KEY] === true;
}

/**
 * Removes the settings marker from the current entry in place (no popstate, no
 * flag, never back()). A no-op when the keyed entry is no longer current.
 */
function stripSettingsKey(): void {
  const state = currentHistoryState();
  if (state === null || state[SETTINGS_HISTORY_KEY] !== true) return;
  const rest = { ...state };
  delete rest[SETTINGS_HISTORY_KEY];
  history.replaceState(
    Object.keys(rest).length > 0 ? rest : null,
    "",
    location.href,
  );
}

/**
 * Reverses openSettingsSheet and owns the per-kind history operation.
 * "user" consumes the pushed entry with back() (flag set first); "forced"
 * strips the marker in place; "popstate" does nothing (the browser already
 * moved).
 */
export function closeSettingsSheet({ kind }: { kind: CloseKind }): void {
  log("close settings sheet", { kind });
  hideSurface();
  _baseState = null;
  if (kind === "popstate") return;
  if (kind === "user" && hasSettingsKey()) {
    _selfClosingViaBack = true;
    startSelfBackTimer();
    history.back();
    return;
  }
  stripSettingsKey();
}

/** Full teardown (re-init and tests only): also drops the registered handler. */
export function resetSettingsSheet(): void {
  const wasOpen = isSettingsSheetOpen();
  hideSurface();
  clearSelfBackFlag();
  _baseState = null;
  if (wasOpen) stripSettingsKey();
  _closeHandler = null;
}

/** Consume-once: true when this popstate is the settings sheet's own back(). */
export function consumePanelSettingsSheetSelfBackClose(): boolean {
  if (!_selfClosingViaBack) return false;
  clearSelfBackFlag();
  return true;
}

/**
 * True while a settings user-close back() is pending, or while the Tag sheet's
 * own back() is in flight (explicit signal from tags/sheet.ts). The shell drops
 * a gear-open while this reads true; neither flag is cleared here.
 */
export function isPanelSettingsSheetSelfBackPending(): boolean {
  return _selfClosingViaBack || isTagSheetSelfBackPending();
}

/** Closes the sheet for a browser Back/Forward through the shell's handler. */
export function closeSettingsSheetFromPopstate(): void {
  if (_closeHandler !== null) {
    _closeHandler("popstate");
    return;
  }
  closeSettingsSheet({ kind: "popstate" });
}

/** The history state captured when the sheet opened (null when closed). */
export function getSettingsSheetBaseState(): unknown {
  return _baseState;
}
