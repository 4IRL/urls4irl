import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS, TABLET_WIDTH } from "../../lib/constants.js";
import { debug } from "../../lib/debug.js";
import { AppEvents, on } from "../../lib/event-bus.js";
import { hideTooltip } from "../../lib/tooltips.js";
import { getState, subscribe } from "../../store/app-store.js";
import type { AppState } from "../../store/app-store.js";
import type { PanelId } from "../../types/settings.js";
import { closeAllMemberRowMenus } from "../members/row-menu.js";
import { dismissActiveTip, maybeShowNextTip } from "../onboarding/nudges.js";
import { fitUTubHeaderAndSubheader } from "../utubs/header-fit.js";
import { announceSettingsStatus } from "./announce.js";
import { canWriteSection } from "./permissions.js";
import { createSaveQueue } from "./queue.js";
import type { SaveQueue } from "./queue.js";
import { getSections, isKnownPanel } from "./registry.js";
import {
  closeSettingsSheet,
  isPanelSettingsSheetSelfBackPending,
  openSettingsSheet,
  registerSettingsSheetCloseHandler,
  resetSettingsSheet,
} from "./sheet.js";
import type { CloseKind } from "./sheet.js";
import { setPanelSettingsOpen } from "./state.js";
import type {
  PanelSection,
  QueueSink,
  SaveStatus,
  SectionContext,
  SectionPatch,
} from "./types.js";

const log = debug("panel-settings");

const POPOVER_ID = "panelSettingsPopover";
const SHEET_ID = "panelSettingsSheet";
const POPOVER_SELECTOR = `#${POPOVER_ID}`;
const SHEET_SELECTOR = `#${SHEET_ID}`;
const SHEET_CLOSE_SELECTOR = "#panelSettingsSheetClose";
const GEAR_SELECTOR = ".panelSettingsGear";
const KEYDOWN_NAMESPACE = "keydown.panelSettings";
const MODAL_NAMESPACE = "show.bs.modal.panelSettings";
const HIDDEN_CLASS = "hidden";
const VIEWPORT_MARGIN_PX = 8;
const GEAR_GAP_PX = 6;
// How long "Saved" stays in the status slot before it clears.
const SAVED_DWELL_MS = 1500;
// How often a "saving" indicator checks whether the queue has gone idle (the
// queue reports no terminal status for a stale outcome).
const SETTLE_POLL_MS = 100;
const BREAKPOINT_QUERY = `(max-width: ${TABLET_WIDTH - 0.02}px)`;
const FOCUSABLE_SELECTOR =
  'a[href], button, input:not([type="hidden"]), select, textarea, [tabindex]:not([tabindex="-1"])';

// Where focus lands when the opening gear is not focusable (hidden or removed).
// The URL deck has no collapsible header, so it falls back to its header buttons.
const FOCUS_FALLBACK_SELECTORS: Readonly<Record<PanelId, readonly string[]>> = {
  utubs: ["#UTubDeckHeaderAndCaret"],
  members: ["#MemberDeckHeaderAndCaret"],
  tags: ["#TagDeckHeaderAndCaret"],
  urls: ["#urlBtnCreate", "#urlBtnMultiSelect"],
};

// Below the breakpoint the Tag deck lives in the Tag sheet, whose handle is the
// focusable stand-in for a missing Tags gear.
const TAG_SHEET_HANDLE_SELECTOR = "#tagSheetHandle";

// A deck's own collapse closes its popover; the URL deck has no collapse.
const COLLAPSE_DECK_BY_PANEL: Readonly<
  Partial<Record<PanelId, "utubs" | "members" | "tags">>
> = {
  utubs: "utubs",
  members: "members",
  tags: "tags",
};

type ForcedReadOnlyReason = "locked" | "forbidden";

interface SectionEntry {
  section: PanelSection;
  wrapper: HTMLElement;
  body: HTMLElement;
  statusElement: HTMLElement;
  noteElement: HTMLElement;
  cleanup: (() => void) | null;
  /** Deep copy of `settings[panel]` at the last render (scope 'utub'). */
  renderedValue: unknown;
  lastControlId: string | null;
  describedControlId: string | null;
  saving: boolean;
  dwellTimer: ReturnType<typeof setTimeout> | null;
  settleTimer: ReturnType<typeof setTimeout> | null;
}

type Surface = "popover" | "sheet";

interface OpenPopover {
  /** Which surface renders this open settings view. */
  surface: Surface;
  /** Render target: the popover element, or the sheet body. */
  container: HTMLElement;
  panel: PanelId;
  gear: HTMLElement;
  /** Active UTub when opened; null for the UTubs popover. */
  utubID: number | null;
  entries: Map<string, SectionEntry>;
}

let _queue: SaveQueue | null = null;
let _current: OpenPopover | null = null;
let _forcedReadOnly: ForcedReadOnlyReason | null = null;
let _disposers: Array<() => void> = [];
let _breakpointQuery: MediaQueryList | null = null;
let _closeFlagTimer: ReturnType<typeof setTimeout> | null = null;
// Section titles outlive their DOM so a late failure can still be announced.
const _titles = new Map<string, string>();

