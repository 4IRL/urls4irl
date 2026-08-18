import type { UtubTag, UtubUrlItem } from "../../../types/url.js";
import type { Schema, SuccessResponse } from "../../../types/api-helpers.d.ts";

import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { KEYS, SHOW_LOADING_ICON_AFTER_MS } from "../../../lib/constants.js";
import { debug } from "../../../lib/debug.js";
import { AppEvents, on } from "../../../lib/event-bus.js";
import { clearOpenForm, setOpenForm } from "../../../lib/modal-tracking.js";
import { HOME_FORM } from "../../../types/metrics-dim-values.js";
import { getState, setState } from "../../../store/app-store.js";
import { mergeAppliedTagsIntoStore } from "../tags/combobox-state.js";
import {
  BULK_RESET_KEY,
  ComboboxMode,
  createTagComboboxBlock,
} from "../tags/combobox.js";
import { createTagBadgeInURL } from "../tags/tags.js";
import { updateVisibleURLsForTagCount } from "../cards/filtering.js";
import { buildTagFilterInDeck } from "../../tags/tags.js";
import { isTagInUTubTagDeck } from "../../tags/utils.js";
import { reapplyTagFilter } from "../../tags/search.js";
import {
  type BulkAction,
  type BulkActionContext,
  registerBulkAction,
} from "./bulk-action-registry.js";

const log = debug("urls:cards");

type AddTagsToUrlsResponse = SuccessResponse<"applyTagsToUtubUrls">;
type UrlBatchTagAppliedEntry = Schema<"UrlBatchTagAppliedSchema">;
type UrlBatchTagSkippedEntry = Schema<"UrlBatchTagSkippedSchema">;
type BulkTagError = Schema<"ErrorResponse_URLTagErrorCodes">;

const PICKER_MOUNT_SELECTOR = "#bulkTagPickerMount";
const BANNER_SELECTOR = "#bulkTagResultBanner";
const DECK_SELECTOR = "#URLDeck";
const PICKER_OPEN_CLASS = "bulkTagPickerOpen";
// Stable in-mode focus-return anchor (the header Exit control) — never the
// ephemeral #bulkActionButtons button, which rebuilds on every selection change.
const FOCUS_RETURN_SELECTOR = "#bulkSelectExit";
const SUBMIT_BTN_SELECTOR = ".urlTagComboboxSubmitBtn";
const CANCEL_BTN_SELECTOR = ".urlTagComboboxCancelBtn";
const MESSAGE_SELECTOR = ".urlTagComboboxMsg";
const LISTBOX_SELECTOR = ".urlTagListbox";
const INPUT_SELECTOR = ".urlTagComboboxInput";
const SUBMIT_LOADING_CLASS = "bulkTagSubmitLoading";

// Trusted static bulk-add-tags icon (Bootstrap `bi-tag`). Injected as raw HTML
// via the registry's `.prepend(iconHtml)`, so this MUST stay a hard-coded literal
// — never interpolate user content into it (HTML-injection sink).
const BULK_ADD_TAGS_ICON_HTML =
  '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" ' +
  'fill="currentColor" class="bi bi-tag" viewBox="0 0 16 16" aria-hidden="true">' +
  '<path d="M6 4.5a1.5 1.5 0 1 1-3 0 1.5 1.5 0 0 1 3 0"/>' +
  '<path d="M2 1a1 1 0 0 0-1 1v4.586a1 1 0 0 0 .293.707l7 7a1 1 0 0 0 1.414 0l4.586-4.586a1 1 0 0 0 0-1.414l-7-7A1 1 0 0 0 6.586 1zm0 5V2h4.586l7 7L9 13.586z"/>' +
  "</svg>";

// This module's own request-field allowlist for inline 400 field errors. Scoped
// to the two fields THIS request sends — deliberately NOT combobox.ts's
// single-field `SUBMIT_FIELD_NAMES`, which omits `utubUrlIds`.
const BULK_SUBMIT_FIELD_NAMES = ["tagStrings", "utubUrlIds"] as const;
type BulkSubmitFieldName = (typeof BULK_SUBMIT_FIELD_NAMES)[number];
function isBulkSubmitFieldName(key: string): key is BulkSubmitFieldName {
  return (BULK_SUBMIT_FIELD_NAMES as readonly string[]).includes(key);
}

