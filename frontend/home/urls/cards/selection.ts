import { $ } from "../../../lib/globals.js";
import { getState, setState } from "../../../store/app-store.js";
import { AppEvents, on } from "../../../lib/event-bus.js";
import { hideAndResetUpdateURLTitleForm } from "./update-title.js";
import { hideAndResetUpdateURLStringForm } from "./update-string.js";
import {
  enableTabbingOnURLCardElements,
  disableTabbingOnURLCardElements,
} from "./utils.js";
import { hideAndResetCreateURLTagForm } from "../tags/create.js";
import { setFocusEventListenersOnURLCard } from "./cards.js";

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

    deselectURL(urlCard);
  });
}

export function disableClickOnSelectedURLCardToHide(urlCard: JQuery): void {
  urlCard.off("click.deselectURL");
}

// Clean up when deselecting a URL card
function deselectURL(urlCard: JQuery): void {
  disableClickOnSelectedURLCardToHide(urlCard);
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

      selectURLCard(urlCard);
    },
  );
}
