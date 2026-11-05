import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import {
  TAG_OVERRIDE_KEYS,
  type TagDisplayKey,
  resolveTagDisplaySettings,
} from "../../logic/tag-display-settings.js";
import { getState, setState } from "../../store/app-store.js";
import type { AppState } from "../../store/app-store.js";
import {
  EMPTY_MEMBER_SETTINGS,
  resolveMemberSettings,
} from "../../types/settings.js";
import {
  patchMemberSettings,
  patchTagDisplayPreferences,
} from "../panel-settings/client.js";
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
import { updateUTubOnFindingStaleData } from "../utubs/stale-data.js";
import { applyClaimingModeChange } from "./tags.js";
import type { ModeChangeOutcome } from "./tags.js";

const log = debug("tags-personal-settings");

const SECTION_ID = "tags-personal";
const DEFAULT_PREFIX = "default.";
const OVERRIDE_PREFIX = "override.";

type ControlValue = string | boolean;

interface SelectOption {
  value: string;
  label: string;
}

interface RowSpec {
  key: TagDisplayKey;
  idBase: string;
  title: string;
  desc?: string;
  /** Select options, or null for a switch. */
  options: SelectOption[] | null;
  /** A nested row's note (shown while its parent switch resolves off). */
  note?: string;
  nested?: boolean;
}

interface BuiltControl {
  element: HTMLElement;
  /** Sets the shown value without firing the change handler. */
  setValue(value: ControlValue): void;
}

interface BuiltRow {
  row: HTMLElement;
  defaultControl: HTMLElement;
  overrideControl: HTMLElement;
  noteElement: HTMLElement | null;
  descId: string | null;
}

const strings = (): Record<string, string> => APP_CONFIG.strings;

function rowSpecs(): RowSpec[] {
  const text = strings();
  return [
    {
      key: "tagSort",
      idBase: "tagsPersonalSort",
      title: text.TAGS_PERSONAL_SETTINGS_SORT_LABEL,
      desc: text.TAGS_PERSONAL_SETTINGS_SORT_DESC,
      options: [
        {
          value: "most_in_view",
          label: text.TAGS_PERSONAL_SETTINGS_SORT_OPTION_MOST_IN_VIEW,
        },
        {
          value: "most_used",
          label: text.TAGS_PERSONAL_SETTINGS_SORT_OPTION_MOST_USED,
        },
        {
          value: "name_az",
          label: text.TAGS_PERSONAL_SETTINGS_SORT_OPTION_NAME_AZ,
        },
        {
          value: "newest",
          label: text.TAGS_PERSONAL_SETTINGS_SORT_OPTION_NEWEST,
        },
        {
          value: "oldest",
          label: text.TAGS_PERSONAL_SETTINGS_SORT_OPTION_OLDEST,
        },
      ],
    },
    {
      key: "tagMatchMode",
      idBase: "tagsPersonalMatch",
      title: text.TAGS_PERSONAL_SETTINGS_MATCH_LABEL,
      options: [
        { value: "all", label: text.TAGS_PERSONAL_SETTINGS_MATCH_OPTION_ALL },
        { value: "any", label: text.TAGS_PERSONAL_SETTINGS_MATCH_OPTION_ANY },
      ],
    },
    {
      key: "tagCountStyle",
      idBase: "tagsPersonalCount",
      title: text.TAGS_PERSONAL_SETTINGS_COUNT_LABEL,
      options: [
        {
          value: "in_view_total",
          label: text.TAGS_PERSONAL_SETTINGS_COUNT_OPTION_IN_VIEW_TOTAL,
        },
        {
          value: "total_only",
          label: text.TAGS_PERSONAL_SETTINGS_COUNT_OPTION_TOTAL_ONLY,
        },
        {
          value: "hidden",
          label: text.TAGS_PERSONAL_SETTINGS_COUNT_OPTION_HIDDEN,
        },
      ],
    },
    {
      key: "showTagsOnCollapsed",
      idBase: "tagsPersonalCollapsed",
      title: text.TAGS_PERSONAL_SETTINGS_COLLAPSED_LABEL,
      desc: text.TAGS_PERSONAL_SETTINGS_COLLAPSED_DESC,
      options: null,
    },
    {
      key: "collapsedTagsStyle",
      idBase: "tagsPersonalCollapsedStyle",
      title: text.TAGS_PERSONAL_SETTINGS_COLLAPSED_STYLE_LABEL,
      options: [
        {
          value: "one_line",
          label: text.TAGS_PERSONAL_SETTINGS_COLLAPSED_STYLE_OPTION_ONE_LINE,
        },
        {
          value: "all",
          label: text.TAGS_PERSONAL_SETTINGS_COLLAPSED_STYLE_OPTION_ALL,
        },
      ],
      note: text.TAGS_PERSONAL_SETTINGS_COLLAPSED_STYLE_ALL_WARNING,
      nested: true,
    },
    {
      key: "tagDropOpensUrl",
      idBase: "tagsPersonalDrop",
      title: text.TAGS_PERSONAL_SETTINGS_DROP_LABEL,
      desc: text.TAGS_PERSONAL_SETTINGS_DROP_DESC,
      options: null,
    },
  ];
}

