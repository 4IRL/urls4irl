import {
  enterMultiSelectMode,
  exitMultiSelectMode,
  isMultiSelectActive,
} from "../bulk-mode.js";
import { deselectAllURLs } from "../../cards/selection.js";
import { resetStore, getState, setState } from "../../../../store/app-store.js";
import { AppEvents, on } from "../../../../lib/event-bus.js";

vi.mock("../../cards/selection.js", () => ({
  deselectAllURLs: vi.fn(),
}));

const $ = window.jQuery;

// #URLDeck receives the deck-level mode class; #toCrossUtubSearch (the navbar
// cross-search trigger) is disabled while mode is active. A couple of selected
// rows let us prove exit strips the marks via the real clearURLSelection().
const DECK_HTML = `
  <div id="URLDeck">
    <div class="urlRow multiSelected" utuburlid="1" aria-checked="true"></div>
    <div class="urlRow multiSelected" utuburlid="2" aria-checked="true"></div>
  </div>
  <button id="toCrossUtubSearch" class="navbar-cross-search"></button>
`;

describe("bulk-mode", () => {
  beforeEach(() => {
    resetStore();
    document.body.innerHTML = DECK_HTML;
    vi.mocked(deselectAllURLs).mockClear();
  });

  describe("enterMultiSelectMode", () => {
    it("sets the store flag, marks the deck, collapses any expanded card, emits", () => {
      const handler = vi.fn();
      const unsubscribe = on(AppEvents.URL_MULTISELECT_MODE_CHANGED, handler);

      enterMultiSelectMode();

      expect(getState().multiSelectMode).toBe(true);
      expect($("#URLDeck").hasClass("multiSelectActive")).toBe(true);
      expect(vi.mocked(deselectAllURLs)).toHaveBeenCalledTimes(1);
      expect(handler).toHaveBeenCalledWith({ active: true });

      unsubscribe();
    });
  });

  describe("exitMultiSelectMode", () => {
    it("clears the flag, unmarks the deck, empties the selection + strips marks, emits", () => {
      enterMultiSelectMode();
      setState({ selectedURLCardIDs: [1, 2] });

      const handler = vi.fn();
      const unsubscribe = on(AppEvents.URL_MULTISELECT_MODE_CHANGED, handler);

      exitMultiSelectMode();

      expect(getState().multiSelectMode).toBe(false);
      expect($("#URLDeck").hasClass("multiSelectActive")).toBe(false);
      // clearURLSelection() ran: selection emptied and every mark stripped.
      expect(getState().selectedURLCardIDs).toEqual([]);
      expect($(".urlRow.multiSelected").length).toBe(0);
      expect(handler).toHaveBeenCalledWith({ active: false });

      unsubscribe();
    });
  });

  it("still tears down the deck DOM when the store flag was pre-cleared before exit", () => {
    // A UTub switch/delete pre-clears multiSelectMode in its own setState
    // BEFORE the UTUB_SELECTED/UTUB_DELETED emit reaches this exit subscriber.
    // The deck must still be torn down (class removed, cross-search restored)
    // — the multiSelectActive class is the authoritative in-mode signal.
    enterMultiSelectMode();
    expect($("#URLDeck").hasClass("multiSelectActive")).toBe(true);
    expect($("#toCrossUtubSearch").hasClass("hidden")).toBe(true);

    setState({ multiSelectMode: false }); // simulate the pre-clear

    exitMultiSelectMode();

    expect($("#URLDeck").hasClass("multiSelectActive")).toBe(false);
    expect($("#toCrossUtubSearch").hasClass("hidden")).toBe(false);
  });

  describe("isMultiSelectActive", () => {
    it("reflects the store's multiSelectMode flag", () => {
      expect(isMultiSelectActive()).toBe(false);
      enterMultiSelectMode();
      expect(isMultiSelectActive()).toBe(true);
      exitMultiSelectMode();
      expect(isMultiSelectActive()).toBe(false);
    });
  });

  describe("cross-UTub-search trigger disabling", () => {
    it("hides #toCrossUtubSearch on enter", () => {
      expect($("#toCrossUtubSearch").hasClass("hidden")).toBe(false);

      enterMultiSelectMode();

      expect($("#toCrossUtubSearch").hasClass("hidden")).toBe(true);
    });

    it("restores #toCrossUtubSearch on exit when it was visible before entry", () => {
      enterMultiSelectMode();
      expect($("#toCrossUtubSearch").hasClass("hidden")).toBe(true);

      exitMultiSelectMode();

      expect($("#toCrossUtubSearch").hasClass("hidden")).toBe(false);
    });

    it("does NOT reveal #toCrossUtubSearch on exit when it was hidden before entry", () => {
      // Trigger starts hidden (e.g. an empty utubs list) — exit must not clobber that.
      $("#toCrossUtubSearch").addClass("hidden");

      enterMultiSelectMode();
      exitMultiSelectMode();

      expect($("#toCrossUtubSearch").hasClass("hidden")).toBe(true);
    });
  });
});
