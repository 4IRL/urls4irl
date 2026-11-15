/**
 * Blocked-control behavior shared by every permission-gated control.
 *
 * A blocked control stays visible and focusable, is `aria-disabled`, never runs
 * its action, and explains why: a tooltip for mouse and keyboard users, and a
 * lock glyph plus a tap note for touch users. Every blocked control also owns an
 * empty `.disabledReasonNote[role="status"]` live region (any pointer type) so a
 * refusal can be announced in place while the Tag sheet makes the URL deck inert.
 */

import { isCoarsePointer } from "../home/mobile.js";

const NOTE_CLASS = "disabledReasonNote";
const TOOLTIP_CLASS = "disabledReasonTooltip";
const LOCK_CLASS = "disabledReasonLock";
const CONTROL_CLASS = "disabledReasonControl";
const TOOLTIP_VISIBLE_CLASS = "disabledReasonTooltipVisible";
const NOTE_CLEAR_MS = 4000;
const FINE_POINTER_QUERY = "(any-pointer: fine)";

interface BlockedState {
  reason: string;
  originalAriaDisabled: string | null;
  originalAriaDescribedBy: string | null;
  note: HTMLElement;
  tooltip: HTMLElement | null;
  lock: HTMLElement | null;
  teardown: Array<() => void>;
}

const blocked = new WeakMap<HTMLElement, BlockedState>();
let tooltipCounter = 0;

// The single note currently holding text (single-note rule) and its clear timer.
let activeNote: HTMLElement | null = null;
let activeNoteTimer: ReturnType<typeof setTimeout> | null = null;

function clearActiveNote(): void {
  if (activeNoteTimer !== null) clearTimeout(activeNoteTimer);
  activeNoteTimer = null;
  if (activeNote !== null) activeNote.textContent = "";
  activeNote = null;
}

function writeNote({ note, text }: { note: HTMLElement; text: string }): void {
  clearActiveNote();
  note.textContent = text;
  activeNote = note;
  activeNoteTimer = setTimeout(clearActiveNote, NOTE_CLEAR_MS);
}

function addListener({
  state,
  target,
  type,
  handler,
  capture = false,
}: {
  state: BlockedState;
  target: EventTarget;
  type: string;
  handler: EventListener;
  capture?: boolean;
}): void {
  target.addEventListener(type, handler, capture);
  state.teardown.push(() => target.removeEventListener(type, handler, capture));
}

function isFocusVisible(element: HTMLElement): boolean {
  try {
    return element.matches(":focus-visible");
  } catch {
    return true;
  }
}

function positionTooltip({
  element,
  tooltip,
}: {
  element: HTMLElement;
  tooltip: HTMLElement;
}): void {
  const rect = element.getBoundingClientRect();
  tooltip.style.top = `${rect.bottom + 6}px`;
  tooltip.style.left = `${Math.max(rect.left, 8)}px`;
}

function wireTooltip({
  element,
  state,
  reason,
}: {
  element: HTMLElement;
  state: BlockedState;
  reason: string;
}): void {
  tooltipCounter += 1;
  const tooltip = document.createElement("div");
  tooltip.id = `disabledReasonTooltip${tooltipCounter}`;
  tooltip.className = TOOLTIP_CLASS;
  tooltip.setAttribute("role", "tooltip");
  tooltip.textContent = reason;
  element.after(tooltip);
  state.tooltip = tooltip;
  element.setAttribute("aria-describedby", tooltip.id);

  const isVisible = (): boolean =>
    tooltip.classList.contains(TOOLTIP_VISIBLE_CLASS);
  const show = (): void => {
    positionTooltip({ element, tooltip });
    tooltip.classList.add(TOOLTIP_VISIBLE_CLASS);
  };
  const hide = (): void => {
    tooltip.classList.remove(TOOLTIP_VISIBLE_CLASS);
  };

  addListener({ state, target: element, type: "mouseenter", handler: show });
  addListener({ state, target: element, type: "mouseleave", handler: hide });
  addListener({
    state,
    target: element,
    type: "focus",
    handler: () => {
      if (isFocusVisible(element)) show();
    },
  });
  addListener({ state, target: element, type: "blur", handler: hide });
  // Never stops the event: a combobox, modal or popover that owns Escape must
  // still receive it. Hides only while visible.
  addListener({
    state,
    target: document,
    type: "keydown",
    handler: (event) => {
      if ((event as KeyboardEvent).key === "Escape" && isVisible()) hide();
    },
  });
}

