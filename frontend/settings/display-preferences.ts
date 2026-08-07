/**
 * Display-preferences controller for the settings page (Display tab).
 *
 * The panel is server-rendered by Jinja (`pages/settings.html`), so — like
 * `change-username.ts` / `connected-accounts.ts` — this binds handlers on the
 * fixed, server-rendered controls keyed by a small `data-*` contract rather
 * than at a TS render step (there is none).
 *
 * data-* contract (rendered by the template, read-only here):
 *   #SettingsPanelUiSettings[data-action-url]   PUT target for the preferences
 *   [role="radio"][data-theme-value]            the theme segmented control
 *
 * Instant-apply (no save button), matching the connected-accounts idiom: every
 * control change fires a debounced (300 ms trailing) PUT so a burst of rapid
 * changes — e.g. arrow-keying through the theme radiogroup — coalesces into one
 * request. On a 200 the endpoint echoes every persisted value back; the handler
 * flips `<html data-theme>` to the chosen theme (resolving `system` via
 * `matchMedia`) and announces "Preferences saved" via the always-mounted global
 * status toast. `.fail` writes the field/generic error into the panel-local
 * `#SettingsUiSettingsStatus` region, never the success toast.
 */

import type { Schema, SuccessResponse } from "../types/api-helpers.d.ts";
import type {
  DateFormatValue,
  DensityValue,
  SortOrderValue,
  ThemeValue,
  ViewModeValue,
} from "../types/preferences.js";
import { $ } from "../lib/globals.js";
import { ajaxCall, is429Handled } from "../lib/ajax.js";
import { APP_CONFIG } from "../lib/config.js";
import { makeDebouncer } from "../lib/debounce.js";

type UpdatePreferencesRequest = Schema<"UpdatePreferencesRequest">;
type UpdatePreferencesResponse = SuccessResponse<"updatePreferences">;
type UpdatePreferencesError = Schema<"ErrorResponse_PreferencesErrorCodes">;

const PANEL_ID = "SettingsPanelUiSettings";
const THEME_GROUP_ID = "SettingsThemeControl";
const STATUS_ID = "SettingsUiSettingsStatus";
const GLOBAL_TOAST_ID = "SettingsGlobalStatusToast";

const THEME_RADIO_SELECTOR = `#${THEME_GROUP_ID} [role="radio"]`;

const DEFAULT_VIEW_SELECT_ID = "SettingsDefaultViewSelect";
const DEFAULT_SORT_SELECT_ID = "SettingsDefaultSortSelect";
const DENSITY_SELECT_ID = "SettingsDensitySelect";
const DATE_FORMAT_SELECT_ID = "SettingsDateFormatSelect";
const SELECT_IDS = [
  DEFAULT_VIEW_SELECT_ID,
  DEFAULT_SORT_SELECT_ID,
  DENSITY_SELECT_ID,
  DATE_FORMAT_SELECT_ID,
];
const SELECT_SELECTOR = SELECT_IDS.map((id) => `#${id}`).join(", ");

// Theme values in radiogroup display order — the roving-tabindex + wrap order.
const THEME_VALUES: ThemeValue[] = ["light", "dark", "system"];

const DEBOUNCE_MS = 300;

const CLICK_NAMESPACE = "click.displayPreferences";
const KEYDOWN_NAMESPACE = "keydown.displayPreferences";
const CHANGE_NAMESPACE = "change.displayPreferences";

const GENERIC_ERROR_MESSAGE = "Unable to process request.";

// The control the user was on when the trailing PUT fired — captured before the
// reentrancy guard disables the panel, restored after it re-enables (WCAG 2.4.3).
let _focusedControlBeforeInFlight: HTMLElement | null = null;

// Single debounced firer shared by every control change (created once at module
// scope so a burst across different controls still coalesces into one PUT).
const debouncedFirePut = makeDebouncer(firePut, DEBOUNCE_MS);

