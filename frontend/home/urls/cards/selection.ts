import { $ } from "../../../lib/globals.js";
import { getState, setState } from "../../../store/app-store.js";
import { AppEvents, on } from "../../../lib/event-bus.js";
import { emit } from "../../../lib/metrics-client.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { isURLSearchActive, getActiveTagCount } from "../url-context.js";
import { hideAndResetUpdateURLTitleForm } from "./update-title.js";
import { hideAndResetUpdateURLStringForm } from "./update-string.js";
import {
  enableTabbingOnURLCardElements,
  disableTabbingOnURLCardElements,
} from "./utils.js";
import { hideAndResetCreateURLTagForm } from "../tags/create.js";
import { setFocusEventListenersOnURLCard } from "./cards.js";
import { SEARCH_ACTIVE } from "../../../types/metrics-dim-values.js";
import { isCoarsePointer } from "../../mobile.js";

// Touch devices have no hover to reveal a tag's delete "×", so tapping a tag
// toggles this class on it (one tag at a time) to slide the "×" out. The
// matching reveal styling lives in styles/home/tags.css.
const TAG_DELETE_REVEAL_CLASS = "tagBadgeDeleteRevealed";
const TAG_DELETE_REVEAL_SELECTOR = "." + TAG_DELETE_REVEAL_CLASS;

// Streamline the jQuery selector extraction of selected URL card. Provides ease of reference by URL Functions.
export function getSelectedURLCard(): JQuery | null {
  const id = getState().selectedURLCardID;
  return id !== null ? $(`.urlRow[utuburlid=${id}]`) : null;
}

// Perform actions on selection of a URL card
export function selectURLCard(urlCard: JQuery): void {
  deselectAllURLs();

  setState({ selectedURLCardID: parseInt(urlCard.attr("utuburlid")!) });
  urlCard.attr({ urlSelected: true });
  urlCard.find(".goToUrlIcon").addClass("visible-flex");
  enableClickOnSelectedURLCardToHide(urlCard);

  enableTabbingOnURLCardElements(urlCard);
}

export function enableClickOnSelectedURLCardToHide(urlCard: JQuery): void {
  urlCard.on("click.deselectURL", (event: JQuery.TriggeredEvent) => {
    const elementsToIgnoreForURLDeselection = [
      ".urlTagBtnCreate",
      ".urlStringBtnUpdate",
      ".urlStringCancelBtnUpdate",
      ".urlTagCancelBtnCreate",
      ".urlTitleAndUpdateIconWrap",
      ".urlTitleBtnUpdate",
      ".urlTitleCancelBtnUpdate",
      ".urlTagBtnDelete",
      ".urlBtnCopy",
      ".goToUrlIcon",
      ".urlBtnAccess",
      ".urlBtnDelete",
    ];

    for (
      let index = 0;
      index < elementsToIgnoreForURLDeselection.length;
      index++
    ) {
      if (
        $(event.target).closest(elementsToIgnoreForURLDeselection[index]).length
      )
        return;
    }

    // On touch, tapping a tag reveals that tag's delete "×" (one at a time)
    // rather than closing the card — the touch equivalent of the desktop hover
    // reveal. The "×" tap itself is handled above (.urlTagBtnDelete is ignored).
    if (isCoarsePointer()) {
      const tappedTagBadge = $(event.target).closest(".tagBadge");
      if (tappedTagBadge.length) {
        const alreadyRevealed = tappedTagBadge.hasClass(
          TAG_DELETE_REVEAL_CLASS,
        );
        urlCard
          .find(TAG_DELETE_REVEAL_SELECTOR)
          .removeClass(TAG_DELETE_REVEAL_CLASS);
        if (!alreadyRevealed) tappedTagBadge.addClass(TAG_DELETE_REVEAL_CLASS);
        return;
      }
    }

    deselectURL(urlCard);
  });
}

export function disableClickOnSelectedURLCardToHide(urlCard: JQuery): void {
  urlCard.off("click.deselectURL");
}

// Clean up when deselecting a URL card
function deselectURL(urlCard: JQuery): void {
  disableClickOnSelectedURLCardToHide(urlCard);
  urlCard.find(TAG_DELETE_REVEAL_SELECTOR).removeClass(TAG_DELETE_REVEAL_CLASS);
  setState({ selectedURLCardID: null });
  urlCard.attr({ urlSelected: false });
  urlCard.find(".urlString").off("click.goToURL");
  urlCard
    .find(".goToUrlIcon")
    .removeClass("visible-flex hidden visible-on-focus");
  hideAndResetUpdateURLTitleForm(urlCard);
  hideAndResetUpdateURLStringForm(urlCard);
  hideAndResetCreateURLTagForm(urlCard);
  disableTabbingOnURLCardElements(urlCard);
  setURLCardSelectionEventListener(urlCard);
  setFocusEventListenersOnURLCard(urlCard);
  urlCard.blur(); // Remove focus after deselecting the URL
}

export function deselectAllURLs(): void {
  const previouslySelectedCard = getSelectedURLCard();
  if (previouslySelectedCard !== null) deselectURL(previouslySelectedCard);
}

function isSelectedCardHidden(): boolean {
  const selectedCard = getSelectedURLCard();
  if (selectedCard === null) return false;
  return (
    selectedCard.attr("searchable") === "false" ||
    selectedCard.attr("filterable") === "false"
  );
}

function deselectIfSelectedCardHidden(): void {
  if (isSelectedCardHidden()) {
    deselectAllURLs();
  }
}

on(AppEvents.URL_SEARCH_VISIBILITY_CHANGED, deselectIfSelectedCardHidden);
on(AppEvents.URL_TAG_FILTER_APPLIED, deselectIfSelectedCardHidden);

export function setURLCardSelectionEventListener(urlCard: JQuery): void {
  urlCard.offAndOn(
    "click.urlSelected",
    function (event: JQuery.TriggeredEvent) {
      if (!$(event.target).closest(".urlRow").length) return;

      if ($(event.target).closest(".urlRow").attr("urlSelected") === "true")
        return;

      emit({
        event: UI_EVENTS.UI_URL_CARD_CLICK,
        search_active: isURLSearchActive()
          ? SEARCH_ACTIVE.TRUE
          : SEARCH_ACTIVE.FALSE,
        active_tag_count: getActiveTagCount(),
      });
      selectURLCard(urlCard);
    },
  );
}
