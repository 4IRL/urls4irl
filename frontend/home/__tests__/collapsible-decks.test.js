import {
  initCollapsibleDecks,
  addCollapsibleClickableHeaderClass,
  removeCollapsibleClickableHeaderClass,
  resetAllDecksIfCollapsed,
} from "../collapsible-decks.js";

vi.mock("../mobile.js", () => ({ isMobile: vi.fn(() => false) }));
vi.mock("../utubs/utils.js", () => ({ isUTubSelected: vi.fn(() => false) }));
vi.mock("../utubs/search.js", () => ({
  closeUTubSearchAndEraseInput: vi.fn(),
}));
vi.mock("../utubs/create.js", () => ({ createUTubHideInput: vi.fn() }));
vi.mock("../members/create.js", () => ({ createMemberHideInput: vi.fn() }));
vi.mock("../tags/create.js", () => ({ createUTubTagHideInput: vi.fn() }));

const $ = window.jQuery;

const DECK_HTML = `
  <div class="deck" id="UTubDeck">
    <div id="UTubDeckHeaderAndCaret">
      <span class="title-caret"></span>
    </div>
  </div>
  <div class="deck" id="MemberDeck">
    <div id="MemberDeckHeaderAndCaret">
      <span class="title-caret"></span>
    </div>
  </div>
  <div class="deck" id="TagDeck">
    <div id="TagDeckHeaderAndCaret">
      <span class="title-caret"></span>
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
  });

  describe("two-deck maximum enforcement", () => {
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
  });
});
