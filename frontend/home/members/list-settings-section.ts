import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { AppEvents, emit } from "../../lib/event-bus.js";
import { getState, setState, subscribe } from "../../store/app-store.js";
import type { MemberSortValue } from "../../types/preferences.js";
import { isMemberSortValue } from "../../types/preferences.js";
import { announceSettingsStatus } from "../panel-settings/announce.js";
import { patchMemberListPreferences } from "../panel-settings/client.js";
import {
  closePanelSettings,
  rerenderSectionIfIdle,
} from "../panel-settings/index.js";
import { registerSection } from "../panel-settings/registry.js";
import { buildRowLabel } from "../panel-settings/row-controls.js";
import type {
  PanelSection,
  SaveResult,
  SectionContext,
  SectionPatch,
} from "../panel-settings/types.js";
import { updateUTubOnFindingStaleData } from "../utubs/stale-data.js";
import { reorderMemberDeck } from "./deck.js";

const log = debug("member-list-settings");

const SECTION_ID = "members-list";
const SORT_SELECT_ID = "members-list-sort";
const SORT_LABEL_ID = "members-list-sort-label";
const SORT_DESC_ID = "members-list-sort-desc";
const SORT_NOTE_ID = "members-list-sort-note";
const JOINED_SORT: MemberSortValue = "recently_joined";
const TRANSFER_ROW_ID = "members-transfer-row";
const TRANSFER_HEADING_ID = "members-transfer-heading";
const TRANSFER_BTN_ID = "members-transfer-owner";
const GEAR_ID = "memberBtnSettings";
const ADD_OPEN = "member-add-open";

interface SortOption {
  value: MemberSortValue;
  label: string;
}

const strings = (): Record<string, string> => APP_CONFIG.strings;

function sortOptions(): SortOption[] {
  return [
    { value: "name_az", label: strings().MEMBERS_LIST_SORT_OPTION_NAME_AZ },
    { value: "role_then_name", label: strings().MEMBERS_LIST_SORT_OPTION_ROLE },
    {
      value: "recently_joined",
      label: strings().MEMBERS_LIST_SORT_OPTION_JOINED,
    },
  ];
}

// Spoken form of an option label for the announcement ("Name A–Z" is read as
// "Name A to Z").
function spokenLabel(label: string): string {
  return label.replace("–", " to ");
}

function noticeFor({
  memberSort,
  prefix,
}: {
  memberSort: MemberSortValue;
  prefix: string;
}): string | undefined {
  const option = sortOptions().find(
    (candidate) => candidate.value === memberSort,
  );
  if (option === undefined) return undefined;
  return `${prefix}${spokenLabel(option.label)}`;
}

// ---------------------------------------------------------------------------
// Edit token (single field: memberSort)
// ---------------------------------------------------------------------------
// Net-new module state: list-preferences.ts is keyed by the UTubs fields only.

let editCounter = 0;
let latestEdit: number | null = null;
// The echoed value was saved to the store while a newer edit was outstanding
// (the store is ahead of the deck).
let baselineAhead = false;

function markEdit(): void {
  editCounter += 1;
  latestEdit = editCounter;
}

function isLatestEdit({ token }: { token: number }): boolean {
  return latestEdit === token;
}

function settleEdit({ token }: { token: number }): void {
  if (latestEdit === token) latestEdit = null;
}

function hasOutstandingEdit(): boolean {
  return latestEdit !== null;
}

