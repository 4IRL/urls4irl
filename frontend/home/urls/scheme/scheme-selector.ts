import { $, getInputValue } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { KEYS } from "../../../lib/constants.js";
import { fillTemplate } from "../../../lib/string-template.js";
import { isCoarsePointer } from "../../mobile.js";
import { getEffectiveDefaultScheme } from "./scheme-default.js";
import { mountSchemePicker } from "./scheme-picker.js";
import { composeURL, isAuthorityScheme } from "./scheme-utils.js";

export interface SchemeSelectorHandle {
  getScheme(): string;
  setScheme(args: {
    scheme: string;
    explicit: boolean;
    announce?: boolean;
  }): void;
  isExplicit(): boolean;
  /** The default snapshotted at mount/reset (or pinned by setDefaultScheme). */
  getDefaultScheme(): string;
  setDefaultScheme(args: { scheme: string }): void;
  setInvalid(args: { invalid: boolean }): void;
  reset(): void;
  close(): void;
  destroy(): void;
  /** True when the toggle is hidden (the UTub hides the selector). */
  isHidden(): boolean;
  /**
   * Hidden only: puts the snapshotted default back (non-explicit, input text
   * untouched) and announces it when the scheme changed. No-op when shown.
   */
  restoreDefaultScheme(): void;
  /** Re-renders the helper line (no-op when not hidden). */
  refreshHelper(): void;
}

export interface MountSchemeSelectorArgs {
  inputContainer: JQuery<HTMLElement>;
  urlInput: JQuery<HTMLElement>;
  idPrefix: string;
  /** Snapshotted by the caller at mount: hide the toggle, show the helper line. */
  hidden?: boolean;
  onChange: (args: { scheme: string; source: "user" | "auto" }) => void;
  onEscapeWhenClosed?: () => void;
}

export const SCHEME_SELECTOR_DATA_KEY = "urlSchemeSelector";

const SELECTOR_CLASS = "urlSchemeSelector";

/**
 * The selector handle mounted on `container`, or `null` when none is mounted so
 * callers (and older panels/tests) degrade to "text input only".
 */
export function getSchemeSelector({
  container,
}: {
  container: JQuery<HTMLElement>;
}): SchemeSelectorHandle | null {
  const handle = container.data(SCHEME_SELECTOR_DATA_KEY) as
    | SchemeSelectorHandle
    | undefined;
  return handle ?? null;
}

// Each mount takes the next number so its arrow-guard event namespace never
// collides with another live (or stale) instance.
let mountCounter = 0;

// The toggle's visible text is the scheme, so its accessible name carries the
// current value too ("URL scheme: https") rather than only the control's role.
function toggleAccessibleName({ scheme }: { scheme: string }): string {
  return `${APP_CONFIG.strings.URL_SCHEME_TOGGLE_LABEL}: ${scheme}`;
}

