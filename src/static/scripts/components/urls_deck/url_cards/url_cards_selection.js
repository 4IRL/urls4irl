"use strict";

// Streamline the jQuery selector extraction of selected URL card. Provides ease of reference by URL Functions.
function getSelectedURLCard() {
  const selectedUrlCard = $(".urlRow[urlSelected=true]");
  return selectedUrlCard.length ? selectedUrlCard : null;
}

// Perform actions on selection of a URL card
function selectURLCard(urlCard) {
  deselectAllURLs();

  urlCard.attr({ urlSelected: true });
  urlCard.find(".goToUrlIcon").addClass("visible-flex");
  enableClickOnSelectedURLCardToHide(urlCard);

  enableTabbingOnURLCardElements(urlCard);
}

function enableClickOnSelectedURLCardToHide(urlCard) {
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

function disableClickOnSelectedURLCardToHide(urlCard) {
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

function deselectAllURLs() {
  const previouslySelectedCard = getSelectedURLCard();
  if (previouslySelectedCard !== null) deselectURL(previouslySelectedCard);
}

function setURLCardSelectionEventListener(urlCard) {
  urlCard.offAndOn("click.urlSelected", function (e) {
    if (!$(e.target).parents(".urlRow").length) return;

    if ($(e.target).closest(".urlRow").attr("urlSelected") === "true") return;

    selectURLCard(urlCard);
  });
}