function wireTouchSurface({
  element,
  state,
}: {
  element: HTMLElement;
  state: BlockedState;
}): void {
  const lock = document.createElement("span");
  lock.className = LOCK_CLASS;
  lock.setAttribute("aria-hidden", "true");
  element.prepend(lock);
  state.lock = lock;

  addListener({
    state,
    target: element,
    type: "click",
    handler: () => {
      writeNote({ note: state.note, text: state.reason });
    },
    capture: true,
  });
  // An outside tap clears the note.
  addListener({
    state,
    target: document,
    type: "pointerdown",
    handler: (event) => {
      if (event.target instanceof Node && element.contains(event.target))
        return;
      if (activeNote === state.note) clearActiveNote();
    },
  });
}

function wireActivationSuppression({
  element,
  state,
}: {
  element: HTMLElement;
  state: BlockedState;
}): void {
  const suppress = (event: Event): void => {
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
  };
  addListener({
    state,
    target: element,
    type: "click",
    handler: suppress,
    capture: true,
  });
  const suppressKey = (event: Event): void => {
    const key = (event as KeyboardEvent).key;
    if (key === "Enter" || key === " ") suppress(event);
  };
  addListener({
    state,
    target: element,
    type: "keydown",
    handler: suppressKey,
    capture: true,
  });
  // A native button fires click on Space keyup.
  addListener({
    state,
    target: element,
    type: "keyup",
    handler: suppressKey,
    capture: true,
  });
}

function clearReason(element: HTMLElement): void {
  const state = blocked.get(element);
  if (state === undefined) return;
  state.teardown.forEach((undo) => undo());
  if (activeNote === state.note) clearActiveNote();
  state.note.remove();
  state.tooltip?.remove();
  state.lock?.remove();
  element.classList.remove(CONTROL_CLASS);
  if (state.originalAriaDisabled === null)
    element.removeAttribute("aria-disabled");
  else element.setAttribute("aria-disabled", state.originalAriaDisabled);
  if (state.originalAriaDescribedBy === null)
    element.removeAttribute("aria-describedby");
  else element.setAttribute("aria-describedby", state.originalAriaDescribedBy);
  blocked.delete(element);
}

function applyReason({
  element,
  reason,
}: {
  element: HTMLElement;
  reason: string;
}): void {
  const existing = blocked.get(element);
  if (existing !== undefined) {
    if (existing.reason === reason) {
      // Idempotent, but re-assert in case another writer cleared the attribute.
      element.setAttribute("aria-disabled", "true");
      return;
    }
    clearReason(element);
  }

  const note = document.createElement("div");
  note.className = NOTE_CLASS;
  note.setAttribute("role", "status");
  const state: BlockedState = {
    reason,
    originalAriaDisabled: element.getAttribute("aria-disabled"),
    originalAriaDescribedBy: element.getAttribute("aria-describedby"),
    note,
    tooltip: null,
    lock: null,
    teardown: [],
  };
  blocked.set(element, state);

  element.classList.add(CONTROL_CLASS);
  element.setAttribute("aria-disabled", "true");
  element.after(note);

  // Touch listener first: the suppression handler stops immediate propagation.
  const coarse = isCoarsePointer();
  if (coarse) wireTouchSurface({ element, state });
  wireActivationSuppression({ element, state });
  if (!coarse || window.matchMedia(FINE_POINTER_QUERY).matches) {
    wireTooltip({ element, state, reason });
  }
}

/**
 * Makes `element` look and act blocked while explaining why, or restores it.
 *
 * @param element - The control to block.
 * @param reason - The explanation, or null to remove every trace of the block.
 */
export function setDisabledReason({
  element,
  reason,
}: {
  element: HTMLElement;
  reason: string | null;
}): void {
  if (reason === null) clearReason(element);
  else applyReason({ element, reason });
}

/**
 * Shows `reason` in the blocked control's note region, replacing any other note
 * and clearing after 4s. A no-op when the element has no reason applied.
 */
export function showDisabledReasonNote({
  element,
  reason,
}: {
  element: HTMLElement;
  reason: string;
}): void {
  const state = blocked.get(element);
  if (state === undefined) return;
  writeNote({ note: state.note, text: reason });
}
