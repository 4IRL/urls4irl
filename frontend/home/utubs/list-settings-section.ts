import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { getState } from "../../store/app-store.js";
import type { UtubSortValue } from "../../types/preferences.js";
import { isUtubSortValue } from "../../types/preferences.js";
import { patchUtubListPreferences } from "../panel-settings/client.js";
import type { EchoedListPreferences } from "../panel-settings/client.js";
import { rerenderSectionIfIdle } from "../panel-settings/index.js";
import { registerSection } from "../panel-settings/registry.js";
import {
  buildRowLabel,
  buildSwitchButton,
} from "../panel-settings/row-controls.js";
import type {
  PanelSection,
  SaveResult,
  SectionContext,
  SectionPatch,
} from "../panel-settings/types.js";
import {
  applyListPreference,
  clearAllEdits,
  getPrefsVersion,
  hasOutstandingEdit,
  isLatestEdit,
  latestToken,
  LIST_PREFERENCE_FIELDS,
  markEdit,
  recordSavedPreference,
  reseedListPreferences,
  setReseedListener,
  settleEdit,
} from "./list-preferences.js";
import type {
  ListPreferenceField,
  ListPreferenceUpdate,
} from "./list-preferences.js";
import { reorderUTubDeck, scrollActiveUTubIntoViewIfHidden } from "./sort.js";
import { getAllUTubs } from "./utils.js";

const log = debug("utub-list-settings");

const SECTION_ID = "utubs-list";
const NOTICE_JOINER = ". ";

interface SortOption {
  value: UtubSortValue;
  label: string;
}

interface SwitchRow {
  field: "showRowCounts" | "showListTotals";
  switchId: string;
  labelId: string;
  descId: string;
  label: string;
  desc: string;
  shownNotice: string;
  hiddenNotice: string;
}

const SORT_SELECT_ID = "utub-list-sort";
const SORT_LABEL_ID = "utub-list-sort-label";

const strings = (): Record<string, string> => APP_CONFIG.strings;

function sortOptions(): SortOption[] {
  return [
    {
      value: "recent_activity",
      label: strings().UTUB_LIST_SETTINGS_SORT_OPTION_RECENT,
    },
    {
      value: "last_opened",
      label: strings().UTUB_LIST_SETTINGS_SORT_OPTION_OPENED,
    },
    {
      value: "name_az",
      label: strings().UTUB_LIST_SETTINGS_SORT_OPTION_NAME_AZ,
    },
    {
      value: "newest_created",
      label: strings().UTUB_LIST_SETTINGS_SORT_OPTION_NEWEST,
    },
    {
      value: "oldest_created",
      label: strings().UTUB_LIST_SETTINGS_SORT_OPTION_OLDEST,
    },
  ];
}

function switchRows(): SwitchRow[] {
  return [
    {
      field: "showRowCounts",
      switchId: "utub-list-row-counts",
      labelId: "utub-list-row-counts-label",
      descId: "utub-list-row-counts-desc",
      label: strings().UTUB_LIST_SETTINGS_ROW_COUNTS_LABEL,
      desc: strings().UTUB_LIST_SETTINGS_ROW_COUNTS_DESC,
      shownNotice: strings().UTUB_LIST_SETTINGS_ROW_COUNTS_SHOWN_NOTICE,
      hiddenNotice: strings().UTUB_LIST_SETTINGS_ROW_COUNTS_HIDDEN_NOTICE,
    },
    {
      field: "showListTotals",
      switchId: "utub-list-list-totals",
      labelId: "utub-list-list-totals-label",
      descId: "utub-list-list-totals-desc",
      label: strings().UTUB_LIST_SETTINGS_LIST_TOTALS_LABEL,
      desc: strings().UTUB_LIST_SETTINGS_LIST_TOTALS_DESC,
      shownNotice: strings().UTUB_LIST_SETTINGS_LIST_TOTALS_SHOWN_NOTICE,
      hiddenNotice: strings().UTUB_LIST_SETTINGS_LIST_TOTALS_HIDDEN_NOTICE,
    },
  ];
}

