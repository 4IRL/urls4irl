import type { UtubUrlItem, UtubTag } from "../../../types/url.js";
import type {
  AddTagsRequest,
  UrlTagsModifiedResponse,
  UrlTagError,
} from "./combobox-state.js";

import { $, bootstrap } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { KEYS } from "../../../lib/constants.js";
import { emit } from "../../../lib/metrics-client.js";
import { clearOpenForm, setOpenForm } from "../../../lib/modal-tracking.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import {
  FORM_CANCEL_TRIGGER,
  FORM_SUBMIT_TRIGGER,
  HOME_FORM,
  TAG_SCOPE,
} from "../../../types/metrics-dim-values.js";
import { filterTagSuggestions, hasExactTagMatch } from "./combobox-state.js";
import {
  createTagDeleteIcon,
  disableTagRemovalInURLCard,
  enableTagRemovalInURLCard,
} from "./tags.js";
import {
  disableEditingURLString,
  disableEditingURLTitle,
  enableEditingURLString,
  enableEditingURLTitle,
} from "../cards/utils.js";
import {
  disableClickOnSelectedURLCardToHide,
  enableClickOnSelectedURLCardToHide,
} from "../cards/selection.js";
import {
  setTimeoutAndShowURLCardLoadingIcon,
  clearTimeoutIDAndHideLoadingIcon,
} from "../cards/loading.js";
import { getUpdatedURL, handleRejectFromGetURL } from "../cards/get.js";
import { isMobile } from "../../mobile.js";
import {
  enableTabbableChildElements,
  disableTabbableChildElements,
} from "../../../lib/jquery-plugins.js";
import { createAddTagIcon } from "../cards/options/tag-btn.js";
import { renderAppliedTagsForUrl } from "../tags/tag-render.js";
import { getState, setState } from "../../../store/app-store.js";

const SUBMIT_FIELD_NAMES = ["tagStrings"] as const;

type SubmitFieldName = (typeof SUBMIT_FIELD_NAMES)[number];

function isSubmitFieldName(key: string): key is SubmitFieldName {
  return (SUBMIT_FIELD_NAMES as readonly string[]).includes(key);
}

const FILTER_DEBOUNCE_MS = 200;
const OPTION_ID_PREFIX = "urlTagOption";
const TOOLTIP_STORE_KEY = "urlTagComboboxTooltip";
export const STAGED_RESET_KEY = "urlTagComboboxResetStaged";
export const STAGED_GET_KEY = "urlTagComboboxGetStaged";
const LIMIT_SYNC_KEY = "urlTagComboboxSyncLimit";

let comboboxIdCounter = 0;

/**
 * Discriminated union of arguments for `createTagComboboxBlock`. `url`-mode
 * mounts on an existing URL card and owns a `utubUrlID` for the batch-apply
 * endpoint. `create`-mode is staging-only inside the Create URL form: there is
 * no `utubUrlID` yet (the URL does not exist), no card to read applied tags
 * from, and the batch-submit path is suppressed in favor of folding staged tags
 * into the create request.
 */
type ComboboxBlockArgs =
  | { mode: "url"; urlCard: JQuery; utubID: number; utubUrlID: number }
  | {
      mode: "create";
      urlCard: null;
      utubID: number;
      onSecondEscape?: () => void;
    };

interface ComboboxRefs {
  mode: "url" | "create";
  urlCard: JQuery | null;
  utubID: number;
  utubUrlID: number;
  wrap: JQuery;
  combobox: JQuery;
  input: JQuery;
  listbox: JQuery;
  message: JQuery;
  submitBtn: JQuery;
  listboxId: string;
  stagedStrings: string[];
  debounceTimer: ReturnType<typeof setTimeout> | null;
  onSecondEscape?: () => void;
}

/**
 * Reads the count of tags already applied to this URL from its
 * `data-utub-url-tag-ids` attribute (comma-separated tag IDs).
 *
 * Example: `data-utub-url-tag-ids="3,7"` → 2.
 */
function getAppliedTagCount(urlCard: JQuery | null): number {
  if (urlCard === null) return 0;
  const raw = (urlCard.attr("data-utub-url-tag-ids") || "").trim();
  if (!raw) return 0;
  return raw.split(",").filter((part) => part.trim().length > 0).length;
}

/**
 * Reads the set of tag IDs already applied to this URL from the card's
 * `data-utub-url-tag-ids` attribute.
 */
