import { $ } from "../../../lib/globals.js";
import { hideAndResetUpdateURLTitleForm } from "./update-title.js";
import { hideAndResetUpdateURLStringForm } from "./update-string.js";
import {
  enableTabbingOnURLCardElements,
  disableTabbingOnURLCardElements,
} from "./utils.js";
import { hideAndResetCreateURLTagForm } from "../tags/create.js";
import { setFocusEventListenersOnURLCard } from "./cards.js";

// Streamline the jQuery selector extraction of selected URL card. Provides ease of reference by URL Functions.
export function getSelectedURLCard() {
  const selectedUrlCard = $(".urlRow[urlSelected=true]");
  return selectedUrlCard.length ? selectedUrlCard : null;
}

// Perform actions on selection of a URL card
export function selectURLCard(urlCard) {
  deselectAllURLs();

  urlCard.attr({ urlSelected: true });
  urlCard.find(".goToUrlIcon").addClass("visible-flex");
  enableClickOnSelectedURLCardToHide(urlCard);

  enableTabbingOnURLCardElements(urlCard);
}

export function enableClickOnSelectedURLCardToHide(urlCard) {
  urlCard.on("click.deselectURL", (e) => {
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

    for (let i = 0; i < elementsToIgnoreForURLDeselection.length; i++) {
      if ($(e.target).closest(elementsToIgnoreForURLDeselection[i]).length)
        return;
    }

    deselectURL(urlCard);
  });
}

export function disableClickOnSelectedURLCardToHide(urlCard) {
  urlCard.off("click.deselectURL");
}

// Clean up when deselecting a URL card
function deselectURL(urlCard) {
  disableClickOnSelectedURLCardToHide(urlCard);
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

export function deselectAllURLs() {
  const previouslySelectedCard = getSelectedURLCard();
  if (previouslySelectedCard !== null) deselectURL(previouslySelectedCard);
}

export function setURLCardSelectionEventListener(urlCard) {
  urlCard.offAndOn("click.urlSelected", function (e) {
    if (!$(e.target).parents(".urlRow").length) return;

    if ($(e.target).closest(".urlRow").attr("urlSelected") === "true") return;

    selectURLCard(urlCard);
  });
}
