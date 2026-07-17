import { $ } from "../lib/globals.js";
import { AppEvents, on } from "../lib/event-bus.js";
import { emit } from "../lib/metrics-client.js";
import { UI_EVENTS } from "../types/metrics-events.js";
import { isMobile } from "./mobile.js";
import { isUTubSelected } from "./utubs/utils.js";
import { resetUTubSearch } from "./utubs/search.js";
import { closeMemberNameFilter } from "./members/search.js";
import { closeTagNameFilter } from "./tags/search.js";
import { createUTubHideInput } from "./utubs/create.js";
import { createMemberHideInput } from "./members/create.js";
import { createUTubTagHideInput } from "./tags/create.js";
import {
  DECK_COLLAPSE_DECK,
  DECK_EXPAND_DECK,
} from "../types/metrics-dim-values.js";
import { debug } from "../lib/debug.js";

const log = debug("home-shell");

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
    const willExpand = caret.hasClass("closed");
    emit({
      event: willExpand ? UI_EVENTS.UI_DECK_EXPAND : UI_EVENTS.UI_DECK_COLLAPSE,
      deck: willExpand ? DECK_EXPAND_DECK.UTUBS : DECK_COLLAPSE_DECK.UTUBS,
    });
    if (willExpand) {
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
      log(
        "collapsible decks: forcing prior deck open due to 2-collapsed limit",
        {
          collapsing: "UTubs",
          numAlreadyCollapsed: numDecksAlreadyCollapsed,
        },
      );
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
    // No UTub selected -> the deck is locked minimized (nothing to show); the
    // header is visually marked non-interactable and clicks are inert.
    if (!isUTubSelected()) return;
    const caret = $("#MemberDeckHeaderAndCaret .title-caret");
    const willExpand = caret.hasClass("closed");
    emit({
      event: willExpand ? UI_EVENTS.UI_DECK_EXPAND : UI_EVENTS.UI_DECK_COLLAPSE,
      deck: willExpand ? DECK_EXPAND_DECK.MEMBERS : DECK_COLLAPSE_DECK.MEMBERS,
    });
    if (willExpand) {
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

    closeMemberNameFilter();
    if (isUTubSelected()) createMemberHideInput();
    $("#MemberDeck > .sidePanelTitle").removeClass("pad-b-0-25rem");

    if (numDecksAlreadyCollapsed >= 2) {
      log(
        "collapsible decks: forcing prior deck open due to 2-collapsed limit",
        {
          collapsing: "Members",
          numAlreadyCollapsed: numDecksAlreadyCollapsed,
        },
      );
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
    // No UTub selected -> the deck is locked minimized (nothing to show); the
    // header is visually marked non-interactable and clicks are inert.
    if (!isUTubSelected()) return;
    const caret = $("#TagDeckHeaderAndCaret .title-caret");
    const willExpand = caret.hasClass("closed");
    emit({
      event: willExpand ? UI_EVENTS.UI_DECK_EXPAND : UI_EVENTS.UI_DECK_COLLAPSE,
      deck: willExpand ? DECK_EXPAND_DECK.TAGS : DECK_COLLAPSE_DECK.TAGS,
    });
    if (willExpand) {
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

    closeTagNameFilter();
    if (isUTubSelected()) createUTubTagHideInput();
    $("#TagDeck > .sidePanelTitle").removeClass("pad-b-0-25rem");

    if (numDecksAlreadyCollapsed >= 2) {
      log(
        "collapsible decks: forcing prior deck open due to 2-collapsed limit",
        {
          collapsing: "Tags",
          numAlreadyCollapsed: numDecksAlreadyCollapsed,
        },
      );
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

function setDeckMinimized(deckSelector: string, minimized: boolean): void {
  const deck = $(deckSelector);
  // Toggle WITHOUT animation: an animating expand briefly slides member/tag rows
  // over the header buttons, intercepting clicks (and it is jarring on every UTub
  // switch). .deck-snap suppresses the transition; the forced reflow commits the
  // change before transitions are re-enabled for user-initiated caret collapse.
  deck.addClass("deck-snap");
  deck.toggleClass("collapsed", minimized);
  $(deckSelector + " .title-caret")
    .first()
    .toggleClass("closed", minimized);
  const deckElement = deck.get(0);
  if (deckElement) void deckElement.offsetHeight;
  deck.removeClass("deck-snap");
}

// Minimize the Member + Tag decks when no UTub is selected (they have nothing to
// show) so the UTubs list gets the room. Desktop only — the decks are not
// collapsible on mobile (single-deck nav).
export function minimizeMemberAndTagDecksWhenNoUTub(): void {
  if (isMobile()) return;
  setDeckMinimized(MEMBER_DECK_CSS_SELECTOR, true);
  setDeckMinimized(UTUB_TAG_DECK_CSS_SELECTOR, true);
  // Lock them: the header reads as non-interactable (hidden caret, dimmed title,
  // no hover/cursor) so it's clear they can't be expanded with no UTub selected.
  $(MEMBER_DECK_CSS_SELECTOR).addClass("deck-locked");
  $(UTUB_TAG_DECK_CSS_SELECTOR).addClass("deck-locked");
}

// Restore the Member + Tag decks when a UTub is selected.
function restoreMemberAndTagDecksForUTub(): void {
  $(MEMBER_DECK_CSS_SELECTOR).removeClass("deck-locked");
  $(UTUB_TAG_DECK_CSS_SELECTOR).removeClass("deck-locked");
  setDeckMinimized(MEMBER_DECK_CSS_SELECTOR, false);
  setDeckMinimized(UTUB_TAG_DECK_CSS_SELECTOR, false);
}

on(AppEvents.UTUB_SELECTED, restoreMemberAndTagDecksForUTub);