function getAppliedTagIds(urlCard: JQuery | null): number[] {
  if (urlCard === null) return [];
  const raw = (urlCard.attr("data-utub-url-tag-ids") || "").trim();
  if (!raw) return [];
  return raw
    .split(",")
    .map((part) => parseInt(part.trim(), 10))
    .filter((id) => !Number.isNaN(id));
}

/**
 * DOM-only builder for the per-URL combobox. Returns the `.urlTagComboboxWrap`
 * node **hidden**; no focus, no lifecycle side effects. Mirrors how
 * `createTagInputBlock` is mounted at card-build time. The open-time lifecycle
 * lives in `showTagCombobox`.
 */
export function createTagComboboxBlock(
  args: ComboboxBlockArgs,
): JQuery<HTMLElement> {
  const { mode, urlCard, utubID } = args;
  const isCreateMode = mode === "create";
  const listboxId = `${OPTION_ID_PREFIX}Listbox-${++comboboxIdCounter}`;

  const wrap = $(document.createElement("div")).addClass(
    "urlTagComboboxWrap hidden flex-column gap-5p",
  );

  const combobox = $(document.createElement("div")).addClass(
    "urlTagCombobox flex-row flex-start",
  );

  const inputId = `${listboxId}-input`;
  const input = $(document.createElement("input"))
    .addClass("urlTagComboboxInput")
    .attr({
      type: "text",
      id: inputId,
      role: "combobox",
      "aria-expanded": "false",
      "aria-controls": listboxId,
      "aria-autocomplete": "list",
      placeholder: APP_CONFIG.strings.ADD_TAGS_PLACEHOLDER,
      minLength: APP_CONFIG.constants.TAGS_MIN_LENGTH,
      maxLength: APP_CONFIG.constants.TAGS_MAX_LENGTH,
    })
    .css("font-size", "16px");

  // Create-mode shows a visible "Tags (optional)" sub-label tied to the input
  // via `for=`; url-mode keeps the existing `aria-label="Add tags"` (no visible
  // label in the URL card). A `<label for=>` takes precedence for screen readers,
  // so the `aria-label` is omitted in create-mode to avoid a conflicting name.
  if (isCreateMode) {
    const label = $(document.createElement("label"))
      .addClass("urlTagComboboxLabel")
      .attr({ for: inputId })
      .text(APP_CONFIG.strings.TAGS_OPTIONAL_LABEL);
    wrap.append(label);
  } else {
    input.attr("aria-label", APP_CONFIG.strings.ADD_TAGS_ARIA_LABEL);
  }

  combobox.append(input);

  const listbox = $(document.createElement("div"))
    .addClass("urlTagListbox hidden")
    .attr({ role: "listbox", id: listboxId });

  const message = $(document.createElement("div"))
    .addClass("urlTagComboboxMsg")
    .attr({ "aria-live": "polite", "aria-atomic": "true" });

  const submitBtn = $(document.createElement("button"))
    .addClass("urlTagComboboxSubmitBtn")
    .attr({ type: "button" })
    .text(APP_CONFIG.strings.ADD_TAGS_SUBMIT);

  const actions = $(document.createElement("div")).addClass(
    "urlTagComboboxActions flex-row gap-5p",
  );

  // Create-mode has no internal submit button: staged tags are folded into the
  // create-URL request, so the batch-apply submit button is omitted entirely.
  if (!isCreateMode) {
    actions.append(submitBtn);
  }

  const footer = $(document.createElement("div"))
    .addClass("urlTagComboboxFooter")
    .append(message)
    .append(actions);

  wrap.append(combobox).append(listbox).append(footer);

  const refs: ComboboxRefs = {
    mode,
    urlCard,
    utubID,
    // url-mode owns a real `utubUrlID`; create-mode has none yet (the URL does
    // not exist) and never reaches the batch-submit path that reads it.
    utubUrlID: args.mode === "url" ? args.utubUrlID : -1,
    wrap,
    combobox,
    input,
    listbox,
    message,
    submitBtn,
    listboxId,
    stagedStrings: [],
    debounceTimer: null,
    onSecondEscape: args.mode === "create" ? args.onSecondEscape : undefined,
  };

  // Expose a staged-state reset so the close/reset lifecycle (which only has the
  // `urlCard` DOM, not this closure) can clear the backing string array — the
  // DOM chips are removed there, but `refs.stagedStrings` must be cleared too.
  wrap.data(STAGED_RESET_KEY, () => {
    refs.stagedStrings = [];
  });

  // Exposes the current staged strings to the create-URL form (which only has the
  // wrap DOM, not this closure) so they can be folded into the create request.
  // Returns a defensive copy so callers cannot mutate the backing array.
  wrap.data(STAGED_GET_KEY, () => [...refs.stagedStrings]);

  // Lets the open-time lifecycle (which only has `urlCard`, not this closure)
  // reflect the URL's tag count immediately on open: at the cap, show the
  // limit-reached message + disabled input before any keystroke.
  wrap.data(LIMIT_SYNC_KEY, () => {
    if (remainingCapacity(refs) <= 0) {
      setLimitReachedState(refs);
    } else {
      reEnableInputIfBelowLimit(refs);
    }
  });

  bindComboboxBehavior(refs);

  return wrap;
}

