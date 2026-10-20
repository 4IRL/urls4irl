import { $ } from "../../../lib/globals.js";
import { KEYS } from "../../../lib/constants.js";
import { emit } from "../../../lib/metrics-client.js";
import { clearOpenForm } from "../../../lib/modal-tracking.js";
import { disposeTooltipsWithin } from "../../../lib/tooltips.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { isURLSearchActive, getActiveTagCount } from "../url-context.js";
import { getState } from "../../../store/app-store.js";
import type { UtubTag, UtubUrlItem } from "../../../types/url.js";
import type { MemberItem } from "../../../types/member.js";
import { createURLDateAddedBadge } from "./adder-badge.js";
import {
  selectURLCard,
  setURLCardSelectionEventListener,
} from "./selection.js";
import { createGoToURLIcon } from "./corner-access.js";
import { createURLTitle, createURLTitleAndUpdateBlock } from "./url-title.js";
import {
  createURLString,
  createURLStringAndUpdateBlock,
} from "./url-string.js";
import { createTagBadgeInURL, createTagBadgesAndWrap } from "../tags/tags.js";
import { ComboboxMode, createTagComboboxBlock } from "../tags/combobox.js";
import { createURLOptionsButtons } from "./options/btns.js";
import { createDeleteURLIcon } from "./options/delete-btn.js";
import { bindURLRowSwipeGesture } from "./swipe.js";
import {
  reapplyMultiSelectMark,
  toggleURLCardSelection,
} from "../bulk-actions/bulk-selection.js";
import {
  createURL,
  createURLHideInput,
  bindCreateURLFocusEventListeners,
  unbindCreateURLFocusEventListeners,
  resetCreateURLFailErrors,
} from "./create.js";
import {
  FORM_CANCEL_TRIGGER,
  FORM_SUBMIT_TRIGGER,
  HOME_FORM,
  SEARCH_ACTIVE,
} from "../../../types/metrics-dim-values.js";
import { debug } from "../../../lib/debug.js";

const log = debug("urls:cards");

export function updateURLAfterFindingStaleData(
  urlCard: JQuery,
  newUrl: UtubUrlItem,
  updatedUTubTags: UtubTag[],
  utubID: number,
): void {
  const urlTitle = urlCard.find(".urlTitle");
  const urlString = urlCard.find(".urlString");

  if (urlTitle.text() !== newUrl.urlTitle) {
    urlTitle.text(newUrl.urlTitle);
  }

  if (urlString.attr("href") !== newUrl.urlString) {
    urlString.text(newUrl.urlString).attr({ href: newUrl.urlString });
  }

  const currentURLTags = urlCard.find(".tagBadge");
  const currentURLTagIDs = $.map(currentURLTags.toArray(), (tag: HTMLElement) =>
    parseInt($(tag).attr("data-utub-tag-id")!),
  );

  log("URL card updated after stale-data refresh", {
    utubUrlID: urlCard.attr("utuburlid"),
    tagsAdded: newUrl.utubUrlTagIDs.filter(
      (id) => !currentURLTagIDs.includes(id),
    ).length,
    tagsRemoved: currentURLTagIDs.filter(
      (id) => !newUrl.utubUrlTagIDs.includes(id),
    ).length,
  });

  // Find tag IDs that are in old and not in new and remove them
  for (
    let currentTagIndex = 0;
    currentTagIndex < currentURLTagIDs.length;
    currentTagIndex++
  ) {
    if (!newUrl.utubUrlTagIDs.includes(currentURLTagIDs[currentTagIndex])) {
      currentURLTags.each(function (_, tag) {
        if (
          parseInt($(tag).attr("data-utub-tag-id")!) ===
          currentURLTagIDs[currentTagIndex]
        ) {
          // A stale-data diff drops the badge silently — dispose its
          // delete-button tooltip so the instance goes with it.
          disposeTooltipsWithin($(tag));
          $(tag).remove();
          return false;
        }
      });
    }
  }

  // Find tag IDs that are in new and not old and add them
  const urlTagContainer = urlCard.find(".urlTagsContainer");
  let tagToAdd: UtubTag | undefined;
  for (
    let newTagIndex = 0;
    newTagIndex < newUrl.utubUrlTagIDs.length;
    newTagIndex++
  ) {
    if (!currentURLTagIDs.includes(newUrl.utubUrlTagIDs[newTagIndex])) {
      tagToAdd = updatedUTubTags.find(
        (tag) => tag.id === newUrl.utubUrlTagIDs[newTagIndex],
      );
      if (tagToAdd) {
        urlTagContainer.append(
          createTagBadgeInURL(tagToAdd.id, tagToAdd.tagString, urlCard, utubID),
        );
      }
    }
  }
}

