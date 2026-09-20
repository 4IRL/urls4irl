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
import { maybeShowNextTip } from "./onboarding/nudges.js";
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

const UTUB_DECK_HEADER_SELECTOR = "#UTubDeckHeaderAndCaret";
const MEMBER_DECK_HEADER_SELECTOR = "#MemberDeckHeaderAndCaret";
const UTUB_TAG_DECK_HEADER_SELECTOR = "#TagDeckHeaderAndCaret";

// Each deck's disclosure button and the `.content` element that button owns.
// Keyed by deck selector so the shared programmatic paths (setDeckMinimized,
// resetAllDecksIfCollapsed) can resolve a header from the deck they were handed.
const DECK_HEADER_SELECTOR_BY_DECK: Readonly<Record<string, string>> = {
  [UTUB_DECK_CSS_SELECTOR]: UTUB_DECK_HEADER_SELECTOR,
  [MEMBER_DECK_CSS_SELECTOR]: MEMBER_DECK_HEADER_SELECTOR,
  [UTUB_TAG_DECK_CSS_SELECTOR]: UTUB_TAG_DECK_HEADER_SELECTOR,
};

const DECK_CONTENT_ID_BY_DECK: Readonly<Record<string, string>> = {
  [UTUB_DECK_CSS_SELECTOR]: "UTubDeckContent",
  [MEMBER_DECK_CSS_SELECTOR]: "MemberDeckContent",
  [UTUB_TAG_DECK_CSS_SELECTOR]: "TagDeckContent",
};

/**
 * Initialize collapsible deck functionality
 */
export function initCollapsibleDecks(): void {
  if (!isMobile()) {
    setupCollapsibleLeftDecks();
    enableDeckHeaderDisclosureForDesktop();
  } else {
    removeCollapsibleClickableHeaderClass();
  }
}

export function removeCollapsibleClickableHeaderClass(): void {
  $(UTUB_DECK_HEADER_SELECTOR).removeClass("clickable");
  $(MEMBER_DECK_HEADER_SELECTOR).removeClass("clickable");
  $(UTUB_TAG_DECK_HEADER_SELECTOR).removeClass("clickable");
  disableDeckHeaderDisclosureForMobile();
}

export function addCollapsibleClickableHeaderClass(): void {
  $(UTUB_DECK_HEADER_SELECTOR).addClass("clickable");
  $(MEMBER_DECK_HEADER_SELECTOR).addClass("clickable");
  $(UTUB_TAG_DECK_HEADER_SELECTOR).addClass("clickable");
  // A page FIRST loaded below 992px took initCollapsibleDecks()'s mobile branch,
  // which binds no click handlers — and init only ever runs once, at DOM-ready
  // (main.ts). Without this, widening the viewport would hand back three
  // focusable buttons that announce a disclosure and do nothing on click or
  // Enter/Space: exactly the focusable-but-inert trap the ARIA work exists to
  // remove. offAndOn makes the re-setup idempotent for the already-desktop path.
  setupCollapsibleLeftDecks();
  // The desktop->mobile crossing ran resetAllDecksIfCollapsed(), which drops
  // `.collapsed` but never `.deck-locked`, so with no UTub selected the decks
  // come back visually expanded yet inert. Re-assert the no-UTub state before
  // the headers' ARIA is derived from it, otherwise aria-expanded="true" would
  // contradict a locked, unusable deck.
  if (!isUTubSelected()) minimizeMemberAndTagDecksWhenNoUTub();
  enableDeckHeaderDisclosureForDesktop();
}

/**
 * Keep a deck header button's `aria-expanded` in sync with its deck. EVERY path
 * that toggles `.collapsed` must call this: the Jinja templates render a static
 * `aria-expanded="true"` that is already wrong on first paint, since
 * minimizeMemberAndTagDecksWhenNoUTub() collapses Members + Tags at init when no
 * UTub is selected.
 *
 * No-op on mobile: there the headers are deliberately stripped of their
 * disclosure ARIA (see disableDeckHeaderDisclosureForMobile) while the shared
 * collapse/restore paths still run, so writing the attribute here would
 * resurrect a control that does nothing.
 */
