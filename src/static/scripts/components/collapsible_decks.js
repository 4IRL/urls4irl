"use strict";

$(document).ready(function () {
  if (!isMobile()) {
    setupCollapsibleLeftDecks();
  } else {
    removeCollapsibleClickableHeaderClass();
  }
});

const UTUB_DECK_CSS_SELECTOR = ".deck#UTubDeck";
const MEMBER_DECK_CSS_SELECTOR = ".deck#MemberDeck";
const UTUB_TAG_DECK_CSS_SELECTOR = ".deck#TagDeck";
const LHS_DECKS = [
  UTUB_DECK_CSS_SELECTOR,
  MEMBER_DECK_CSS_SELECTOR,
  UTUB_TAG_DECK_CSS_SELECTOR,
];

function removeCollapsibleClickableHeaderClass() {
  $("#UTubDeckHeaderAndCaret").removeClass("clickable");
  $("#MemberDeckHeaderAndCaret").removeClass("clickable");
  $("#TagDeckHeaderAndCaret").removeClass("clickable");
}

function addCollapsibleClickableHeaderClass() {
  $("#UTubDeckHeaderAndCaret").addClass("clickable");
  $("#MemberDeckHeaderAndCaret").addClass("clickable");
  $("#TagDeckHeaderAndCaret").addClass("clickable");
}

function setupCollapsibleLeftDecks() {
  setupUTubHeaderForMaximizeMinimize();
  setupMemberHeaderForMaximizeMinimize();
  setupTagHeaderForMaximizeMinimize();
}

function resetAllDecksIfCollapsed() {
  const caretUTubDeck = $("#UTubDeckHeaderAndCaret .title-caret");
  if (caretUTubDeck.hasClass("closed")) {
    caretUTubDeck.removeClass("closed");
    $(UTUB_DECK_CSS_SELECTOR).removeClass("collapsed");
  }

  const caretMemberDeck = $("#MemberDeckHeaderAndCaret .title-caret");
  if (caretMemberDeck.hasClass("closed")) {
    caretMemberDeck.removeClass("closed");
    $(MEMBER_DECK_CSS_SELECTOR).removeClass("collapsed");
    !isUTubSelected()
      ? $("#MemberDeck > .sidePanelTitle").addClass("pad-b-0-25rem")
      : null;
    return;
  }

  const caretTagDeck = $("#TagDeckHeaderAndCaret .title-caret");
  if (caretTagDeck.hasClass("closed")) {
    caretTagDeck.removeClass("closed");
    $(UTUB_TAG_DECK_CSS_SELECTOR).removeClass("collapsed");
    !isUTubSelected()
      ? $("#TagDeck > .sidePanelTitle").addClass("pad-b-0-25rem")
      : null;
    return;
  }
}

function setupUTubHeaderForMaximizeMinimize() {
  const headerAndCaret = $("#UTubDeckHeaderAndCaret");
  if (!headerAndCaret.hasClass("clickable"))
    headerAndCaret.addClass("clickable");

  headerAndCaret.offAndOn("click.collapsibleUTubDeck", () => {
    if (isMobile()) return;
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
    isUTubSelected() ? createUTubHideInput() : null;

    if (numDecksAlreadyCollapsed >= 2) {
      ensureOnlyTwoDecksCollapsedAtOnce(UTUB_DECK_CSS_SELECTOR);
    }
    setLastCollapsed(UTUB_DECK_CSS_SELECTOR);
  });
}

function setupMemberHeaderForMaximizeMinimize() {
  const headerAndCaret = $("#MemberDeckHeaderAndCaret");
  if (!headerAndCaret.hasClass("clickable"))
    headerAndCaret.addClass("clickable");

  headerAndCaret.offAndOn("click.collapsibleMemberDeck", () => {
    if (isMobile()) return;
    const caret = $("#MemberDeckHeaderAndCaret .title-caret");
    if (caret.hasClass("closed")) {
      caret.removeClass("closed");
      $(MEMBER_DECK_CSS_SELECTOR).removeClass("collapsed");
      !isUTubSelected()
        ? $("#MemberDeck > .sidePanelTitle").addClass("pad-b-0-25rem")
        : null;
      return;
    }

    const numDecksAlreadyCollapsed = getNumDecksAlreadyCollapsed();
    caret.addClass("closed");
    $(MEMBER_DECK_CSS_SELECTOR).addClass("collapsed");

    isUTubSelected() ? createMemberHideInput() : null;
    $("#MemberDeck > .sidePanelTitle").removeClass("pad-b-0-25rem");

    if (numDecksAlreadyCollapsed >= 2) {
      ensureOnlyTwoDecksCollapsedAtOnce(MEMBER_DECK_CSS_SELECTOR);
    }
    setLastCollapsed(MEMBER_DECK_CSS_SELECTOR);
  });
}

function setupTagHeaderForMaximizeMinimize() {
  const headerAndCaret = $("#TagDeckHeaderAndCaret");
  if (!headerAndCaret.hasClass("clickable"))
    headerAndCaret.addClass("clickable");

  headerAndCaret.offAndOn("click.collapsibleUTubTagDeck", () => {
    if (isMobile()) return;
    const caret = $("#TagDeckHeaderAndCaret .title-caret");
    if (caret.hasClass("closed")) {
      caret.removeClass("closed");
      $(UTUB_TAG_DECK_CSS_SELECTOR).removeClass("collapsed");
      !isUTubSelected()
        ? $("#TagDeck > .sidePanelTitle").addClass("pad-b-0-25rem")
        : null;
      return;
    }

    const numDecksAlreadyCollapsed = getNumDecksAlreadyCollapsed();
    caret.addClass("closed");
    $(UTUB_TAG_DECK_CSS_SELECTOR).addClass("collapsed");

    isUTubSelected() ? createUTubTagHideInput() : null;
    $("#TagDeck > .sidePanelTitle").removeClass("pad-b-0-25rem");

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