/**
 * Wires all event listeners to the combobox elements. Operates on the closure
 * `refs` so each card's combobox owns its own staged-strings state.
 */
function bindComboboxBehavior(refs: ComboboxRefs): void {
  const { input, combobox, submitBtn } = refs;

  input.on("focus.urlTagCombobox", () => combobox.addClass("focused"));
  input.on("blur.urlTagCombobox", () => {
    combobox.removeClass("focused");
    if (refs.debounceTimer) clearTimeout(refs.debounceTimer);
  });

  input.on("input.urlTagCombobox", () => {
    if (refs.debounceTimer) clearTimeout(refs.debounceTimer);
    refs.debounceTimer = setTimeout(() => {
      renderListbox(refs);
    }, FILTER_DEBOUNCE_MS);
  });

  input.on("keydown.urlTagCombobox", (keydownEvent: JQuery.TriggeredEvent) =>
    handleInputKeydown(refs, keydownEvent),
  );

  // Create-mode has no batch-submit button and no `urlCard`/`utubUrlID`; staged
  // tags are folded into the create-URL request instead, so the batch-apply
  // click handler is never wired.
  if (refs.urlCard === null) return;
  const submitUrlCard = refs.urlCard;

  submitBtn.on("click.urlTagCombobox", () => {
    if (refs.stagedStrings.length === 0) return;
    emit({
      event: UI_EVENTS.UI_FORM_SUBMIT,
      form: HOME_FORM.TAG_CREATE,
      trigger: FORM_SUBMIT_TRIGGER.BUTTON_CLICK,
    });
    clearOpenForm();
    void submitStagedTags({
      urlCard: submitUrlCard,
      utubID: refs.utubID,
      utubUrlID: refs.utubUrlID,
      stagedStrings: [...refs.stagedStrings],
    });
  });
}

/**
 * Remaining number of tags that can still be staged/applied before the URL
 * hits the cap. `TAGS_MAX_ON_URLS - (appliedCount + stagedCount)`.
 */
function remainingCapacity(refs: ComboboxRefs): number {
  const appliedCount = getAppliedTagCount(refs.urlCard);
  return (
    APP_CONFIG.constants.TAGS_MAX_ON_URLS -
    (appliedCount + refs.stagedStrings.length)
  );
}

/**
 * Returns the currently active option element (if any), per
 * `aria-activedescendant`.
 */
function getActiveOption(refs: ComboboxRefs): JQuery {
  const activeId = refs.input.attr("aria-activedescendant");
  if (!activeId) return $();
  return refs.listbox.find(`#${activeId}`);
}

/**
 * Rebuilds the listbox options from `filterTagSuggestions`, the conditional
 * "Create tag" option, the empty-UTub hint, and the applied-tag disabled rows.
 */