function setDeckHeaderExpanded({
  headerSelector,
  expanded,
}: {
  headerSelector: string;
  expanded: boolean;
}): void {
  if (isMobile()) return;
  $(headerSelector).attr("aria-expanded", expanded ? "true" : "false");
}

/**
 * Mark a deck header as non-interactive while its deck is locked (no UTub
 * selected). `aria-disabled` is paired with `tabindex="-1"` deliberately:
 * `aria-disabled` alone does NOT remove an element from the tab order, and the
 * click handlers' `if (!isUTubSelected()) return;` guard makes activation inert,
 * so a focusable-but-dead control announcing a stale `aria-expanded` is exactly
 * the trap to avoid. Mobile is left alone — the headers are already
 * `tabindex="-1"` there for a different reason.
 */
function setDeckHeaderLocked({
  headerSelector,
  locked,
}: {
  headerSelector: string;
  locked: boolean;
}): void {
  if (isMobile()) return;
  const header = $(headerSelector);
  if (locked) {
    header.attr("aria-disabled", "true").attr("tabindex", "-1");
  } else {
    header.removeAttr("aria-disabled").removeAttr("tabindex");
  }
}

/**
 * Below the tablet breakpoint the decks are not collapsible: no click handler is
 * bound and `.title-caret` is `display: none`. Left as-is, the three header
 * <button>s would be dead tab stops still announcing
 * "expanded, button, controls …DeckContent". Worse for the Tag deck, whose
 * header sheet.ts relocates into the bottom sheet: with the sheet OPEN the
 * button sits inside the sheet's focus trap and activating it bubbles to
 * #TagDeckTitleGroup's handler, CLOSING the whole sheet — a control announced as
 * a disclosure acting as a dismiss button. So take them out of the tab order and
 * strip the disclosure ARIA entirely while mobile.
 */
function disableDeckHeaderDisclosureForMobile(): void {
  for (const deckSelector of LHS_DECKS) {
    $(DECK_HEADER_SELECTOR_BY_DECK[deckSelector])
      .attr("tabindex", "-1")
      // `aria-disabled` goes too, not just the disclosure pair: setDeckHeaderLocked()
      // early-returns on mobile, so a lock written on desktop (no UTub selected)
      // would otherwise stick for the rest of the mobile session — including
      // after a UTub is selected and the decks are perfectly usable.
      .removeAttr("aria-disabled")
      .removeAttr("aria-expanded")
      .removeAttr("aria-controls");
  }
}

/**
 * Inverse of the above, for the desktop breakpoint where the headers really are
 * disclosure controls. `aria-expanded` is re-derived from the live `.collapsed`
 * state rather than assumed, and a locked deck keeps its own
 * `aria-disabled`/`tabindex="-1"` so restoring the tab order cannot silently
 * unlock a deck with no UTub selected.
 *
 * Guarded once here rather than per-write: the two setters below each no-op on
 * mobile, so without this the `aria-controls` write would still land and leave a
 * half-formed disclosure (controls, but no expanded state) if this were ever
 * reached below the breakpoint.
 */
function enableDeckHeaderDisclosureForDesktop(): void {
  if (isMobile()) return;
  for (const deckSelector of LHS_DECKS) {
    const headerSelector = DECK_HEADER_SELECTOR_BY_DECK[deckSelector];
    const deck = $(deckSelector);
    $(headerSelector).attr(
      "aria-controls",
      DECK_CONTENT_ID_BY_DECK[deckSelector],
    );
    setDeckHeaderExpanded({
      headerSelector,
      expanded: !deck.hasClass("collapsed"),
    });
    setDeckHeaderLocked({
      headerSelector,
      locked: deck.hasClass("deck-locked"),
    });
  }
}

function setupCollapsibleLeftDecks() {
  setupUTubHeaderForMaximizeMinimize();
  setupMemberHeaderForMaximizeMinimize();
  setupTagHeaderForMaximizeMinimize();
}