// Create a URL block to add to current UTub/URLDeck. `members` is passed only by
// the stale-data deck diff, whose store still holds the pre-refresh members while
// it builds cards; the stacked badge resolves the adder from it when given.
export function createURLBlock({
  url,
  dictTags,
  utubID,
  members,
}: {
  url: UtubUrlItem;
  dictTags: UtubTag[];
  utubID: number;
  members?: MemberItem[];
}): JQuery<HTMLElement> {
  const urlCard = $(document.createElement("div"))
    .addClass("urlRow flex-column full-width pointerable")
    .enableTab(); // Holds everything in the URL

  const urlRowContent = $(document.createElement("div")).addClass(
    "urlRowContent flex-column full-width",
  );

  const urlTitleGoToURLWrap = $(document.createElement("div")).addClass(
    "flex-row full-width align-center jc-sb",
  );

  // Append update URL title form if user can edit the URL
  if (url.canDelete) {
    urlTitleGoToURLWrap.append(
      createURLTitleAndUpdateBlock(url.urlTitle, urlCard, utubID),
    );
  } else {
    urlTitleGoToURLWrap.append(createURLTitle(url.urlTitle));
  }

  urlTitleGoToURLWrap.append(createGoToURLIcon(url.urlString));

  urlRowContent.append(urlTitleGoToURLWrap);
  urlCard.attr({
    utubUrlID: url.utubUrlID,
    urlSelected: false,
    filterable: true,
    "data-utub-url-tag-ids": url.utubUrlTagIDs.join(","),
  });

  // URL-string row: the URL string block flex-grows and truncates while the
  // date-added badge is pinned to the far right (margin-left:auto in urls.css),
  // so the date reads as the URL's metadata at the card's lower-right, inline
  // with the URL string. Kept inside .urlRowContent (position:relative,
  // z-index:1) so it renders above the absolutely-positioned .urlRowSwipeReveal.
  const urlStringRow = $(document.createElement("div")).addClass(
    "urlStringRow flex-row full-width align-center",
  );

  // Append update URL form if user can edit the URL
  if (url.canDelete) {
    urlStringRow.append(
      createURLStringAndUpdateBlock(url.urlString, urlCard, utubID),
    );
  } else {
    urlStringRow.append(createURLString(url.urlString));
  }

  urlStringRow.append(
    createURLDateAddedBadge({
      addedAt: url.addedAt,
      addedByUserID: url.addedByUserID,
      placementClass: "urlDateAddedBadgeInline",
      withAdder: false,
    }),
  );
  urlRowContent.append(urlStringRow);

  urlRowContent.append(
    createTagsAndOptionsForUrlBlock(url, dictTags, urlCard, utubID),
  );

  // Expanded-only attribution row: a full-width "Added by <user> · <date>" line
  // below the buttons row, shown when the card is selected on BOTH desktop and
  // mobile (see urls.css). Last child of .urlRowContent so it sits under the
  // tags/options block; collapsed cards never show it, so it adds no height.
  urlRowContent.append(
    createURLDateAddedBadge({
      addedAt: url.addedAt,
      addedByUserID: url.addedByUserID,
      placementClass: "urlDateAddedBadgeStacked",
      withAdder: true,
      members,
    }),
  );

  // Multi-select checkbox affordance, rendered on every card but hidden by CSS
  // unless the deck is in multi-select mode (#URLDeck.multiSelectActive). Sits
  // before .urlRowContent so it reads as the row's leading control.
  urlCard.append(createURLSelectCheckbox(url));

  if (url.canDelete) {
    urlCard.append(createURLRowSwipeReveal());
  }
  urlCard.append(urlRowContent);

  setURLCardSelectionEventListener(urlCard);
  setFocusEventListenersOnURLCard(urlCard);

  if (url.canDelete) {
    bindURLRowSwipeGesture({
      urlRow: urlCard,
      utubUrlID: url.utubUrlID,
      utubID,
    });
  }

  // Re-derive the multi-select mark from the store so a rebuilt/re-added card in
  // a live selection survives the deck-diff and stays visibly checked.
  reapplyMultiSelectMark(urlCard);

  return urlCard;
}

