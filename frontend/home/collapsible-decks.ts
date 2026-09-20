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
import { getState } from "../store/app-store.js";
import { collapsedTagFilterAnnouncement } from "./tags/utils.js";
import {
  getDeckLayout,
  PERSISTABLE_DECK,
  setDeckMinimizedPreference,
} from "./deck-layout-storage.js";
import type { DeckLayout } from "./deck-layout-storage.js";
import {
  DECK_COLLAPSE_DECK,
  DECK_EXPAND_DECK,
} from "../types/metrics-dim-values.js";
import { debug } from "../lib/debug.js";

const log = debug("home-shell");

// Locally-derived alias for the closed set of persistable decks —
// `deck-layout-storage.ts` keeps its own copy file-local, so this mirrors the
// consumer-side derivation left-panel-toggle.ts and tags/sheet.ts already use.
type PersistableDeck = (typeof PERSISTABLE_DECK)[keyof typeof PERSISTABLE_DECK];

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
const COLLAPSED_TAG_FILTER_ANNOUNCEMENT_SELECTOR =
  "#TagDeckCollapsedFilterAnnouncement";

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

/**
 * Persist one deck's collapsed state as the user's standing preference.
 *
 * Every write funnels through here so the `!isMobile()` guard lives on the
 * write path itself rather than being re-derived at each call site.
 * `isMobile()` is a live viewport-width read: a desktop user who narrows the
 * window crosses into the mobile layout, which force-expands the decks — that
 * layout-driven expand must never be written back as a chosen preference.
 *
 * Only the Member and Tag decks are ever persisted (Design Decision 1): a
 * persisted UTubs collapse would compose with the no-UTub auto-lock into an
 * all-inert left panel.
 *
 * @param deck - which persistable deck the preference is for.
 * @param minimized - `true` when the deck ends up collapsed, `false` expanded.
 */
