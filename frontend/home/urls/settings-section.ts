import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { getState } from "../../store/app-store.js";
import { patchUtubSettings } from "../panel-settings/client.js";
import { registerSection } from "../panel-settings/registry.js";
import type {
  PanelSection,
  SaveResult,
  SectionContext,
  SectionPatch,
} from "../panel-settings/types.js";
import { HTTPS_SCHEME } from "./scheme/scheme-default.js";
import { mountSchemePicker } from "./scheme/scheme-picker.js";

const log = debug("urls-settings");

const SECTION_ID = "urls-defaults";
const TOGGLE_ID = "urlsSettingsDefaultScheme";
const SWITCH_ID = "urlsSettingsHideSwitch";
const SCHEME_LABEL_ID = "urlsSettingsDefaultSchemeLabel";
const SCHEME_DESC_ID = "urlsSettingsDefaultSchemeDesc";
const HIDE_LABEL_ID = "urlsSettingsHideLabel";
const HIDE_DESC_ID = "urlsSettingsHideDesc";
const HIDE_HINT_ID = "urlsSettingsHideHint";

/** What the live render exposes to `save` so a server-driven flip lands in place. */
interface MountedView {
  utubID: number | null;
  setLastHideIntent: (value: boolean) => void;
}

function buildRowLabel({
  titleId,
  title,
  descId,
  desc,
}: {
  titleId: string;
  title: string;
  descId: string;
  desc: string;
}): HTMLElement {
  const label = document.createElement("div");
  label.className = "panelSettingsRowLabel";
  const titleElement = document.createElement("div");
  titleElement.className = "panelSettingsRowName";
  titleElement.id = titleId;
  titleElement.textContent = title;
  const descElement = document.createElement("div");
  descElement.className = "panelSettingsRowDesc";
  descElement.id = descId;
  descElement.textContent = desc;
  label.append(titleElement, descElement);
  return label;
}

function hasOwn({ patch, key }: { patch: SectionPatch; key: string }): boolean {
  return Object.prototype.hasOwnProperty.call(patch, key);
}

/**
 * Registers the "New URLs" section on the URLs gear: the default-scheme picker
 * and the hide-selector switch. Returns the unregister function.
 */