// Spoken form of an option label for the announcement ("Name A–Z" is read as
// "Name A to Z").
function spokenLabel(label: string): string {
  return label.replace("–", " to ");
}

function noticeFor({
  field,
  value,
}: {
  field: ListPreferenceField;
  value: unknown;
}): string | undefined {
  if (field === "utubSort") {
    const option = sortOptions().find((candidate) => candidate.value === value);
    if (option === undefined) return undefined;
    return `${strings().UTUB_LIST_SETTINGS_SORT_NOTICE_PREFIX}${spokenLabel(option.label)}`;
  }
  const row = switchRows().find((candidate) => candidate.field === field);
  if (row === undefined || typeof value !== "boolean") return undefined;
  return value ? row.shownNotice : row.hiddenNotice;
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

function buildSortRow({ ctx }: { ctx: SectionContext }): HTMLElement {
  const row = document.createElement("div");
  row.className = "panelSettingsRow";
  row.append(
    buildRowLabel({
      titleId: SORT_LABEL_ID,
      title: strings().UTUB_LIST_SETTINGS_SORT_LABEL,
      descId: `${SORT_LABEL_ID}-desc`,
    }),
  );

  const wrap = document.createElement("div");
  wrap.className = "panelSettingsSelectWrap";
  const select = document.createElement("select");
  select.className = "panelSettingsSelect";
  select.id = SORT_SELECT_ID;
  select.setAttribute("aria-labelledby", SORT_LABEL_ID);
  for (const option of sortOptions()) {
    const optionElement = document.createElement("option");
    optionElement.value = option.value;
    optionElement.textContent = option.label;
    select.append(optionElement);
  }
  // Read from the store on every render, never from a closure copy.
  select.value = getState().preferences.utubSort;

  select.addEventListener("change", () => {
    if (!ctx.canWrite) {
      select.value = getState().preferences.utubSort;
      return;
    }
    const picked = select.value;
    if (!isUtubSortValue(picked)) return;
    markEdit("utubSort");
    ctx.submit({ patch: { utubSort: picked }, debounce: true });
  });

  wrap.append(select);
  row.append(wrap);
  return row;
}

function buildSwitchRow({
  row,
  ctx,
}: {
  row: SwitchRow;
  ctx: SectionContext;
}): HTMLElement {
  const rowElement = document.createElement("div");
  rowElement.className = "panelSettingsRow";
  const label = buildRowLabel({
    titleId: row.labelId,
    title: row.label,
    descId: row.descId,
    desc: row.desc,
  });
  const switchButton = buildSwitchButton({
    id: row.switchId,
    labelledBy: row.labelId,
  });
  switchButton.setAttribute("aria-describedby", row.descId);
  switchButton.setAttribute(
    "aria-checked",
    String(getState().preferences[row.field]),
  );
  switchButton.addEventListener("click", () => {
    if (!ctx.canWrite) return;
    const next = switchButton.getAttribute("aria-checked") !== "true";
    switchButton.setAttribute("aria-checked", String(next));
    markEdit(row.field);
    ctx.submit({ patch: { [row.field]: next } });
  });
  rowElement.append(label, switchButton);
  return rowElement;
}

function render({
  container,
  ctx,
}: {
  container: HTMLElement;
  ctx: SectionContext;
}): void {
  container.append(
    buildSortRow({ ctx }),
    ...switchRows().map((row) => buildSwitchRow({ row, ctx })),
  );
}

// ---------------------------------------------------------------------------
// Save
// ---------------------------------------------------------------------------

// Fields whose echoed value was saved to the store while a newer edit of the
// same field was outstanding (the store is ahead of the deck).
const baselineAhead = new Set<ListPreferenceField>();

function fieldsIn({ patch }: { patch: SectionPatch }): ListPreferenceField[] {
  return LIST_PREFERENCE_FIELDS.filter((field) =>
    Object.prototype.hasOwnProperty.call(patch, field),
  );
}

// Narrows a field of a preferences object into the typed update union.
function toUpdate({
  preferences,
  field,
}: {
  preferences: EchoedListPreferences;
  field: ListPreferenceField;
}): ListPreferenceUpdate {
  if (field === "utubSort") return { field, value: preferences.utubSort };
  return { field, value: preferences[field] };
}

function applyToDeck(update: ListPreferenceUpdate): void {
  applyListPreference(update);
  if (update.field === "utubSort") {
    reorderUTubDeck(update.value);
    scrollActiveUTubIntoViewIfHidden();
  }
}

function reapplyAheadFields(): void {
  const stored = getState().preferences;
  for (const field of LIST_PREFERENCE_FIELDS) {
    if (!baselineAhead.has(field)) continue;
    applyToDeck(toUpdate({ preferences: stored, field }));
  }
  baselineAhead.clear();
}

// The server may have committed a timed-out PATCH, and a global section has no
// shell resync. One best-effort, guarded resync; never rebuilds the deck.
async function resyncAfterTimeout(): Promise<void> {
  const capturedVersion = getPrefsVersion();
  try {
    const response = await getAllUTubs();
    const changed = reseedListPreferences({
      preferences: response.preferences,
      capturedVersion,
    });
    if (changed.includes("utubSort")) {
      reorderUTubDeck(getState().preferences.utubSort);
      scrollActiveUTubIntoViewIfHidden();
    }
  } catch (error) {
    log("resync after timeout failed", error);
  }
}

async function save({
  patch,
}: {
  utubID: number | null;
  patch: SectionPatch;
}): Promise<SaveResult> {
  const fields = fieldsIn({ patch });
  const sent = new Map<ListPreferenceField, number | null>();
  for (const field of fields) sent.set(field, latestToken(field));

  const outcome = await patchUtubListPreferences({ patch });

  if (outcome.outcome === "failed") {
    // The queue drops the other pending edits on error without running their
    // save callbacks, so every token is cleared here. The store was never
    // written optimistically; the shell's error re-render shows its values.
    clearAllEdits();
    reapplyAheadFields();
    if (outcome.timedOut) void resyncAfterTimeout();
    return outcome.result;
  }

  const notices: string[] = [];
  for (const field of fields) {
    const update = toUpdate({ preferences: outcome.preferences, field });
    const token = sent.get(field) ?? null;
    // Checked before settleEdit, which clears the mark. A null token fails
    // closed: the echo is treated as superseded.
    const isLatest = token !== null && isLatestEdit({ field, token });
    // The saved baseline is always recorded, so a later failure or a rebuild
    // reseed can never lose what the server committed.
    recordSavedPreference(update);
    if (token !== null) settleEdit({ field, token });
    if (!isLatest) {
      baselineAhead.add(field);
      continue;
    }
    baselineAhead.delete(field);
    applyToDeck(update);
    const notice = noticeFor(update);
    if (notice !== undefined) notices.push(notice);
  }

  return notices.length > 0
    ? { outcome: "ok", notice: notices.join(NOTICE_JOINER) }
    : { outcome: "ok" };
}

function onReseed(): void {
  // A later failed save falls back to a value the user has seen, so only
  // re-render when nothing is being edited.
  if (LIST_PREFERENCE_FIELDS.some((field) => hasOutstandingEdit(field))) return;
  rerenderSectionIfIdle({ sectionId: SECTION_ID });
}

/**
 * Registers the "Your UTub list" section on the UTubs gear: the user's own list
 * sort, row counts and totals. Returns the unregister function.
 */
export function registerUtubListSettingsSection(): () => void {
  baselineAhead.clear();
  const section: PanelSection = {
    id: SECTION_ID,
    panel: "utubs",
    scope: "user",
    userKind: "global",
    title: APP_CONFIG.strings.UTUB_LIST_SETTINGS_SECTION_TITLE,
    render,
    save,
  };
  const unregister = registerSection(section);
  setReseedListener(onReseed);
  return () => {
    setReseedListener(null);
    baselineAhead.clear();
    unregister();
  };
}