export function mountSchemeSelector({
  inputContainer,
  urlInput,
  idPrefix,
  hidden = false,
  onChange,
  onEscapeWhenClosed,
}: MountSchemeSelectorArgs): SchemeSelectorHandle {
  // Re-mounting on the same container is idempotent: tear the old one down.
  getSchemeSelector({ container: inputContainer })?.destroy();

  mountCounter += 1;
  const arrowGuardEvent = `keyup.urlSchemeArrowGuard${mountCounter}`;
  const helperInputEvent = `input.urlSchemeHelper${mountCounter}`;

  // Snapshotted at mount and at each reset so a settings change elsewhere never
  // rewrites an open panel.
  let defaultScheme = getEffectiveDefaultScheme();
  let currentScheme = defaultScheme;
  let explicit = false;
  let destroyed = false;
  let refocusTimer: ReturnType<typeof setTimeout> | null = null;
  let announceTimer: ReturnType<typeof setTimeout> | null = null;

  const announceRegion = $(document.createElement("span"))
    .addClass("urlSchemeAnnounce visually-hidden")
    .attr({ "aria-live": "polite", "aria-atomic": "true" });

  const helperId = `${idPrefix}SchemeHelper`;
  const helper = $(document.createElement("p"))
    .addClass("urlSchemeHelper")
    .attr("id", helperId);

  function setHelperDescribed({ described }: { described: boolean }): void {
    const tokens = (urlInput.attr("aria-describedby") ?? "")
      .split(/\s+/)
      .filter((token) => token !== "" && token !== helperId);
    if (described) tokens.push(helperId);
    if (tokens.length === 0) {
      urlInput.removeAttr("aria-describedby");
    } else {
      urlInput.attr("aria-describedby", tokens.join(" "));
    }
  }

  // Text nodes only (the typed text is user input). Derived from composeURL, the
  // submit logic, so the line never names a URL that would not be submitted.
  function renderHelper(): void {
    if (!hidden || destroyed) return;
    const strings = APP_CONFIG.strings;
    const prefix = `${currentScheme}${
      isAuthorityScheme({ scheme: currentScheme }) ? "://" : ":"
    }`;
    const text = getInputValue(urlInput).trim();
    const bold = (value: string): JQuery<HTMLElement> =>
      $(document.createElement("strong")).text(value);

    helper.empty();
    if (text === "") {
      helper
        .append(
          document.createTextNode(`${strings.URL_SCHEME_HELPER_DEFAULT} `),
        )
        .append(bold(prefix))
        .append(
          document.createTextNode(` ${strings.URL_SCHEME_HELPER_TYPE_HINT}`),
        );
    } else {
      const composed = composeURL({ scheme: currentScheme, text });
      // An unchanged compose (unsupported prefix, malformed token) adds no
      // scheme: the field error or the stored value speaks instead.
      if (composed !== text && composed.startsWith(prefix)) {
        helper
          .append(
            document.createTextNode(
              `${strings.URL_SCHEME_HELPER_WILL_SAVE_AS} `,
            ),
          )
          .append(bold(prefix))
          .append(document.createTextNode(composed.slice(prefix.length)));
      }
    }
    setHelperDescribed({ described: helper.contents().length > 0 });
  }

  function clearRefocusTimer(): void {
    if (refocusTimer === null) return;
    clearTimeout(refocusTimer);
    refocusTimer = null;
  }

  function focusAfterSelect(): void {
    if (isCoarsePointer()) {
      picker.toggle.trigger("focus");
      return;
    }
    // Deferred: the row activates on keyup, and focusing the URL input
    // synchronously would bind keyup.updateURLStringFocus mid-dispatch so the
    // very same Enter keyup would submit the form.
    refocusTimer = setTimeout(() => {
      refocusTimer = null;
      if (destroyed) return;
      urlInput.trigger("focus");
    }, 0);
  }

  function applyScheme({
    scheme,
    isExplicit,
  }: {
    scheme: string;
    isExplicit: boolean;
  }): void {
    currentScheme = scheme;
    explicit = isExplicit;
    picker.setScheme({ scheme });
    renderHelper();
  }

  function clearAnnounceTimer(): void {
    if (announceTimer === null) return;
    clearTimeout(announceTimer);
    announceTimer = null;
  }

  // Cleared first, then set on a deferred tick: a repeat of the same text is
  // otherwise not a change, so a screen reader would not re-read it.
  function announceScheme({ scheme }: { scheme: string }): void {
    clearAnnounceTimer();
    announceRegion.text("");
    announceTimer = setTimeout(() => {
      announceTimer = null;
      if (destroyed) return;
      announceRegion.text(
        fillTemplate({
          template: APP_CONFIG.strings.URL_SCHEME_SET_ANNOUNCE,
          values: { scheme },
        }),
      );
    }, 0);
  }

  const picker = mountSchemePicker({
    idPrefix,
    initialScheme: currentScheme,
    accessibleName: toggleAccessibleName,
    boundary: inputContainer,
    onEscapeWhenClosed,
    // Armed before onChange (via onSelect): if the owner closes/resets/destroys
    // the selector from its callback, that cancels the pending refocus instead
    // of arming one on a dead panel, and a throwing callback still gets its
    // refocus.
    focusAfterSelect,
    onSelect({ scheme }) {
      applyScheme({ scheme, isExplicit: true });
      announceScheme({ scheme });
      onChange({ scheme, source: "user" });
    },
  });
  const { toggle, listbox } = picker;

  const handle: SchemeSelectorHandle = {
    getScheme: () => currentScheme,
    isExplicit: () => explicit,
    getDefaultScheme: () => defaultScheme,
    setDefaultScheme({ scheme }) {
      defaultScheme = scheme;
    },
    setScheme({ scheme, explicit: isExplicit, announce = false }) {
      applyScheme({ scheme, isExplicit });
      if (announce) announceScheme({ scheme });
    },
    setInvalid({ invalid }) {
      picker.setInvalid({ invalid });
    },
    reset() {
      clearRefocusTimer();
      picker.close();
      defaultScheme = getEffectiveDefaultScheme();
      applyScheme({ scheme: defaultScheme, isExplicit: false });
      clearAnnounceTimer();
      announceRegion.text("");
    },
    close() {
      clearRefocusTimer();
      picker.close();
    },
    isHidden: () => hidden,
    restoreDefaultScheme() {
      if (!hidden) return;
      const changed = currentScheme !== defaultScheme;
      applyScheme({ scheme: defaultScheme, isExplicit: false });
      if (changed) announceScheme({ scheme: defaultScheme });
    },
    refreshHelper: renderHelper,
    destroy() {
      if (destroyed) return;
      destroyed = true;
      urlInput.off(helperInputEvent);
      // Cancels the pending refocus and unbinds this instance's own document,
      // focusout and key listeners (each carries a per-mount namespace).
      clearRefocusTimer();
      picker.destroy();
      clearAnnounceTimer();
      inputContainer.off(arrowGuardEvent);
      // A newer mount on this container owns the shared class, data key and DOM;
      // a stale handle must not tear those down.
      if (getSchemeSelector({ container: inputContainer }) !== handle) return;

      inputRow.children(".text-input-inner-container").insertBefore(inputRow);
      inputRow.remove();
      listbox.remove();
      announceRegion.remove();
      helper.remove();
      setHelperDescribed({ described: false });
      inputContainer.removeClass(SELECTOR_CLASS);
      inputContainer.removeData(SCHEME_SELECTOR_DATA_KEY);
    },
  };

  // --- DOM assembly: [toggle][.text-input-inner-container] row, then listbox ---
  const innerContainer = inputContainer.children(".text-input-inner-container");
  const inputRow = $(document.createElement("div")).addClass(
    "urlSchemeInputRow flex-row",
  );
  if (innerContainer.length > 0) {
    innerContainer.first().before(inputRow);
  } else {
    // No input wrapper to sit beside: still attach the toggle rather than
    // silently dropping it.
    inputContainer.prepend(inputRow);
  }
  inputRow.append(toggle).append(innerContainer);
  if (hidden) {
    // `.hidden` (display:none !important), not the attribute: the toggle's own
    // `display: inline-flex` would override `hidden`. It also leaves the tab order.
    toggle.addClass("hidden");
    inputRow.addClass("urlSchemeHidden");
    inputRow.after(helper);
    helper.after(listbox);
    // Bound on the selector so it follows typing whichever listener runs first;
    // applyScheme re-renders on every scheme change.
    urlInput.on(helperInputEvent, renderHelper);
  } else {
    inputRow.after(listbox);
  }
  listbox.after(announceRegion);
  inputContainer.addClass(SELECTOR_CLASS);

  // Arrow keyup must never reach the document-level card navigator
  // (keyup.switchurls), which has no target guard and would move the selected
  // card, tearing down an open edit panel. Stopping here, below `document`,
  // works regardless of bind order.
  inputContainer.offAndOnExact(
    arrowGuardEvent,
    function (event: JQuery.TriggeredEvent) {
      if (event.key === KEYS.ARROW_UP || event.key === KEYS.ARROW_DOWN) {
        event.stopPropagation();
      }
    },
  );

  inputContainer.data(SCHEME_SELECTOR_DATA_KEY, handle);
  renderHelper();
  return handle;
}
