"use strict";

$(document).ready(function () {
  setupUTubHeaderForMaximizeMinimize();
  setupMemberHeaderForMaximizeMinimize();
  setupTagHeaderForMaximizeMinimize();
});

const UTUB_DECK_CSS_SELECTOR = ".deck#UTubDeck";
const MEMBER_DECK_CSS_SELECTOR = ".deck#MemberDeck";
const UTUB_TAG_DECK_CSS_SELECTOR = ".deck#TagDeck";
const LHS_DECKS = [
  UTUB_DECK_CSS_SELECTOR,
  MEMBER_DECK_CSS_SELECTOR,
  UTUB_TAG_DECK_CSS_SELECTOR,
];

function setupUTubHeaderForMaximizeMinimize() {
  $("#UTubDeckHeaderAndCaret").offAndOn("click.collapsibleUTubDeck", () => {
    const caret = $("#UTubDeckHeaderAndCaret .title-caret");
    if (caret.hasClass("closed")) {
      caret.removeClass("closed");
      $(UTUB_DECK_CSS_SELECTOR).removeClass("collapsed");
      return;
    }

    const numDecksAlreadyCollapsed = getNumDecksAlreadyCollapsed();
    caret.addClass("closed");
    $(UTUB_DECK_CSS_SELECTOR).addClass("collapsed");

    closeUTubSearchAndEraseInput();
    createUTubHideInput();

    if (numDecksAlreadyCollapsed >= 2) {
      ensureOnlyTwoDecksCollapsedAtOnce(UTUB_DECK_CSS_SELECTOR);
    }
    setLastCollapsed(UTUB_DECK_CSS_SELECTOR);
  });
}

function setupMemberHeaderForMaximizeMinimize() {
  $("#MemberDeckHeaderAndCaret").offAndOn("click.collapsibleMemberDeck", () => {
    const caret = $("#MemberDeckHeaderAndCaret .title-caret");
    if (caret.hasClass("closed")) {
      caret.removeClass("closed");
      $(MEMBER_DECK_CSS_SELECTOR).removeClass("collapsed");
      return;
    }

    const numDecksAlreadyCollapsed = getNumDecksAlreadyCollapsed();
    caret.addClass("closed");
    $(MEMBER_DECK_CSS_SELECTOR).addClass("collapsed");

    createMemberHideInput();

    if (numDecksAlreadyCollapsed >= 2) {
      ensureOnlyTwoDecksCollapsedAtOnce(MEMBER_DECK_CSS_SELECTOR);
    }
    setLastCollapsed(MEMBER_DECK_CSS_SELECTOR);
  });
}

function setupTagHeaderForMaximizeMinimize() {
  $("#TagDeckHeaderAndCaret").offAndOn("click.collapsibleUTubTagDeck", () => {
    const caret = $("#TagDeckHeaderAndCaret .title-caret");
    if (caret.hasClass("closed")) {
      caret.removeClass("closed");
      $(UTUB_TAG_DECK_CSS_SELECTOR).removeClass("collapsed");
      return;
    }

    const numDecksAlreadyCollapsed = getNumDecksAlreadyCollapsed();
    caret.addClass("closed");
    $(UTUB_TAG_DECK_CSS_SELECTOR).addClass("collapsed");

    createUTubTagHideInput();

    if (numDecksAlreadyCollapsed >= 2) {
      ensureOnlyTwoDecksCollapsedAtOnce(UTUB_TAG_DECK_CSS_SELECTOR);
    }
    setLastCollapsed(UTUB_TAG_DECK_CSS_SELECTOR);
  });
}

function getNumDecksAlreadyCollapsed() {
  let collapsedDecksCount = 0;

  for (let i = 0; i < LHS_DECKS.length; i++) {
    if ($(LHS_DECKS[i]).hasClass("collapsed")) collapsedDecksCount += 1;
  }

  return collapsedDecksCount;
}

function ensureOnlyTwoDecksCollapsedAtOnce(collapsingDeck) {
  let deckToExpandSelector;
  for (let i = 0; i < LHS_DECKS.length; i++) {
    if ($(LHS_DECKS[i]).attr("data-last-collapsed") === "true") {
      deckToExpandSelector = LHS_DECKS[i];
      break;
    }
  }

  const deckToExpand = $(deckToExpandSelector);
  deckToExpand.find(".title-caret").first().removeClass("closed");
  deckToExpand.removeClass("collapsed");
}

function setLastCollapsed(collapsingDeck) {
  for (let i = 0; i < LHS_DECKS.length; i++) {
    collapsingDeck === LHS_DECKS[i]
      ? $(collapsingDeck).attr("data-last-collapsed", "true")
      : $(LHS_DECKS[i]).attr("data-last-collapsed", "false");
  }
}