function persistDeckMinimized({
  deck,
  minimized,
}: {
  deck: PersistableDeck;
  minimized: boolean;
}): void {
  if (isMobile()) return;
  setDeckMinimizedPreference({ deck, minimized });
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
      clearLastCollapsed(UTUB_DECK_CSS_SELECTOR);
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
      persistDeckMinimized({
        deck: PERSISTABLE_DECK.MEMBERS,
        minimized: false,
      });
      clearLastCollapsed(MEMBER_DECK_CSS_SELECTOR);
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

    // Written BEFORE the 2-collapsed cap runs, deliberately: the cap can evict
    // this very deck (it expands whichever deck carries the stale
    // data-last-collapsed marker, which a programmatic minimize/restore cycle
    // can leave pointing at an expanded Member deck). Persisting first lets the
    // cap's own `minimized: false` write land last and win, so storage always
    // ends up matching the deck's final on-screen state.
    persistDeckMinimized({ deck: PERSISTABLE_DECK.MEMBERS, minimized: true });

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
      persistDeckMinimized({ deck: PERSISTABLE_DECK.TAGS, minimized: false });
      clearLastCollapsed(UTUB_TAG_DECK_CSS_SELECTOR);
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

    // [DD-19] Announce the standing filter state at the moment of collapse.
    // The collapse click emits no TAG_FILTER_CHANGED, so without this write a
    // user who collapses an already-filtered deck hears nothing about the
    // filters the deck just hid until they next change one.
    $(COLLAPSED_TAG_FILTER_ANNOUNCEMENT_SELECTOR).text(
      collapsedTagFilterAnnouncement(getState().selectedTagIDs.length),
    );

    // Before the cap, for the same reason as the Member collapse branch above:
    // an eviction that re-expands this deck must be the last write to land.
    persistDeckMinimized({ deck: PERSISTABLE_DECK.TAGS, minimized: true });

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

/**
 * The deck the LRU marker names, or `undefined` when no LIVE marker exists.
 *
 * A marker on a deck that is NOT currently `.collapsed` is stale and treated as
 * absent: it describes a collapse that has since been undone, so trusting it
 * would make the cap "evict" an already-expanded deck — including, in the
 * reachable no-UTub sequence, the very deck the user just clicked. Every expand
 * path clears its own marker (clearLastCollapsed), so this check is the
 * belt-and-braces half: a future expand path that forgets to clear leaves a
 * harmless marker rather than a mis-directed eviction.
 */
function findDeckMarkedLastCollapsed(): string | undefined {
  for (let i = 0; i < LHS_DECKS.length; i++) {
    const deck = $(LHS_DECKS[i]);
    if (
      deck.attr("data-last-collapsed") === "true" &&
      deck.hasClass("collapsed")
    ) {
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

  // The eviction is the user's effective layout from here on, so persist it
  // like any other expand — otherwise the next UTub selection would restore the
  // deck the cap just forced open back to collapsed. Handled inside this
  // function so no call site has to care which deck was evicted. The UTubs deck
  // is never persisted (Design Decision 1), so the fallback case writes nothing.
  if (deckToExpandSelector === MEMBER_DECK_CSS_SELECTOR) {
    persistDeckMinimized({ deck: PERSISTABLE_DECK.MEMBERS, minimized: false });
  } else if (deckToExpandSelector === UTUB_TAG_DECK_CSS_SELECTOR) {
    persistDeckMinimized({ deck: PERSISTABLE_DECK.TAGS, minimized: false });
  }

  // An eviction opens a deck just like a caret click does, so a nudge whose
  // anchor sat inside it has to be re-evaluated too. Deferred one tick for the
  // same reason as the expand branches (the visibility/opacity transition is
  // still in flight in this task). Fired for ALL three outcomes, including the
  // UTubs fallback: NUDGE_REGISTRY anchors a tip in every deck (#utubBtnCreate,
  // #memberBtnCreate, #utubTagBtnCreate), not only the two persistable ones.
  setTimeout(() => maybeShowNextTip(), 0);
}

/**
 * Drop the LRU marker from a deck that is being expanded.
 *
 * Called from every expand path — the three caret branches and the programmatic
 * setDeckMinimized({ minimized: false }) — so the marker can never outlive the
 * collapse it described. Without it, "collapse X, expand X, let something else
 * collapse two decks programmatically" leaves X marked while expanded, and the
 * next cap firing re-expands X instead of evicting a genuinely collapsed deck.
 *
 * Only the expanding deck is touched: any other deck's marker is still valid if
 * that deck is collapsed, and findDeckMarkedLastCollapsed() discards it if not.
 */
function clearLastCollapsed(expandingDeck: string): void {
  $(expandingDeck).attr("data-last-collapsed", "false");
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

/**
 * Collapse or expand a deck programmatically (no user click involved), so it
 * deliberately emits no metric and writes no preference — the callers are the
 * app-forced no-UTub minimize and the persisted-layout restore.
 *
 * @param deckSelector - the `.deck#<X>` selector of the deck to toggle.
 * @param minimized - `true` to collapse the deck, `false` to expand it.
 */
function setDeckMinimized({
  deckSelector,
  minimized,
}: {
  deckSelector: string;
  minimized: boolean;
}): void {
  const deck = $(deckSelector);
  const headerSelector = DECK_HEADER_SELECTOR_BY_DECK[deckSelector];
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
  if (minimized) {
    // Mirror the click-collapse path (:394 / :461), which strips this class so
    // a collapsed header band carries no expanded-state padding. Nothing
    // stripped it on the programmatic path, so a deck collapsed here (the
    // no-UTub minimize, or a restored-collapsed layout) ended up in a different
    // DOM state than the identical deck collapsed by a caret click.
    //
    // DOM-state bookkeeping, not a visual change: decks.css:207-211 sets
    // `padding-block: 0` on `#MemberDeck/#TagDeck .titleElement:first-child`,
    // an id selector that outranks this single class, so the pad it names is
    // already suppressed on both decks this function is ever called with. Kept
    // in sync anyway so the two collapse paths cannot diverge if that override
    // is ever scoped or removed.
    //
    // No symmetric re-add on expand, deliberately: the class belongs to the
    // NO-UTub state. init.ts:37 adds it from setUIWhenNoUTubSelected(), and the
    // only re-adds (resetAllDecksIfCollapsed, the caret expand branches) are all
    // guarded on `!isUTubSelected()`. Re-adding it here would put it back in the
    // UTub-selected state, where nothing puts it today.
    $(`${deckSelector} > .sidePanelTitle`).removeClass("pad-b-0-25rem");
    rescueFocusFromCollapsedDeck({ deckElement, headerSelector });
  } else {
    clearLastCollapsed(deckSelector);
  }
  setDeckHeaderExpanded({
    headerSelector,
    expanded: !minimized,
  });
}

/**
 * Keep focus inside the page when a deck is collapsed out from under it.
 *
 * A collapsed deck's `.content` / `.button-container` are `visibility: hidden`
 * (decks.css), which prunes any focused descendant from the focus tree and
 * drops `document.activeElement` to `<body>` — a WCAG 2.4.3 focus-order break
 * with no visible indicator and nothing to Shift+Tab back to.
 *
 * The caret-click path is already safe: focus sits on the header button, which
 * lives in `.titleElement:first-child` and is never hidden. Every PROGRAMMATIC
 * collapse can fire while focus is inside the deck, though, because none of
 * them is initiated from within it — `minimizeMemberAndTagDecksWhenNoUTub()`
 * (Back to /home leaves focus wherever it was), the persisted-layout restore on
 * a history-nav UTub selection, and the mobile->desktop crossing, which
 * re-collapses a deck `resetAllDecksIfCollapsed()` had expanded.
 *
 * Retargeting to that deck's own header button mirrors the contract
 * `closeTagSheet({ returnFocus })` already uses: when a region goes away, hand
 * focus to the control that owns it. Only fires when focus is genuinely inside
 * the deck (and not already on its header), so it can never steal focus from
 * elsewhere on the page — at init, `document.activeElement` is `<body>`, which
 * no deck contains.
 */
function rescueFocusFromCollapsedDeck({
  deckElement,
  headerSelector,
}: {
  deckElement: HTMLElement | undefined;
  headerSelector: string;
}): void {
  if (!deckElement) return;
  const activeElement = document.activeElement;
  if (!(activeElement instanceof HTMLElement)) return;
  if (activeElement === $(headerSelector).get(0)) return;
  if (!deckElement.contains(activeElement)) return;
  $(headerSelector).trigger("focus");
}

// Minimize the Member + Tag decks when no UTub is selected (they have nothing to
// show) so the UTubs list gets the room. Desktop only — the decks are not
// collapsible on mobile (single-deck nav).
export function minimizeMemberAndTagDecksWhenNoUTub(): void {
  if (isMobile()) return;
  setDeckMinimized({ deckSelector: MEMBER_DECK_CSS_SELECTOR, minimized: true });
  setDeckMinimized({
    deckSelector: UTUB_TAG_DECK_CSS_SELECTOR,
    minimized: true,
  });
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

/**
 * Give the 2-collapsed LRU an anchor after a restore.
 *
 * Without this, a restored-collapsed deck leaves every deck at the Jinja
 * default `data-last-collapsed="false"`, so the next collapse that trips the
 * cap hits ensureOnlyTwoDecksCollapsedAtOnce()'s marker-free UTubs fallback
 * instead of evicting the deck the user actually left shut.
 *
 * Nothing is seeded when neither deck was restored collapsed: reaching the cap
 * from there takes two further user collapses, and each one writes the marker
 * itself, so a stale marker can never be the value the cap reads.
 *
 * @param membersMinimized - whether the Member deck was restored collapsed.
 * @param tagsMinimized - whether the Tag deck was restored collapsed.
 */
function seedLastCollapsedFromRestoredLayout({
  membersMinimized,
  tagsMinimized,
}: DeckLayout): void {
  if (!membersMinimized && !tagsMinimized) return;
  // Whichever single deck came back collapsed is the anchor; when BOTH did, the
  // Tag deck wins because it is the later-restored of the two, so it stands in
  // as the most-recently-collapsed and the next user collapse evicts it.
  setLastCollapsed(
    tagsMinimized ? UTUB_TAG_DECK_CSS_SELECTOR : MEMBER_DECK_CSS_SELECTOR,
  );
}

/**
 * Apply the user's saved Member/Tag layout to the left panel, instead of
 * force-expanding both decks and erasing the choice.
 *
 * Exported because two callers need it: the UTUB_SELECTED subscriber below, and
 * mobile.ts's crossing back to desktop — the mobile viewport resets both decks
 * expanded (`resetAllDecksIfCollapsed`), so without re-applying here a user who
 * narrows and re-widens the window loses the layout they saved.
 *
 * Deliberately emits NO metric (Design Decision 6): UI_DECK_COLLAPSE /
 * UI_DECK_EXPAND mean "a user clicked a caret", and emitting here would inflate
 * them on every UTub switch and could swallow a genuine click via the metrics
 * dedupe map.
 *
 * It also runs none of the deck-reset side effects a caret collapse runs
 * (closeMemberNameFilter / closeTagNameFilter / createMemberHideInput /
 * createUTubTagHideInput), for a different reason per caller. On the
 * UTUB_SELECTED path it is required: setMemberDeckOnUTubSelected and
 * setTagDeckOnUTubSelected are subscribed AFTER this and already do exactly
 * that — a duplicate createMemberHideInput would clear the co-member candidate
 * cache. On the viewport-crossing path nothing else resets them, and that is
 * deliberate too: a resize is not a UTub switch, so an in-progress member/tag
 * name filter is preserved across it rather than silently wiped.
 */
export function applyPersistedDeckLayout(): void {
  // Below the tablet breakpoint the decks are not collapsible at all (single-
  // deck nav, and the Tag deck is relocated into the bottom sheet), so there is
  // no saved layout to apply — and applying one would strand a sheet the user
  // cannot reopen. mobile.ts re-applies it on the crossing back to desktop.
  if (isMobile()) return;

  // With no UTub selected both decks are already collapsed AND `.deck-locked`
  // by minimizeMemberAndTagDecksWhenNoUTub(). Applying a saved-expanded value
  // here would open an inert deck whose caret is hidden, so the user could not
  // shut it again. The next UTub selection applies the layout anyway.
  if (!isUTubSelected()) return;

  const layout = getDeckLayout();
  setDeckMinimized({
    deckSelector: MEMBER_DECK_CSS_SELECTOR,
    minimized: layout.membersMinimized,
  });
  setDeckMinimized({
    deckSelector: UTUB_TAG_DECK_CSS_SELECTOR,
    minimized: layout.tagsMinimized,
  });

  seedLastCollapsedFromRestoredLayout(layout);

  // The saved layout composes with a deck this path never touches: a user who
  // left the UTubs deck collapsed and both persisted decks collapsed would land
  // on three header-only decks. Expand the UTubs deck — the one deck that is
  // never persisted, so re-opening it discards no saved intent.
  if (getNumDecksAlreadyCollapsed() >= 3) {
    setDeckMinimized({
      deckSelector: UTUB_DECK_CSS_SELECTOR,
      minimized: false,
    });
    log(
      "collapsible decks: restored layout would collapse all three decks, forcing the UTubs deck open",
      {
        membersMinimized: layout.membersMinimized,
        tagsMinimized: layout.tagsMinimized,
      },
    );
  }
}

/**
 * Unlock the Member and Tag decks for the newly-selected UTub, then hand off to
 * applyPersistedDeckLayout() for the layout itself.
 *
 * The unlock is unconditional and runs ahead of the handoff (whose own guards
 * early-return on mobile and with no UTub selected): the lock is what makes
 * these decks inert with no UTub selected, so a selection must always clear it
 * (test_member_and_tag_decks_unlocked_when_utub_selected asserts this).
 */
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

  applyPersistedDeckLayout();
}

on(AppEvents.UTUB_SELECTED, restoreMemberAndTagDecksForUTub);