function clearEdits(): void {
  latestEdit = null;
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

// Adds or removes only the note's token, directly after the description id, so
// the render path and the toggle path agree on [desc, note, status].
function setNoteDescribed({
  select,
  shown,
}: {
  select: HTMLSelectElement;
  shown: boolean;
}): void {
  const tokens = (select.getAttribute("aria-describedby") ?? "")
    .split(" ")
    .filter((token) => token !== "" && token !== SORT_NOTE_ID);
  if (shown) {
    const descIndex = tokens.indexOf(SORT_DESC_ID);
    if (descIndex === -1) tokens.push(SORT_NOTE_ID);
    else tokens.splice(descIndex + 1, 0, SORT_NOTE_ID);
  }
  select.setAttribute("aria-describedby", tokens.join(" "));
}

function render({
  container,
  ctx,
}: {
  container: HTMLElement;
  ctx: SectionContext;
}): void {
  const row = document.createElement("div");
  row.className = "panelSettingsRow";
  const label = buildRowLabel({
    titleId: SORT_LABEL_ID,
    title: strings().MEMBERS_LIST_SORT_LABEL,
    descId: SORT_DESC_ID,
    desc: strings().MEMBERS_LIST_SORT_DESC,
  });
  const note = document.createElement("div");
  note.className = "panelSettingsRowDesc";
  note.id = SORT_NOTE_ID;
  note.textContent = strings().MEMBERS_LIST_SORT_JOINED_NOTE;
  label.append(note);
  row.append(label);

  const wrap = document.createElement("div");
  wrap.className = "panelSettingsSelectWrap";
  const select = document.createElement("select");
  select.className = "panelSettingsSelect";
  select.id = SORT_SELECT_ID;
  select.setAttribute("aria-labelledby", SORT_LABEL_ID);
  select.setAttribute("aria-describedby", SORT_DESC_ID);
  for (const option of sortOptions()) {
    const optionElement = document.createElement("option");
    optionElement.value = option.value;
    optionElement.textContent = option.label;
    select.append(optionElement);
  }
  // Read from the store on every render, never from a closure copy.
  select.value = getState().preferences.memberSort;

  const syncNote = (): void => {
    const shown = select.value === JOINED_SORT;
    note.hidden = !shown;
    setNoteDescribed({ select, shown });
  };
  syncNote();

  select.addEventListener("change", () => {
    if (!ctx.canWrite) {
      select.value = getState().preferences.memberSort;
      syncNote();
      return;
    }
    const picked = select.value;
    if (!isMemberSortValue(picked)) return;
    markEdit();
    setState({ memberSortVersion: getState().memberSortVersion + 1 });
    syncNote();
    ctx.submit({ patch: { memberSort: picked }, debounce: true });
  });

  wrap.append(select);
  row.append(wrap);
  container.append(row);
  container.append(buildTransferRow());
}

// ---------------------------------------------------------------------------
// Transfer ownership action
// ---------------------------------------------------------------------------
// The owner-only entry to the transfer modal. The row is always rendered and its
// visibility follows the store in place (see syncTransferRow), so a membership
// change never needs a re-render that could clobber a pending sort edit.

// Owner of the active UTub with at least one other member to hand it to.
function canTransferOwnership(): boolean {
  const state = getState();
  if (!state.isCurrentUserOwner) return false;
  return state.members.some((member) => member.id !== state.utubOwnerID);
}

function transferRowElement(): HTMLElement | null {
  return document.getElementById(TRANSFER_ROW_ID);
}

// Trailing diagonal arrow (bootstrap-icons arrow-up-right, inlined because the
// icon font is not loaded): signals that the button opens something else
// instead of changing a setting in place. Decorative; the label names it.
const SVG_NS = "http://www.w3.org/2000/svg";
const OPENS_ARROW_PATH =
  "M14 2.5a.5.5 0 0 0-.5-.5h-6a.5.5 0 0 0 0 1h4.793L2.146 13.146a.5.5 0 0 0 .708.708L13 3.707V8.5a.5.5 0 0 0 1 0z";

function buildOpensArrow(): SVGElement {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "panelSettingsActionIcon");
  svg.setAttribute("viewBox", "0 0 16 16");
  svg.setAttribute("width", "16");
  svg.setAttribute("height", "16");
  svg.setAttribute("fill", "currentColor");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("focusable", "false");
  const path = document.createElementNS(SVG_NS, "path");
  path.setAttribute("fill-rule", "evenodd");
  path.setAttribute("d", OPENS_ARROW_PATH);
  svg.append(path);
  return svg;
}

function buildTransferRow(): HTMLElement {
  const row = document.createElement("div");
  row.className = "panelSettingsRow panelSettingsRow--subsection";
  row.id = TRANSFER_ROW_ID;
  row.setAttribute("role", "group");
  row.setAttribute("aria-labelledby", TRANSFER_HEADING_ID);
  row.hidden = !canTransferOwnership();

  const heading = document.createElement("div");
  heading.className = "panelSettingsSubheading";
  heading.id = TRANSFER_HEADING_ID;
  heading.textContent = strings().MEMBERS_TRANSFER_SECTION_TITLE;
  row.append(heading);

  const button = document.createElement("button");
  button.type = "button";
  button.id = TRANSFER_BTN_ID;
  button.className = "panelSettingsActionBtn";
  const label = document.createElement("span");
  label.textContent = strings().TRANSFER_OWNER_ACTION;
  button.append(label, buildOpensArrow());
  // The member-add combobox gates the deck's other member controls; the
  // transfer modal would strand its staged chips just like a removal modal.
  const addOpen = (): boolean =>
    document.getElementById("MemberDeck")?.classList.contains(ADD_OPEN) ===
    true;
  if (addOpen()) button.setAttribute("aria-disabled", "true");
  button.addEventListener("click", () => {
    if (addOpen()) return;
    if (!canTransferOwnership()) return;
    // Close the gear first (focus returns to it), then open the modal with the
    // gear as the opener so a plain dismissal lands back on the gear.
    closePanelSettings();
    emit(AppEvents.TRANSFER_PICKER_REQUESTED, { opener: `#${GEAR_ID}` });
  });
  row.append(button);
  return row;
}