function buildControl({
  id,
  labelledBy,
  describedBy,
  options,
  value,
  disabled,
  onChange,
}: {
  id: string;
  labelledBy: string;
  describedBy: string | null;
  options: SelectOption[] | null;
  value: ControlValue;
  disabled: boolean;
  onChange: (value: ControlValue) => void;
}): BuiltControl {
  if (options === null) {
    const switchButton = buildSwitchButton({ id, labelledBy });
    switchButton.setAttribute("aria-checked", String(value === true));
    if (describedBy !== null) {
      switchButton.setAttribute("aria-describedby", describedBy);
    }
    if (disabled) switchButton.setAttribute("aria-disabled", "true");
    switchButton.addEventListener("click", () => {
      if (switchButton.getAttribute("aria-disabled") === "true") return;
      const next = switchButton.getAttribute("aria-checked") !== "true";
      switchButton.setAttribute("aria-checked", String(next));
      onChange(next);
    });
    return {
      element: switchButton,
      setValue: (next) =>
        switchButton.setAttribute("aria-checked", String(next === true)),
    };
  }

  const wrap = document.createElement("div");
  wrap.className = "panelSettingsSelectWrap";
  const select = document.createElement("select");
  select.className = "panelSettingsSelect";
  select.id = id;
  select.setAttribute("aria-labelledby", labelledBy);
  if (describedBy !== null)
    select.setAttribute("aria-describedby", describedBy);
  for (const option of options) {
    const optionElement = document.createElement("option");
    optionElement.value = option.value;
    optionElement.textContent = option.label;
    select.append(optionElement);
  }
  select.value = String(value);
  if (disabled) select.setAttribute("aria-disabled", "true");
  let shownValue = String(value);
  select.addEventListener("change", () => {
    if (select.getAttribute("aria-disabled") === "true") {
      // aria-disabled does not stop a native select from changing.
      select.value = shownValue;
      return;
    }
    shownValue = select.value;
    onChange(select.value);
  });
  wrap.append(select);
  return {
    element: wrap,
    setValue: (next) => {
      shownValue = String(next);
      select.value = shownValue;
    },
  };
}

/** The interactive element inside a built control (the select or the switch). */
function interactiveOf(control: HTMLElement): HTMLElement {
  return control.querySelector<HTMLElement>("select") ?? control;
}

