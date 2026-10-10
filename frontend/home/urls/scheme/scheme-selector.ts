import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { KEYS } from "../../../lib/constants.js";
import { createRovingListbox } from "../../../lib/roving-listbox.js";
import { isCoarsePointer } from "../../mobile.js";

export interface SchemeSelectorHandle {
  element: JQuery<HTMLElement>;
  getScheme(): string;
  setScheme(args: {
    scheme: string;
    explicit: boolean;
    announce?: boolean;
  }): void;
  isExplicit(): boolean;
  setInvalid(args: { invalid: boolean }): void;
  reset(): void;
  close(): void;
  destroy(): void;
}

export interface MountSchemeSelectorArgs {
  inputContainer: JQuery<HTMLElement>;
  urlInput: JQuery<HTMLElement>;
  idPrefix: string;
  onChange: (args: { scheme: string; source: "user" | "auto" }) => void;
  onEscapeWhenClosed?: () => void;
}

export const SCHEME_SELECTOR_DATA_KEY = "urlSchemeSelector";

const SELECTOR_CLASS = "urlSchemeSelector";
const OPTION_SELECTOR = '.urlSchemeOption[role="option"]';
const ENABLED_OPTION_SELECTOR = '.urlSchemeOption[role="option"]:not(.hidden)';
const OPTIONS_SELECTOR = ".urlSchemeOptions";
const NO_MATCHES_SELECTOR = ".urlSchemeHint";

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

// Fills a `{token}` placeholder. A replacer function (not a string) so a `$&`
// or `$1` inside `value` is inserted literally instead of being expanded.
function fillTemplate({
  template,
  token,
  value,
}: {
  template: string;
  token: string;
  value: string;
}): string {
  return template.replace(token, () => value);
}

// Each mount takes the next number, so its document/container event namespaces
// and listbox/option ids never collide with another live (or stale) instance,
// even one mounted with the same idPrefix.
let mountCounter = 0;

// The toggle's visible text is the scheme, so its accessible name carries the
// current value too ("URL scheme: https") rather than only the control's role.
function toggleAccessibleName({ scheme }: { scheme: string }): string {
  return `${APP_CONFIG.strings.URL_SCHEME_TOGGLE_LABEL}: ${scheme}`;
}

// Ids and event namespaces must not contain spaces or dots.
function sanitizeIdPrefix({ idPrefix }: { idPrefix: string }): string {
  return idPrefix.replace(/[^A-Za-z0-9_-]/g, "-");
}