// Expand every collapsed deck. All three branches must run: a Members-collapsed
// state used to short-circuit before the Tag branch, stranding #TagDeck.collapsed
// — which the desktop -> mobile crossing then relocates into the bottom sheet,
// where `.deck.collapsed .content { height: 0 }` renders an empty sheet the user
// cannot reopen (the caret handlers early-return on mobile).
export function resetAllDecksIfCollapsed(): void {
  const caretUTubDeck = $(`${UTUB_DECK_HEADER_SELECTOR} .title-caret`);
  if (caretUTubDeck.hasClass("closed")) {
    caretUTubDeck.removeClass("closed");
    $(UTUB_DECK_CSS_SELECTOR).removeClass("collapsed");
    setDeckHeaderExpanded({
      headerSelector: UTUB_DECK_HEADER_SELECTOR,
      expanded: true,
    });
  }

  const caretMemberDeck = $(`${MEMBER_DECK_HEADER_SELECTOR} .title-caret`);
  if (caretMemberDeck.hasClass("closed")) {
    caretMemberDeck.removeClass("closed");
    $(MEMBER_DECK_CSS_SELECTOR).removeClass("collapsed");
    setDeckHeaderExpanded({
      headerSelector: MEMBER_DECK_HEADER_SELECTOR,
      expanded: true,
    });
    if (!isUTubSelected()) {
      $("#MemberDeck > .sidePanelTitle").addClass("pad-b-0-25rem");
    }
  }

  const caretTagDeck = $(`${UTUB_TAG_DECK_HEADER_SELECTOR} .title-caret`);
  if (caretTagDeck.hasClass("closed")) {
    caretTagDeck.removeClass("closed");
    $(UTUB_TAG_DECK_CSS_SELECTOR).removeClass("collapsed");
    setDeckHeaderExpanded({
      headerSelector: UTUB_TAG_DECK_HEADER_SELECTOR,
      expanded: true,
    });
    if (!isUTubSelected()) {
      $("#TagDeck > .sidePanelTitle").addClass("pad-b-0-25rem");
    }
  }
}

