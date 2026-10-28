import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { getState, setState } from "../../store/app-store.js";
import type { AppState } from "../../store/app-store.js";
import type {
  DensityValue,
  SortOrderValue,
  ViewModeValue,
} from "../../types/preferences.js";
import {
  EMPTY_MEMBER_SETTINGS,
  resolveMemberSettings,
} from "../../types/settings.js";
import type { ResolvedMemberUrlsSettings } from "../../types/settings.js";
import { patchMemberSettings } from "../panel-settings/client.js";
import { syncDeckOrderToServer } from "./view-settings.js";
import {
  isViewMode,
  isWideViewport,
  normalizeViewMode,
  renderedViewMode,
} from "./view-mode.js";
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

const log = debug("urls-personal-settings");

const SECTION_ID = "urls-personal";
const FINE_POINTER_QUERY = "(any-pointer: fine)";

type SwitchKey = keyof Pick<
  ResolvedMemberUrlsSettings,
  | "hide_copy_button"
  | "hide_short_link_button"
  | "hide_date_added"
  | "disable_swipe_delete"
>;

interface SwitchRow {
  key: SwitchKey;
  switchId: string;
  labelId: string;
  descId: string;
  label: string;
  desc: string;
  hiddenNotice: string;
  shownNotice: string;
}

interface SelectOption<Value extends string> {
  value: Value;
  label: string;
}

const strings = (): Record<string, string> => APP_CONFIG.strings;

function sortOptions(): Array<SelectOption<SortOrderValue>> {
  return [
    {
      value: "newest",
      label: strings().URLS_PERSONAL_SETTINGS_SORT_OPTION_NEWEST,
    },
    {
      value: "oldest",
      label: strings().URLS_PERSONAL_SETTINGS_SORT_OPTION_OLDEST,
    },
    {
      value: "title_az",
      label: strings().URLS_PERSONAL_SETTINGS_SORT_OPTION_TITLE_AZ,
    },
  ];
}

function viewOptions({
  includeCards,
}: {
  includeCards: boolean;
}): Array<SelectOption<ViewModeValue>> {
  const options: Array<SelectOption<ViewModeValue>> = [
    { value: "list", label: strings().URLS_PERSONAL_SETTINGS_VIEW_OPTION_LIST },
    {
      value: "title_line",
      label: strings().URLS_PERSONAL_SETTINGS_VIEW_OPTION_TITLE_LINE,
    },
    {
      value: "url_line",
      label: strings().URLS_PERSONAL_SETTINGS_VIEW_OPTION_URL_LINE,
    },
  ];
  if (includeCards) {
    options.push({
      value: "cards",
      label: strings().URLS_PERSONAL_SETTINGS_VIEW_OPTION_CARDS,
    });
  }
  return options;
}

/**
 * Options for the per-UTub Layout select. Cards is offered only on wide
 * screens, but a saved `cards` override stays visible (and clearable through
 * Default) on small screens as one extra, selected option.
 */
function pickerViewOptions({
  wide,
  override,
}: {
  wide: boolean;
  override: ViewModeValue | null;
}): Array<SelectOption<ViewModeValue>> {
  const options = viewOptions({ includeCards: wide });
  if (!wide && override === "cards") {
    options.push({
      value: "cards",
      label: strings().URLS_PERSONAL_SETTINGS_VIEW_OPTION_CARDS_SMALL_SCREEN,
    });
  }
  return options;
}

/** The Default option's label for the account default view. */
function defaultViewLabel({
  wide,
  accountDefault,
}: {
  wide: boolean;
  accountDefault: ViewModeValue;
}): string {
  if (!wide && accountDefault === "cards") {
    return strings().URLS_PERSONAL_SETTINGS_VIEW_OPTION_CARDS_SMALL_SCREEN;
  }
  return labelOf({
    options: viewOptions({ includeCards: true }),
    value: accountDefault,
  });
}

function densityOptions(): Array<SelectOption<DensityValue>> {
  return [
    {
      value: "comfortable",
      label: strings().URLS_PERSONAL_SETTINGS_DENSITY_OPTION_COMFORTABLE,
    },
    {
      value: "compact",
      label: strings().URLS_PERSONAL_SETTINGS_DENSITY_OPTION_COMPACT,
    },
  ];
}

