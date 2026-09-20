import {
  initCollapsibleDecks,
  addCollapsibleClickableHeaderClass,
  removeCollapsibleClickableHeaderClass,
  minimizeMemberAndTagDecksWhenNoUTub,
  resetAllDecksIfCollapsed,
} from "../collapsible-decks.js";

vi.mock("../mobile.js", () => ({ isMobile: vi.fn(() => false) }));
vi.mock("../utubs/utils.js", () => ({ isUTubSelected: vi.fn(() => false) }));
vi.mock("../utubs/search.js", () => ({
  resetUTubSearch: vi.fn(),
}));
vi.mock("../utubs/create.js", () => ({ createUTubHideInput: vi.fn() }));
vi.mock("../members/create.js", () => ({ createMemberHideInput: vi.fn() }));
vi.mock("../members/search.js", () => ({ closeMemberNameFilter: vi.fn() }));
vi.mock("../tags/create.js", () => ({ createUTubTagHideInput: vi.fn() }));
vi.mock("../tags/search.js", () => ({ closeTagNameFilter: vi.fn() }));
vi.mock("../onboarding/nudges.js", () => ({ maybeShowNextTip: vi.fn() }));

const $ = window.jQuery;

// data-last-collapsed="false" mirrors the Jinja default every deck is rendered
// with (UTubDeck.html:1, MemberDeck.html:1, TagsDeck.html:1); the Member/Tag
// `.sidePanelTitle.pad-b-0-25rem` wrappers mirror MemberDeckHeaders.html:1 and
// TagsDeck.html:2, which the collapse/reset paths add and remove that class on.
const DECK_HTML = `
  <div class="deck" id="UTubDeck" data-last-collapsed="false">
    <div id="UTubDeckHeaderAndCaret">
      <span class="title-caret"></span>
    </div>
    <div id="SearchUTubWrap"></div>
  </div>
  <div class="deck" id="MemberDeck" data-last-collapsed="false">
    <div class="titleElement sidePanelTitle pad-b-0-25rem">
      <div id="MemberDeckHeaderAndCaret">
        <span class="title-caret"></span>
      </div>
    </div>
  </div>
  <div class="deck" id="TagDeck" data-last-collapsed="false">
    <div class="titleElement sidePanelTitle pad-b-0-25rem">
      <div id="TagDeckHeaderAndCaret">
        <span class="title-caret"></span>
      </div>
    </div>
  </div>
`;

