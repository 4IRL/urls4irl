import { UI_EVENTS } from "../../types/metrics-events.js";
import { AppEvents, emit as emitAppEvent } from "../../lib/event-bus.js";
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
// collapsible-decks.ts defers a maybeShowNextTip() re-eval on every Member/Tag
// expand. Mocked here so the real nudges.ts (which imports isUTubSearchActive
// from the partially-mocked ../utubs/search.js above) never enters the graph.
vi.mock("../onboarding/nudges.js", () => ({ maybeShowNextTip: vi.fn() }));

const $ = window.jQuery;

// Mirrors the production disclosure markup: a real <button> holding the caret
// AND the visible, unroled title <span>, with the semantic heading as a
// visually-hidden <h2> SIBLING after the button (ARIA prunes descendant roles
// inside a button, so the heading cannot nest).
const DECK_HTML = `
  <div class="deck" id="UTubDeck">
    <button type="button" id="UTubDeckHeaderAndCaret" aria-expanded="true" aria-controls="UTubDeckContent">
      <span class="title-caret"></span>
      <span id="UTubDeckHeader">UTubs</span>
    </button>
    <h2 id="UTubDeckHeaderA11y" class="visually-hidden">UTubs</h2>
    <div id="UTubDeckContent" class="content"></div>
  </div>
  <div class="deck" id="MemberDeck">
    <button type="button" id="MemberDeckHeaderAndCaret" aria-expanded="true" aria-controls="MemberDeckContent">
      <span class="title-caret"></span>
      <span id="MemberDeckHeader">Members</span>
    </button>
    <h2 id="MemberDeckHeaderA11y" class="visually-hidden">Members</h2>
    <div id="MemberDeckContent" class="content"></div>
  </div>
  <div class="deck" id="TagDeck">
    <button type="button" id="TagDeckHeaderAndCaret" aria-expanded="true" aria-controls="TagDeckContent">
      <span class="title-caret"></span>
      <span id="TagDeckHeader">Tags</span>
    </button>
    <h2 id="TagDeckHeaderA11y" class="visually-hidden">Tags</h2>
    <div id="TagDeckContent" class="content"></div>
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

  // UI_DECK_COLLAPSE / UI_DECK_EXPAND mean "a user clicked a caret". Applying
  // the saved layout on a UTub selection is not a click, so it must stay silent
  // (Design Decision 6): emitting here would inflate both dimensions on every
  // UTub switch, and the metrics client's dedupe map could then swallow a
  // genuine click that followed.
  describe("persisted layout restore", () => {
    // Map-backed localStorage stub, same shape as `installStorageStub()` in
    // `collapsible-decks.test.ts` / `deck-layout-storage.test.ts`: happy-dom has
    // no ambient localStorage, so without it `getDeckLayout()` hits its own
    // try/catch, returns the default, and the restore below would never collapse
    // anything — making "emits no metric" vacuous.
    beforeEach(() => {
      const data = new Map<string, string>();
      vi.stubGlobal("localStorage", {
        getItem: (key: string): string | null => data.get(key) ?? null,
        setItem: (key: string, value: string): void => {
          data.set(key, String(value));
        },
        removeItem: (key: string): void => {
          data.delete(key);
        },
        clear: (): void => {
          data.clear();
        },
        key: (index: number): string | null =>
          Array.from(data.keys())[index] ?? null,
        get length(): number {
          return data.size;
        },
      });
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it("emits nothing when a UTub selection applies a saved collapsed layout", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initCollapsibleDecks();
      window.localStorage.setItem(
        "u4i:deckLayout",
        JSON.stringify({ membersMinimized: true, tagsMinimized: true }),
      );

      emitAppEvent(AppEvents.UTUB_SELECTED, {
        utubID: 1,
        utubName: "MyUTub",
        urls: [],
        tags: [],
        members: [],
        utubOwnerID: 1,
        isCurrentUserOwner: true,
        currentUserID: 1,
      });

      // The restore really ran — otherwise "no metric" would be vacuous.
      expect($(".deck#MemberDeck").hasClass("collapsed")).toBe(true);
      expect($(".deck#TagDeck").hasClass("collapsed")).toBe(true);
      expect(emit).not.toHaveBeenCalled();
    });
  });
});