export function registerUrlsSettingsSection(): () => void {
  let mounted: MountedView | null = null;

  function render({
    container,
    ctx,
  }: {
    container: HTMLElement;
    ctx: SectionContext;
  }): () => void {
    const urlsSlice = ctx.settings?.urls;
    const initialScheme =
      urlsSlice?.default_url_scheme ?? APP_CONFIG.constants.URL_DEFAULT_SCHEME;
    let lastHideIntent = urlsSlice?.hide_scheme_selector === true;
    const readOnly = !ctx.canWrite;

    // Row 1: default scheme picker.
    const schemeRow = document.createElement("div");
    schemeRow.className = "panelSettingsRow";
    schemeRow.append(
      buildRowLabel({
        titleId: SCHEME_LABEL_ID,
        title: APP_CONFIG.strings.URLS_SETTINGS_DEFAULT_SCHEME_LABEL,
        descId: SCHEME_DESC_ID,
        desc: APP_CONFIG.strings.URLS_SETTINGS_DEFAULT_SCHEME_DESC,
      }),
    );

    // Row 2: hide switch.
    const hideRow = document.createElement("div");
    hideRow.className = "panelSettingsRow";
    const hideLabel = buildRowLabel({
      titleId: HIDE_LABEL_ID,
      title: APP_CONFIG.strings.URLS_SETTINGS_HIDE_LABEL,
      descId: HIDE_DESC_ID,
      desc: APP_CONFIG.strings.URLS_SETTINGS_HIDE_DESC,
    });
    const hint = document.createElement("div");
    hint.className = "urlsSettingsHint";
    hint.id = HIDE_HINT_ID;
    hint.textContent = APP_CONFIG.strings.URLS_SETTINGS_HIDE_REQUIRES_HTTPS;
    hint.hidden = true;
    hideLabel.append(hint);

    const switchButton = document.createElement("button");
    switchButton.type = "button";
    switchButton.id = SWITCH_ID;
    switchButton.className = "urlsSettingsSwitch";
    switchButton.setAttribute("role", "switch");
    switchButton.setAttribute("aria-labelledby", HIDE_LABEL_ID);
    const track = document.createElement("span");
    track.className = "urlsSettingsSwitchTrack";
    const thumb = document.createElement("span");
    thumb.className = "urlsSettingsSwitchThumb";
    track.append(thumb);
    switchButton.append(track);
    hideRow.append(hideLabel, switchButton);

    container.append(schemeRow, hideRow);

    function syncSwitch(): void {
      const nonHttps = picker.getScheme() !== HTTPS_SCHEME;
      switchButton.setAttribute(
        "aria-checked",
        String(!nonHttps && lastHideIntent),
      );
      if (nonHttps || readOnly) {
        switchButton.setAttribute("aria-disabled", "true");
      } else {
        switchButton.removeAttribute("aria-disabled");
      }
      hint.hidden = !nonHttps;
      switchButton.setAttribute(
        "aria-describedby",
        nonHttps ? `${HIDE_DESC_ID} ${HIDE_HINT_ID}` : HIDE_DESC_ID,
      );
    }

    const picker = mountSchemePicker({
      container: $(schemeRow),
      idPrefix: "urlsSettings",
      initialScheme,
      labelledBy: SCHEME_LABEL_ID,
      toggleId: TOGGLE_ID,
      focusAfterSelect: "toggle",
      onSelect: ({ scheme }) => {
        syncSwitch();
        ctx.submit({ patch: { default_url_scheme: scheme } });
      },
    });
    picker.toggle.attr("aria-describedby", SCHEME_DESC_ID);
    picker.setReadOnly({ readOnly });

    function activateSwitch(): void {
      if (switchButton.getAttribute("aria-disabled") === "true") return;
      lastHideIntent = switchButton.getAttribute("aria-checked") !== "true";
      syncSwitch();
      ctx.submit({ patch: { hide_scheme_selector: lastHideIntent } });
    }

    // A <button> turns Enter and Space into a click, so one handler covers all.
    switchButton.addEventListener("click", activateSwitch);

    syncSwitch();

    const view: MountedView = {
      utubID: getState().activeUTubID,
      setLastHideIntent: (value) => {
        lastHideIntent = value;
        syncSwitch();
      },
    };
    mounted = view;

    return () => {
      if (mounted === view) mounted = null;
      picker.destroy();
    };
  }

  async function save({
    utubID,
    patch,
  }: {
    utubID: number | null;
    patch: SectionPatch;
  }): Promise<SaveResult> {
    if (utubID === null) return { outcome: "error" };

    // Latest intent wins: a non-https default cannot carry hide=true (the server
    // would answer 400). The mirrored switch intent is not cleared.
    const sanitized: SectionPatch = { ...patch };
    const pickedScheme = sanitized.default_url_scheme;
    const picksNonHttps =
      typeof pickedScheme === "string" && pickedScheme !== HTTPS_SCHEME;
    if (picksNonHttps && sanitized.hide_scheme_selector === true) {
      delete sanitized.hide_scheme_selector;
    }

    // The stored value, read before the await: patchUtubSettings writes the
    // response into the slice before it resolves.
    const baselineHidden =
      getState().settings?.urls?.hide_scheme_selector === true;

    const result = await patchUtubSettings({
      utubID,
      panel: "urls",
      patch: sanitized,
    });

    // The queue only resyncs from the server on an error outcome.
    if (result.outcome === "invalid") return { outcome: "error" };
    if (result.outcome !== "ok") return result;

    const hiddenAfter = result.settings?.urls?.hide_scheme_selector;
    const autoReset =
      baselineHidden &&
      !hasOwn({ patch: sanitized, key: "hide_scheme_selector" }) &&
      hiddenAfter === false;

    if (picksNonHttps && typeof hiddenAfter === "boolean") {
      const view = mounted;
      if (view !== null && view.utubID === utubID) {
        view.setLastHideIntent(hiddenAfter);
      } else {
        log("save resolved after unmount or UTub change", { utubID });
      }
    }

    if (autoReset) {
      return {
        outcome: "ok",
        settings: result.settings,
        notice: APP_CONFIG.strings.URLS_SETTINGS_SELECTOR_RESTORED,
      };
    }
    return result;
  }

  const section: PanelSection = {
    id: SECTION_ID,
    panel: "urls",
    scope: "utub",
    title: APP_CONFIG.strings.URLS_SETTINGS_SECTION_TITLE,
    render,
    save,
  };
  return registerSection(section);
}
