import { APP_CONFIG } from "../../lib/config.js";
import { $ } from "../../lib/globals.js";
import { debug } from "../../lib/debug.js";
import { KEYS } from "../../lib/constants.js";
import { createRovingListbox } from "../../lib/roving-listbox.js";
import { getState } from "../../store/app-store.js";
import type { UtubSummaryItem } from "../../types/utub.js";
import {
  PATCH_TIMEOUT_MS,
  handleActiveUTubGone,
  patchUtubPin,
} from "../panel-settings/client.js";
import { registerSection } from "../panel-settings/registry.js";
import type {
  SaveResult,
  SectionContext,
  SectionPatch,
} from "../panel-settings/types.js";
import { makeUTubPinIcon } from "./pin-marker.js";
import { purgeUTubLocally } from "./remove-local.js";
import { setUTubRowPinned } from "./sort.js";
import { getAllUTubs } from "./utils.js";

const log = debug("utub-pins");

const SECTION_ID = "utubs-pins";
const NOTICE_JOINER = " ";

const INPUT_ID = "utub-pins-input";
const CAP_NOTE_ID = "utub-pins-cap-note";
const NONE_LEFT_ID = "utub-pins-none-left";
const LISTBOX_ID = "utub-pins-listbox";
const REMOVE_ID_PREFIX = "utub-pins-remove-";

const strings = (): Record<string, string> => APP_CONFIG.strings;
const maxPinned = (): number => APP_CONFIG.constants.MAX_PINNED_UTUBS;

type SettleOutcome = "ok" | "failed" | "cap" | "gone";

// Recorded before submit and read by the post-settle helper, which never derives
// focus from document.activeElement (the shell's error render may have moved it).
type FocusPlan =
  | { kind: "unpin"; actedId: string; candidates: string[] }
  | { kind: "pick"; submittedText: string };

// Module scope on purpose: the in-flight flag, the live render's container and
// cleanup, and the picker's typed state must survive a popover rebuild.
let inFlight = false;
let currentContainer: HTMLElement | null = null;
let currentCtx: SectionContext | null = null;
let currentCleanup: (() => void) | null = null;
let renderGeneration = 0;
let lastNotice: string | null = null;
let filterText = "";
let selectionStart: number | null = null;
let selectionEnd: number | null = null;
let focusPlan: FocusPlan | null = null;
let lastOutcome: SettleOutcome = "failed";

function resetModuleState(): void {
  inFlight = false;
  currentContainer = null;
  currentCtx = null;
  currentCleanup = null;
  renderGeneration = 0;
  lastNotice = null;
  filterText = "";
  selectionStart = null;
  selectionEnd = null;
  focusPlan = null;
  lastOutcome = "failed";
}

function fill({
  template,
  name = "",
  count = 0,
}: {
  template: string;
  name?: string;
  count?: number;
}): string {
  const values: Record<string, string> = {
    name,
    count: String(count),
    max: String(maxPinned()),
  };
  // One pass, so a UTub name that looks like a placeholder is never expanded.
  return template.replace(
    /\{(name|count|max)\}/g,
    (_match, key: string) => values[key],
  );
}

function pinnedUtubs(): UtubSummaryItem[] {
  return getState().utubs.filter((utub) => utub.isPinned);
}

function isCapped(): boolean {
  return pinnedUtubs().length >= maxPinned();
}

function removeButtonId({ utubID }: { utubID: number }): string {
  return `${REMOVE_ID_PREFIX}${utubID}`;
}