function renderListbox(refs: ComboboxRefs): void {
  const { input, listbox } = refs;
  const query = (input.val() as string) ?? "";
  const trimmedQuery = query.trim();

  listbox.empty();
  input.removeAttr("aria-activedescendant");

  const remaining = remainingCapacity(refs);
  const atLimit = remaining <= 0;

  if (atLimit) {
    listbox.addClass("hidden");
    input.attr("aria-expanded", "false");
    setLimitReachedState(refs);
    return;
  }

  const appliedTagIds = getAppliedTagIds(refs.urlCard);
  const suggestions = filterTagSuggestions({
    query: trimmedQuery,
    appliedTagIds,
    stagedTagStrings: refs.stagedStrings,
  });

  const hasAnyUtubTags = getState().tags.length > 0;
  let optionIndex = 0;

  suggestions.forEach((tag) => {
    listbox.append(buildSuggestionOption(refs, tag, optionIndex++));
  });

  const showCreateNew =
    trimmedQuery.length >= APP_CONFIG.constants.TAGS_MIN_LENGTH &&
    !hasExactTagMatch({ query: trimmedQuery });

  if (showCreateNew) {
    listbox.append(buildCreateNewOption(refs, trimmedQuery, optionIndex++));
  }

  if (!hasAnyUtubTags && trimmedQuery.length === 0) {
    listbox.append(buildHintRow());
    listbox.removeClass("hidden");
    input.attr("aria-expanded", "true");
    announce(refs, APP_CONFIG.strings.TAGS_EMPTY_HINT);
    // Keep the submit button in sync even on this early-return path: in a UTub
    // with no existing tags, staging the first chip lands here, and skipping this
    // would leave the submit button stuck disabled.
    updateSubmitState(refs);
    return;
  }

  const hasOptions = optionIndex > 0;
  listbox.toggleClass("hidden", !hasOptions);
  input.attr("aria-expanded", hasOptions ? "true" : "false");

  if (hasOptions) {
    // Auto-activate only the "create new" action row (never an arbitrary
    // existing match), so that — and only that — row carries the active
    // highlight on render. Existing suggestions highlight on hover/arrow. When
    // there is no create-new row (e.g. the query exactly matches a tag), nothing
    // is pre-highlighted, and Enter still stages the typed query directly.
    const createNewOption = listbox.find(".urlTagOptionCreateNew");
    if (createNewOption.length > 0) {
      activateOption(refs, createNewOption);
    }
    announceMatchCount(refs, suggestions.length);
  } else if (trimmedQuery.length > 0) {
    announce(refs, APP_CONFIG.strings.TAGS_NO_MATCHES);
  } else {
    // An empty query yields no suggestions by design (filter-only behavior), so
    // the dropdown closes silently — no "no matches" announcement. This path is
    // hit e.g. right after staging a chip clears the input and re-renders; clear
    // any lingering match-count text from the prior keystroke.
    announce(refs, "");
  }

  updateSubmitState(refs);
}

function buildSuggestionOption(
  refs: ComboboxRefs,
  tag: UtubTag,
  index: number,
): JQuery {
  const optionId = `${refs.listboxId}-opt-${index}`;
  const option = $(document.createElement("div"))
    .addClass("urlTagOption")
    .attr({ role: "option", id: optionId, "aria-selected": "false" })
    .data("tagString", tag.tagString);

  option.append(
    $(document.createElement("span"))
      .addClass("urlTagOptionLabel")
      .text(tag.tagString),
  );
  option.append(
    $(document.createElement("span"))
      .addClass("urlTagOptionCount")
      .text(`${tag.tagApplied} URLs`),
  );

  option.on("click.urlTagCombobox", () => stageTagString(refs, tag.tagString));
  return option;
}

function buildCreateNewOption(
  refs: ComboboxRefs,
  query: string,
  index: number,
): JQuery {
  const optionId = `${refs.listboxId}-opt-${index}`;
  const option = $(document.createElement("div"))
    .addClass("urlTagOption urlTagOptionCreateNew")
    .attr({ role: "option", id: optionId, "aria-selected": "false" })
    .data("tagString", query)
    .data("createNew", true);

  option.append(
    $(document.createElement("span"))
      .addClass("urlTagOptionCreateIcon")
      .attr({ "aria-hidden": "true" })
      .text("+"),
  );
  option.append(
    $(document.createElement("span"))
      .addClass("urlTagOptionLabel")
      .text(`${APP_CONFIG.strings.TAG_CREATE_NEW} "${query}"`),
  );

  option.on("click.urlTagCombobox", () => stageTagString(refs, query));
  return option;
}

function buildHintRow(): JQuery {
  return $(document.createElement("div"))
    .addClass("urlTagListboxHint")
    .attr({ role: "presentation" })
    .text(APP_CONFIG.strings.TAGS_EMPTY_HINT);
}

/**
 * Moves the active option highlight to the given option element and updates
 * `aria-activedescendant`.
 */
function activateOption(refs: ComboboxRefs, option: JQuery): void {
  refs.listbox
    .find(".urlTagOption")
    .removeClass("active")
    .attr("aria-selected", "false");
  if (option.length === 0) {
    refs.input.removeAttr("aria-activedescendant");
    return;
  }
  option.addClass("active").attr("aria-selected", "true");
  refs.input.attr("aria-activedescendant", option.attr("id") as string);
}

function moveActiveOption(refs: ComboboxRefs, direction: 1 | -1): void {
  const options = refs.listbox.find(".urlTagOption");
  if (options.length === 0) return;

  const active = getActiveOption(refs);
  let nextIndex: number;
  if (active.length === 0) {
    nextIndex = direction === 1 ? 0 : options.length - 1;
  } else {
    const currentIndex = options.index(active);
    nextIndex = (currentIndex + direction + options.length) % options.length;
  }
  activateOption(refs, options.eq(nextIndex));
}