export function initDisplayPreferences(): void {
  if (document.getElementById(PANEL_ID) === null) return;

  $(THEME_RADIO_SELECTOR).offAndOnExact(CLICK_NAMESPACE, handleThemeClick);
  $(THEME_RADIO_SELECTOR).offAndOnExact(KEYDOWN_NAMESPACE, handleThemeKeydown);
  $(SELECT_SELECTOR).offAndOnExact(CHANGE_NAMESPACE, handleSelectChange);
}

export function _resetDisplayPreferencesForTests(): void {
  $(THEME_RADIO_SELECTOR).off(CLICK_NAMESPACE).off(KEYDOWN_NAMESPACE);
  $(SELECT_SELECTOR).off(CHANGE_NAMESPACE);
  _focusedControlBeforeInFlight = null;
}

function handleThemeClick(event: JQuery.TriggeredEvent): void {
  const clicked = event.currentTarget as HTMLButtonElement;
  const value = clicked.dataset.themeValue as ThemeValue | undefined;
  if (value === undefined) return;
  selectThemeRadio(value, { focus: true });
  debouncedFirePut();
}

/**
 * WAI-ARIA radio pattern for the theme segmented control: Arrow keys rove
 * through the radios (selection follows focus, wrap-around at the ends);
 * Space/Enter (re)activate the focused radio. Every handled key debounce-fires
 * the PUT — but NEVER synchronously, and the reentrancy guard is not engaged
 * here, so a rapid arrow burst within the debounce window always lands on live,
 * enabled controls.
 */
// keydown (not keyup) — ARIA APG radiogroup spec; intentional deviation from
// the repo's keyup convention, matching settings-page.ts's tablist controller.
function handleThemeKeydown(event: JQuery.TriggeredEvent): void {
  const key = event.key as string | undefined;
  const current = event.currentTarget as HTMLButtonElement;
  const currentValue = current.dataset.themeValue as ThemeValue | undefined;
  if (currentValue === undefined) return;
  const currentIndex = THEME_VALUES.indexOf(currentValue);
  if (currentIndex === -1) return;

  let nextValue: ThemeValue;
  if (key === "ArrowRight" || key === "ArrowDown") {
    nextValue = THEME_VALUES[(currentIndex + 1) % THEME_VALUES.length];
  } else if (key === "ArrowLeft" || key === "ArrowUp") {
    nextValue =
      THEME_VALUES[
        (currentIndex - 1 + THEME_VALUES.length) % THEME_VALUES.length
      ];
  } else if (key === " " || key === "Spacebar" || key === "Enter") {
    nextValue = currentValue;
  } else {
    return;
  }

  event.preventDefault();
  selectThemeRadio(nextValue, { focus: true });
  debouncedFirePut();
}

function handleSelectChange(): void {
  debouncedFirePut();
}

/**
 * Mark `targetValue`'s radio checked (and the roving `tabindex` 0), all others
 * unchecked (`tabindex` -1). Optionally move focus to the checked radio, per the
 * ARIA radiogroup "selection follows focus" rule.
 */
function selectThemeRadio(
  targetValue: ThemeValue,
  { focus }: { focus: boolean },
): void {
  $(THEME_RADIO_SELECTOR).each(function () {
    const radio = this as HTMLButtonElement;
    const isTarget = radio.dataset.themeValue === targetValue;
    radio.setAttribute("aria-checked", isTarget ? "true" : "false");
    radio.setAttribute("tabindex", isTarget ? "0" : "-1");
    if (isTarget && focus) $(radio).trigger("focus");
  });
}

/**
 * Fire the trailing PUT. This is the only place `setPanelInFlight(true)`
 * engages — engaging it synchronously on the first change of a burst would
 * disable the radios mid-arrow-navigation and stop them receiving the very key
 * events the roving pattern depends on.
 */