// --- Picker-open flag (owned here; imported by bulk-bar/selection/index) -------

let bulkTagPickerOpen = false;

/** Whether the bulk tag picker is currently mounted/open. */
export function isBulkTagPickerOpen(): boolean {
  return bulkTagPickerOpen;
}

/** Set the picker-open flag. */
export function setBulkTagPickerOpen(open: boolean): void {
  bulkTagPickerOpen = open;
}

// --- Open-picker lifecycle state ----------------------------------------------

let currentSnapshot: number[] = [];
let currentUtubID: number | null = null;
let currentWrap: JQuery | null = null;
let submitInFlight = false;
let loadingTimeoutID: number | null = null;
let escapeListener: ((event: KeyboardEvent) => void) | null = null;

// --- Action registration ------------------------------------------------------

const bulkAddTagsAction: BulkAction = {
  id: "bulk-add-tags",
  label: APP_CONFIG.strings.ADD_TAGS_SUBMIT,
  iconHtml: BULK_ADD_TAGS_ICON_HTML,
  isAvailable: (context: BulkActionContext) =>
    context.selectedURLCardIDs.length > 0,
  onActivate: openBulkTagPicker,
};

// Bus subscriptions are process-wide (no rebind), and the action registry is
// append-only, so guard both against a repeat initBulkActions().
let _bulkTagInitialized = false;

/**
 * Register the bulk-add-tags action and wire the mode-exit teardown. Called from
 * initBulkActions(); the import itself is what makes registration run.
 */
export function initBulkTag(): void {
  if (_bulkTagInitialized) return;
  _bulkTagInitialized = true;

  registerBulkAction(bulkAddTagsAction);

  // Mode exit / UTub switch tears the picker down even if the user never closed
  // it. bulk-tag.ts depends on the event, never on bulk-mode.ts (which stays a
  // leaf module unaware this module exists), keeping the dependency one-way.
  on(AppEvents.URL_MULTISELECT_MODE_CHANGED, ({ active }) => {
    if (active === false && isBulkTagPickerOpen()) {
      log("bulk tag picker torn down on multi-select mode exit");
      closeAndResetPicker({ returnFocus: false });
    }
  });
}

// --- Open / close lifecycle ---------------------------------------------------

/**
 * Open the bulk tag picker for the current selection: snapshot the selected ids,
 * mount the BULK-mode combobox in the stable `#bulkTagPickerMount`, lock the
 * selection, and focus the input. Re-entrant activation is a defined no-op.
 */
function openBulkTagPicker(context: BulkActionContext): void {
  if (isBulkTagPickerOpen()) return;

  const utubID = getState().activeUTubID;
  if (utubID === null) return;

  const snapshot = [...context.selectedURLCardIDs];
  if (snapshot.length === 0) return;

  log("open bulk tag picker", { snapshot, utubID });

  currentSnapshot = snapshot;
  currentUtubID = utubID;
  submitInFlight = false;
  setBulkTagPickerOpen(true);
  setOpenForm(HOME_FORM.TAG_CREATE);

  const mount = $(PICKER_MOUNT_SELECTOR);
  mount.empty();

  const wrap = createTagComboboxBlock({
    mode: ComboboxMode.BULK,
    urlCard: null,
    utubID,
    selectedCount: snapshot.length,
    onSubmit: submitBulkTags,
  });
  mount.append(wrap);
  currentWrap = wrap;

  // Add the Cancel button ahead of the combobox's own submit button (mock order).
  const cancelBtn = $(document.createElement("button"))
    .addClass("urlTagComboboxCancelBtn tabbable")
    .attr({ type: "button" })
    .text("Cancel");
  cancelBtn.on("click.bulkTagCancel", () => {
    if (submitInFlight) return;
    closeAndResetPicker();
  });
  wrap.find(".urlTagComboboxActions").prepend(cancelBtn);

  // Reveal both the mount wrapper and the inner combobox wrap (BULK has the extra
  // #bulkTagPickerMount layer the single-card URL mode does not).
  mount.showClassFlex();
  wrap.showClassFlex();
  $(DECK_SELECTOR).addClass(PICKER_OPEN_CLASS);

  // The picker supersedes any prior result banner.
  $(BANNER_SELECTOR).addClass("hidden").empty();

  attachEscapeListener();
  wrap.find(INPUT_SELECTOR).trigger("focus");
}