/**
 * Stages a (trimmed, non-empty, length-valid) tag string as a chip. Already
 * staged strings (case-insensitive) and over-cap stages are ignored.
 */
function stageTagString(refs: ComboboxRefs, rawString: string): void {
  const trimmed = rawString.trim();
  if (trimmed.length < APP_CONFIG.constants.TAGS_MIN_LENGTH) return;
  if (trimmed.length > APP_CONFIG.constants.TAGS_MAX_LENGTH) return;
  if (remainingCapacity(refs) <= 0) return;

  const alreadyStaged = refs.stagedStrings.some(
    (staged) => staged.toLowerCase() === trimmed.toLowerCase(),
  );
  if (alreadyStaged) return;

  refs.stagedStrings.push(trimmed);
  refs.combobox
    .find(".urlTagComboboxInput")
    .before(buildStagedChip(refs, trimmed));

  refs.input.val("");
  // renderListbox already applies the limit-reached state when capacity hits 0.
  renderListbox(refs);
}

function buildStagedChip(refs: ComboboxRefs, tagString: string): JQuery {
  const chip = $(document.createElement("span"))
    .addClass("urlTagStagedChip flex-row align-center")
    .attr({ "data-staged-tag-string": tagString });

  chip.append(
    $(document.createElement("span"))
      .addClass("urlTagStagedChipText")
      .text(tagString),
  );

  const removeButton = $(document.createElement("button"))
    .addClass(
      "urlTagStagedChipRemove flex-row align-center pointerable tabbable",
    )
    .attr({ type: "button", "aria-label": `Remove tag ${tagString}` })
    .append(createTagDeleteIcon());

  removeButton.on("click.urlTagCombobox", () =>
    removeStagedChip(refs, chip, tagString),
  );

  chip.append(removeButton);
  return chip;
}

/**
 * Removes a staged chip and its backing string, returning focus to the input
 * (WCAG 2.4.3 focus order).
 */
function removeStagedChip(
  refs: ComboboxRefs,
  chip: JQuery,
  tagString: string,
): void {
  refs.stagedStrings = refs.stagedStrings.filter(
    (staged) => staged !== tagString,
  );
  chip.remove();
  reEnableInputIfBelowLimit(refs);
  renderListbox(refs);
  refs.input.trigger("focus");
}

function reEnableInputIfBelowLimit(refs: ComboboxRefs): void {
  if (remainingCapacity(refs) > 0) {
    refs.input.prop("disabled", false);
    refs.combobox.removeClass("disabled");
  }
}

/**
 * Disables the input + create-new and surfaces the limit-reached message when
 * the URL is at capacity. Chips stay removable.
 */
function setLimitReachedState(refs: ComboboxRefs): void {
  refs.input.prop("disabled", true).val("");
  refs.combobox.addClass("disabled");
  refs.listbox.empty().addClass("hidden");
  refs.input.attr("aria-expanded", "false");
  announce(
    refs,
    APP_CONFIG.strings.TAGS_LIMIT_REACHED.replace(
      "{max}",
      String(APP_CONFIG.constants.TAGS_MAX_ON_URLS),
    ),
    "warn",
  );
  updateSubmitState(refs);
}

function announce(
  refs: ComboboxRefs,
  text: string,
  tone: "normal" | "warn" = "normal",
): void {
  refs.message.text(text);
  refs.message.toggleClass("warn", tone === "warn");
}

function announceMatchCount(refs: ComboboxRefs, count: number): void {
  const text =
    count === 1
      ? APP_CONFIG.strings.TAGS_MATCH_COUNT_ONE
      : APP_CONFIG.strings.TAGS_MATCH_COUNT.replace("{n}", String(count));
  announce(refs, text);
}

function updateSubmitState(refs: ComboboxRefs): void {
  refs.submitBtn.prop("disabled", refs.stagedStrings.length === 0);
}

/**
 * Keydown dispatch for the combobox input. All handlers bound to `keydown`
 * (never `keyup`) so the combobox beats the tag-sheet listener and ESC is not
 * subject to the keyup stale-event race.
 */