function elementById(id: string): HTMLElement | null {
  return currentContainer?.querySelector<HTMLElement>(`[id="${id}"]`) ?? null;
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

function runCleanup(): void {
  const cleanup = currentCleanup;
  currentCleanup = null;
  try {
    cleanup?.();
  } catch (error) {
    log("section cleanup threw", error);
  }
}

function rememberTyped({ input }: { input: HTMLInputElement }): void {
  filterText = input.value;
  selectionStart = input.selectionStart;
  selectionEnd = input.selectionEnd;
}

function restoreSelection({ input }: { input: HTMLInputElement }): void {
  if (selectionStart === null || selectionEnd === null) return;
  try {
    input.setSelectionRange(selectionStart, selectionEnd);
  } catch (error) {
    log("restoring the picker selection failed", error);
  }
}

// Marks the controls aria-disabled the moment a write starts, without rebuilding
// the body (a rebuild would drop focus and the typed state).
function syncBusyState(): void {
  const container = currentContainer;
  if (container === null) return;
  const busy = inFlight;
  container
    .querySelectorAll<HTMLElement>(".utubPinsRemove")
    .forEach((button) => {
      button.setAttribute("aria-disabled", String(busy));
    });
  const input = container.querySelector<HTMLElement>(`[id="${INPUT_ID}"]`);
  input?.setAttribute("aria-disabled", String(busy || isCapped()));
}

function beginWrite({
  utubID,
  pinned,
  ctx,
}: {
  utubID: number;
  pinned: boolean;
  ctx: SectionContext;
}): void {
  // Set synchronously, before submit, so a same-tick second activation is
  // dropped before it is enqueued (a second patch would shallow-merge into the
  // pending one and lose a UTub id).
  inFlight = true;
  syncBusyState();
  try {
    ctx.submit({ patch: { utubID, pinned }, debounce: false });
  } catch (error) {
    // save() never runs for a refused submit, so nothing else would clear this.
    log("submitting the pin write threw", error);
    inFlight = false;
    focusPlan = null;
    syncBusyState();
  }
}

// Decorative close icon (Bootstrap Icons "x-lg"); the button's aria-label names it.
const REMOVE_ICON_SVG =
  `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" class="bi bi-x-lg utubPinsRemoveIcon" viewBox="0 0 16 16" aria-hidden="true">` +
  `<path d="M2.146 2.854a.5.5 0 1 1 .708-.708L8 7.293l5.146-5.147a.5.5 0 0 1 .708.708L8.707 8l5.147 5.146a.5.5 0 0 1-.708.708L8 8.707l-5.146 5.147a.5.5 0 0 1-.708-.708L7.293 8z"/>` +
  `</svg>`;

function buildPinnedList({ ctx }: { ctx: SectionContext }): HTMLElement {
  const list = document.createElement("ul");
  list.className = "utubPinsList";
  for (const utub of pinnedUtubs()) {
    const item = document.createElement("li");
    item.className = "utubPinsItem";

    const icon = makeUTubPinIcon()[0];
    const name = document.createElement("span");
    name.className = "utubPinsName";
    name.textContent = utub.name;

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "utubPinsRemove";
    remove.id = removeButtonId({ utubID: utub.id });
    remove.setAttribute(
      "aria-label",
      fill({ template: strings().UTUB_PINS_UNPIN_LABEL, name: utub.name }),
    );
    remove.setAttribute("aria-disabled", String(inFlight));
    remove.insertAdjacentHTML("beforeend", REMOVE_ICON_SVG);
    remove.addEventListener("click", () => {
      if (!ctx.canWrite || inFlight) return;
      const ids = Array.from(
        list.querySelectorAll<HTMLElement>(".utubPinsRemove"),
      ).map((button) => button.id);
      const at = ids.indexOf(remove.id);
      focusPlan = {
        kind: "unpin",
        actedId: remove.id,
        candidates: [
          ...ids.slice(at + 1),
          ...ids.slice(0, at).reverse(),
          INPUT_ID,
        ],
      };
      lastNotice = null;
      beginWrite({ utubID: utub.id, pinned: false, ctx });
    });

    item.append(icon, name, remove);
    list.append(item);
  }
  return list;
}

function buildPicker({ ctx }: { ctx: SectionContext }): {
  element: HTMLElement;
  cleanup: () => void;
} {
  const capped = isCapped();
  // The picker is always empty at the cap.
  if (capped) {
    filterText = "";
    selectionStart = null;
    selectionEnd = null;
  }
  const pinnable = getState().utubs.filter((utub) => !utub.isPinned);
  const noneLeft = !capped && pinnable.length === 0;

  const picker = document.createElement("div");
  picker.className = "utubPinsPicker";

  const input = document.createElement("input");
  input.type = "text";
  input.id = INPUT_ID;
  input.className = "utubPinsInput";
  input.autocomplete = "off";
  input.placeholder = strings().UTUB_PINS_PICKER_PLACEHOLDER;
  input.setAttribute("aria-label", strings().UTUB_PINS_PICKER_PLACEHOLDER);
  input.setAttribute("aria-disabled", String(capped || inFlight));
  input.value = filterText;
  input.setAttribute("role", "combobox");
  input.setAttribute("aria-autocomplete", "list");
  input.setAttribute("aria-controls", LISTBOX_ID);
  input.setAttribute("aria-expanded", "false");
  if (capped) input.setAttribute("aria-describedby", CAP_NOTE_ID);
  else if (noneLeft) input.setAttribute("aria-describedby", NONE_LEFT_ID);

  const options = document.createElement("div");
  options.className = "utubPinsOptions";
  options.id = LISTBOX_ID;
  options.setAttribute("role", "listbox");
  options.hidden = true;

  const noMatch = document.createElement("div");
  noMatch.className = "utubPinsNoMatch";
  noMatch.setAttribute("role", "status");

  picker.append(input);
  if (capped) {
    const note = document.createElement("p");
    note.id = CAP_NOTE_ID;
    note.className = "utubPinsCapNote";
    note.textContent = strings().UTUB_PINS_CAP_REACHED;
    picker.append(note);
  } else if (noneLeft) {
    const hint = document.createElement("p");
    hint.id = NONE_LEFT_ID;
    hint.className = "utubPinsHint";
    hint.textContent = strings().UTUB_PINS_NONE_LEFT_HINT;
    picker.append(hint);
  }
  picker.append(options, noMatch);

  const activate = ({ utubID }: { utubID: number }): void => {
    if (!ctx.canWrite || inFlight || isCapped()) return;
    if (!getState().utubs.some((utub) => utub.id === utubID)) return;
    focusPlan = { kind: "pick", submittedText: filterText };
    lastNotice = null;
    beginWrite({ utubID, pinned: true, ctx });
  };

  const roving = createRovingListbox({
    container: () => $(picker),
    optionSelector: ".utubPinsOption",
    enabledOptionSelector: ".utubPinsOption",
    listboxSelector: ".utubPinsOptions",
    noMatchesSelector: ".utubPinsNoMatch",
    filterText: (row) => row.text(),
    // No onEscape: the roving instance would swallow every Escape, so the
    // popover could never close. The two-step Escape below is section-owned.
    onActivateRow: (row) => {
      activate({ utubID: Number(row.attr("data-utub-id")) });
    },
  });

  const renderOptions = (): void => {
    const query = input.value.trim().toLowerCase();
    const showList = query !== "" && !isCapped();
    const matches = showList
      ? pinnable.filter((utub) => utub.name.toLowerCase().includes(query))
      : [];
    options.replaceChildren();
    for (const utub of matches) {
      const option = document.createElement("div");
      option.className = "utubPinsOption";
      option.setAttribute("role", "option");
      option.setAttribute("tabindex", "-1");
      option.setAttribute("data-utub-id", String(utub.id));
      option.textContent = utub.name;
      options.append(option);
    }
    options.hidden = matches.length === 0;
    input.setAttribute("aria-expanded", String(matches.length > 0));
    noMatch.textContent =
      showList && pinnable.length > 0 && matches.length === 0
        ? strings().UTUB_PINS_NO_MATCH
        : "";
    roving.resetRovingEntry();
  };

  input.addEventListener("input", () => {
    if (isCapped()) input.value = "";
    rememberTyped({ input });
    renderOptions();
  });
  for (const type of ["keyup", "click", "select"]) {
    input.addEventListener(type, () => rememberTyped({ input }));
  }
  input.addEventListener("focus", () => {
    // Keeps the input and its first options visible when the mobile soft
    // keyboard shrinks the sheet. Nothing focuses the input on open.
    if (typeof input.scrollIntoView === "function") {
      input.scrollIntoView({ block: "nearest" });
    }
  });
  input.addEventListener("keydown", (event) => {
    if (event.key !== KEYS.ENTER || event.isComposing) return;
    event.preventDefault();
    const first = options.querySelector<HTMLElement>(".utubPinsOption");
    if (first === null) return;
    activate({ utubID: Number(first.getAttribute("data-utub-id")) });
  });
  options.addEventListener("click", (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const option = target.closest<HTMLElement>(".utubPinsOption");
    if (option === null) return;
    activate({ utubID: Number(option.getAttribute("data-utub-id")) });
  });

  // First Escape (text present or an option focused) clears the filter and is
  // stopped; with nothing to clear it passes through so the popover closes.
  picker.addEventListener("keydown", (event) => {
    if (event.key !== KEYS.ESCAPE) return;
    const target = event.target;
    const onOption =
      target instanceof Element && target.closest(".utubPinsOption") !== null;
    if (!onOption && input.value === "") return;
    event.stopPropagation();
    event.preventDefault();
    input.value = "";
    rememberTyped({ input });
    renderOptions();
    input.focus();
  });

  roving.attachKeyListeners();
  renderOptions();

  return { element: picker, cleanup: () => roving.detachKeyListeners() };
}

function buildBody({
  container,
  ctx,
}: {
  container: HTMLElement;
  ctx: SectionContext;
}): () => void {
  const pinned = pinnedUtubs();

  const root = document.createElement("div");
  root.className = "utubPins";

  const counter = document.createElement("p");
  counter.className = "utubPinsCounter";
  counter.textContent = fill({
    template: strings().UTUB_PINS_COUNTER,
    count: pinned.length,
  });
  const desc = document.createElement("p");
  desc.className = "panelSettingsRowDesc";
  desc.textContent = strings().UTUB_PINS_DESC;
  root.append(counter, desc);

  if (lastNotice !== null) {
    // Plain text, not role=alert: the shell live region already announces it.
    const notice = document.createElement("p");
    notice.className = "utubPinsNotice";
    notice.textContent = lastNotice;
    root.append(notice);
  }

  if (pinned.length === 0) {
    const empty = document.createElement("p");
    empty.className = "utubPinsHint";
    empty.textContent = strings().UTUB_PINS_EMPTY_HINT;
    root.append(empty);
  } else {
    root.append(buildPinnedList({ ctx }));
  }

  const picker = buildPicker({ ctx });
  root.append(picker.element);
  container.append(root);
  return picker.cleanup;
}

// Section-owned re-render (the shell does not re-render a global section after
// an ok save). Disposes the previous render first, so a listener is never leaked
// or double-disposed.
function renderBody(): void {
  const container = currentContainer;
  const ctx = currentCtx;
  if (container === null || ctx === null) return;
  const active = document.activeElement;
  const focusedId =
    active instanceof HTMLElement && container.contains(active)
      ? active.id
      : "";

  runCleanup();
  container.replaceChildren();
  currentCleanup = buildBody({ container, ctx });

  if (focusedId === "") return;
  const restored = elementById(focusedId);
  restored?.focus();
  if (restored instanceof HTMLInputElement)
    restoreSelection({ input: restored });
}

function render({
  container,
  ctx,
}: {
  container: HTMLElement;
  ctx: SectionContext;
}): () => void {
  currentContainer = container;
  currentCtx = ctx;
  renderGeneration += 1;
  renderBody();
  // One stable function: it always disposes whichever render is live.
  return () => {
    runCleanup();
    const generation = renderGeneration;
    // A shell re-render calls this and then render() in the same tick; only a
    // real teardown (popover closed) leaves the generation unchanged.
    queueMicrotask(() => {
      if (generation !== renderGeneration) return;
      filterText = "";
      selectionStart = null;
      selectionEnd = null;
      lastNotice = null;
    });
  };
}

// ---------------------------------------------------------------------------
// Focus (by stable id)
// ---------------------------------------------------------------------------

function focusInput(): void {
  const input = elementById(INPUT_ID);
  if (!(input instanceof HTMLInputElement)) return;
  input.focus();
  restoreSelection({ input });
}

function applyFocusPlan({
  plan,
  inputHadFocus,
}: {
  plan: FocusPlan | null;
  inputHadFocus: boolean;
}): void {
  if (plan === null) return;
  if (plan.kind === "pick" || inputHadFocus) {
    focusInput();
    return;
  }
  if (lastOutcome === "failed") {
    const acted = elementById(plan.actedId);
    if (acted !== null) {
      acted.focus();
      return;
    }
  }
  for (const id of plan.candidates) {
    const candidate = elementById(id);
    if (candidate === null) continue;
    candidate.focus();
    return;
  }
  focusInput();
}

// ---------------------------------------------------------------------------
// Save
// ---------------------------------------------------------------------------

function isPinPatch(
  patch: SectionPatch,
): patch is { utubID: number; pinned: boolean } {
  return typeof patch.utubID === "number" && typeof patch.pinned === "boolean";
}

type PinsResponse = Awaited<ReturnType<typeof getAllUTubs>>;

// getAllUTubs raced against PATCH_TIMEOUT_MS; a timeout takes the same branch as
// a failure.
async function fetchServerUtubs(): Promise<PinsResponse["utubs"] | null> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const response = await Promise.race([
      Promise.resolve(getAllUTubs()),
      new Promise<never>((_resolve, reject) => {
        timer = setTimeout(
          () => reject(new Error("getAllUTubs timed out")),
          PATCH_TIMEOUT_MS,
        );
      }),
    ]);
    if (!Array.isArray(response?.utubs)) return null;
    return response.utubs;
  } catch (error) {
    log("reseeding pins failed", error);
    return null;
  } finally {
    clearTimeout(timer);
  }
}