function buildTagRow({
  spec,
  defaultValue,
  overrideValue,
  inert,
  onDefaultChange,
  onOverrideChange,
  onUseDefault,
}: {
  spec: RowSpec;
  defaultValue: ControlValue;
  overrideValue: ControlValue | null;
  inert: boolean;
  onDefaultChange: (value: ControlValue) => void;
  onOverrideChange: (value: ControlValue) => void;
  onUseDefault: () => void;
}): BuiltRow {
  const text = strings();
  const { idBase } = spec;
  const labelId = `${idBase}Label`;
  const descId = spec.desc === undefined ? null : `${idBase}Desc`;
  const noteId = `${idBase}Note`;
  const scopeDefaultId = `${idBase}ScopeDefault`;
  const scopeOverrideId = `${idBase}ScopeOverride`;
  const overrideWrapId = `${idBase}OverrideWrap`;
  const linkId = `${idBase}RevealLink`;
  const overrideControlId = `${idBase}OverrideControl`;

  const row = document.createElement("div");
  row.className = spec.nested
    ? "panelSettingsRow tagsSettingsRow tagsSettingsRow--nested"
    : "panelSettingsRow tagsSettingsRow";
  row.dataset.tagSetting = spec.key;

  const label = buildRowLabel({
    titleId: labelId,
    title: spec.title,
    ...(descId !== null && spec.desc !== undefined
      ? { descId, desc: spec.desc }
      : {}),
  });
  let noteElement: HTMLElement | null = null;
  if (spec.note !== undefined) {
    noteElement = document.createElement("div");
    noteElement.className = "urlsSettingsHint";
    noteElement.id = noteId;
    noteElement.textContent = spec.note;
    noteElement.hidden = true;
    label.append(noteElement);
  }
  row.append(label);

  const controls = document.createElement("div");
  controls.className = "tagsSettingsControls";

  // The account default.
  const defaultGroup = document.createElement("div");
  defaultGroup.className = "tagsSettingsGroup";
  const defaultScope = document.createElement("span");
  defaultScope.className = "tagsSettingsScope";
  defaultScope.id = scopeDefaultId;
  defaultScope.textContent = text.TAGS_PERSONAL_SETTINGS_ALL_UTUBS_LABEL;
  let currentDefault = defaultValue;
  // True once the override control has been changed (or rendered from a stored
  // override); a revealed-but-unsaved override control mirrors the default.
  let overrideStored = overrideValue !== null;
  const defaultControl = buildControl({
    id: `${idBase}DefaultControl`,
    labelledBy: `${labelId} ${scopeDefaultId}`,
    describedBy: descId,
    options: spec.options,
    value: defaultValue,
    disabled: inert,
    onChange: (value) => {
      currentDefault = value;
      if (!overrideStored) overrideControl.setValue(value);
      onDefaultChange(value);
    },
  });
  defaultGroup.append(defaultScope, defaultControl.element);

  // The reveal link stays in the DOM (hidden while the override is expanded).
  const hasOverride = overrideValue !== null;
  const link = document.createElement("button");
  link.type = "button";
  link.className = "tagsSettingsLink";
  link.id = linkId;
  link.textContent = text.TAGS_PERSONAL_SETTINGS_OVERRIDE_DISCLOSURE;
  link.setAttribute("aria-describedby", labelId);
  link.setAttribute("aria-controls", overrideWrapId);
  link.setAttribute("aria-expanded", String(hasOverride));
  link.hidden = hasOverride;
  if (inert) link.setAttribute("aria-disabled", "true");

  // The override wrapper is always in the DOM so aria-controls always resolves.
  const overrideWrap = document.createElement("div");
  overrideWrap.className = "tagsSettingsGroup tagsSettingsGroup--override";
  overrideWrap.id = overrideWrapId;
  overrideWrap.hidden = !hasOverride;
  const overrideScope = document.createElement("span");
  overrideScope.className = "tagsSettingsScope tagsSettingsScope--override";
  overrideScope.id = scopeOverrideId;
  overrideScope.textContent = text.TAGS_PERSONAL_SETTINGS_THIS_UTUB_LABEL;
  const overrideControl = buildControl({
    id: overrideControlId,
    labelledBy: `${labelId} ${scopeOverrideId}`,
    describedBy: descId,
    options: spec.options,
    value: overrideValue ?? defaultValue,
    disabled: inert,
    onChange: (value) => {
      overrideStored = true;
      onOverrideChange(value);
    },
  });
  const useDefault = document.createElement("button");
  useDefault.type = "button";
  useDefault.className = "tagsSettingsLink";
  useDefault.id = `${idBase}UseDefault`;
  useDefault.textContent = text.TAGS_PERSONAL_SETTINGS_USE_DEFAULT_OPTION;
  useDefault.setAttribute("aria-describedby", labelId);
  if (inert) useDefault.setAttribute("aria-disabled", "true");
  overrideWrap.append(overrideScope, overrideControl.element, useDefault);

  // Reveal only: nothing is stored until the override control first changes.
  link.addEventListener("click", () => {
    if (inert) return;
    overrideControl.setValue(currentDefault);
    overrideWrap.hidden = false;
    link.hidden = true;
    link.setAttribute("aria-expanded", "true");
    interactiveOf(overrideControl.element).focus();
  });
  useDefault.addEventListener("click", () => {
    if (inert) return;
    overrideWrap.hidden = true;
    link.hidden = false;
    link.setAttribute("aria-expanded", "false");
    overrideStored = false;
    overrideControl.setValue(currentDefault);
    onUseDefault();
    link.focus();
  });

  controls.append(defaultGroup, link, overrideWrap);
  row.append(controls);
  return {
    row,
    defaultControl: interactiveOf(defaultControl.element),
    overrideControl: interactiveOf(overrideControl.element),
    noteElement,
    descId,
  };
}