function handleInputKeydown(
  refs: ComboboxRefs,
  keydownEvent: JQuery.TriggeredEvent,
): void {
  const query = ((refs.input.val() as string) ?? "").trim();
  const activeOption = getActiveOption(refs);

  switch (keydownEvent.key) {
    case KEYS.ARROW_DOWN:
      keydownEvent.preventDefault();
      moveActiveOption(refs, 1);
      break;
    case KEYS.ARROW_UP:
      keydownEvent.preventDefault();
      moveActiveOption(refs, -1);
      break;
    case KEYS.ENTER: {
      keydownEvent.preventDefault();
      const canSubmit =
        query.length === 0 &&
        refs.stagedStrings.length > 0 &&
        activeOption.length === 0;
      if (canSubmit) {
        // Create-mode has no batch-submit path: Enter with only staged tags is a
        // no-op so it never folds into a batch AJAX call. Users Tab to (or click)
        // the form's "Add URL" button, which folds staged tags into the create
        // request instead.
        if (refs.urlCard === null) break;
        emit({
          event: UI_EVENTS.UI_FORM_SUBMIT,
          form: HOME_FORM.TAG_CREATE,
          trigger: FORM_SUBMIT_TRIGGER.ENTER_KEY,
        });
        clearOpenForm();
        void submitStagedTags({
          urlCard: refs.urlCard,
          utubID: refs.utubID,
          utubUrlID: refs.utubUrlID,
          stagedStrings: [...refs.stagedStrings],
        });
      } else {
        stageActiveOrQuery(refs, query, activeOption);
      }
      break;
    }
    case KEYS.TAB: {
      if (activeOption.length > 0) {
        keydownEvent.preventDefault();
        stageActiveOrQuery(refs, query, activeOption);
        // In create-mode `urlCard` is null and there is no internal submit button
        // to focus; Tab propagates naturally to the form's "Add URL" button.
        if (remainingCapacity(refs) <= 0 && refs.urlCard !== null) {
          refs.submitBtn.trigger("focus");
        }
      }
      break;
    }
    case KEYS.BACKSPACE:
      if (query.length === 0 && refs.stagedStrings.length > 0) {
        keydownEvent.preventDefault();
        const lastChip = refs.combobox.find(".urlTagStagedChip").last();
        const lastString = lastChip.attr("data-staged-tag-string") as string;
        removeStagedChip(refs, lastChip, lastString);
      }
      break;
    case KEYS.ESCAPE:
      if (!refs.listbox.hasClass("hidden")) {
        // First Escape: close only the dropdown; do not let it bubble to the
        // card-level cancel/deselect handlers.
        keydownEvent.stopPropagation();
        keydownEvent.preventDefault();
        closeDropdown(refs);
      } else {
        // Second Escape (dropdown already closed): cancel the whole combobox.
        emit({
          event: UI_EVENTS.UI_FORM_CANCEL,
          form: HOME_FORM.TAG_CREATE,
          trigger: FORM_CANCEL_TRIGGER.ESCAPE_KEY,
        });
        if (refs.urlCard === null) {
          // Create-mode: the combobox is a sub-control of the create-URL form. It
          // does not own the form lifecycle, but the open-form token
          // (`HOME_FORM.URL_CREATE`) must still be cleared here before delegating
          // dismissal to the create form's hide handler — never skip
          // `clearOpenForm()`.
          clearOpenForm();
          refs.onSecondEscape?.();
        } else {
          clearOpenForm();
          hideAndResetTagCombobox(refs.urlCard);
        }
      }
      break;
    default:
    /* no-op */
  }
}

function stageActiveOrQuery(
  refs: ComboboxRefs,
  query: string,
  activeOption: JQuery,
): void {
  if (activeOption.length > 0) {
    stageTagString(refs, activeOption.data("tagString") as string);
  } else if (query.length > 0) {
    stageTagString(refs, query);
  }
}

function closeDropdown(refs: ComboboxRefs): void {
  if (refs.debounceTimer) clearTimeout(refs.debounceTimer);
  refs.listbox.empty().addClass("hidden");
  refs.input.attr("aria-expanded", "false").removeAttr("aria-activedescendant");
}

/**
 * Open-time lifecycle. Mirrors `showCreateURLTagForm` in `create.ts`. Expects
 * `createTagComboboxBlock` to have already mounted the hidden wrap at card-build
 * time.
 */