/**
 * Shared close/reset used by every close path (submit success, Cancel, Escape,
 * mode-exit, UTub switch): resets the combobox state, hides the picker, unlocks
 * the selection, clears the open-form token, and drops the picker-open flag.
 */
function closeAndResetPicker({
  returnFocus = true,
}: {
  returnFocus?: boolean;
} = {}): void {
  if (currentWrap !== null) {
    const resetBulk = currentWrap.data(BULK_RESET_KEY) as
      | (() => void)
      | undefined;
    if (resetBulk) resetBulk();
    // Strip the in-flight submit affordance + re-enable the buttons so a wrap
    // closed mid-flight (e.g. mode-exit teardown) never keeps a stale spinner /
    // disabled state if it is somehow re-shown before the next open empties it.
    currentWrap
      .find(SUBMIT_BTN_SELECTOR)
      .removeClass(SUBMIT_LOADING_CLASS)
      .prop("disabled", false);
    currentWrap.find(CANCEL_BTN_SELECTOR).prop("disabled", false);
    currentWrap.hideClass();
  }
  $(PICKER_MOUNT_SELECTOR).hideClass();
  $(DECK_SELECTOR).removeClass(PICKER_OPEN_CLASS);

  detachEscapeListener();
  clearOpenForm();
  setBulkTagPickerOpen(false);

  currentWrap = null;
  currentSnapshot = [];
  currentUtubID = null;
  submitInFlight = false;
  if (loadingTimeoutID !== null) {
    clearTimeout(loadingTimeoutID);
    loadingTimeoutID = null;
  }

  if (returnFocus) {
    const anchor = $(FOCUS_RETURN_SELECTOR);
    if (anchor.length > 0) anchor[0]?.focus();
  }
}

// --- Escape precedence (single container capture-phase listener) --------------

function attachEscapeListener(): void {
  const mountElement = $(PICKER_MOUNT_SELECTOR)[0];
  if (!mountElement) return;
  escapeListener = handleContainerEscape;
  mountElement.addEventListener("keydown", escapeListener, { capture: true });
}

function detachEscapeListener(): void {
  const mountElement = $(PICKER_MOUNT_SELECTOR)[0];
  if (mountElement && escapeListener) {
    mountElement.removeEventListener("keydown", escapeListener, {
      capture: true,
    });
  }
  escapeListener = null;
}

/**
 * Owns ALL Escape handling for the picker. First Escape (listbox open) closes
 * only the dropdown; second Escape (listbox closed) discards + closes — unless a
 * submit is in flight, in which case it is a no-op (but still swallowed). Always
 * `stopPropagation()`s so Escape never reaches the per-input combobox handler or
 * the document-level multi-select-exit handler.
 */
function handleContainerEscape(event: KeyboardEvent): void {
  if (event.key !== KEYS.ESCAPE) return;
  if (currentWrap === null) return;

  event.stopPropagation();
  event.preventDefault();

  const listbox = currentWrap.find(LISTBOX_SELECTOR);
  const dropdownOpen = listbox.length > 0 && !listbox.hasClass("hidden");
  if (dropdownOpen) {
    listbox.empty().addClass("hidden").removeAttr("aria-activedescendant");
    currentWrap.find(INPUT_SELECTOR).attr("aria-expanded", "false");
    return;
  }

  // Second Escape: discard + close, unless the request is still in flight.
  if (submitInFlight) return;
  closeAndResetPicker();
}

// --- Submit -------------------------------------------------------------------