/**
 * The one place the nested "How many" selects' state is set, called at render
 * and from every switch change handler (default, override and "Use my default
 * here"): the shell skips a re-render while focus is inside the section. The
 * selects are aria-disabled, and the note shown, while the resolved switch is off.
 */
function applyCollapsedSelectState({
  selects,
  note,
  descId,
  switchOn,
  inert,
}: {
  selects: HTMLElement[];
  note: HTMLElement;
  descId: string | null;
  switchOn: boolean;
  inert: boolean;
}): void {
  const switchOff = !switchOn;
  for (const select of selects) {
    if (inert || switchOff) {
      select.setAttribute("aria-disabled", "true");
    } else {
      select.removeAttribute("aria-disabled");
    }
    const describedBy = [descId, switchOff ? note.id : null].filter(
      (id): id is string => id !== null,
    );
    if (describedBy.length > 0) {
      select.setAttribute("aria-describedby", describedBy.join(" "));
    } else {
      select.removeAttribute("aria-describedby");
    }
  }
  note.hidden = !switchOff;
}

/** The store values the section's render depends on. */
const RERENDER_ON: Array<(state: AppState) => unknown> = [
  (state) => state.preferences.tagSort,
  (state) => state.preferences.tagMatchMode,
  (state) => state.preferences.tagCountStyle,
  (state) => state.preferences.showTagsOnCollapsed,
  (state) => state.preferences.collapsedTagsStyle,
  (state) => state.preferences.tagDropOpensUrl,
  (state) => state.memberSettings?.tags,
];