export function showTagCombobox({
  urlCard,
  urlTagBtnCreate,
}: {
  urlCard: JQuery;
  urlTagBtnCreate: JQuery;
}): void {
  emit({ event: UI_EVENTS.UI_TAG_CREATE_OPEN, scope: TAG_SCOPE.URL });
  setOpenForm(HOME_FORM.TAG_CREATE);

  const comboboxWrap = urlCard.find(".urlTagComboboxWrap");
  enableTabbableChildElements(comboboxWrap);
  comboboxWrap.showClassFlex();

  // Reflect the URL's tag count immediately: if it is already at the cap, show
  // the limit-reached message + disabled input on open, not after the first key.
  const syncLimit = comboboxWrap.data(LIMIT_SYNC_KEY) as
    | (() => void)
    | undefined;
  if (syncLimit) syncLimit();

  if (isMobile()) {
    comboboxWrap.find("input").focus();
  } else {
    setTimeout(function () {
      comboboxWrap.find("input").trigger("focus");
    }, 100);
  }

  // Disable URL buttons while tags are being added
  urlCard.find(".urlBtnAccess").hideClass();
  disableEditingURLString(urlCard);
  urlCard.find(".urlBtnDelete").hideClass();
  urlCard.find(".urlBtnCopy").hideClass();

  // Prevent hovering on tags from adding padding
  urlCard.find(".tagBadge").removeClass("tagBadgeHoverable");

  const tooltipElement = urlTagBtnCreate.get(0);
  const tooltip = tooltipElement
    ? bootstrap.Tooltip.getInstance(tooltipElement)
    : null;
  if (tooltip) {
    tooltip.hide();
    tooltip.disable();
    urlCard.data(TOOLTIP_STORE_KEY, tooltip);
  }

  urlTagBtnCreate
    .removeClass("fourty-p-width")
    .addClass("cancel urlTagCancelBigBtnCreate")
    .text("Cancel")
    .offAndOnExact("click", function () {
      emit({
        event: UI_EVENTS.UI_FORM_CANCEL,
        form: HOME_FORM.TAG_CREATE,
        trigger: FORM_CANCEL_TRIGGER.CANCEL_BUTTON,
      });
      clearOpenForm();
      hideAndResetTagCombobox(urlCard);
    });

  disableTagRemovalInURLCard(urlCard);
  disableEditingURLTitle(urlCard);
  disableClickOnSelectedURLCardToHide(urlCard);
}

/**
 * Close + reset lifecycle. Mirrors `hideAndResetCreateURLTagForm`. Clears staged
 * chips, restores card buttons, re-enables tag removal/hover/tooltip, and
 * re-enables card-deselect when the card is still selected.
 */
export function hideAndResetTagCombobox(urlCard: JQuery): void {
  const comboboxWrap = urlCard.find(".urlTagComboboxWrap");

  // Modify add tag button back to its add state
  const urlTagBtnCreate = urlCard.find(".urlTagBtnCreate");
  urlTagBtnCreate
    .removeClass("cancel urlTagCancelBigBtnCreate")
    .addClass("fourty-p-width")
    .offAndOnExact("click", function () {
      showTagCombobox({ urlCard, urlTagBtnCreate });
    })
    .text("")
    .append(createAddTagIcon());

  disableTabbableChildElements(comboboxWrap);
  comboboxWrap.hideClass();

  // Reset staged chips, input, and listbox
  const resetStaged = comboboxWrap.data(STAGED_RESET_KEY) as
    | (() => void)
    | undefined;
  if (resetStaged) resetStaged();
  comboboxWrap.find(".urlTagStagedChip").remove();
  comboboxWrap.find(".urlTagComboboxInput").val("").prop("disabled", false);
  comboboxWrap
    .find(".urlTagListbox")
    .empty()
    .addClass("hidden")
    .removeAttr("aria-activedescendant");
  comboboxWrap.find(".urlTagCombobox").removeClass("disabled focused");
  comboboxWrap.find(".urlTagComboboxMsg").text("").removeClass("warn");

  // Re-enable URL buttons
  urlCard.find(".urlBtnAccess").showClassFlex();
  enableEditingURLString(urlCard);
  urlCard.find(".urlBtnDelete").showClassFlex();
  urlCard.find(".urlBtnCopy").showClassFlex();

  // Re-enable hovering on tags for deletion
  urlCard.find(".tagBadge").addClass("tagBadgeHoverable");

  enableTagRemovalInURLCard(urlCard);
  enableEditingURLTitle(urlCard);

  const tooltip = urlCard.data(TOOLTIP_STORE_KEY) as
    | { enable: () => void }
    | undefined;
  if (tooltip) {
    tooltip.enable();
    urlCard.removeData(TOOLTIP_STORE_KEY);
  }

  const selectedAttr = urlCard.attr("urlSelected");
  if (
    typeof selectedAttr === "string" &&
    selectedAttr.toLowerCase() === "true"
  ) {
    enableClickOnSelectedURLCardToHide(urlCard);
  }
}

