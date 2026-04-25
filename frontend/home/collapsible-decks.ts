import { $ } from "../lib/globals.js";
import { isMobile } from "./mobile.js";
import { isUTubSelected } from "./utubs/utils.js";
import { resetUTubSearch } from "./utubs/search.js";
import { createUTubHideInput } from "./utubs/create.js";
import { createMemberHideInput } from "./members/create.js";
import { createUTubTagHideInput } from "./tags/create.js";

const UTUB_DECK_CSS_SELECTOR = ".deck#UTubDeck";
const MEMBER_DECK_CSS_SELECTOR = ".deck#MemberDeck";
const UTUB_TAG_DECK_CSS_SELECTOR = ".deck#TagDeck";
const LHS_DECKS: readonly string[] = [
  UTUB_DECK_CSS_SELECTOR,
  MEMBER_DECK_CSS_SELECTOR,
  UTUB_TAG_DECK_CSS_SELECTOR,
];

/**
 * Initialize collapsible deck functionality
 */
export function initCollapsibleDecks(): void {
  if (!isMobile()) {
    setupCollapsibleLeftDecks();
  } else {
    removeCollapsibleClickableHeaderClass();
  }
}

export function removeCollapsibleClickableHeaderClass(): void {
  $("#UTubDeckHeaderAndCaret").removeClass("clickable");
  $("#MemberDeckHeaderAndCaret").removeClass("clickable");
  $("#TagDeckHeaderAndCaret").removeClass("clickable");
}

export function addCollapsibleClickableHeaderClass(): void {
  $("#UTubDeckHeaderAndCaret").addClass("clickable");
  $("#MemberDeckHeaderAndCaret").addClass("clickable");
  $("#TagDeckHeaderAndCaret").addClass("clickable");
}

function setupCollapsibleLeftDecks() {
  setupUTubHeaderForMaximizeMinimize();
  setupMemberHeaderForMaximizeMinimize();
  setupTagHeaderForMaximizeMinimize();
}

export function resetAllDecksIfCollapsed(): void {
  const caretUTubDeck = $("#UTubDeckHeaderAndCaret .title-caret");
  if (caretUTubDeck.hasClass("closed")) {
    caretUTubDeck.removeClass("closed");
    $(UTUB_DECK_CSS_SELECTOR).removeClass("collapsed");
  }

  const caretMemberDeck = $("#MemberDeckHeaderAndCaret .title-caret");
  if (caretMemberDeck.hasClass("closed")) {
    caretMemberDeck.removeClass("closed");
    $(MEMBER_DECK_CSS_SELECTOR).removeClass("collapsed");
    if (!isUTubSelected()) {
      $("#MemberDeck > .sidePanelTitle").addClass("pad-b-0-25rem");
    }
    return;
  }

  const caretTagDeck = $("#TagDeckHeaderAndCaret .title-caret");
  if (caretTagDeck.hasClass("closed")) {
    caretTagDeck.removeClass("closed");
    $(UTUB_TAG_DECK_CSS_SELECTOR).removeClass("collapsed");
    if (!isUTubSelected()) {
      $("#TagDeck > .sidePanelTitle").addClass("pad-b-0-25rem");
    }
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

    resetUTubSearch();
    if (isUTubSelected()) createUTubHideInput();

    if (numDecksAlreadyCollapsed >= 2) {
      ensureOnlyTwoDecksCollapsedAtOnce();
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
      if (!isUTubSelected()) {
        $("#MemberDeck > .sidePanelTitle").addClass("pad-b-0-25rem");
      }
      return;
    }

    const numDecksAlreadyCollapsed = getNumDecksAlreadyCollapsed();
    caret.addClass("closed");
    $(MEMBER_DECK_CSS_SELECTOR).addClass("collapsed");

    if (isUTubSelected()) createMemberHideInput();
    $("#MemberDeck > .sidePanelTitle").removeClass("pad-b-0-25rem");

    if (numDecksAlreadyCollapsed >= 2) {
      ensureOnlyTwoDecksCollapsedAtOnce();
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
      if (!isUTubSelected()) {
        $("#TagDeck > .sidePanelTitle").addClass("pad-b-0-25rem");
      }
      return;
    }

    const numDecksAlreadyCollapsed = getNumDecksAlreadyCollapsed();
    caret.addClass("closed");
    $(UTUB_TAG_DECK_CSS_SELECTOR).addClass("collapsed");

    if (isUTubSelected()) createUTubTagHideInput();
    $("#TagDeck > .sidePanelTitle").removeClass("pad-b-0-25rem");

    if (numDecksAlreadyCollapsed >= 2) {
      ensureOnlyTwoDecksCollapsedAtOnce();
    }
    setLastCollapsed(UTUB_TAG_DECK_CSS_SELECTOR);
  });
}

function getNumDecksAlreadyCollapsed(): number {
  let collapsedDecksCount = 0;

  for (let i = 0; i < LHS_DECKS.length; i++) {
    if ($(LHS_DECKS[i]).hasClass("collapsed")) collapsedDecksCount += 1;
  }

  return collapsedDecksCount;
}

function ensureOnlyTwoDecksCollapsedAtOnce(): void {
  let deckToExpandSelector: string | undefined;
  for (let i = 0; i < LHS_DECKS.length; i++) {
    if ($(LHS_DECKS[i]).attr("data-last-collapsed") === "true") {
      deckToExpandSelector = LHS_DECKS[i];
      break;
    }
  }

  if (!deckToExpandSelector) return;
  const deckToExpand = $(deckToExpandSelector);
  deckToExpand.find(".title-caret").first().removeClass("closed");
  deckToExpand.removeClass("collapsed");
}

function setLastCollapsed(collapsingDeck: string): void {
  for (let i = 0; i < LHS_DECKS.length; i++) {
    if (collapsingDeck === LHS_DECKS[i]) {
      $(collapsingDeck).attr("data-last-collapsed", "true");
    } else {
      $(LHS_DECKS[i]).attr("data-last-collapsed", "false");
    }
  }
}