export function mountSchemeSelector({
  inputContainer,
  urlInput,
  idPrefix,
  onChange,
  onEscapeWhenClosed,
}: MountSchemeSelectorArgs): SchemeSelectorHandle {
  // Re-mounting on the same container is idempotent: tear the old one down.
  getSchemeSelector({ container: inputContainer })?.destroy();

  mountCounter += 1;
  const instanceKey = `${sanitizeIdPrefix({ idPrefix })}-${mountCounter}`;
  const documentClickEvent = `click.urlSchemeSelector${mountCounter}`;
  const focusOutEvent = `focusout.urlSchemeSelector${mountCounter}`;
  const arrowGuardEvent = `keyup.urlSchemeArrowGuard${mountCounter}`;
  const listboxId = `${instanceKey}-urlSchemeListbox`;

  let currentScheme = APP_CONFIG.constants.URL_DEFAULT_SCHEME;
  let explicit = false;
  let isOpen = false;
  let destroyed = false;
  let rowsBuilt = false;
  let refocusTimer: ReturnType<typeof setTimeout> | null = null;
  let announceTimer: ReturnType<typeof setTimeout> | null = null;
  // Enter on the filter activates on KEYUP (like the rows), but only when its
  // keydown also landed on the filter: opening the list with Enter on the toggle
  // moves focus to the filter mid-press, and that Enter keyup must not select.
  let filterEnterArmed = false;

  const toggleLabel = $(document.createElement("span"))
    .addClass("urlSchemeToggleLabel")
    .text(currentScheme);
  const toggleCaret = $(document.createElement("span"))
    .addClass("urlSchemeToggleCaret")
    .attr("aria-hidden", "true")
    .text("▾");
  const toggle = $(document.createElement("button"))
    .addClass("urlSchemeToggle")
    .attr({
      type: "button",
      "aria-haspopup": "listbox",
      "aria-expanded": "false",
      "aria-controls": listboxId,
      "aria-label": toggleAccessibleName({ scheme: currentScheme }),
    })
    .append(toggleLabel)
    .append(toggleCaret);

  const filterInput = $(document.createElement("input"))
    .addClass("text-input urlSchemeFilter")
    .attr({
      type: "search",
      autocomplete: "off",
      autocorrect: "off",
      autocapitalize: "off",
      "aria-label": APP_CONFIG.strings.URL_SCHEME_FILTER_LABEL,
      placeholder: APP_CONFIG.strings.URL_SCHEME_FILTER_LABEL,
    });
  const filterWrap = $(document.createElement("div"))
    .addClass("urlSchemeFilterWrap")
    .append(
      $(document.createElement("div"))
        .addClass("text-input-inner-container")
        .append(filterInput),
    );

  const noMatchesHint = $(document.createElement("div"))
    .addClass("urlSchemeHint hidden")
    .attr({ role: "status", "aria-live": "polite" })
    .text(APP_CONFIG.strings.URL_SCHEME_NO_MATCHES);
  const options = $(document.createElement("div"))
    .addClass("urlSchemeOptions")
    .attr("role", "listbox")
    .append(noMatchesHint);
  const matchMessage = $(document.createElement("div"))
    .addClass("urlSchemeMsg")
    .attr({ "aria-live": "polite", "aria-atomic": "true" });
  const listbox = $(document.createElement("div"))
    .addClass("urlSchemeListbox hidden")
    .attr("id", listboxId)
    .append(filterWrap)
    .append(options)
    .append(matchMessage);

  const announceRegion = $(document.createElement("span"))
    .addClass("urlSchemeAnnounce visually-hidden")
    .attr({ "aria-live": "polite", "aria-atomic": "true" });

  const roving = createRovingListbox({
    container: () => listbox,
    optionSelector: OPTION_SELECTOR,
    enabledOptionSelector: ENABLED_OPTION_SELECTOR,
    listboxSelector: OPTIONS_SELECTOR,
    noMatchesSelector: NO_MATCHES_SELECTOR,
    filterText: (row) => row.attr("data-scheme") ?? "",
    onActivateRow: (row) => selectRow(row),
    onEscape: () => closeList({ restoreFocus: true }),
  });

  function clearRefocusTimer(): void {
    if (refocusTimer === null) return;
    clearTimeout(refocusTimer);
    refocusTimer = null;
  }

  function buildRows(): void {
    if (rowsBuilt) return;
    rowsBuilt = true;
    const hints = APP_CONFIG.constants.URL_SCHEME_HINTS;
    const rows = APP_CONFIG.constants.URL_SCHEMES.map((scheme) => {
      const row = $(document.createElement("div"))
        .addClass("urlSchemeOption flex-row jc-sb align-center")
        .attr({
          role: "option",
          "data-scheme": scheme,
          "aria-selected": String(scheme === currentScheme),
          tabindex: "-1",
        })
        .append(
          $(document.createElement("span"))
            .addClass("urlSchemeOptionLabel")
            .text(scheme),
        );
      // Own keys only: an inherited name like "constructor" is not a hint.
      if (Object.prototype.hasOwnProperty.call(hints, scheme)) {
        row.append(
          $(document.createElement("span"))
            .addClass("urlSchemeOptionHint")
            .text(hints[scheme]),
        );
      }
      return row[0];
    });
    noMatchesHint.before(rows);
  }

  function syncSelectedRows(): void {
    options.find(OPTION_SELECTOR).each((_, element) => {
      const row = $(element);
      row.attr(
        "aria-selected",
        String(row.attr("data-scheme") === currentScheme),
      );
    });
  }

  function updateMatchMessage(): void {
    const visibleCount = options.find(ENABLED_OPTION_SELECTOR).length;
    const hasQuery = String(filterInput.val() ?? "").trim() !== "";
    if (!hasQuery || visibleCount === 0) {
      matchMessage.text("");
      return;
    }
    matchMessage.text(
      visibleCount === 1
        ? APP_CONFIG.strings.URL_SCHEME_MATCH_ONE
        : fillTemplate({
            template: APP_CONFIG.strings.URL_SCHEME_MATCH_MANY,
            token: "{count}",
            value: String(visibleCount),
          }),
    );
  }

  function clearFilter(): void {
    filterInput.val("");
    if (!rowsBuilt) return;
    roving.applyFilter("");
    matchMessage.text("");
  }

  function seedRovingEntry(): void {
    options.find(OPTION_SELECTOR).attr("tabindex", "-1");
    const selectedRow = options.find(
      `${OPTION_SELECTOR}[aria-selected="true"]`,
    );
    const entryRow =
      selectedRow.length > 0
        ? selectedRow
        : options.find(OPTION_SELECTOR).first();
    entryRow.attr("tabindex", "0");
    // Only meaningful once the listbox is visible (see openList).
    entryRow[0]?.scrollIntoView({ block: "nearest" });
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
    toggleLabel.text(scheme);
    toggle.attr("aria-label", toggleAccessibleName({ scheme }));
    syncSelectedRows();
  }

  function closeList({ restoreFocus }: { restoreFocus: boolean }): void {
    clearRefocusTimer();
    filterEnterArmed = false;
    if (!isOpen) return;
    isOpen = false;
    toggle.attr("aria-expanded", "false");
    listbox.addClass("hidden");
    roving.detachKeyListeners();
    $(document).off(documentClickEvent);
    inputContainer.off(focusOutEvent);
    clearFilter();
    if (restoreFocus) toggle.trigger("focus");
  }

  function openList(): void {
    if (isOpen) return;
    isOpen = true;
    filterEnterArmed = false;
    buildRows();
    clearFilter();
    syncSelectedRows();
    toggle.attr("aria-expanded", "true");
    listbox.removeClass("hidden");
    // After the unhide: scrollIntoView is a no-op on a `display: none` subtree.
    seedRovingEntry();
    roving.attachKeyListeners();

    $(document).offAndOnExact(
      documentClickEvent,
      function (event: JQuery.TriggeredEvent) {
        const target = event.target as Node | null;
        if (target !== null && inputContainer[0].contains(target)) return;
        closeList({ restoreFocus: false });
      },
    );
    inputContainer.offAndOnExact(
      focusOutEvent,
      function (event: JQuery.TriggeredEvent) {
        // jQuery does not copy relatedTarget onto focus events; read the native one.
        const nativeEvent = event.originalEvent as FocusEvent | undefined;
        const nextFocus = nativeEvent?.relatedTarget ?? null;
        if (!(nextFocus instanceof Node)) return;
        if (inputContainer[0].contains(nextFocus)) return;
        closeList({ restoreFocus: false });
      },
    );

    // Touch: keep focus on the toggle so the on-screen keyboard stays down.
    if (!isCoarsePointer()) filterInput.trigger("focus");
  }

  function focusAfterSelect(): void {
    if (isCoarsePointer()) {
      toggle.trigger("focus");
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
          token: "{scheme}",
          value: scheme,
        }),
      );
    }, 0);
  }

  function selectRow(row: JQuery<HTMLElement>): void {
    const scheme = row.attr("data-scheme");
    if (scheme === undefined) return;
    applyScheme({ scheme, isExplicit: true });
    announceScheme({ scheme });
    closeList({ restoreFocus: false });
    // Armed before onChange: if the owner closes/resets/destroys the selector
    // from its callback, that cancels the pending refocus instead of arming one
    // on a dead panel, and a throwing callback still gets its refocus.
    focusAfterSelect();
    onChange({ scheme, source: "user" });
  }

  function selectFirstVisibleRow(): void {
    const firstRow = options.find(ENABLED_OPTION_SELECTOR).first();
    if (firstRow.length > 0) selectRow(firstRow);
  }

  const handle: SchemeSelectorHandle = {
    element: inputContainer,
    getScheme: () => currentScheme,
    isExplicit: () => explicit,
    setScheme({ scheme, explicit: isExplicit, announce = false }) {
      applyScheme({ scheme, isExplicit });
      if (announce) announceScheme({ scheme });
    },
    setInvalid({ invalid }) {
      toggle.toggleClass("invalid-field", invalid);
    },
    reset() {
      closeList({ restoreFocus: false });
      applyScheme({
        scheme: APP_CONFIG.constants.URL_DEFAULT_SCHEME,
        isExplicit: false,
      });
      clearAnnounceTimer();
      announceRegion.text("");
    },
    close() {
      closeList({ restoreFocus: false });
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      // Cancels the pending refocus and unbinds this instance's own document,
      // focusout and key listeners (each carries a per-mount namespace).
      closeList({ restoreFocus: false });
      clearAnnounceTimer();
      toggle.off(".urlSchemeToggle .urlSchemeToggleEscape");
      filterInput.off(".urlSchemeFilter");
      options.off(".urlSchemeSelect");
      inputContainer.off(arrowGuardEvent);
      // A newer mount on this container owns the shared class, data key and DOM;
      // a stale handle must not tear those down.
      if (getSchemeSelector({ container: inputContainer }) !== handle) return;

      inputRow.children(".text-input-inner-container").insertBefore(inputRow);
      inputRow.remove();
      listbox.remove();
      announceRegion.remove();
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
  inputRow.after(listbox);
  listbox.after(announceRegion);
  inputContainer.addClass(SELECTOR_CLASS);

  // --- Handlers ---------------------------------------------------------------
  toggle.offAndOnExact("click.urlSchemeToggle", () => {
    if (isOpen) closeList({ restoreFocus: true });
    else openList();
  });

  toggle.offAndOnExact(
    "keydown.urlSchemeToggleEscape",
    function (event: JQuery.TriggeredEvent) {
      if (event.key !== KEYS.ESCAPE) return;
      if (isOpen) {
        // Coarse pointer: focus never left the toggle, so the list's own
        // capture-phase Escape (bound on the listbox) cannot see this event.
        event.stopPropagation();
        event.preventDefault();
        closeList({ restoreFocus: true });
        return;
      }
      // Closed: an owner callback handles it (and must not also hit a panel-level
      // Escape handler); with no owner, bubble untouched.
      if (onEscapeWhenClosed === undefined) return;
      event.stopPropagation();
      onEscapeWhenClosed();
    },
  );

  options.offAndOnExact(
    "click.urlSchemeSelect",
    function (event: JQuery.TriggeredEvent) {
      const row = $(event.target as HTMLElement).closest(OPTION_SELECTOR);
      if (row.length > 0) selectRow(row);
    },
  );

  filterInput.offAndOnExact("input.urlSchemeFilter", () => {
    roving.applyFilter(String(filterInput.val() ?? ""));
    updateMatchMessage();
  });
  filterInput.offAndOnExact(
    "keydown.urlSchemeFilter",
    function (event: JQuery.TriggeredEvent) {
      if (event.key !== KEYS.ENTER) return;
      event.preventDefault();
      filterEnterArmed = true;
    },
  );
  filterInput.offAndOnExact(
    "keyup.urlSchemeFilter",
    function (event: JQuery.TriggeredEvent) {
      if (event.key !== KEYS.ENTER || !filterEnterArmed) return;
      filterEnterArmed = false;
      selectFirstVisibleRow();
    },
  );

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
  return handle;
}