/**
 * Drive the single bulk POST. Disables the submit + Cancel buttons and posts the
 * transient "Adding tags…" live-region message for the request's duration.
 */
function submitBulkTags(stagedStrings: string[]): void {
  if (currentUtubID === null || currentWrap === null) return;
  if (submitInFlight) return;

  const utubID = currentUtubID;
  const snapshot = [...currentSnapshot];
  const wrap = currentWrap;
  const submitBtn = wrap.find(SUBMIT_BTN_SELECTOR);
  const cancelBtn = wrap.find(CANCEL_BTN_SELECTOR);
  const message = wrap.find(MESSAGE_SELECTOR);

  submitInFlight = true;
  submitBtn.prop("disabled", true);
  cancelBtn.prop("disabled", true);
  loadingTimeoutID = setTimeoutAndShowBulkTagLoadingIcon(submitBtn);
  message.text(APP_CONFIG.strings.URL_BULK_TAGS_SUBMITTING).removeClass("warn");

  log("submit bulk tags", { utubID, snapshot, stagedStrings });

  const request = ajaxCall("post", APP_CONFIG.routes.applyTagsToURLs(utubID), {
    utubUrlIds: snapshot,
    tagStrings: stagedStrings,
  });

  request.done(function (
    response: AddTagsToUrlsResponse,
    _: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status === 200) {
      handleBulkSubmitSuccess({
        response,
        utubID,
        totalSelected: snapshot.length,
      });
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    handleBulkSubmitFail(xhr);
  });

  request.always(function () {
    submitInFlight = false;
    if (loadingTimeoutID !== null) {
      clearTimeoutIDAndHideBulkTagLoadingIcon({
        timeoutID: loadingTimeoutID,
        submitBtn,
      });
      loadingTimeoutID = null;
    }
    submitBtn.prop("disabled", false);
    cancelBtn.prop("disabled", false);
  });
}

function handleBulkSubmitSuccess({
  response,
  utubID,
  totalSelected,
}: {
  response: AddTagsToUrlsResponse;
  utubID: number;
  totalSelected: number;
}): void {
  // Bail if the active UTub changed while the request was in flight (a
  // switch/delete tears the picker down via the mode-exit subscription). Without
  // this, a late success would render badges/deck-filters/banner against a
  // different UTub's deck using the now-stale captured utubID/snapshot.
  if (getState().activeUTubID !== utubID) return;

  // Caller-owned store patch: fold each applied URL's fresh tag-id slice into the
  // urls store (mirrors submitStagedTagsSuccess — the render helper stays a pure
  // DOM/deck utility that only merges the tag vocabulary).
  const appliedTagIdsByUrl = new Map<number, number[]>(
    response.applied.map((entry) => [entry.utubUrlID, entry.utubUrlTagIDs]),
  );
  setState({
    urls: getState().urls.map((existingUrl: UtubUrlItem) =>
      appliedTagIdsByUrl.has(existingUrl.utubUrlID)
        ? {
            ...existingUrl,
            utubUrlTagIDs: appliedTagIdsByUrl.get(existingUrl.utubUrlID)!,
          }
        : existingUrl,
    ),
  });

  renderBulkAppliedTags({ applied: response.applied, utubID });
  renderBulkResultBanner({
    applied: response.applied,
    skipped: response.skipped,
    totalSelected,
  });
  closeAndResetPicker();
}

function handleBulkSubmitFail(xhr: JQuery.jqXHR): void {
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
      const responseJSON = xhr.responseJSON as BulkTagError;
      if (responseJSON.errors) {
        displayBulkFieldError(responseJSON.errors);
      } else if (responseJSON.message) {
        // The service's ONLY message-level (non-field) 400 is URL_NOT_IN_UTUB —
        // a stale/foreign selection. Show the bridged stale-selection copy (never
        // the raw server string) so the user knows to refresh their selection.
        displayBulkMessage(APP_CONFIG.strings.URL_BULK_TAGS_STALE_SELECTION);
      }
      break;
    }
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