// Brings the store, the deck and (via the post-settle render) the section in line
// with the server after a stale-tab cap or a missing UTub. A failed or timed-out
// fetch leaves the store as it was.
async function reseedPins(): Promise<void> {
  const serverUtubs = await fetchServerUtubs();
  if (serverUtubs === null) return;

  const serverPinned = new Map(
    serverUtubs.map((utub) => [utub.id, utub.isPinned]),
  );
  for (const utub of getState().utubs) {
    const isPinned = serverPinned.get(utub.id);
    if (isPinned !== undefined && isPinned !== utub.isPinned) {
      setUTubRowPinned({ utubID: utub.id, isPinned });
    }
  }
  // A UTub the server no longer lists is purged synchronously (before the
  // post-settle render reads the store). Only the active one goes on through
  // the existing removal contract, with its banner and mobile announcement.
  // Only a store-pinned UTub is purged here: an unpinned one the response omits
  // may have been created or joined in this tab after the fetch began.
  for (const utub of [...getState().utubs]) {
    if (serverPinned.has(utub.id) || !utub.isPinned) continue;
    purgeGoneUtub({ utubID: utub.id });
  }
}

function purgeGoneUtub({ utubID }: { utubID: number }): void {
  const wasActive = getState().activeUTubID === utubID;
  purgeUTubLocally({ utubID });
  if (wasActive) handleActiveUTubGone({ utubID });
}