describe("Collapsible Decks", () => {
  beforeEach(() => {
    document.body.innerHTML = DECK_HTML;
    initCollapsibleDecks();
  });

  describe("addCollapsibleClickableHeaderClass", () => {
    it("adds clickable class to all 3 deck headers", () => {
      removeCollapsibleClickableHeaderClass();
      addCollapsibleClickableHeaderClass();
      expect($("#UTubDeckHeaderAndCaret").hasClass("clickable")).toBe(true);
      expect($("#MemberDeckHeaderAndCaret").hasClass("clickable")).toBe(true);
      expect($("#TagDeckHeaderAndCaret").hasClass("clickable")).toBe(true);
    });
  });

  describe("removeCollapsibleClickableHeaderClass", () => {
    it("removes clickable class from all 3 deck headers", () => {
      removeCollapsibleClickableHeaderClass();
      expect($("#UTubDeckHeaderAndCaret").hasClass("clickable")).toBe(false);
      expect($("#MemberDeckHeaderAndCaret").hasClass("clickable")).toBe(false);
      expect($("#TagDeckHeaderAndCaret").hasClass("clickable")).toBe(false);
    });
  });

  describe("single deck collapse and expand", () => {
    it("clicking #UTubDeckHeaderAndCaret collapses the UTub deck and closes caret", () => {
      $("#UTubDeckHeaderAndCaret").trigger("click");
      expect($(".deck#UTubDeck").hasClass("collapsed")).toBe(true);
      expect($("#UTubDeckHeaderAndCaret .title-caret").hasClass("closed")).toBe(
        true,
      );
    });

    it("clicking #UTubDeckHeaderAndCaret again expands the deck", () => {
      $("#UTubDeckHeaderAndCaret").trigger("click");
      $("#UTubDeckHeaderAndCaret").trigger("click");
      expect($(".deck#UTubDeck").hasClass("collapsed")).toBe(false);
      expect($("#UTubDeckHeaderAndCaret .title-caret").hasClass("closed")).toBe(
        false,
      );
    });

    it("collapsing the UTub deck does not hide #SearchUTubWrap", () => {
      expect($("#SearchUTubWrap").hasClass("hidden")).toBe(false);
      $("#UTubDeckHeaderAndCaret").trigger("click");
      expect($(".deck#UTubDeck").hasClass("collapsed")).toBe(true);
      expect($("#SearchUTubWrap").hasClass("hidden")).toBe(false);
    });
  });

  describe("resetAllDecksIfCollapsed", () => {
    it("removes collapsed and closed classes from a collapsed UTub deck", () => {
      $(".deck#UTubDeck").addClass("collapsed");
      $("#UTubDeckHeaderAndCaret .title-caret").addClass("closed");

      resetAllDecksIfCollapsed();

      expect($(".deck#UTubDeck").hasClass("collapsed")).toBe(false);
      expect($("#UTubDeckHeaderAndCaret .title-caret").hasClass("closed")).toBe(
        false,
      );
    });

    it("is a no-op when no deck is collapsed", () => {
      resetAllDecksIfCollapsed();
      expect($(".deck#UTubDeck").hasClass("collapsed")).toBe(false);
      expect($(".deck#MemberDeck").hasClass("collapsed")).toBe(false);
      expect($(".deck#TagDeck").hasClass("collapsed")).toBe(false);
    });

    // The Member branch used to `return` before the Tag branch ever ran, so a
    // Members-collapsed state stranded #TagDeck.collapsed — which the desktop ->
    // mobile crossing then relocates into the bottom sheet as an empty, unopenable
    // panel.
    it("expands all three decks, including the Tag deck the Member branch used to short-circuit past", () => {
      const deckSelectors = [
        ".deck#UTubDeck",
        ".deck#MemberDeck",
        ".deck#TagDeck",
      ];
      const caretSelectors = [
        "#UTubDeckHeaderAndCaret .title-caret",
        "#MemberDeckHeaderAndCaret .title-caret",
        "#TagDeckHeaderAndCaret .title-caret",
      ];
      deckSelectors.forEach((deckSelector) =>
        $(deckSelector).addClass("collapsed"),
      );
      caretSelectors.forEach((caretSelector) =>
        $(caretSelector).addClass("closed"),
      );

      resetAllDecksIfCollapsed();

      deckSelectors.forEach((deckSelector) =>
        expect($(deckSelector).hasClass("collapsed")).toBe(false),
      );
      caretSelectors.forEach((caretSelector) =>
        expect($(caretSelector).hasClass("closed")).toBe(false),
      );
    });

    // isUTubSelected() is false by default in this spec, so both guarded
    // pad-b-0-25rem re-adds fire — the Tag one only became reachable once the
    // Member branch stopped returning.
    it("re-adds pad-b-0-25rem to both the Member and Tag titles when no UTub is selected", () => {
      const titleSelectors = [
        "#MemberDeck > .sidePanelTitle",
        "#TagDeck > .sidePanelTitle",
      ];
      $(".deck#MemberDeck").addClass("collapsed");
      $("#MemberDeckHeaderAndCaret .title-caret").addClass("closed");
      $(".deck#TagDeck").addClass("collapsed");
      $("#TagDeckHeaderAndCaret .title-caret").addClass("closed");
      // The collapse handlers strip this class; the reset path restores it.
      titleSelectors.forEach((titleSelector) =>
        $(titleSelector).removeClass("pad-b-0-25rem"),
      );

      resetAllDecksIfCollapsed();

      titleSelectors.forEach((titleSelector) =>
        expect($(titleSelector).hasClass("pad-b-0-25rem")).toBe(true),
      );
    });
  });

  describe("tag filter close on collapse", () => {
    // Collapsing the Tag deck requires a selected UTub (otherwise the header is
    // inert and the collapse branch never runs).
    beforeEach(async () => {
      const { isUTubSelected } = await import("../utubs/utils.js");
      (isUTubSelected as ReturnType<typeof vi.fn>).mockReturnValue(true);
      vi.clearAllMocks();
    });

    it("collapsing the Tag deck closes the tag name filter", async () => {
      const { closeTagNameFilter } = await import("../tags/search.js");

      $("#TagDeckHeaderAndCaret").trigger("click");

      expect($(".deck#TagDeck").hasClass("collapsed")).toBe(true);
      expect(closeTagNameFilter).toHaveBeenCalledTimes(1);
    });

    it("expanding the Tag deck does not close the tag name filter", async () => {
      const { closeTagNameFilter } = await import("../tags/search.js");

      // Collapse first, then clear mocks so only the expand call is observed.
      $("#TagDeckHeaderAndCaret").trigger("click");
      vi.clearAllMocks();

      $("#TagDeckHeaderAndCaret").trigger("click");

      expect($(".deck#TagDeck").hasClass("collapsed")).toBe(false);
      expect(closeTagNameFilter).not.toHaveBeenCalled();
    });
  });

  describe("member filter close on collapse", () => {
    // Collapsing the Member deck requires a selected UTub (otherwise the header
    // is inert and the collapse branch never runs).
    beforeEach(async () => {
      const { isUTubSelected } = await import("../utubs/utils.js");
      (isUTubSelected as ReturnType<typeof vi.fn>).mockReturnValue(true);
      vi.clearAllMocks();
    });

    it("collapsing the Member deck closes the member name filter", async () => {
      const { closeMemberNameFilter } = await import("../members/search.js");

      $("#MemberDeckHeaderAndCaret").trigger("click");

      expect($(".deck#MemberDeck").hasClass("collapsed")).toBe(true);
      expect(closeMemberNameFilter).toHaveBeenCalledTimes(1);
    });

    it("expanding the Member deck does not close the member name filter", async () => {
      const { closeMemberNameFilter } = await import("../members/search.js");

      // Collapse first, then clear mocks so only the expand call is observed.
      $("#MemberDeckHeaderAndCaret").trigger("click");
      vi.clearAllMocks();

      $("#MemberDeckHeaderAndCaret").trigger("click");

      expect($(".deck#MemberDeck").hasClass("collapsed")).toBe(false);
      expect(closeMemberNameFilter).not.toHaveBeenCalled();
    });
  });

  describe("two-deck maximum enforcement", () => {
    // Collapsing the Member/Tag decks requires a selected UTub (otherwise they
    // are locked minimized and their headers are inert).
    beforeEach(async () => {
      const { isUTubSelected } = await import("../utubs/utils.js");
      (isUTubSelected as ReturnType<typeof vi.fn>).mockReturnValue(true);
    });

    it("auto-expands the most-recently collapsed deck when a third is collapsed", () => {
      // 1st collapse: UTub (data-last-collapsed=true)
      $("#UTubDeckHeaderAndCaret").trigger("click");
      // 2nd collapse: Member (data-last-collapsed=true, UTub=false)
      $("#MemberDeckHeaderAndCaret").trigger("click");
      // 3rd collapse: Tag triggers auto-expand of Member (most recently collapsed)
      $("#TagDeckHeaderAndCaret").trigger("click");

      expect($(".deck#UTubDeck").hasClass("collapsed")).toBe(true);
      expect($(".deck#MemberDeck").hasClass("collapsed")).toBe(false);
      expect($(".deck#TagDeck").hasClass("collapsed")).toBe(true);
    });

    // No deck carries data-last-collapsed="true" on a freshly-loaded page —
    // Jinja seeds "false" on all three and only a caret click ever flips one to
    // "true". Collapsing a third deck from that state must still evict one, and
    // the UTubs deck is the deterministic choice: it is the only deck that is
    // never auto-locked, so expanding it always leaves a usable left panel.
    //
    // The production route into that marker-free pair is the no-UTub state, where
    // minimizeMemberAndTagDecksWhenNoUTub() collapses and locks Members + Tags
    // without ever writing a marker. Collapsing the UTubs deck there would be
    // reverted by the cap immediately, so the click is inert instead — it must
    // not wipe the UTub search on a collapse that cannot stick.
    it("makes the UTubs caret click inert when Members and Tags are locked collapsed with no UTub selected", async () => {
      const { isUTubSelected } = await import("../utubs/utils.js");
      const { resetUTubSearch } = await import("../utubs/search.js");
      (isUTubSelected as ReturnType<typeof vi.fn>).mockReturnValue(false);
      minimizeMemberAndTagDecksWhenNoUTub();
      vi.clearAllMocks();

      $("#UTubDeckHeaderAndCaret").trigger("click");

      expect($(".deck#UTubDeck").hasClass("collapsed")).toBe(false);
      expect($("#UTubDeckHeaderAndCaret .title-caret").hasClass("closed")).toBe(
        false,
      );
      expect($(".deck#MemberDeck").hasClass("collapsed")).toBe(true);
      expect($(".deck#TagDeck").hasClass("collapsed")).toBe(true);
      expect(resetUTubSearch).not.toHaveBeenCalled();
    });

    it("expands the UTubs deck when the Tag deck is collapsed third with no data-last-collapsed marker", () => {
      $(".deck#UTubDeck").addClass("collapsed");
      $("#UTubDeckHeaderAndCaret .title-caret").addClass("closed");
      $(".deck#MemberDeck").addClass("collapsed");
      $("#MemberDeckHeaderAndCaret .title-caret").addClass("closed");

      $("#TagDeckHeaderAndCaret").trigger("click");

      expect($(".deck#UTubDeck").hasClass("collapsed")).toBe(false);
      expect($("#UTubDeckHeaderAndCaret .title-caret").hasClass("closed")).toBe(
        false,
      );
      expect($(".deck#MemberDeck").hasClass("collapsed")).toBe(true);
      expect($(".deck#TagDeck").hasClass("collapsed")).toBe(true);
    });
  });

  describe("onboarding nudge re-evaluation on expand", () => {
    // Expanding a Member/Tag deck re-evaluates the onboarding nudges, so a tip
    // whose anchor was hidden inside the collapsed deck can finally show. The
    // call is deferred one tick (the visibility transition is still in flight in
    // the click's own task), so fake timers make it deterministic.
    beforeEach(async () => {
      const { isUTubSelected } = await import("../utubs/utils.js");
      (isUTubSelected as ReturnType<typeof vi.fn>).mockReturnValue(true);
      vi.useFakeTimers();
      vi.clearAllMocks();
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("expanding the Member deck re-evaluates the onboarding nudges on the next tick", async () => {
      const { maybeShowNextTip } = await import("../onboarding/nudges.js");

      // Collapse first, then clear mocks so only the expand call is observed.
      $("#MemberDeckHeaderAndCaret").trigger("click");
      vi.runAllTimers();
      vi.clearAllMocks();

      $("#MemberDeckHeaderAndCaret").trigger("click");
      vi.runAllTimers();

      expect($(".deck#MemberDeck").hasClass("collapsed")).toBe(false);
      expect(maybeShowNextTip).toHaveBeenCalledTimes(1);
    });

    it("expanding the Tag deck re-evaluates the onboarding nudges on the next tick", async () => {
      const { maybeShowNextTip } = await import("../onboarding/nudges.js");

      $("#TagDeckHeaderAndCaret").trigger("click");
      vi.runAllTimers();
      vi.clearAllMocks();

      $("#TagDeckHeaderAndCaret").trigger("click");
      vi.runAllTimers();

      expect($(".deck#TagDeck").hasClass("collapsed")).toBe(false);
      expect(maybeShowNextTip).toHaveBeenCalledTimes(1);
    });

    it("collapsing the Member or Tag deck queues no nudge re-evaluation", async () => {
      const { maybeShowNextTip } = await import("../onboarding/nudges.js");

      $("#MemberDeckHeaderAndCaret").trigger("click");
      $("#TagDeckHeaderAndCaret").trigger("click");
      // Run the timers through to prove no deferred call was ever queued, not
      // just that none has fired yet.
      vi.runAllTimers();

      expect($(".deck#MemberDeck").hasClass("collapsed")).toBe(true);
      expect($(".deck#TagDeck").hasClass("collapsed")).toBe(true);
      expect(maybeShowNextTip).not.toHaveBeenCalled();
    });
  });
});