// Per-card multi-select checkbox: a .urlSelectCheckboxWrap <label> wrapping a
// role="checkbox" span whose aria-checked mirrors selection. The store
// (selectedURLCardIDs) is the source of truth and the .urlRow.multiSelected mark
// is re-derived from it; this control just toggles membership. stopPropagation
// keeps its tap/keypress from also reaching the row's click.urlSelected handler.
function createURLSelectCheckbox(url: UtubUrlItem): JQuery<HTMLElement> {
  const checkboxWrap = $(document.createElement("label")).addClass(
    "urlSelectCheckboxWrap",
  );
  const checkbox = $(document.createElement("span"))
    .addClass("urlSelectCheckbox")
    .attr({
      role: "checkbox",
      "aria-checked": "false",
      tabindex: 0,
      // Fall back to the URL string so an untitled URL's checkbox still has an
      // accessible name (both values are data, not display strings).
      "aria-label": url.urlTitle || url.urlString,
    });

  checkbox.on(
    "click.multiSelectCheckbox",
    function (event: JQuery.TriggeredEvent) {
      event.stopPropagation();
      toggleURLCardSelection(url.utubUrlID);
    },
  );
  checkbox.on(
    "keydown.multiSelectCheckbox",
    function (event: JQuery.TriggeredEvent) {
      if (event.key === KEYS.ENTER || event.key === KEYS.SPACE) {
        event.preventDefault();
        event.stopPropagation();
        toggleURLCardSelection(url.utubUrlID);
      }
    },
  );

  checkboxWrap.append(checkbox);
  return checkboxWrap;
}

// Absolutely-positioned red delete affordance revealed behind .urlRowContent
// as the row is swiped left. Purely decorative: the delete action is
// triggered by completing the swipe gesture or the existing .urlBtnDelete,
// never by tapping this panel directly.
function createURLRowSwipeReveal(): JQuery<HTMLElement> {
  const swipeReveal = $(document.createElement("div")).addClass(
    "urlRowSwipeReveal",
  );

  const swipeRevealIcon = $(document.createElement("div"))
    .addClass("urlRowSwipeRevealIcon")
    .attr({ "aria-hidden": "true" })
    .append(createDeleteURLIcon());

  swipeReveal.append(swipeRevealIcon);

  return swipeReveal;
}

// Add focus and blur on URL card when tabbing through URLs
export function setFocusEventListenersOnURLCard(urlCard: JQuery): void {
  const utubUrlID = urlCard.attr("utuburlid");
  urlCard.offAndOn("focus.focusURLCard" + utubUrlID, function () {
    urlCard.find(".goToUrlIcon").addClass("visible-on-focus");
    $(document).on(
      "keyup.focusURLCard" + utubUrlID,
      function (event: JQuery.TriggeredEvent) {
        if (event.key === KEYS.ENTER) {
          // In multi-select mode, Enter toggles the card's membership instead of
          // expanding it (single-select). Branch before the metric/select path.
          if (getState().multiSelectMode) {
            toggleURLCardSelection(parseInt(urlCard.attr("utuburlid")!, 10));
            return;
          }
          emit({
            event: UI_EVENTS.UI_URL_CARD_CLICK,
            search_active: isURLSearchActive()
              ? SEARCH_ACTIVE.TRUE
              : SEARCH_ACTIVE.FALSE,
            active_tag_count: getActiveTagCount(),
          });
          selectURLCard(urlCard);
          urlCard.trigger("focusout");
        }
      },
    );
  });

  urlCard.offAndOn(
    "focusout.focusURLCard" + utubUrlID,
    function (event: JQuery.TriggeredEvent) {
      const target = $(event.target);
      if (target.closest(".urlRow").is(urlCard)) {
        if (target.hasClass("goToUrlIcon")) {
          urlCard.find(".goToUrlIcon").removeClass("visible-on-focus");
        }
        $(document).off("keyup.focusURLCard" + utubUrlID);
      }
    },
  );
}

