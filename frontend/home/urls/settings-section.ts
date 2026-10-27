import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { getState } from "../../store/app-store.js";
import { patchUtubSettings } from "../panel-settings/client.js";
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
const ALLOW_SHORT_LINKS_SWITCH_ID = "urlsSettingsAllowShortLinksSwitch";
const ALLOW_SHORT_LINKS_LABEL_ID = "urlsSettingsAllowShortLinksLabel";
const ALLOW_SHORT_LINKS_DESC_ID = "urlsSettingsAllowShortLinksDesc";

/** What the live render exposes to `save` so a server-driven flip lands in place. */
interface MountedView {
  utubID: number | null;
  setLastHideIntent: (value: boolean) => void;
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

    const switchButton = buildSwitchButton({
      id: SWITCH_ID,
      labelledBy: HIDE_LABEL_ID,
    });
    hideRow.append(hideLabel, switchButton);

    // Row 3: allow short links switch.
    const shortLinksRow = document.createElement("div");
    shortLinksRow.className = "panelSettingsRow";
    const shortLinksSwitch = buildSwitchButton({
      id: ALLOW_SHORT_LINKS_SWITCH_ID,
      labelledBy: ALLOW_SHORT_LINKS_LABEL_ID,
    });
    shortLinksSwitch.setAttribute(
      "aria-describedby",
      ALLOW_SHORT_LINKS_DESC_ID,
    );
    shortLinksSwitch.setAttribute(
      "aria-checked",
      String(urlsSlice?.allow_short_links ?? true),
    );
    if (readOnly) shortLinksSwitch.setAttribute("aria-disabled", "true");
    shortLinksRow.append(
      buildRowLabel({
        titleId: ALLOW_SHORT_LINKS_LABEL_ID,
        title: APP_CONFIG.strings.URLS_SETTINGS_ALLOW_SHORT_LINKS_LABEL,
        descId: ALLOW_SHORT_LINKS_DESC_ID,
        desc: APP_CONFIG.strings.URLS_SETTINGS_ALLOW_SHORT_LINKS_DESC,
      }),
      shortLinksSwitch,
    );
    shortLinksSwitch.addEventListener("click", () => {
      if (shortLinksSwitch.getAttribute("aria-disabled") === "true") return;
      const allow = shortLinksSwitch.getAttribute("aria-checked") !== "true";
      shortLinksSwitch.setAttribute("aria-checked", String(allow));
      ctx.submit({ patch: { allow_short_links: allow } });
    });

    container.append(schemeRow, hideRow, shortLinksRow);

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

    // A coalesced patch can carry both; announce each change that happened.
    const notices: string[] = [];
    const allowIntent = sanitized.allow_short_links;
    if (typeof allowIntent === "boolean") {
      notices.push(
        allowIntent
          ? APP_CONFIG.strings.URLS_SETTINGS_SHORT_LINKS_ON_NOTICE
          : APP_CONFIG.strings.URLS_SETTINGS_SHORT_LINKS_OFF_NOTICE,
      );
    }
    if (autoReset) {
      notices.push(APP_CONFIG.strings.URLS_SETTINGS_SELECTOR_RESTORED);
    }
    if (notices.length > 0) {
      return {
        outcome: "ok",
        settings: result.settings,
        notice: notices.join(". "),
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