function displayBulkFieldError(errors: Record<string, string[]>): void {
  for (const fieldName in errors) {
    if (isBulkSubmitFieldName(fieldName)) {
      displayBulkMessage(errors[fieldName][0]);
      return;
    }
  }
}

function displayBulkMessage(message: string): void {
  currentWrap?.find(MESSAGE_SELECTOR).text(message).addClass("warn");
}

// --- Loading indicator (bulk-mode analog of cards/loading.ts) -----------------

function setTimeoutAndShowBulkTagLoadingIcon(submitBtn: JQuery): number {
  return window.setTimeout(function () {
    submitBtn.addClass(SUBMIT_LOADING_CLASS);
  }, SHOW_LOADING_ICON_AFTER_MS);
}

function clearTimeoutIDAndHideBulkTagLoadingIcon({
  timeoutID,
  submitBtn,
}: {
  timeoutID: number;
  submitBtn: JQuery;
}): void {
  clearTimeout(timeoutID);
  submitBtn.removeClass(SUBMIT_LOADING_CLASS);
}

// --- Render applied tags (once-per-distinct-tag deck sync, DD-23) -------------

/**
 * Bulk-aware analog of `renderAppliedTagsForUrl`: per-card badge work runs once
 * per applied URL, but the LHS tag-deck sync runs exactly once per DISTINCT tag
 * (not once per card), then the visible/numerator counts are recomputed in a
 * single pass. Skipped URLs are never touched (they are not in `applied`).
 */
function renderBulkAppliedTags({
  applied,
  utubID,
}: {
  applied: UrlBatchTagAppliedEntry[];
  utubID: number;
}): void {
  // Deduped union of every entry's appliedTags, keyed by tag id. The same tag id
  // repeats across entries when it was applied to multiple URLs — its
  // `tagApplied` total is UTub-wide and identical, so first-write-wins.
  const distinctAppliedTags = new Map<number, UtubTag>();
  applied.forEach((entry) => {
    entry.appliedTags.forEach((appliedTag) => {
      if (!distinctAppliedTags.has(appliedTag.id)) {
        distinctAppliedTags.set(appliedTag.id, appliedTag);
      }
    });
  });

  if (distinctAppliedTags.size === 0) return;

  // Snapshot which distinct tags already existed in the deck BEFORE the store
  // merge appends brand-new ones (otherwise every applied tag reports in-deck).
  const tagIdsAlreadyInDeck = new Set<number>();
  distinctAppliedTags.forEach((appliedTag) => {
    if (isTagInUTubTagDeck(appliedTag.id)) {
      tagIdsAlreadyInDeck.add(appliedTag.id);
    }
  });

  mergeAppliedTagsIntoStore({ appliedTags: [...distinctAppliedTags.values()] });

  // Per-URL badge work — genuinely once per applied card.
  applied.forEach((entry) => {
    const urlCard = $(`.urlRow[utuburlid=${entry.utubUrlID}]`);
    if (urlCard.length === 0) return;
    const tagsContainer = urlCard.find(".urlTagsContainer");
    urlCard.attr("data-utub-url-tag-ids", entry.utubUrlTagIDs.join(","));
    entry.appliedTags.forEach((appliedTag) => {
      tagsContainer.append(
        createTagBadgeInURL(
          appliedTag.id,
          appliedTag.tagString,
          urlCard,
          utubID,
        ),
      );
    });
  });

  // Deck sync exactly ONCE per distinct tag.
  let builtNewDeckFilter = false;
  distinctAppliedTags.forEach((appliedTag) => {
    if (!tagIdsAlreadyInDeck.has(appliedTag.id)) {
      const newTag = buildTagFilterInDeck(
        utubID,
        appliedTag.id,
        appliedTag.tagString,
        appliedTag.tagApplied,
      );
      if (
        $(".tagFilter.selected").length ===
        APP_CONFIG.constants.TAGS_MAX_ON_URLS
      ) {
        newTag.addClass("disabled").off(".tagFilterSelected");
      }
      $("#listTags").append(newTag);
      reapplyTagFilter();
      builtNewDeckFilter = true;
    } else {
      // Already in deck: write only the authoritative UTub-wide total (the
      // right-hand/denominator digit of `X / Y`) directly from `tagApplied`. The
      // visible/numerator half is recomputed once, below — never mirrored from the
      // total (a bulk selection can include filter-hidden URLs).
      const countElem = $(
        `.tagFilter[data-utub-tag-id="${appliedTag.id}"] .tagAppliedToUrlsCount`,
      );
      const countText = countElem.text().split(" / ");
      if (countText.length === 2) {
        countElem.text(`${countText[0]} / ${appliedTag.tagApplied}`);
      }
    }
  });

  // Recompute the visible/numerator half for every currently-displayed deck tag
  // in one pass (it iterates every in-deck tag internally).
  updateVisibleURLsForTagCount();

  $("#unselectAllTagFilters").showClassNormal();
  if (builtNewDeckFilter) {
    $("#utubTagBtnUpdateAllOpen").showClassNormal();
  }
}