// Snapshots the reconcile pass diffs against.
let _lastActiveUTubID: number | null = null;
let _lastIsOwner = false;
let _lastIsCoCreator = false;
let _lastIsLocked = false;

// ---------------------------------------------------------------- helpers

function popoverElement(): HTMLElement | null {
  return document.querySelector<HTMLElement>(POPOVER_SELECTOR);
}

function sheetElement(): HTMLElement | null {
  return document.querySelector<HTMLElement>(SHEET_SELECTOR);
}

// The dialog element of the open surface (Tab trap root, inside-focus test and
// last-resort focus target); never the sheet's body container.
function surfaceElement(): HTMLElement | null {
  return _current?.surface === "sheet" ? sheetElement() : popoverElement();
}

function allGears(): HTMLElement[] {
  return Array.from(document.querySelectorAll<HTMLElement>(GEAR_SELECTOR));
}

function isPerUTubPanel({ panel }: { panel: PanelId }): boolean {
  return panel !== "utubs";
}

function isBelowBreakpoint(): boolean {
  if (_breakpointQuery !== null) return _breakpointQuery.matches;
  return window.innerWidth < TABLET_WIDTH;
}

function isFocusable(element: Element | null | undefined): boolean {
  if (!(element instanceof HTMLElement) || !element.isConnected) return false;
  if (element.classList.contains(HIDDEN_CLASS)) return false;
  const style = getComputedStyle(element);
  return style.display !== "none" && style.visibility !== "hidden";
}