function render({
  container,
  ctx,
}: {
  container: HTMLElement;
  ctx: SectionContext;
}): void {
  const state = getState();
  // The slice is supplied with the active UTub; show the controls inert until it
  // arrives. The section is open to every role, including in a locked UTub, so
  // `ctx.canWrite` is deliberately not consulted.
  const slice = state.memberSettings;
  const inert = slice === null;
  const tagsOverride = (slice ?? EMPTY_MEMBER_SETTINGS).tags;
  const defaults = resolveTagDisplaySettings({
    preferences: state.preferences,
    tagsOverride: null,
  });
  const defaultValues: Record<TagDisplayKey, ControlValue> = { ...defaults };
  const overrideValues: Record<TagDisplayKey, ControlValue | null> = {
    tagSort: tagsOverride.tag_sort,
    tagMatchMode: tagsOverride.tag_match_mode,
    tagCountStyle: tagsOverride.tag_count_style,
    showTagsOnCollapsed: tagsOverride.show_tags_on_collapsed,
    collapsedTagsStyle: tagsOverride.collapsed_tags_style,
    tagDropOpensUrl: tagsOverride.tag_drop_opens_url,
  };

  const submit = ({
    prefix,
    key,
    value,
  }: {
    prefix: string;
    key: TagDisplayKey;
    value: ControlValue | null;
  }): void => {
    if (inert) return;
    ctx.submit({ patch: { [`${prefix}${key}`]: value } });
  };

  let nestedSelects: HTMLElement[] = [];
  let nestedNote: HTMLElement | null = null;
  let nestedDescId: string | null = null;
  const refreshNested = (): void => {
    if (nestedNote === null) return;
    applyCollapsedSelectState({
      selects: nestedSelects,
      note: nestedNote,
      descId: nestedDescId,
      switchOn:
        (overrideValues.showTagsOnCollapsed ??
          defaultValues.showTagsOnCollapsed) === true,
      inert,
    });
  };

  const rows: HTMLElement[] = [];
  for (const spec of rowSpecs()) {
    const { key } = spec;
    const built = buildTagRow({
      spec,
      defaultValue: defaultValues[key],
      overrideValue: overrideValues[key],
      inert,
      onDefaultChange: (value) => {
        defaultValues[key] = value;
        // Bumped at edit time, like `memberSortVersion` on pick: it rejects any
        // payload fetched before this save, and a failure does not roll it back.
        setState({ tagDisplayVersion: getState().tagDisplayVersion + 1 });
        refreshNested();
        submit({ prefix: DEFAULT_PREFIX, key, value });
      },
      onOverrideChange: (value) => {
        overrideValues[key] = value;
        refreshNested();
        submit({ prefix: OVERRIDE_PREFIX, key, value });
      },
      onUseDefault: () => {
        const hadOverride = overrideValues[key] !== null;
        overrideValues[key] = null;
        refreshNested();
        // An override that was only revealed has nothing stored to clear.
        if (hadOverride) submit({ prefix: OVERRIDE_PREFIX, key, value: null });
      },
    });
    if (key === "collapsedTagsStyle" && built.noteElement !== null) {
      nestedSelects = [built.defaultControl, built.overrideControl];
      nestedNote = built.noteElement;
      nestedDescId = built.descId;
    }
    rows.push(built.row);
  }
  refreshNested();
  container.append(...rows);
}

// ---------------------------------------------------------------------------
// Save
// ---------------------------------------------------------------------------

// Orders concurrent default sends: only the latest-sent echo is written.
let sendCounter = 0;

function isTagDisplayKey(name: string): name is TagDisplayKey {
  return Object.prototype.hasOwnProperty.call(TAG_OVERRIDE_KEYS, name);
}

/** Splits the flat patch into the default send and the (snake_case) override send. */
function splitPatch({ patch }: { patch: SectionPatch }): {
  defaults: SectionPatch;
  overrides: SectionPatch;
} {
  const defaults: SectionPatch = {};
  const overrides: SectionPatch = {};
  for (const [patchKey, value] of Object.entries(patch)) {
    if (patchKey.startsWith(DEFAULT_PREFIX)) {
      const name = patchKey.slice(DEFAULT_PREFIX.length);
      if (isTagDisplayKey(name)) defaults[name] = value;
    } else if (patchKey.startsWith(OVERRIDE_PREFIX)) {
      const name = patchKey.slice(OVERRIDE_PREFIX.length);
      if (isTagDisplayKey(name)) overrides[TAG_OVERRIDE_KEYS[name]] = value;
    }
  }
  return { defaults, overrides };
}

function currentMatchMode(): string {
  const { preferences, memberSettings } = getState();
  return resolveTagDisplaySettings({
    preferences,
    tagsOverride: memberSettings?.tags,
  }).tagMatchMode;
}

/**
 * Joins the outcomes of the save's claimed writes: the final resolved mode wins
 * (a filter-result sentence only when it differs from the starting mode, the
 * later write's sentence when both flipped), a trim sentence is kept whenever
 * any write trimmed.
 */
function joinNotice({
  startMode,
  outcomes,
}: {
  startMode: string | null;
  outcomes: ModeChangeOutcome[];
}): string | undefined {
  // No claimed write happened, so there is nothing for this save to announce.
  if (startMode === null) return undefined;
  const filterResult =
    currentMatchMode() === startMode
      ? null
      : ([...outcomes]
          .reverse()
          .find((outcome) => outcome.filterResult !== null)?.filterResult ??
        null);
  const trimNotice =
    outcomes.find((outcome) => outcome.trimNotice !== null)?.trimNotice ?? null;
  const sentences = [filterResult, trimNotice].filter(
    (sentence): sentence is string => sentence !== null,
  );
  return sentences.length > 0 ? sentences.join(". ") : undefined;
}