function switchRows(): SwitchRow[] {
  return [
    {
      key: "hide_copy_button",
      switchId: "urlsPersonalHideCopySwitch",
      labelId: "urlsPersonalHideCopyLabel",
      descId: "urlsPersonalHideCopyDesc",
      label: strings().URLS_PERSONAL_SETTINGS_HIDE_COPY_LABEL,
      desc: strings().URLS_PERSONAL_SETTINGS_HIDE_COPY_DESC,
      hiddenNotice: strings().URLS_PERSONAL_SETTINGS_COPY_HIDDEN_NOTICE,
      shownNotice: strings().URLS_PERSONAL_SETTINGS_COPY_SHOWN_NOTICE,
    },
    {
      key: "hide_short_link_button",
      switchId: "urlsPersonalHideShortLinkSwitch",
      labelId: "urlsPersonalHideShortLinkLabel",
      descId: "urlsPersonalHideShortLinkDesc",
      label: strings().URLS_PERSONAL_SETTINGS_HIDE_SHORT_LINK_LABEL,
      desc: strings().URLS_PERSONAL_SETTINGS_HIDE_SHORT_LINK_DESC,
      hiddenNotice: strings().URLS_PERSONAL_SETTINGS_SHORT_LINK_HIDDEN_NOTICE,
      shownNotice: strings().URLS_PERSONAL_SETTINGS_SHORT_LINK_SHOWN_NOTICE,
    },
    {
      key: "hide_date_added",
      switchId: "urlsPersonalHideDateSwitch",
      labelId: "urlsPersonalHideDateLabel",
      descId: "urlsPersonalHideDateDesc",
      label: strings().URLS_PERSONAL_SETTINGS_HIDE_DATE_LABEL,
      desc: strings().URLS_PERSONAL_SETTINGS_HIDE_DATE_DESC,
      hiddenNotice: strings().URLS_PERSONAL_SETTINGS_DATE_HIDDEN_NOTICE,
      shownNotice: strings().URLS_PERSONAL_SETTINGS_DATE_SHOWN_NOTICE,
    },
    {
      key: "disable_swipe_delete",
      switchId: "urlsPersonalDisableSwipeSwitch",
      labelId: "urlsPersonalDisableSwipeLabel",
      descId: "urlsPersonalDisableSwipeDesc",
      label: strings().URLS_PERSONAL_SETTINGS_DISABLE_SWIPE_LABEL,
      desc: strings().URLS_PERSONAL_SETTINGS_DISABLE_SWIPE_DESC,
      hiddenNotice: strings().URLS_PERSONAL_SETTINGS_SWIPE_OFF_NOTICE,
      shownNotice: strings().URLS_PERSONAL_SETTINGS_SWIPE_ON_NOTICE,
    },
  ];
}

function labelOf<Value extends string>({
  options,
  value,
}: {
  options: Array<SelectOption<Value>>;
  value: Value;
}): string {
  return options.find((option) => option.value === value)?.label ?? value;
}

function hasFinePointer(): boolean {
  // No matchMedia (an old or headless environment) cannot be a touch-only
  // device we could detect, so the row stays.
  if (typeof window.matchMedia !== "function") return true;
  return window.matchMedia(FINE_POINTER_QUERY).matches;
}

/** The select is described by its desc, plus the hint while the hint shows. */
function syncDescribedBy({
  select,
  descId,
  hintElement,
}: {
  select: HTMLSelectElement;
  descId: string;
  hintElement: HTMLElement;
}): void {
  select.setAttribute(
    "aria-describedby",
    hintElement.hidden ? descId : `${descId} ${hintElement.id}`,
  );
}

/** Density only has an effect in List (and on the selected URL). */
function densityDisabledFor(viewMode: ViewModeValue): boolean {
  return viewMode !== "list";
}

/** The view that would render for a per-UTub override (null = account default). */
function renderedViewFor({
  override,
  accountDefault,
}: {
  override: ViewModeValue | null;
  accountDefault: ViewModeValue;
}): ViewModeValue {
  return renderedViewMode(
    isViewMode(override) ? override : normalizeViewMode(accountDefault),
  );
}