// Shows or hides the open row to match the store. The row's own button never
// keeps focus while hidden: it moves to the sort select first.
function syncTransferRow(): void {
  const row = transferRowElement();
  if (row === null) return;
  const shown = canTransferOwnership();
  if (!shown && row.contains(document.activeElement)) {
    (
      document.getElementById(SORT_SELECT_ID) ??
      document.getElementById(GEAR_ID)
    )?.focus();
  }
  row.hidden = !shown;
}

// ---------------------------------------------------------------------------
// Save
// ---------------------------------------------------------------------------

function reapplyDeckToStore(): void {
  const state = getState();
  reorderMemberDeck({
    members: state.members,
    memberSort: state.preferences.memberSort,
  });
}

function reapplyIfAhead(): void {
  if (!baselineAhead) return;
  reapplyDeckToStore();
  baselineAhead = false;
}

// The server may have committed a timed-out PATCH. One awaited resync of the
// active UTub (it writes the store and reorders the deck silently); the
// announcement is gated on observed state, since the resync can return early
// without applying anything.
async function resyncAfterTimeout(): Promise<void> {
  const before = getState();
  const sortBefore = before.preferences.memberSort;
  const activeUTubID = before.activeUTubID;
  // With no active UTub no resync runs: the select keeps showing the saved store
  // value until the next UTub load refreshes the preferences.
  if (activeUTubID !== null) {
    try {
      await updateUTubOnFindingStaleData({ utubID: activeUTubID });
    } catch (error) {
      log("resync after timeout failed", error);
    }
  }
  if (hasOutstandingEdit()) return;
  reapplyIfAhead();
  const sortAfter = getState().preferences.memberSort;
  if (sortAfter === sortBefore) return;
  const notice = noticeFor({
    memberSort: sortAfter,
    prefix: strings().MEMBERS_LIST_SORT_NOTICE_PREFIX,
  });
  if (notice !== undefined) announceSettingsStatus({ message: notice });
}

async function save({
  patch,
}: {
  utubID: number | null;
  patch: SectionPatch;
}): Promise<SaveResult> {
  const sentToken = latestEdit;

  const outcome = await patchMemberListPreferences({ patch });

  if (outcome.outcome === "failed") {
    // The queue drops other pending edits on error without running their save
    // callbacks, so the token is cleared here. The store was never written
    // optimistically; the shell's error re-render shows its value.
    clearEdits();
    if (outcome.timedOut) {
      await resyncAfterTimeout();
    } else {
      reapplyIfAhead();
    }
    return outcome.result;
  }

  const { memberSort } = outcome.preferences;
  // Checked before settleEdit, which clears the mark. A null token fails closed:
  // the echo is treated as superseded.
  const isLatest = sentToken !== null && isLatestEdit({ token: sentToken });
  // The saved baseline is always recorded, so a later failure can never lose
  // what the server committed.
  const state = getState();
  setState({
    preferences: { ...state.preferences, memberSort },
    memberSortVersion: state.memberSortVersion + 1,
  });
  if (sentToken !== null) settleEdit({ token: sentToken });
  if (!isLatest) {
    baselineAhead = true;
    return { outcome: "ok" };
  }
  baselineAhead = false;
  reorderMemberDeck({ members: getState().members, memberSort });
  const notice = noticeFor({
    memberSort,
    prefix: strings().MEMBERS_LIST_SORT_NOTICE_PREFIX,
  });
  return notice === undefined ? { outcome: "ok" } : { outcome: "ok", notice };
}

/**
 * Registers the "Your member list" section on the Members gear: the viewer's
 * own member sort, shared by every UTub. Returns the unregister function.
 */
export function registerMembersListSettingsSection(): () => void {
  baselineAhead = false;
  latestEdit = null;
  let lastSeenSort = getState().preferences.memberSort;
  // Refreshes write memberSort without going through this section, so an idle
  // open section re-renders on a change. A pending edit is never replaced, and
  // the section's own writes run under a token, so they never re-render it.
  const unsubscribe = subscribe(() => {
    syncTransferRow();
    const current = getState().preferences.memberSort;
    if (current === lastSeenSort) return;
    lastSeenSort = current;
    if (hasOutstandingEdit()) return;
    rerenderSectionIfIdle({ sectionId: SECTION_ID });
  });
  const section: PanelSection = {
    id: SECTION_ID,
    panel: "members",
    scope: "user",
    userKind: "global",
    title: APP_CONFIG.strings.MEMBERS_LIST_SETTINGS_SECTION_TITLE,
    render,
    save,
  };
  const unregister = registerSection(section);
  return () => {
    unsubscribe();
    baselineAhead = false;
    latestEdit = null;
    unregister();
  };
}