/**
 * Submits the staged tag strings to the batch endpoint. Preserves the
 * single-path concurrent-deletion guard (`getUpdatedURL`) and loading icon, and
 * keeps the card from deselecting mid-flight. The `UI_FORM_SUBMIT` emit and
 * `clearOpenForm()` are owned by the caller (submit button / Enter-key handler),
 * mirroring how `create.ts` emits in the button handler before calling
 * `createURLTag`.
 */
export async function submitStagedTags({
  urlCard,
  utubID,
  utubUrlID,
  stagedStrings,
}: {
  urlCard: JQuery;
  utubID: number;
  utubUrlID: number;
  stagedStrings: string[];
}): Promise<void> {
  const timeoutID: number = setTimeoutAndShowURLCardLoadingIcon(urlCard);
  try {
    await getUpdatedURL(utubID, utubUrlID, urlCard);

    disableClickOnSelectedURLCardToHide(urlCard);

    const data: AddTagsRequest = { tagStrings: stagedStrings };
    const request = ajaxCall(
      "post",
      APP_CONFIG.routes.createURLTagsBatch(utubID, utubUrlID),
      data,
    );

    request.done(function (
      response: UrlTagsModifiedResponse,
      _: JQuery.Ajax.SuccessTextStatus,
      xhr: JQuery.jqXHR,
    ) {
      if (xhr.status === 200) {
        submitStagedTagsSuccess({ response, urlCard, utubID });
      }
    });

    request.fail(function (xhr: JQuery.jqXHR) {
      submitStagedTagsFail({ xhr, urlCard });
    });

    request.always(function () {
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    });
  } catch (error) {
    clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    handleRejectFromGetURL(error as JQuery.jqXHR, urlCard, {
      showError: true,
      message: "Another user has deleted this URL",
    });
  }
}

/**
 * Applies a successful batch response: merges applied tags into the store,
 * appends real `.tagBadge` nodes, rebuilds the URL's tag-id attribute, syncs the
 * tag deck, and resets the combobox.
 */
export function submitStagedTagsSuccess({
  response,
  urlCard,
  utubID,
}: {
  response: UrlTagsModifiedResponse;
  urlCard: JQuery;
  utubID: number;
}): void {
  if (response.appliedTags.length > 0) {
    emit({ event: UI_EVENTS.UI_TAG_APPLY });
  }

  // Caller-owned store patch: update the existing URL entry's tag-ID slice. This
  // stays here (not inside `renderAppliedTagsForUrl`) because the helper is a
  // pure render+DOM+deck-sync utility — only the tag-vocab merge runs inside it.
  const urlID = parseInt(urlCard.attr("utuburlid") as string);
  setState({
    urls: getState().urls.map((existingUrl: UtubUrlItem) =>
      existingUrl.utubUrlID === urlID
        ? { ...existingUrl, utubUrlTagIDs: response.utubUrlTagIDs }
        : existingUrl,
    ),
  });

  renderAppliedTagsForUrl({
    appliedTags: response.appliedTags,
    utubUrlTagIDs: response.utubUrlTagIDs,
    urlCard,
    utubID,
  });

  hideAndResetTagCombobox(urlCard);
}

/**
 * Handles a failed batch submit: 429 short-circuit, CSRF HTML handling, 400
 * field/message inline errors, and the error page for the remaining statuses.
 */
export function submitStagedTagsFail({
  xhr,
  urlCard,
}: {
  xhr: JQuery.jqXHR;
  urlCard: JQuery;
}): void {
  if (is429Handled(xhr)) return;

  if (!("responseJSON" in xhr)) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      $("body").html(xhr.responseText);
      return;
    }
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  switch (xhr.status) {
    case 400: {
      const responseJSON = xhr.responseJSON as UrlTagError;
      if (responseJSON.errors) {
        displayBatchFieldErrors(
          responseJSON.errors as Partial<Record<SubmitFieldName, string[]>>,
          urlCard,
        );
      } else if (responseJSON.message) {
        displayBatchMessage(responseJSON.message as string, urlCard);
      }
      break;
    }
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

function displayBatchFieldErrors(
  errors: Partial<Record<SubmitFieldName, string[]>>,
  urlCard: JQuery,
): void {
  for (const errorFieldName in errors) {
    if (isSubmitFieldName(errorFieldName)) {
      displayBatchMessage(errors[errorFieldName]![0], urlCard);
      return;
    }
  }
}

function displayBatchMessage(message: string, urlCard: JQuery): void {
  urlCard.find(".urlTagComboboxMsg").text(message).addClass("warn");
}