// The helper is the only place that clears the in-flight flag. It runs as a
// macrotask, after the shell's own error render (inside sink.report, while the
// queue still has work) and the queue's finally, so on the error path the shell
// render still sees the flag set (controls aria-disabled).
function settleAfterSave(): void {
  inFlight = false;
  const plan = focusPlan;
  focusPlan = null;
  if (
    plan?.kind === "pick" &&
    lastOutcome === "ok" &&
    filterText === plan.submittedText
  ) {
    filterText = "";
    selectionStart = null;
    selectionEnd = null;
  }
  const container = currentContainer;
  if (container === null || !container.isConnected) return;
  const active = document.activeElement;
  const inputHadFocus =
    active instanceof HTMLElement &&
    container.contains(active) &&
    active.id === INPUT_ID;
  renderBody();
  applyFocusPlan({ plan, inputHadFocus });
}

async function save({
  patch,
}: {
  utubID: number | null;
  patch: SectionPatch;
}): Promise<SaveResult> {
  try {
    lastOutcome = "failed";
    if (!isPinPatch(patch)) return { outcome: "error", resync: false };
    const { utubID, pinned } = patch;
    const name =
      getState().utubs.find((utub) => utub.id === utubID)?.name ?? "";

    const result = await patchUtubPin({ utubID, pinned });

    if (result.outcome === "ok") {
      lastOutcome = "ok";
      lastNotice = null;
      setUTubRowPinned({ utubID, isPinned: result.isPinned });
      const notices = [
        fill({
          template: result.isPinned
            ? strings().UTUB_PINS_PINNED_NOTICE
            : strings().UTUB_PINS_UNPINNED_NOTICE,
          name,
          count: result.pinnedCount,
        }),
      ];
      // The reaches-cap test reads the response's live count, not the store.
      if (result.isPinned && result.pinnedCount >= maxPinned()) {
        notices.push(strings().UTUB_PINS_CAP_REACHED);
      }
      return { outcome: "ok", notice: notices.join(NOTICE_JOINER) };
    }

    if (result.outcome === "cap" || result.outcome === "gone") {
      lastOutcome = result.outcome;
      const notice =
        result.outcome === "cap"
          ? strings().UTUB_PINS_CAP_REACHED
          : strings().UTUB_PINS_UTUB_GONE;
      lastNotice = notice;
      // The 404 target goes first, so a failed or timed-out reseed still drops it.
      if (result.outcome === "gone") purgeGoneUtub({ utubID });
      await reseedPins();
      return { outcome: "error", resync: false, notice };
    }

    // Network, 400, 5xx, 429, a 409 with another code, a non-JSON 404 or a
    // malformed 200: nothing changes and the shell's own text is used.
    return { outcome: "error", resync: false };
  } catch (error) {
    log("pin save threw", error);
    return { outcome: "error", resync: false };
  } finally {
    setTimeout(settleAfterSave, 0);
  }
}

/**
 * Registers the "Pinned UTubs" section on the UTubs gear, after "Your UTub
 * list". Returns the unregister function.
 */
export function registerUtubPinsSection(): () => void {
  resetModuleState();
  const unregister = registerSection({
    id: SECTION_ID,
    panel: "utubs",
    scope: "user",
    userKind: "global",
    title: APP_CONFIG.strings.UTUB_PINS_SECTION_TITLE,
    render,
    save,
  });
  return () => {
    resetModuleState();
    unregister();
  };
}