/**
 * The one place the Density control's view-driven state is set, called at render
 * and from the view select's change handler (the store re-render is skipped
 * while focus is inside the section). Inert rows stay aria-disabled regardless.
 */
function applyDensityState({
  row,
  viewValue,
  inert,
}: {
  row: HTMLElement;
  viewValue: ViewModeValue;
  inert: boolean;
}): void {
  const select = row.querySelector<HTMLSelectElement>("select");
  const hintElement = row.querySelector<HTMLElement>(".urlsSettingsHint");
  if (select === null || hintElement === null) return;
  const viewDisabled = densityDisabledFor(viewValue);
  if (inert || viewDisabled) {
    select.setAttribute("aria-disabled", "true");
  } else {
    select.removeAttribute("aria-disabled");
  }
  hintElement.hidden = !viewDisabled;
  const descId = select.dataset.descId;
  if (descId === undefined) return;
  syncDescribedBy({ select, descId, hintElement });
}

function buildSelectRow<Value extends string>({
  idPrefix,
  title,
  desc,
  options,
  current,
  defaultLabel,
  disabled,
  hint,
  onChange,
}: {
  idPrefix: string;
  title: string;
  desc?: string;
  options: Array<SelectOption<Value>>;
  current: Value | null;
  defaultLabel: string;
  disabled: boolean;
  hint?: { text: string; visible: boolean };
  onChange: (value: Value | null) => void;
}): HTMLElement {
  const row = document.createElement("div");
  row.className = "panelSettingsRow";
  const labelId = `${idPrefix}Label`;
  const descId = `${idPrefix}Desc`;

  const label = buildRowLabel({ titleId: labelId, title, descId, desc });
  row.append(label);

  const wrap = document.createElement("div");
  wrap.className = "panelSettingsSelectWrap";
  const select = document.createElement("select");
  select.className = "panelSettingsSelect";
  select.id = `${idPrefix}Select`;
  select.setAttribute("aria-labelledby", labelId);
  if (desc !== undefined) select.setAttribute("aria-describedby", descId);
  if (hint !== undefined) {
    select.dataset.descId = descId;
    const hintElement = document.createElement("div");
    hintElement.className = "urlsSettingsHint";
    hintElement.id = `${idPrefix}Hint`;
    hintElement.textContent = hint.text;
    hintElement.hidden = !hint.visible;
    label.append(hintElement);
    syncDescribedBy({ select, descId, hintElement });
  }

  const defaultOption = document.createElement("option");
  defaultOption.value = "";
  defaultOption.textContent = `${strings().URLS_PERSONAL_SETTINGS_DEFAULT_OPTION_PREFIX}${defaultLabel}`;
  select.append(defaultOption);
  for (const option of options) {
    const optionElement = document.createElement("option");
    optionElement.value = option.value;
    optionElement.textContent = option.label;
    select.append(optionElement);
  }

  const renderedValue = current ?? "";
  select.value = renderedValue;
  select.classList.toggle("overridden", current !== null);
  if (disabled) select.setAttribute("aria-disabled", "true");

  select.addEventListener("change", () => {
    if (select.getAttribute("aria-disabled") === "true") {
      // aria-disabled does not stop a native select from changing.
      select.value = renderedValue;
      return;
    }
    const picked = options.find((option) => option.value === select.value);
    select.classList.toggle("overridden", picked !== undefined);
    onChange(picked === undefined ? null : picked.value);
  });

  wrap.append(select);
  row.append(wrap);
  return row;
}