// --- Result banner ------------------------------------------------------------

/**
 * Render the partial-success banner in `#bulkTagResultBanner`. Three states:
 * all-succeeded (polite), some-skipped (polite; skipped titles HTML-escaped via
 * `.text()`), all-over-limit (assertive).
 */
function renderBulkResultBanner({
  applied,
  skipped,
  totalSelected,
}: {
  applied: UrlBatchTagAppliedEntry[];
  skipped: UrlBatchTagSkippedEntry[];
  totalSelected: number;
}): void {
  const banner = $(BANNER_SELECTOR);
  banner.empty().removeClass("hidden success partial fail");

  // Count only URLs that genuinely gained ≥1 tag (DD-5). The backend `applied`
  // array includes non-skipped URLs even when `appliedTags` is empty (every
  // requested tag was already present), so those must NOT inflate the banner's
  // "modified" count.
  const appliedCount = applied.filter(
    (entry) => entry.appliedTags.length > 0,
  ).length;
  const skippedCount = skipped.length;
  const maxTags = String(APP_CONFIG.constants.TAGS_MAX_ON_URLS);

  let variant: string;
  let glyph: string;
  let ariaLive: string;
  let text: string;

  if (skippedCount === 0) {
    variant = "success";
    glyph = "✅";
    ariaLive = "polite";
    text =
      appliedCount === 1
        ? APP_CONFIG.strings.URL_BULK_TAGS_APPLIED_ONE
        : APP_CONFIG.strings.URL_BULK_TAGS_APPLIED.replace(
            "{n}",
            String(appliedCount),
          );
  } else if (appliedCount === 0) {
    variant = "fail";
    glyph = "🚫";
    ariaLive = "assertive";
    text = APP_CONFIG.strings.URL_BULK_TAGS_NONE.replace(
      "{n}",
      String(totalSelected),
    ).replace("{max}", maxTags);
  } else {
    variant = "partial";
    glyph = "⚠️";
    ariaLive = "polite";
    const titles = skipped
      .map((skip) => urlTitleForId(skip.utubUrlID))
      .filter((title) => title.length > 0)
      .join(", ");
    text = APP_CONFIG.strings.URL_BULK_TAGS_PARTIAL.replace(
      "{applied}",
      String(appliedCount),
    )
      .replace("{skipped}", String(skippedCount))
      .replace("{max}", maxTags)
      .replace("{titles}", titles);
  }

  // `.text()` escapes the whole string (including user-content titles).
  const icon = $(document.createElement("span"))
    .addClass("bulkTagBannerIcon")
    .attr({ "aria-hidden": "true" })
    .text(glyph);
  const body = $(document.createElement("div"))
    .addClass("bulkTagBannerBody")
    .text(text);

  banner
    .addClass(variant)
    .attr("aria-live", ariaLive)
    .append(icon)
    .append(body);
}

/** URL title for a given utubUrlID from the store (empty string if unknown). */
function urlTitleForId(utubUrlID: number): string {
  const match = getState().urls.find((url) => url.utubUrlID === utubUrlID);
  return match?.urlTitle ?? "";
}