function setupUTubHeaderForMaximizeMinimize() {
  const headerAndCaret = $(UTUB_DECK_HEADER_SELECTOR);
  if (!headerAndCaret.hasClass("clickable"))
    headerAndCaret.addClass("clickable");

  headerAndCaret.offAndOn("click.collapsibleUTubDeck", () => {
    if (isMobile()) return;
    const caret = $(`${UTUB_DECK_HEADER_SELECTOR} .title-caret`);
    const willExpand = caret.hasClass("closed");
    // The 2-collapsed cap would re-expand this deck the moment it collapsed
    // (Members + Tags are already collapsed and locked with no UTub selected),
    // so treat the click as inert rather than running side effects for a
    // collapse that cannot stick.
    if (
      !willExpand &&
      wouldCollapseBeImmediatelyReverted(UTUB_DECK_CSS_SELECTOR)
    )
      return;
    emit({
      event: willExpand ? UI_EVENTS.UI_DECK_EXPAND : UI_EVENTS.UI_DECK_COLLAPSE,
      deck: willExpand ? DECK_EXPAND_DECK.UTUBS : DECK_COLLAPSE_DECK.UTUBS,
    });
    if (willExpand) {
      caret.removeClass("closed");
      $(UTUB_DECK_CSS_SELECTOR).removeClass("collapsed");
      setDeckHeaderExpanded({
        headerSelector: UTUB_DECK_HEADER_SELECTOR,
        expanded: true,
      });
      // Same as the Member/Tag expand branches below: #utubBtnCreate sits in
      // this deck's .button-container, so a nudge anchored to it was skipped
      // while collapsed. Deferred one tick so the class removal has settled.
      setTimeout(() => maybeShowNextTip(), 0);
      return;
    }

    const numDecksAlreadyCollapsed = getNumDecksAlreadyCollapsed();
    caret.addClass("closed");
    $(UTUB_DECK_CSS_SELECTOR).addClass("collapsed");
    setDeckHeaderExpanded({
      headerSelector: UTUB_DECK_HEADER_SELECTOR,
      expanded: false,
    });

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
  const headerAndCaret = $(MEMBER_DECK_HEADER_SELECTOR);
  if (!headerAndCaret.hasClass("clickable"))
    headerAndCaret.addClass("clickable");

  headerAndCaret.offAndOn("click.collapsibleMemberDeck", () => {
    if (isMobile()) return;
    // No UTub selected -> the deck is locked minimized (nothing to show); the
    // header is visually marked non-interactable and clicks are inert.
    if (!isUTubSelected()) return;
    const caret = $(`${MEMBER_DECK_HEADER_SELECTOR} .title-caret`);
    const willExpand = caret.hasClass("closed");
    emit({
      event: willExpand ? UI_EVENTS.UI_DECK_EXPAND : UI_EVENTS.UI_DECK_COLLAPSE,
      deck: willExpand ? DECK_EXPAND_DECK.MEMBERS : DECK_COLLAPSE_DECK.MEMBERS,
    });
    if (willExpand) {
      caret.removeClass("closed");
      $(MEMBER_DECK_CSS_SELECTOR).removeClass("collapsed");
      setDeckHeaderExpanded({
        headerSelector: MEMBER_DECK_HEADER_SELECTOR,
        expanded: true,
      });
      if (!isUTubSelected()) {
        $("#MemberDeck > .sidePanelTitle").addClass("pad-b-0-25rem");
      }
      // A nudge whose anchor sat inside this deck was skipped while collapsed
      // (visibility:hidden). Re-evaluate now the deck is open — deferred one
      // tick so the class removal is committed and the deck's style/layout has
      // settled before isAnchorVisible() reads the anchor. Mirrors nudges.ts's
      // own TAG_SHEET_TOGGLED first deferred tick (its repeat loop is not
      // needed: nothing here animates a position to reposition against).
      setTimeout(() => maybeShowNextTip(), 0);
      return;
    }

    const numDecksAlreadyCollapsed = getNumDecksAlreadyCollapsed();
    caret.addClass("closed");
    $(MEMBER_DECK_CSS_SELECTOR).addClass("collapsed");
    setDeckHeaderExpanded({
      headerSelector: MEMBER_DECK_HEADER_SELECTOR,
      expanded: false,
    });

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
  const headerAndCaret = $(UTUB_TAG_DECK_HEADER_SELECTOR);
  if (!headerAndCaret.hasClass("clickable"))
    headerAndCaret.addClass("clickable");

  headerAndCaret.offAndOn("click.collapsibleUTubTagDeck", () => {
    if (isMobile()) return;
    // No UTub selected -> the deck is locked minimized (nothing to show); the
    // header is visually marked non-interactable and clicks are inert.
    if (!isUTubSelected()) return;
    const caret = $(`${UTUB_TAG_DECK_HEADER_SELECTOR} .title-caret`);
    const willExpand = caret.hasClass("closed");
    emit({
      event: willExpand ? UI_EVENTS.UI_DECK_EXPAND : UI_EVENTS.UI_DECK_COLLAPSE,
      deck: willExpand ? DECK_EXPAND_DECK.TAGS : DECK_COLLAPSE_DECK.TAGS,
    });
    if (willExpand) {
      caret.removeClass("closed");
      $(UTUB_TAG_DECK_CSS_SELECTOR).removeClass("collapsed");
      setDeckHeaderExpanded({
        headerSelector: UTUB_TAG_DECK_HEADER_SELECTOR,
        expanded: true,
      });
      if (!isUTubSelected()) {
        $("#TagDeck > .sidePanelTitle").addClass("pad-b-0-25rem");
      }
      // See the Member-deck expand branch above: deferred one tick so the class
      // removal is committed and the deck has settled before re-evaluating.
      setTimeout(() => maybeShowNextTip(), 0);
      return;
    }

    const numDecksAlreadyCollapsed = getNumDecksAlreadyCollapsed();
    caret.addClass("closed");
    $(UTUB_TAG_DECK_CSS_SELECTOR).addClass("collapsed");
    setDeckHeaderExpanded({
      headerSelector: UTUB_TAG_DECK_HEADER_SELECTOR,
      expanded: false,
    });

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

function findDeckMarkedLastCollapsed(): string | undefined {
  for (let i = 0; i < LHS_DECKS.length; i++) {
    if ($(LHS_DECKS[i]).attr("data-last-collapsed") === "true") {
      return LHS_DECKS[i];
    }
  }
  return undefined;
}

// True when collapsing `deckSelector` would be undone the instant it happened:
// two decks are already collapsed and no deck carries the LRU marker, so the
// cap's fallback below would expand this very deck. Only the UTubs deck can
// reach this — the marker-free 2-collapsed state is Members+Tags minimized by
// minimizeMemberAndTagDecksWhenNoUTub(), whose headers are inert with no UTub
// selected. The caller returns early instead, so a click that cannot stick does
// not still run the collapse side effects (resetUTubSearch() would wipe an
// in-progress UTub filter) or emit a UI_DECK_COLLAPSE that never happened.
function wouldCollapseBeImmediatelyReverted(deckSelector: string): boolean {
  return (
    deckSelector === UTUB_DECK_CSS_SELECTOR &&
    getNumDecksAlreadyCollapsed() >= 2 &&
    findDeckMarkedLastCollapsed() === undefined
  );
}

function ensureOnlyTwoDecksCollapsedAtOnce(): void {
  let deckToExpandSelector = findDeckMarkedLastCollapsed();

  if (!deckToExpandSelector) {
    // No deck carries the LRU marker — the state of every freshly-loaded page,
    // since Jinja seeds data-last-collapsed="false" on all three and only a
    // caret click ever flips one to "true". Returning here would leave all
    // three decks collapsed, so fall back to expanding the UTubs deck: it is
    // the one deck that is never auto-locked, so expanding it always leaves a
    // usable left panel.
    deckToExpandSelector = UTUB_DECK_CSS_SELECTOR;
    log(
      "collapsible decks: no data-last-collapsed marker set, falling back to expanding the UTubs deck",
      {
        deckToExpand: UTUB_DECK_CSS_SELECTOR,
      },
    );
  }
  const deckToExpand = $(deckToExpandSelector);
  deckToExpand.find(".title-caret").first().removeClass("closed");
  deckToExpand.removeClass("collapsed");
  setDeckHeaderExpanded({
    headerSelector: DECK_HEADER_SELECTOR_BY_DECK[deckToExpandSelector],
    expanded: true,
  });
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
  setDeckHeaderExpanded({
    headerSelector: DECK_HEADER_SELECTOR_BY_DECK[deckSelector],
    expanded: !minimized,
  });
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
  // The visual lock above is pointer-only; mirror it for keyboard/SR users.
  setDeckHeaderLocked({
    headerSelector: MEMBER_DECK_HEADER_SELECTOR,
    locked: true,
  });
  setDeckHeaderLocked({
    headerSelector: UTUB_TAG_DECK_HEADER_SELECTOR,
    locked: true,
  });
}

// Restore the Member + Tag decks when a UTub is selected.
function restoreMemberAndTagDecksForUTub(): void {
  $(MEMBER_DECK_CSS_SELECTOR).removeClass("deck-locked");
  $(UTUB_TAG_DECK_CSS_SELECTOR).removeClass("deck-locked");
  setDeckHeaderLocked({
    headerSelector: MEMBER_DECK_HEADER_SELECTOR,
    locked: false,
  });
  setDeckHeaderLocked({
    headerSelector: UTUB_TAG_DECK_HEADER_SELECTOR,
    locked: false,
  });
  setDeckMinimized(MEMBER_DECK_CSS_SELECTOR, false);
  setDeckMinimized(UTUB_TAG_DECK_CSS_SELECTOR, false);
}

on(AppEvents.UTUB_SELECTED, restoreMemberAndTagDecksForUTub);