function focusableDescendants({ root }: { root: HTMLElement }): HTMLElement[] {
  return Array.from(
    root.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter(
    (element) =>
      !element.hasAttribute("disabled") &&
      element.getAttribute("tabindex") !== "-1" &&
      !element.closest("[hidden]") &&
      isFocusable(element),
  );
}

function cloneValue<Value>(value: Value): Value {
  if (value === undefined) return value;
  return JSON.parse(JSON.stringify(value)) as Value;
}

function isDeepEqual({
  left,
  right,
}: {
  left: unknown;
  right: unknown;
}): boolean {
  if (Object.is(left, right)) return true;
  if (
    typeof left !== "object" ||
    typeof right !== "object" ||
    left === null ||
    right === null
  ) {
    return false;
  }
  if (Array.isArray(left) !== Array.isArray(right)) return false;
  const leftRecord = left as Record<string, unknown>;
  const rightRecord = right as Record<string, unknown>;
  const leftKeys = Object.keys(leftRecord);
  if (leftKeys.length !== Object.keys(rightRecord).length) return false;
  return leftKeys.every(
    (key) =>
      Object.prototype.hasOwnProperty.call(rightRecord, key) &&
      isDeepEqual({ left: leftRecord[key], right: rightRecord[key] }),
  );
}

function sliceFor({ panel }: { panel: PanelId }): unknown {
  return getState().settings?.[panel];
}

function titleOf({ sectionId }: { sectionId: string }): string {
  return _titles.get(sectionId) ?? "";
}

function say({ message }: { message: string }): void {
  announceSettingsStatus({ message });
}

function sayStatus({
  sectionId,
  status,
}: {
  sectionId: string;
  status: string;
}): void {
  const title = titleOf({ sectionId });
  say({ message: title === "" ? status : `${title}: ${status}` });
}

function isManager({ state }: { state: AppState }): boolean {
  return state.isCurrentUserOwner || state.isCoCreator;
}

// ------------------------------------------------------- section context

function readOnlyNoteFor({
  section,
}: {
  section: PanelSection;
}): string | null {
  if (section.scope !== "utub") return null;
  const state = getState();
  if (_forcedReadOnly === "forbidden" || !isManager({ state })) {
    return APP_CONFIG.strings.PANEL_SETTINGS_MANAGERS_ONLY;
  }
  if (_forcedReadOnly === "locked" || state.isCurrentUTubLocked) {
    return APP_CONFIG.strings.PANEL_SETTINGS_UTUB_LOCKED;
  }
  return null;
}

function contextFor({ section }: { section: PanelSection }): SectionContext {
  const state = getState();
  const forced = section.scope === "utub" && _forcedReadOnly !== null;
  return {
    settings: section.scope === "utub" ? state.settings : null,
    canWrite: canWriteSection({ section, state }) && !forced,
    submit: ({ patch, debounce }) => submit({ section, patch, debounce }),
  };
}

function submit({
  section,
  patch,
  debounce,
}: {
  section: PanelSection;
  patch: SectionPatch;
  debounce?: boolean;
}): void {
  const entry = _current?.entries.get(section.id);
  if (entry) clearError({ entry });
  _queue?.enqueue({
    section,
    patch,
    ...(debounce === undefined ? {} : { debounce }),
  });
}

// ------------------------------------------------------- section render

function setStatus({
  entry,
  state,
  text,
}: {
  entry: SectionEntry;
  state: SaveStatus | null;
  text: string;
}): void {
  if (state === null) {
    delete entry.statusElement.dataset.state;
  } else {
    entry.statusElement.dataset.state = state;
  }
  entry.statusElement.textContent = text;
}

function controlFor({ entry }: { entry: SectionEntry }): HTMLElement | null {
  if (entry.lastControlId !== null) {
    const byId = entry.body.querySelector<HTMLElement>(
      `[id="${entry.lastControlId}"]`,
    );
    if (byId) return byId;
  }
  return focusableDescendants({ root: entry.body })[0] ?? null;
}

function statusElementId({ entry }: { entry: SectionEntry }): string {
  return `panelSettingsStatus-${entry.section.id}`;
}

function clearError({ entry }: { entry: SectionEntry }): void {
  if (entry.statusElement.dataset.state !== "error") return;
  setStatus({ entry, state: null, text: "" });
  if (entry.describedControlId !== null) {
    const control = entry.body.querySelector<HTMLElement>(
      `[id="${entry.describedControlId}"]`,
    );
    const remaining = (control?.getAttribute("aria-describedby") ?? "")
      .split(/\s+/)
      .filter((token) => token !== "" && token !== statusElementId({ entry }));
    if (remaining.length > 0) {
      control?.setAttribute("aria-describedby", remaining.join(" "));
    } else {
      control?.removeAttribute("aria-describedby");
    }
    entry.describedControlId = null;
  }
}

// A persistent inline message tied to the control by aria-describedby; never
// role="alert" (the polite live region carries the announcement).
function showError({
  entry,
  message,
}: {
  entry: SectionEntry;
  message: string;
}): void {
  clearError({ entry });
  setStatus({ entry, state: "error", text: message });
  const control = controlFor({ entry });
  if (!control) return;
  if (control.id === "") {
    control.id = `panelSettingsControl-${entry.section.id}`;
  }
  const existing = control.getAttribute("aria-describedby");
  control.setAttribute(
    "aria-describedby",
    existing
      ? `${existing} ${statusElementId({ entry })}`
      : statusElementId({ entry }),
  );
  entry.describedControlId = control.id;
}

function focusIsInside({ entry }: { entry: SectionEntry }): boolean {
  return entry.wrapper.contains(document.activeElement);
}

function applyNote({ entry }: { entry: SectionEntry }): void {
  const note = readOnlyNoteFor({ section: entry.section });
  entry.noteElement.textContent = note ?? "";
  entry.noteElement.hidden = note === null;
}

function renderSectionBody({ entry }: { entry: SectionEntry }): void {
  const active = document.activeElement;
  const hadFocus = active instanceof HTMLElement && focusIsInside({ entry });
  const focusedId = hadFocus ? active.id : "";

  try {
    entry.cleanup?.();
  } catch (error) {
    log("section cleanup threw", { sectionId: entry.section.id, error });
  }
  entry.cleanup = null;
  entry.body.replaceChildren();
  entry.renderedValue =
    entry.section.scope === "utub"
      ? cloneValue(sliceFor({ panel: entry.section.panel }))
      : undefined;

  try {
    const result = entry.section.render({
      container: entry.body,
      ctx: contextFor({ section: entry.section }),
    });
    entry.cleanup = typeof result === "function" ? result : null;
  } catch (error) {
    log("section render threw", { sectionId: entry.section.id, error });
  }

  if (entry.body.childElementCount === 0 && entry.body.textContent === "") {
    const empty = document.createElement("p");
    empty.className = "panelSettingsRowDesc";
    empty.textContent = APP_CONFIG.strings.PANEL_SETTINGS_EMPTY;
    entry.body.append(empty);
  }

  applyNote({ entry });
  if (hadFocus) {
    // By id when it has one, else the first control, else the dialog: focus
    // never falls to the body (which a forced close reads as "restore the gear").
    const byId =
      focusedId === ""
        ? null
        : entry.body.querySelector<HTMLElement>(`[id="${focusedId}"]`);
    (
      byId ??
      focusableDescendants({ root: entry.body })[0] ??
      surfaceElement()
    )?.focus();
  }
}

function createEntry({
  section,
  popover,
}: {
  section: PanelSection;
  popover: OpenPopover;
}): SectionEntry {
  const wrapper = document.createElement("section");
  wrapper.className = "panelSettingsSection";
  wrapper.dataset.sectionId = section.id;

  const heading = document.createElement("h2");
  heading.className = "panelSettingsRowTitle";
  heading.textContent = section.title;

  const scope = document.createElement("div");
  scope.className = "panelSettingsScope";
  scope.textContent =
    section.scope === "utub"
      ? APP_CONFIG.strings.PANEL_SETTINGS_SCOPE_UTUB
      : APP_CONFIG.strings.PANEL_SETTINGS_SCOPE_USER;

  const body = document.createElement("div");
  body.className = "panelSettingsSectionBody";

  const statusElement = document.createElement("p");
  statusElement.className = "panelSettingsStatus";

  const noteElement = document.createElement("p");
  noteElement.className = "panelSettingsReadOnlyNote";
  noteElement.hidden = true;

  wrapper.append(heading, scope, body, statusElement, noteElement);

  const entry: SectionEntry = {
    section,
    wrapper,
    body,
    statusElement,
    noteElement,
    cleanup: null,
    renderedValue: undefined,
    lastControlId: null,
    describedControlId: null,
    saving: false,
    dwellTimer: null,
    settleTimer: null,
  };
  statusElement.id = statusElementId({ entry });
  _titles.set(section.id, section.title);

  wrapper.addEventListener("focusin", (event) => {
    const target = event.target;
    if (
      target instanceof HTMLElement &&
      body.contains(target) &&
      target.id !== ""
    ) {
      entry.lastControlId = target.id;
    }
  });
  wrapper.addEventListener("focusout", () => {
    _queue?.flush({ sectionId: section.id });
  });

  popover.entries.set(section.id, entry);
  return entry;
}

function teardownEntry({ entry }: { entry: SectionEntry }): void {
  if (entry.dwellTimer !== null) clearTimeout(entry.dwellTimer);
  if (entry.settleTimer !== null) clearTimeout(entry.settleTimer);
  entry.dwellTimer = null;
  entry.settleTimer = null;
  try {
    entry.cleanup?.();
  } catch (error) {
    log("section cleanup threw", { sectionId: entry.section.id, error });
  }
  entry.cleanup = null;
  entry.wrapper.remove();
}

function renderAllSections({ popover }: { popover: OpenPopover }): void {
  const element = popover.container;
  const sections = getSections(popover.panel);
  for (const [sectionId, entry] of popover.entries) {
    if (!sections.some((section) => section.id === sectionId)) {
      teardownEntry({ entry });
      popover.entries.delete(sectionId);
    }
  }
  const focused = document.activeElement;
  sections.forEach((section, index) => {
    let entry = popover.entries.get(section.id);
    let isFresh = false;
    if (entry === undefined || entry.section !== section) {
      if (entry) teardownEntry({ entry });
      entry = createEntry({ section, popover });
      isFresh = true;
    }
    // Only move a wrapper that is new or out of order: a move blurs its focus.
    if (element.children[index] !== entry.wrapper) {
      element.insertBefore(entry.wrapper, element.children[index] ?? null);
    }
    // An unchanged section keeps its DOM, typed text and focus.
    if (isFresh) renderSectionBody({ entry });
  });
  if (
    focused instanceof HTMLElement &&
    focused.isConnected &&
    document.activeElement !== focused
  ) {
    focused.focus();
  }
}

// ----------------------------------------------------- saving indicators

function stopSaving({ entry }: { entry: SectionEntry }): void {
  if (entry.settleTimer !== null) clearTimeout(entry.settleTimer);
  entry.settleTimer = null;
  entry.saving = false;
  entry.wrapper.removeAttribute("aria-busy");
  if (entry.statusElement.dataset.state === "saving") {
    setStatus({ entry, state: null, text: "" });
  }
}

// The queue reports no terminal status for a stale outcome, so the sink watches
// for the section going idle and clears the indicator itself.
function watchSettle({ entry }: { entry: SectionEntry }): void {
  if (entry.settleTimer !== null) clearTimeout(entry.settleTimer);
  const check = (): void => {
    entry.settleTimer = null;
    if (!entry.saving) return;
    if (_queue?.hasWork({ sectionId: entry.section.id })) {
      entry.settleTimer = setTimeout(check, SETTLE_POLL_MS);
      return;
    }
    stopSaving({ entry });
  };
  entry.settleTimer = setTimeout(check, SETTLE_POLL_MS);
}

function rerenderIfIdle({ entry }: { entry: SectionEntry }): void {
  if (_queue?.hasWork({ sectionId: entry.section.id })) return;
  if (focusIsInside({ entry })) return;
  renderSectionBody({ entry });
}

function reconcileSavedValue({
  entry,
  savedPatch,
}: {
  entry: SectionEntry;
  savedPatch: SectionPatch | undefined;
}): void {
  if (savedPatch === undefined || entry.section.scope !== "utub") return;
  if (_current?.entries.get(entry.section.id) !== entry) return;
  const slice = cloneValue(sliceFor({ panel: entry.section.panel }));
  const expected = {
    ...(entry.renderedValue as Record<string, unknown> | undefined),
    ...savedPatch,
  };
  // Always adopt the stored value as the baseline, so the next save and any
  // external write compare against what the server holds, not a stale render.
  entry.renderedValue = slice;
  if (isDeepEqual({ left: slice, right: expected })) return;
  // The server normalized the value. Unsent edits block the re-render (the save
  // that just finished is still in flight, so `hasWork` would always say busy).
  if (_queue?.hasUnsentEdits({ sectionId: entry.section.id })) return;
  if (focusIsInside({ entry })) return;
  renderSectionBody({ entry });
}

// ------------------------------------------------------------------ sink

// A late outcome for a UTub other than the one the popover was opened for must
// not touch it (the queue keeps saving to the UTub it captured).
function isOtherUTub({ utubID }: { utubID: number | null }): boolean {
  return (
    utubID !== null &&
    _current !== null &&
    _current.utubID !== null &&
    _current.utubID !== utubID
  );
}

function entryFor({
  sectionId,
  utubID,
}: {
  sectionId: string;
  utubID: number | null;
}): SectionEntry | undefined {
  if (isOtherUTub({ utubID })) return undefined;
  return _current?.entries.get(sectionId);
}

function buildSink(): QueueSink {
  return {
    report({ sectionId, utubID, status, savedPatch }) {
      const entry = entryFor({ sectionId, utubID });

      if (status === "error") {
        // Announced even with no popover attached (a late save failure).
        sayStatus({
          sectionId,
          status: APP_CONFIG.strings.PANEL_SETTINGS_SAVE_FAILED,
        });
        if (!entry) return;
        stopSaving({ entry });
        renderSectionBody({ entry });
        showError({
          entry,
          message: APP_CONFIG.strings.PANEL_SETTINGS_REVERTED,
        });
        return;
      }

      if (!entry) return;

      if (status === "saving") {
        if (entry.dwellTimer !== null) clearTimeout(entry.dwellTimer);
        entry.dwellTimer = null;
        entry.saving = true;
        entry.wrapper.setAttribute("aria-busy", "true");
        setStatus({
          entry,
          state: "saving",
          text: APP_CONFIG.strings.PANEL_SETTINGS_SAVING,
        });
        watchSettle({ entry });
        return;
      }

      // saved
      stopSaving({ entry });
      clearError({ entry });
      setStatus({
        entry,
        state: "saved",
        text: APP_CONFIG.strings.PANEL_SETTINGS_SAVED,
      });
      sayStatus({
        sectionId,
        status: APP_CONFIG.strings.PANEL_SETTINGS_SAVED,
      });
      // Synchronous: a coalesced edit re-sends right after this report and would
      // cancel a deferred check.
      reconcileSavedValue({ entry, savedPatch });
      if (entry.dwellTimer !== null) clearTimeout(entry.dwellTimer);
      entry.dwellTimer = setTimeout(() => {
        entry.dwellTimer = null;
        if (entry.statusElement.dataset.state === "saved") {
          setStatus({ entry, state: null, text: "" });
        }
      }, SAVED_DWELL_MS);
    },

    forceReadOnly({ reason, utubID }) {
      const popover = _current;
      if (popover === null || isOtherUTub({ utubID })) return;
      const alreadyForced = _forcedReadOnly === reason;
      _forcedReadOnly = reason;
      for (const entry of popover.entries.values()) {
        stopSaving({ entry });
        if (entry.section.scope === "utub") renderSectionBody({ entry });
      }
      if (alreadyForced) return;
      say({
        message:
          reason === "locked"
            ? APP_CONFIG.strings.PANEL_SETTINGS_UTUB_LOCKED
            : APP_CONFIG.strings.PANEL_SETTINGS_MANAGERS_ONLY,
      });
    },

    announce({ sectionId, utubID, message }) {
      // A stale failure: that section is no longer saving.
      const entry = entryFor({ sectionId, utubID });
      if (entry) stopSaving({ entry });
      say({ message });
    },

    resynced({ sectionId, utubID }) {
      const entry = entryFor({ sectionId, utubID });
      if (!entry) return;
      // Re-render even with focus inside: the resync is authoritative. Only
      // unsent edits block it (the failed save's own in-flight flag is still up).
      if (_queue?.hasUnsentEdits({ sectionId })) return;
      renderSectionBody({ entry });
    },

    isForcedReadOnly() {
      return _forcedReadOnly !== null;
    },
  };
}

// -------------------------------------------------------------- position

function positionPopover({ gear }: { gear: HTMLElement }): void {
  const element = popoverElement();
  if (!element) return;
  const rect = gear.getBoundingClientRect();
  const width = element.offsetWidth;
  const height = element.offsetHeight;
  const maxLeft = Math.max(
    VIEWPORT_MARGIN_PX,
    window.innerWidth - width - VIEWPORT_MARGIN_PX,
  );
  const maxTop = Math.max(
    VIEWPORT_MARGIN_PX,
    window.innerHeight - height - VIEWPORT_MARGIN_PX,
  );
  // Below the gear, right edges aligned, clamped into the viewport.
  const left = Math.min(
    Math.max(rect.right - width, VIEWPORT_MARGIN_PX),
    maxLeft,
  );
  const top = Math.min(
    Math.max(rect.bottom + GEAR_GAP_PX, VIEWPORT_MARGIN_PX),
    maxTop,
  );
  element.style.left = `${left}px`;
  element.style.top = `${top}px`;
}

// ------------------------------------------------------------ open/close

function restoreFocusTo({
  gear,
  panel,
}: {
  gear: HTMLElement;
  panel: PanelId;
}): void {
  if (isFocusable(gear)) {
    gear.focus();
    return;
  }
  const selectors =
    panel === "tags" && isBelowBreakpoint()
      ? [TAG_SHEET_HANDLE_SELECTOR, ...FOCUS_FALLBACK_SELECTORS[panel]]
      : FOCUS_FALLBACK_SELECTORS[panel];
  for (const selector of selectors) {
    const fallback = document.querySelector<HTMLElement>(selector);
    if (isFocusable(fallback)) {
      fallback?.focus();
      return;
    }
  }
}

function openPopover({ gear }: { gear: HTMLElement }): void {
  const surface: Surface = isBelowBreakpoint() ? "sheet" : "popover";
  const element = surface === "sheet" ? sheetElement() : popoverElement();
  const panel = gear.dataset.panel;
  if (!element || !isKnownPanel(panel)) return;
  if (getSections(panel).length === 0) return;
  // A sheet close or Tag sheet close is still unwinding its history entry: the
  // tap is dropped (before any internal close) and stays dropped.
  if (surface === "sheet" && isPanelSettingsSheetSelfBackPending()) return;

  if (_current !== null) {
    // Switching popovers is a quiet user close; the sheet's gears are inert while
    // it is open, so reaching this on the sheet is a forced close.
    closePopover({
      kind: _current.surface === "sheet" ? "forced" : "user",
      restoreFocus: false,
    });
  }

  closeAllMemberRowMenus();
  dismissActiveTip({ markSeen: false });
  hideTooltip(gear);

  gear.setAttribute("aria-expanded", "true");
  const label = gear.getAttribute("aria-label");

  if (_closeFlagTimer !== null) clearTimeout(_closeFlagTimer);
  _closeFlagTimer = null;
  _forcedReadOnly = null;

  let container: HTMLElement;
  if (surface === "sheet") {
    // The sheet is labelled by its title element, which carries the gear label.
    container = openSettingsSheet({ title: label ?? "" });
  } else {
    element.removeAttribute("aria-labelledby");
    element.removeAttribute("aria-label");
    if (label) element.setAttribute("aria-label", label);
    container = element;
  }
  const popover: OpenPopover = {
    surface,
    container,
    panel,
    gear,
    utubID: isPerUTubPanel({ panel }) ? getState().activeUTubID : null,
    entries: new Map(),
  };
  _current = popover;
  setPanelSettingsOpen({ open: true });

  try {
    container.replaceChildren();
    if (surface === "popover") element.classList.remove(HIDDEN_CLASS);
    renderAllSections({ popover });
    if (surface === "popover") positionPopover({ gear });

    const first = focusableDescendants({ root: container })[0];
    const fallback =
      surface === "sheet"
        ? (document.querySelector<HTMLElement>(SHEET_CLOSE_SELECTOR) ?? element)
        : element;
    // The sheet is fixed-position: never let focus scroll the page behind it.
    (first ?? fallback).focus({ preventScroll: surface === "sheet" });
  } catch (error) {
    // An inert page with a half-rendered sheet would lock the user in.
    if (surface === "sheet") {
      closePopover({ kind: "forced", restoreFocus: false });
    }
    throw error;
  }
}

function closePopover({
  kind,
  restoreFocus = true,
}: {
  kind: CloseKind;
  restoreFocus?: boolean;
}): void {
  const popover = _current;
  const element = surfaceElement();
  if (popover === null || !element) return;
  const forced = kind === "forced";

  // Pending edits always go out on close.
  _queue?.flush({});

  const active = document.activeElement;
  const focusWasInside =
    active === null || active === document.body || element.contains(active);

  _current = null;
  _forcedReadOnly = null;
  for (const entry of popover.entries.values()) {
    teardownEntry({ entry });
  }
  popover.entries.clear();
  popover.container.replaceChildren();
  // The surface teardown (inert restore on the sheet) completes before focus
  // returns to the gear, which may sit inside a previously inert region.
  if (popover.surface === "sheet") {
    closeSettingsSheet({ kind });
  } else {
    element.classList.add(HIDDEN_CLASS);
  }
  popover.gear.setAttribute("aria-expanded", "false");

  if (restoreFocus && (!forced || focusWasInside)) {
    restoreFocusTo({ gear: popover.gear, panel: popover.panel });
  }
  if (forced) {
    say({ message: APP_CONFIG.strings.PANEL_SETTINGS_CLOSED });
  }

  // Escape handlers elsewhere read the flag for the rest of this tick, so the
  // same keydown that closed the popover cannot also exit another mode.
  if (_closeFlagTimer !== null) clearTimeout(_closeFlagTimer);
  _closeFlagTimer = setTimeout(() => {
    _closeFlagTimer = null;
    if (_current !== null) return;
    setPanelSettingsOpen({ open: false });
    maybeShowNextTip();
  }, 0);
}

function closeIfPanel({
  matches,
}: {
  matches: (panel: PanelId) => boolean;
}): void {
  if (_current !== null && matches(_current.panel)) {
    closePopover({ kind: "forced" });
  }
}

function closeForPerUTubPanels(): void {
  closeIfPanel({ matches: (panel) => isPerUTubPanel({ panel }) });
}

function closeAnyOpen(): void {
  closeIfPanel({ matches: () => true });
}

// ----------------------------------------------------------- gears

function recomputeGears(): void {
  const state = getState();
  const controls = isBelowBreakpoint() ? SHEET_ID : POPOVER_ID;
  let changed = false;
  for (const gear of allGears()) {
    const panel = gear.dataset.panel;
    gear.setAttribute("aria-controls", controls);
    const visible =
      isKnownPanel(panel) &&
      getSections(panel).length > 0 &&
      (panel === "utubs" || state.activeUTubID !== null);
    if (gear.classList.contains(HIDDEN_CLASS) === visible) {
      gear.classList.toggle(HIDDEN_CLASS, !visible);
      changed = true;
    }
  }
  if (changed) fitUTubHeaderAndSubheader();
}

function onGearClick(event: Event): void {
  const gear = event.currentTarget;
  if (!(gear instanceof HTMLElement)) return;
  if (_current !== null && _current.gear === gear) {
    closePopover({ kind: "user" });
    return;
  }
  openPopover({ gear });
}

// Keeps the tooltip from re-showing (hover or keyboard focus) while the popover
// opened by this gear is up.
function onGearTooltipShow(event: Event): void {
  const gear = event.currentTarget;
  if (
    gear instanceof HTMLElement &&
    gear.getAttribute("aria-expanded") === "true"
  ) {
    event.preventDefault();
  }
}

// ------------------------------------------------------------- reconcile

/**
 * One pass for every store change, in a fixed order: removal drop, gear
 * visibility, close triggers (which win and skip the re-renders), lock flip,
 * slice re-render.
 */
export function reconcilePanelSettings({
  changedKeys,
}: {
  changedKeys: ReadonlyArray<keyof AppState>;
}): void {
  const state = getState();

  // 1. A UTub that left the list: its pending saves have nowhere to go.
  if (
    _lastActiveUTubID !== null &&
    state.activeUTubID !== _lastActiveUTubID &&
    (changedKeys.includes("utubs") || changedKeys.includes("activeUTubID")) &&
    !state.utubs.some((utub) => utub.id === _lastActiveUTubID)
  ) {
    _queue?.dropUTub({ utubID: _lastActiveUTubID });
  }

  // 2. Gear visibility (and header re-fit).
  recomputeGears();

  const popover = _current;
  const lockFlipped = state.isCurrentUTubLocked !== _lastIsLocked;
  const roleFlipped =
    state.isCurrentUserOwner !== _lastIsOwner ||
    state.isCoCreator !== _lastIsCoCreator;
  snapshotState();

  if (popover === null) return;

  // 3. Close triggers win and skip the re-renders.
  if (isPerUTubPanel({ panel: popover.panel })) {
    const hasUTubSection = Array.from(popover.entries.values()).some(
      (entry) => entry.section.scope === "utub",
    );
    const sliceGone =
      changedKeys.includes("settings") &&
      state.settings === null &&
      hasUTubSection;
    if (
      state.activeUTubID === null ||
      state.activeUTubID !== popover.utubID ||
      roleFlipped ||
      sliceGone
    ) {
      closePopover({ kind: "forced" });
      return;
    }
  }

  // 4. Lock flip: re-render read-only (or writable) without closing.
  if (lockFlipped && isPerUTubPanel({ panel: popover.panel })) {
    for (const entry of popover.entries.values()) {
      if (entry.section.scope === "utub") renderSectionBody({ entry });
    }
    if (state.isCurrentUTubLocked && _forcedReadOnly !== "locked") {
      say({ message: APP_CONFIG.strings.PANEL_SETTINGS_UTUB_LOCKED });
    }
  }

  // 5. An external slice write (not the shell's own PATCH, which bumps
  // settingsVersion in the same notification).
  if (
    changedKeys.includes("settings") &&
    !changedKeys.includes("settingsVersion")
  ) {
    for (const entry of popover.entries.values()) {
      if (entry.section.scope !== "utub") continue;
      const slice = sliceFor({ panel: entry.section.panel });
      if (isDeepEqual({ left: slice, right: entry.renderedValue })) continue;
      rerenderIfIdle({ entry });
    }
  }
}

function snapshotState(): void {
  const state = getState();
  _lastActiveUTubID = state.activeUTubID;
  _lastIsOwner = state.isCurrentUserOwner;
  _lastIsCoCreator = state.isCoCreator;
  _lastIsLocked = state.isCurrentUTubLocked;
}

// --------------------------------------------------------- bus handlers

function onSectionsChanged(): void {
  recomputeGears();
  const popover = _current;
  if (popover === null) return;
  // A section registered or unregistered while open. Pending saves of a section
  // that went away still complete (the queue holds its section object); only its
  // DOM is dropped here.
  if (getSections(popover.panel).length === 0) {
    closePopover({ kind: "forced" });
    return;
  }
  renderAllSections({ popover });
}

function onPointerDown(event: Event): void {
  const popover = _current;
  const element = surfaceElement();
  if (popover === null || !element) return;
  // The sheet's outside is its backdrop, which closes it through its own click.
  if (popover.surface === "sheet") return;
  const target = event.target;
  if (!(target instanceof Node)) return;
  if (element.contains(target)) return;
  // Gear clicks are handled by the gear's own click (toggle / switch).
  if (target instanceof Element && target.closest(GEAR_SELECTOR)) return;
  const { gear, panel } = popover;
  closePopover({ kind: "user", restoreFocus: false });
  // The browser's default mousedown focus handling runs after this capture
  // handler, so restore afterwards, and only if nothing took focus (a clicked
  // control keeps it; blank space leaves the body).
  setTimeout(() => {
    const active = document.activeElement;
    if (active === null || active === document.body) {
      restoreFocusTo({ gear, panel });
    }
  }, 0);
}

function onEscape(event: JQuery.TriggeredEvent): void {
  if (event.key !== KEYS.ESCAPE || _current === null) return;
  event.preventDefault();
  // Nothing else may react to the Escape that closes the sheet.
  if (_current.surface === "sheet") event.stopImmediatePropagation();
  closePopover({ kind: "user" });
}

function onPopoverKeydown(event: KeyboardEvent): void {
  if (event.key !== KEYS.TAB) return;
  const element = surfaceElement();
  if (!element || _current === null) return;
  const focusable = focusableDescendants({ root: element });
  if (focusable.length === 0) {
    event.preventDefault();
    element.focus();
    return;
  }
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  const active = document.activeElement;
  if (event.shiftKey && (active === first || active === element)) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus();
  }
}