// Create both the tag container and the button container for a URL
function createTagsAndOptionsForUrlBlock(
  url: UtubUrlItem,
  dictTags: UtubTag[],
  urlCard: JQuery,
  utubID: number,
): JQuery<HTMLElement> {
  const tagsAndButtonsWrap = $(document.createElement("div")).addClass(
    "tagsAndButtonsWrap full-width",
  );
  const tagsAndTagCreateWrap = $(document.createElement("div")).addClass(
    "urlTags flex-column",
  );
  const tagBadgesWrap = createTagBadgesAndWrap(
    dictTags,
    url.utubUrlTagIDs,
    urlCard,
    utubID,
  );

  tagsAndButtonsWrap.append(tagsAndTagCreateWrap);
  tagsAndTagCreateWrap.append(tagBadgesWrap);

  tagsAndTagCreateWrap.append(
    createTagComboboxBlock({
      mode: ComboboxMode.URL,
      urlCard,
      utubID,
      utubUrlID: url.utubUrlID,
    }),
  );

  tagsAndButtonsWrap.append(createURLOptionsButtons(url, urlCard, utubID));

  return tagsAndButtonsWrap;
}

// New URL card and input text fields. Initially hidden, shown when create URL is requested. Input field recreated here to ensure at the end of list after creation of new URL
export function newURLInputAddEventListeners(
  urlInputForm: JQuery,
  utubID: number,
): void {
  const urlBtnCreate = urlInputForm.find("#urlSubmitBtnCreate");
  const urlBtnDelete = urlInputForm.find("#urlCancelBtnCreate");
  const createURLTitleInput = urlInputForm.find("#urlTitleCreate");
  const createURLInput = urlInputForm.find("#urlStringCreate");

  $(urlBtnCreate).onExact("click.createURL", function () {
    emit({
      event: UI_EVENTS.UI_FORM_SUBMIT,
      form: HOME_FORM.URL_CREATE,
      trigger: FORM_SUBMIT_TRIGGER.BUTTON_CLICK,
    });
    clearOpenForm();
    createURL({ createURLTitleInput, createURLInput, utubID });
  });

  $(urlBtnDelete).onExact("click.createURL", function () {
    emit({
      event: UI_EVENTS.UI_FORM_CANCEL,
      form: HOME_FORM.URL_CREATE,
      trigger: FORM_CANCEL_TRIGGER.CANCEL_BUTTON,
    });
    clearOpenForm();
    createURLHideInput();
  });

  const inputArr = [createURLInput, createURLTitleInput];

  for (let inputIndex = 0; inputIndex < inputArr.length; inputIndex++) {
    $(inputArr[inputIndex]).on("focus.createURL", function () {
      bindCreateURLFocusEventListeners(
        $(inputArr[inputIndex]),
        createURLInput,
        createURLTitleInput,
        utubID,
      );
    });

    $(inputArr[inputIndex]).on("blur.createURL", function () {
      unbindCreateURLFocusEventListeners($(inputArr[inputIndex]));
    });
  }
}

export function newURLInputRemoveEventListeners(): void {
  resetCreateURLFailErrors();
  $("#urlSubmitBtnCreate").off();
  $("#urlCancelBtnCreate").off();
  $(document).off(".createURL");
  $("#urlTitleCreate").off(".createURL");
  $("#urlStringCreate").off(".createURL");
}