function buildSwitchRow({
  row,
  checked,
  disabled,
  hint,
  onToggle,
}: {
  row: SwitchRow;
  checked: boolean;
  disabled: boolean;
  hint?: { id: string; text: string };
  onToggle: (next: boolean) => void;
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
  switchButton.setAttribute("aria-checked", String(checked));
  const describedBy = [row.descId];
  if (hint !== undefined) {
    const hintElement = document.createElement("div");
    hintElement.className = "urlsSettingsHint";
    hintElement.id = hint.id;
    hintElement.textContent = hint.text;
    label.append(hintElement);
    describedBy.push(hint.id);
  }
  switchButton.setAttribute("aria-describedby", describedBy.join(" "));
  if (disabled) switchButton.setAttribute("aria-disabled", "true");
  switchButton.addEventListener("click", () => {
    if (switchButton.getAttribute("aria-disabled") === "true") return;
    const next = switchButton.getAttribute("aria-checked") !== "true";
    switchButton.setAttribute("aria-checked", String(next));
    onToggle(next);
  });
  rowElement.append(label, switchButton);
  return rowElement;
}

function noticeFor({ patch }: { patch: SectionPatch }): string | undefined {
  const notices: string[] = [];
  const text = strings();
  for (const row of switchRows()) {
    const value = patch[row.key];
    if (typeof value === "boolean") {
      notices.push(value ? row.hiddenNotice : row.shownNotice);
    }
  }
  const groups: Array<{
    key: "sort" | "view_mode" | "density";
    options: Array<SelectOption<string>>;
    setPrefix: string;
    defaultNotice: string;
  }> = [
    {
      key: "sort",
      options: sortOptions(),
      setPrefix: text.URLS_PERSONAL_SETTINGS_SORT_SET_NOTICE_PREFIX,
      defaultNotice: text.URLS_PERSONAL_SETTINGS_SORT_DEFAULT_NOTICE,
    },
    {
      key: "view_mode",
      options: viewOptions({ includeCards: true }),
      setPrefix: text.URLS_PERSONAL_SETTINGS_VIEW_SET_NOTICE_PREFIX,
      defaultNotice: text.URLS_PERSONAL_SETTINGS_VIEW_DEFAULT_NOTICE,
    },
    {
      key: "density",
      options: densityOptions(),
      setPrefix: text.URLS_PERSONAL_SETTINGS_DENSITY_SET_NOTICE_PREFIX,
      defaultNotice: text.URLS_PERSONAL_SETTINGS_DENSITY_DEFAULT_NOTICE,
    },
  ];
  for (const group of groups) {
    if (!Object.prototype.hasOwnProperty.call(patch, group.key)) continue;
    const value = patch[group.key];
    if (value === null) {
      notices.push(group.defaultNotice);
    } else if (typeof value === "string") {
      notices.push(
        `${group.setPrefix}${labelOf({ options: group.options, value })}`,
      );
    }
  }
  return notices.length > 0 ? notices.join(". ") : undefined;
}

/** The store values the personal section's render depends on. */
const RERENDER_ON: Array<(state: AppState) => unknown> = [
  (state) => state.memberSettings,
  (state) => state.settings?.urls.allow_short_links,
  (state) => state.preferences,
];

function render({
  container,
  ctx,
}: {
  container: HTMLElement;
  ctx: SectionContext;
}): void {
  const state = getState();
  // Defensive: the slice is supplied with the active UTub, so a null here means
  // it has not arrived; show it inert until the shell re-renders on arrival.
  const slice = state.memberSettings;
  const awaitingSlice = slice === null;
  const urls = (slice ?? EMPTY_MEMBER_SETTINGS).urls;
  const inert = awaitingSlice || !ctx.canWrite;
  const shortLinksOff = state.settings?.urls.allow_short_links === false;
  const preferences = state.preferences;

  const submitPatch = (patch: SectionPatch): void => {
    if (inert) return;
    ctx.submit({ patch });
  };

  const rows: HTMLElement[] = [];

  // Read once per render; the popover rebuilds the section on each open, so a
  // resize across the breakpoint is picked up on the next open.
  const wide = isWideViewport();
  const renderedView = renderedViewFor({
    override: urls.view_mode,
    accountDefault: preferences.defaultView,
  });
  let densityRow: HTMLElement | null = null;

  rows.push(
    buildSelectRow({
      idPrefix: "urlsSettingsSort",
      title: strings().URLS_PERSONAL_SETTINGS_SORT_LABEL,
      options: sortOptions(),
      current: urls.sort,
      defaultLabel: labelOf({
        options: sortOptions(),
        value: preferences.defaultSort,
      }),
      disabled: inert,
      onChange: (value) => submitPatch({ sort: value }),
    }),
    buildSelectRow({
      idPrefix: "urlsSettingsView",
      title: strings().URLS_PERSONAL_SETTINGS_VIEW_LABEL,
      options: pickerViewOptions({ wide, override: urls.view_mode }),
      current: urls.view_mode,
      defaultLabel: defaultViewLabel({
        wide,
        accountDefault: preferences.defaultView,
      }),
      disabled: inert,
      onChange: (value) => {
        // Optimistic and immediate: the store re-render is skipped while the
        // view select holds focus. A failed save re-renders the true state.
        if (densityRow !== null) {
          applyDensityState({
            row: densityRow,
            viewValue: renderedViewFor({
              override: value,
              accountDefault: preferences.defaultView,
            }),
            inert,
          });
        }
        submitPatch({ view_mode: value });
      },
    }),
  );

  // Compact spacing only applies with a fine pointer, so a touch-only device
  // never sees a control that cannot take effect.
  if (hasFinePointer()) {
    densityRow = buildSelectRow({
      idPrefix: "urlsSettingsDensity",
      title: strings().URLS_PERSONAL_SETTINGS_DENSITY_LABEL,
      desc: strings().URLS_PERSONAL_SETTINGS_DENSITY_DESC,
      options: densityOptions(),
      current: urls.density,
      defaultLabel: labelOf({
        options: densityOptions(),
        value: preferences.density,
      }),
      disabled: inert,
      hint: {
        text: strings().URLS_PERSONAL_SETTINGS_DENSITY_VIEW_HINT,
        visible: densityDisabledFor(renderedView),
      },
      onChange: (value) => submitPatch({ density: value }),
    });
    applyDensityState({ row: densityRow, viewValue: renderedView, inert });
    rows.push(densityRow);
  }

  for (const row of switchRows()) {
    const isShortLinkSwitch = row.key === "hide_short_link_button";
    const hintId = "urlsPersonalHideShortLinkHint";
    rows.push(
      buildSwitchRow({
        row,
        checked: urls[row.key],
        disabled: inert || (isShortLinkSwitch && shortLinksOff),
        ...(isShortLinkSwitch && shortLinksOff
          ? {
              hint: {
                id: hintId,
                text: strings().URLS_PERSONAL_SETTINGS_SHORT_LINKS_OFF_HINT,
              },
            }
          : {}),
        onToggle: (next) => submitPatch({ [row.key]: next }),
      }),
    );
  }

  container.append(...rows);
}

async function save({
  utubID,
  patch,
}: {
  utubID: number | null;
  patch: SectionPatch;
}): Promise<SaveResult> {
  if (utubID === null) return { outcome: "error" };

  const result = await patchMemberSettings({ utubID, panel: "urls", patch });

  // The queue only resyncs from the server on an error outcome.
  if (result.outcome === "invalid") return { outcome: "error" };
  if (result.outcome !== "ok") return result;

  // Guarded again at the write site: a save resolving after a UTub switch must
  // never write into the new UTub's slice.
  const current = getState();
  if (current.activeUTubID !== utubID) {
    log("save resolved after UTub change, dropping", { utubID });
    return { outcome: "stale", failed: false };
  }
  setState({
    memberSettings: resolveMemberSettings(result.memberSettings),
    memberSettingsVersion: current.memberSettingsVersion + 1,
  });
  // Reorder the open deck to the server's order for the new sort; a failure
  // inside keeps the saved sort and announces a notice, never a save error.
  if (Object.prototype.hasOwnProperty.call(patch, "sort")) {
    void syncDeckOrderToServer();
  }
  const notice = noticeFor({ patch });
  return notice === undefined ? { outcome: "ok" } : { outcome: "ok", notice };
}

/**
 * Registers the "Your view of this UTub" section on the URLs gear: the member's
 * own per-UTub view overrides. Returns the unregister function.
 */
export function registerUrlsPersonalSettingsSection(): () => void {
  const section: PanelSection = {
    id: SECTION_ID,
    panel: "urls",
    scope: "user",
    userKind: "per-utub",
    title: APP_CONFIG.strings.URLS_PERSONAL_SETTINGS_SECTION_TITLE,
    rerenderOn: RERENDER_ON,
    render,
    save,
  };
  return registerSection(section);
}