function firePut(): void {
  const actionUrl = getActionUrl();
  if (!actionUrl) return;

  const payload = buildPayload();

  // Capture focus BEFORE disabling — the guard blurs focus onto <body> with no
  // way back otherwise (WCAG 2.4.3).
  _focusedControlBeforeInFlight = document.activeElement as HTMLElement | null;
  clearStatus();
  setPanelInFlight(true);

  const request = ajaxCall("put", actionUrl, payload);

  request.done(function (
    response: UpdatePreferencesResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    setPanelInFlight(false);
    restoreFocus();
    if (xhr.status !== 200) return;

    // Flip to the server-echoed theme (server-authoritative), mirroring
    // change-username.ts's echo-based update-in-place rather than trusting the
    // value we sent.
    applyTheme(response.theme as ThemeValue);
    $(`#${GLOBAL_TOAST_ID}`).text(
      APP_CONFIG.strings.SETTINGS_PREFERENCES_SAVED,
    );
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    setPanelInFlight(false);
    restoreFocus();
    if (is429Handled(xhr)) return;

    const responseJson = xhr.responseJSON as UpdatePreferencesError | undefined;
    showStatus({
      message:
        firstFieldError(responseJson) ??
        responseJson?.message ??
        GENERIC_ERROR_MESSAGE,
      type: "danger",
    });
  });
}

function getActionUrl(): string | undefined {
  return document.getElementById(PANEL_ID)?.dataset.actionUrl;
}

function buildPayload(): UpdatePreferencesRequest {
  return {
    theme: getCheckedThemeValue(),
    defaultView: getSelectValue(DEFAULT_VIEW_SELECT_ID) as ViewModeValue,
    defaultSort: getSelectValue(DEFAULT_SORT_SELECT_ID) as SortOrderValue,
    density: getSelectValue(DENSITY_SELECT_ID) as DensityValue,
    dateFormat: getSelectValue(DATE_FORMAT_SELECT_ID) as DateFormatValue,
  };
}

function getCheckedThemeValue(): ThemeValue {
  const checked = document.querySelector(
    `${THEME_RADIO_SELECTOR}[aria-checked="true"]`,
  ) as HTMLButtonElement | null;
  return (checked?.dataset.themeValue as ThemeValue | undefined) ?? "system";
}

function getSelectValue(selectId: string): string {
  return (
    (document.getElementById(selectId) as HTMLSelectElement | null)?.value ?? ""
  );
}

function applyTheme(theme: ThemeValue): void {
  const resolved =
    theme === "system"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : theme;
  document.documentElement.dataset.theme = resolved;
  // Keep the raw stored preference available so the settings control's selected
  // state stays consistent with what the server rendered.
  document.documentElement.dataset.themePref = theme;
}

/**
 * Reentrancy guard: disable every panel control (all three theme radios AND all
 * four selects) while the PUT is in flight, mirroring `change-username.ts`'s
 * `setInFlight`. Released in both `.done` and `.fail`.
 */
function setPanelInFlight(inFlight: boolean): void {
  const controls = $(THEME_RADIO_SELECTOR).add(SELECT_SELECTOR);
  if (inFlight) {
    controls.attr("disabled", "disabled").attr("aria-busy", "true");
  } else {
    controls.removeAttr("disabled").removeAttr("aria-busy");
  }
}

function restoreFocus(): void {
  const target = _focusedControlBeforeInFlight;
  _focusedControlBeforeInFlight = null;
  if (target && typeof target.focus === "function") {
    $(target).trigger("focus");
  }
}

function firstFieldError(
  responseJson: UpdatePreferencesError | undefined,
): string | undefined {
  const errors = responseJson?.errors;
  if (!errors) return undefined;
  for (const messages of Object.values(errors)) {
    if (Array.isArray(messages) && messages.length > 0) return messages[0];
  }
  return undefined;
}

function showStatus({
  message,
  type,
}: {
  message: string;
  type: "success" | "danger";
}): void {
  $(`#${STATUS_ID}`)
    .removeClass("d-none alert-success alert-danger")
    .addClass(`alert-${type}`)
    .text(message);
}

function clearStatus(): void {
  $(`#${STATUS_ID}`)
    .addClass("d-none")
    .removeClass("alert-success alert-danger")
    .text("");
}