function onBreakpointChange(): void {
  // Whichever surface is open belongs to the viewport that just ended.
  closeAnyOpen();
  recomputeGears();
}

function onResize(): void {
  if (_current !== null && _current.surface === "popover") {
    positionPopover({ gear: _current.gear });
  }
}

// ------------------------------------------------------------ lifecycle

function disposeAll(): void {
  for (const dispose of _disposers) dispose();
  _disposers = [];
}

/** Drops all state and listeners (initPanelSettings re-entry and tests). */
export function resetPopover(): void {
  disposeAll();
  if (_closeFlagTimer !== null) clearTimeout(_closeFlagTimer);
  _closeFlagTimer = null;
  if (_current !== null) {
    for (const entry of _current.entries.values()) teardownEntry({ entry });
    _current = null;
  }
  resetSettingsSheet();
  _queue = null;
  _forcedReadOnly = null;
  _breakpointQuery = null;
  _titles.clear();
  setPanelSettingsOpen({ open: false });
}

/**
 * Wire the gears, the popover surface, the save queue and every close trigger.
 * Safe to call again: the previous wiring is torn down first.
 */
export function initPopover(): void {
  resetPopover();

  const queue = createSaveQueue({ sink: buildSink() });
  _queue = queue;

  for (const gear of allGears()) {
    gear.addEventListener("click", onGearClick);
    gear.addEventListener("show.bs.tooltip", onGearTooltipShow);
    _disposers.push(() => {
      gear.removeEventListener("click", onGearClick);
      gear.removeEventListener("show.bs.tooltip", onGearTooltipShow);
    });
  }

  for (const element of [popoverElement(), sheetElement()]) {
    if (!element) continue;
    element.addEventListener("keydown", onPopoverKeydown);
    _disposers.push(() =>
      element.removeEventListener("keydown", onPopoverKeydown),
    );
  }
  registerSettingsSheetCloseHandler((kind) => closePopover({ kind }));

  document.addEventListener("pointerdown", onPointerDown, true);
  _disposers.push(() =>
    document.removeEventListener("pointerdown", onPointerDown, true),
  );
  window.addEventListener("resize", onResize);
  _disposers.push(() => window.removeEventListener("resize", onResize));

  $(document).off(KEYDOWN_NAMESPACE).on(KEYDOWN_NAMESPACE, onEscape);
  $(document).off(MODAL_NAMESPACE).on(MODAL_NAMESPACE, closeAnyOpen);
  _disposers.push(() => {
    $(document).off(KEYDOWN_NAMESPACE);
    $(document).off(MODAL_NAMESPACE);
  });

  if (typeof window.matchMedia === "function") {
    _breakpointQuery = window.matchMedia(BREAKPOINT_QUERY);
    const query = _breakpointQuery;
    query.addEventListener("change", onBreakpointChange);
    _disposers.push(() =>
      query.removeEventListener("change", onBreakpointChange),
    );
  }

  _disposers.push(
    subscribe((changedKeys) => reconcilePanelSettings({ changedKeys })),
  );
  _disposers.push(
    on(AppEvents.PANEL_SETTINGS_SECTIONS_CHANGED, onSectionsChanged),
  );
  _disposers.push(on(AppEvents.UTUB_SELECTED, closeForPerUTubPanels));
  _disposers.push(
    on(AppEvents.UTUB_DELETED, ({ utubID }) => {
      // Backstop for a deletion that never reached the store pass.
      queue.dropUTub({ utubID });
      closeForPerUTubPanels();
    }),
  );
  _disposers.push(
    on(AppEvents.FORM_MODE_CHANGED, ({ openForm }) => {
      if (openForm !== null) closeAnyOpen();
    }),
  );
  _disposers.push(
    on(AppEvents.URL_MULTISELECT_MODE_CHANGED, ({ active }) => {
      if (active) closeAnyOpen();
    }),
  );
  _disposers.push(
    on(AppEvents.CROSS_UTUB_SEARCH_VISIBILITY_CHANGED, ({ active }) => {
      if (active) closeAnyOpen();
    }),
  );
  _disposers.push(on(AppEvents.TRASH_OPENED, closeAnyOpen));
  _disposers.push(on(AppEvents.MOBILE_DECK_SWITCHED, closeAnyOpen));
  _disposers.push(
    on(AppEvents.DECK_COLLAPSE_CHANGED, ({ deck, collapsed }) => {
      if (!collapsed) return;
      closeIfPanel({
        matches: (panel) => COLLAPSE_DECK_BY_PANEL[panel] === deck,
      });
    }),
  );
  _disposers.push(on(AppEvents.LEFT_PANEL_COLLAPSE_CHANGED, closeAnyOpen));

  // Final pass: sections may have registered before init ran.
  snapshotState();
  recomputeGears();
}
