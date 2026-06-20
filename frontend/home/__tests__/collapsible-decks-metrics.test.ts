import { UI_EVENTS } from "../../types/metrics-events.js";
import { initCollapsibleDecks } from "../collapsible-decks.js";
import {
  DECK_COLLAPSE_DECK,
  DECK_EXPAND_DECK,
} from "../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../mobile.js", () => ({ isMobile: vi.fn(() => false) }));
vi.mock("../utubs/utils.js", () => ({ isUTubSelected: vi.fn(() => false) }));
vi.mock("../utubs/search.js", () => ({ resetUTubSearch: vi.fn() }));
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

describe("collapsible-decks metrics emitters", () => {
  beforeEach(async () => {
    document.body.innerHTML = DECK_HTML;
    vi.clearAllMocks();
    const { isMobile } = await import("../mobile.js");
    (isMobile as ReturnType<typeof vi.fn>).mockReturnValue(false);
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  describe("UTub deck", () => {
    it("emits ui_deck_collapse with deck=utubs on first click (expanded -> collapsed)", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initCollapsibleDecks();

      $("#UTubDeckHeaderAndCaret").trigger("click");

      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_DECK_COLLAPSE,
        deck: DECK_COLLAPSE_DECK.UTUBS,
      });
    });

    it("emits ui_deck_expand with deck=utubs on second click (collapsed -> expanded)", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initCollapsibleDecks();

      $("#UTubDeckHeaderAndCaret").trigger("click");
      $("#UTubDeckHeaderAndCaret").trigger("click");

      expect(emit).toHaveBeenCalledTimes(2);
      expect(emit).toHaveBeenNthCalledWith(1, {
        event: UI_EVENTS.UI_DECK_COLLAPSE,
        deck: DECK_COLLAPSE_DECK.UTUBS,
      });
      expect(emit).toHaveBeenNthCalledWith(2, {
        event: UI_EVENTS.UI_DECK_EXPAND,
        deck: DECK_EXPAND_DECK.UTUBS,
      });
    });

    it("does not emit on mobile (isMobile()=true short-circuits the handler)", async () => {
      const { isMobile } = await import("../mobile.js");
      const { emit } = await import("../../lib/metrics-client.js");
      initCollapsibleDecks();
      (isMobile as ReturnType<typeof vi.fn>).mockReturnValue(true);

      $("#UTubDeckHeaderAndCaret").trigger("click");

      expect(emit).not.toHaveBeenCalled();
    });
  });

  describe("Member deck", () => {
    // The Member deck is only collapsible while a UTub is selected (otherwise it
    // is locked minimized), so the collapse/expand handler guards on
    // isUTubSelected(). Simulate an open UTub for these gestures.
    beforeEach(async () => {
      const { isUTubSelected } = await import("../utubs/utils.js");
      (isUTubSelected as ReturnType<typeof vi.fn>).mockReturnValue(true);
    });

    it("emits ui_deck_collapse with deck=members on first click", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initCollapsibleDecks();

      $("#MemberDeckHeaderAndCaret").trigger("click");

      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_DECK_COLLAPSE,
        deck: DECK_COLLAPSE_DECK.MEMBERS,
      });
    });

    it("emits ui_deck_expand with deck=members on second click", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initCollapsibleDecks();

      $("#MemberDeckHeaderAndCaret").trigger("click");
      $("#MemberDeckHeaderAndCaret").trigger("click");

      expect(emit).toHaveBeenNthCalledWith(2, {
        event: UI_EVENTS.UI_DECK_EXPAND,
        deck: DECK_EXPAND_DECK.MEMBERS,
      });
    });

    it("does not emit on mobile", async () => {
      const { isMobile } = await import("../mobile.js");
      const { emit } = await import("../../lib/metrics-client.js");
      initCollapsibleDecks();
      (isMobile as ReturnType<typeof vi.fn>).mockReturnValue(true);

      $("#MemberDeckHeaderAndCaret").trigger("click");

      expect(emit).not.toHaveBeenCalled();
    });
  });

  describe("Tag deck", () => {
    // The Tag deck is only collapsible while a UTub is selected (otherwise it is
    // locked minimized), so the handler guards on isUTubSelected().
    beforeEach(async () => {
      const { isUTubSelected } = await import("../utubs/utils.js");
      (isUTubSelected as ReturnType<typeof vi.fn>).mockReturnValue(true);
    });

    it("emits ui_deck_collapse with deck=tags on first click", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initCollapsibleDecks();

      $("#TagDeckHeaderAndCaret").trigger("click");

      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_DECK_COLLAPSE,
        deck: DECK_COLLAPSE_DECK.TAGS,
      });
    });

    it("emits ui_deck_expand with deck=tags on second click", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initCollapsibleDecks();

      $("#TagDeckHeaderAndCaret").trigger("click");
      $("#TagDeckHeaderAndCaret").trigger("click");

      expect(emit).toHaveBeenNthCalledWith(2, {
        event: UI_EVENTS.UI_DECK_EXPAND,
        deck: DECK_EXPAND_DECK.TAGS,
      });
    });

    it("does not emit on mobile", async () => {
      const { isMobile } = await import("../mobile.js");
      const { emit } = await import("../../lib/metrics-client.js");
      initCollapsibleDecks();
      (isMobile as ReturnType<typeof vi.fn>).mockReturnValue(true);

      $("#TagDeckHeaderAndCaret").trigger("click");

      expect(emit).not.toHaveBeenCalled();
    });
  });
});