async function resyncAfterTimeout(): Promise<void> {
  const { activeUTubID } = getState();
  if (activeUTubID === null) return;
  try {
    await updateUTubOnFindingStaleData({ utubID: activeUTubID });
  } catch (error) {
    log("resync after timeout failed", error);
  }
}

async function save({
  utubID,
  patch,
}: {
  utubID: number | null;
  patch: SectionPatch;
}): Promise<SaveResult> {
  if (utubID === null) return { outcome: "error" };
  const { defaults, overrides } = splitPatch({ patch });
  const hasDefaults = Object.keys(defaults).length > 0;
  const hasOverrides = Object.keys(overrides).length > 0;
  if (!hasDefaults && !hasOverrides) return { outcome: "error" };

  // Captured lazily, right before the first claimed write, so a mode change
  // landing while a send is pending is not mistaken for this save's own flip.
  let startMode: string | null = null;
  const outcomes: ModeChangeOutcome[] = [];
  const claimWrite = (write: () => void): void => {
    startMode ??= currentMatchMode();
    outcomes.push(applyClaimingModeChange(write));
  };
  const withNotice = <Result extends SaveResult>(result: Result): Result => {
    const notice = joinNotice({ startMode, outcomes });
    return notice === undefined ? result : { ...result, notice };
  };

  if (hasDefaults) {
    sendCounter += 1;
    const thisSend = sendCounter;
    const outcome = await patchTagDisplayPreferences({ patch: defaults });
    if (outcome.outcome === "failed") {
      // A timed-out send may have committed: refresh the defaults before the
      // error is reported. Any other failure never wrote the store.
      if (outcome.timedOut) await resyncAfterTimeout();
      // The override is skipped; the queue's own member-settings resync is not
      // needed (nothing was written, or the resync above already ran).
      return outcome.result.outcome === "error"
        ? { ...outcome.result, resync: false }
        : outcome.result;
    }
    if (thisSend === sendCounter) {
      const current = getState();
      claimWrite(() =>
        setState({
          preferences: { ...current.preferences, ...outcome.preferences },
          tagDisplayVersion: current.tagDisplayVersion + 1,
        }),
      );
    } else {
      log("older default echo discarded", { thisSend, latest: sendCounter });
    }
  }

  if (hasOverrides) {
    const outcome = await patchMemberSettings({
      utubID,
      panel: "tags",
      patch: overrides,
    });
    if (outcome.outcome !== "ok") {
      if (outcome.outcome === "invalid")
        return withNotice({ outcome: "error" });
      if (outcome.outcome === "locked" || outcome.outcome === "forbidden") {
        return withNotice({ outcome: "error" });
      }
      return outcome.outcome === "gone" ? outcome : withNotice(outcome);
    }
    // Guarded again at the write site: a save resolving after a UTub switch must
    // never write into the new UTub's slice. The default echo stands.
    const current = getState();
    if (current.activeUTubID !== utubID) {
      log("save resolved after UTub change, dropping override", { utubID });
      return withNotice({ outcome: "stale", failed: false });
    }
    claimWrite(() =>
      setState({
        memberSettings: resolveMemberSettings(outcome.memberSettings),
        memberSettingsVersion: current.memberSettingsVersion + 1,
      }),
    );
  }

  return withNotice({ outcome: "ok" });
}

/**
 * Registers the "Your tags" section on the Tags gear: the member's tag display
 * defaults for every UTub, each with an optional override for this UTub. Returns
 * the unregister function.
 */
export function registerTagsPersonalSettingsSection(): () => void {
  const section: PanelSection = {
    id: SECTION_ID,
    panel: "tags",
    scope: "user",
    userKind: "per-utub",
    title: APP_CONFIG.strings.TAGS_PERSONAL_SETTINGS_SECTION_TITLE,
    rerenderOn: RERENDER_ON,
    render,
    save,
  };
  return registerSection(section);
}
