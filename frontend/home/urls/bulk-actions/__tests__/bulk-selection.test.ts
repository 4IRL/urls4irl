import {
  toggleURLCardSelection,
  clearURLSelection,
  selectAllVisibleURLCards,
  getSelectedURLCardIDs,
  reapplyMultiSelectMark,
  reapplyAllMultiSelectMarks,
  pruneRemovedFromSelection,
} from "../bulk-selection.js";
import { resetStore, setState, getState } from "../../../../store/app-store.js";
import { AppEvents, on } from "../../../../lib/event-bus.js";

const $ = window.jQuery;

// Three cards with distinct utuburlids; all visible by default (filterable=true,
// no searchable=false). Individual tests flip attributes to simulate a hidden row.
const MULTI_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="false" filterable="true">
    <span class="goToUrlIcon"></span>
    <a class="urlString" href="https://alpha.com"></a>
  </div>
  <div class="urlRow" utuburlid="2" urlSelected="false" filterable="true">
    <span class="goToUrlIcon"></span>
    <a class="urlString" href="https://beta.com"></a>
  </div>
  <div class="urlRow" utuburlid="3" urlSelected="false" filterable="true">
    <span class="goToUrlIcon"></span>
    <a class="urlString" href="https://gamma.com"></a>
  </div>
`;

function rowById(id: number): JQuery {
  return $(`.urlRow[utuburlid=${id}]`);
}

describe("bulk-selection", () => {
  beforeEach(() => {
    resetStore();
    document.body.innerHTML = MULTI_CARD_HTML;
  });

  describe("toggleURLCardSelection", () => {
    it("selects a card: updates store, marks the row, emits the new array", () => {
      const handler = vi.fn();
      const unsubscribe = on(AppEvents.URL_MULTISELECT_CHANGED, handler);

      toggleURLCardSelection(2);

      expect(getState().selectedURLCardIDs).toEqual([2]);
      expect(rowById(2).hasClass("multiSelected")).toBe(true);
      expect(rowById(2).attr("aria-checked")).toBe("true");
      expect(handler).toHaveBeenCalledWith({ selectedURLCardIDs: [2] });

      unsubscribe();
    });

    it("toggling the same card again removes it, clears the mark, emits []", () => {
      toggleURLCardSelection(2);

      const handler = vi.fn();
      const unsubscribe = on(AppEvents.URL_MULTISELECT_CHANGED, handler);

      toggleURLCardSelection(2);

      expect(getState().selectedURLCardIDs).toEqual([]);
      expect(rowById(2).hasClass("multiSelected")).toBe(false);
      expect(rowById(2).attr("aria-checked")).toBe("false");
      expect(handler).toHaveBeenCalledWith({ selectedURLCardIDs: [] });

      unsubscribe();
    });

    it("keeps the row's single-select urlSelected attribute false (the two selection models never collide)", () => {
      // A multi-selected row is a selection target, not an expanded single-select
      // card: it must never gain urlSelected="true". Keeping this invariant is
      // what lets the `#URLDeck.multiSelectActive .goToUrlIcon` suppression rule
      // (bulk-actions.css) rely on the row staying urlSelected="false" — the
      // go-to icon is a single-select-only affordance.
      toggleURLCardSelection(2);

      expect(rowById(2).hasClass("multiSelected")).toBe(true);
      expect(rowById(2).attr("urlSelected")).toBe("false");
    });

    it("never mutates selectedURLCardIDs in place (setState receives a fresh array)", () => {
      const before = getState().selectedURLCardIDs;

      toggleURLCardSelection(2);

      const after = getState().selectedURLCardIDs;
      expect(after).not.toBe(before);
      // The originally-captured array reference is untouched.
      expect(before).toEqual([]);
      expect(after).toEqual([2]);
    });
  });

  describe("clearURLSelection", () => {
    it("empties the array and strips all .multiSelected marks", () => {
      toggleURLCardSelection(1);
      toggleURLCardSelection(3);
      expect(getState().selectedURLCardIDs).toEqual([1, 3]);

      clearURLSelection();

      expect(getState().selectedURLCardIDs).toEqual([]);
      expect($(".urlRow.multiSelected").length).toBe(0);
      expect(rowById(1).attr("aria-checked")).toBe("false");
      expect(rowById(3).attr("aria-checked")).toBe("false");
    });

    it("strips the stray .visible-on-focus go-to-icon reveal from every row (Clear/Exit cleanup)", () => {
      // Tapping a row in multi-select focuses it, so cards.ts adds
      // `.visible-on-focus` to its .goToUrlIcon. Since exiting mode does not
      // re-render the deck, clearURLSelection (called on both Clear and Exit)
      // must strip that class — otherwise `.visible-on-focus`'s
      // `visibility: visible !important` shows a stray icon once the in-mode
      // `#URLDeck.multiSelectActive` suppression is gone. Cover both a still-
      // selected row and a tapped-then-deselected (no longer .multiSelected) one.
      toggleURLCardSelection(1);
      toggleURLCardSelection(2);
      rowById(1).find(".goToUrlIcon").addClass("visible-on-focus"); // still selected
      rowById(2).find(".goToUrlIcon").addClass("visible-on-focus");
      toggleURLCardSelection(2); // deselect: keeps the stray class, loses .multiSelected

      clearURLSelection();

      expect(rowById(1).find(".goToUrlIcon").hasClass("visible-on-focus")).toBe(
        false,
      );
      expect(rowById(2).find(".goToUrlIcon").hasClass("visible-on-focus")).toBe(
        false,
      );
    });
  });

  describe("selectAllVisibleURLCards", () => {
    it("unions only the visible rows' ids into the selection (hidden excluded)", () => {
      rowById(3).attr("filterable", "false"); // hide row 3

      selectAllVisibleURLCards();

      const selected = getState().selectedURLCardIDs;
      expect(selected).toContain(1);
      expect(selected).toContain(2);
      expect(selected).not.toContain(3);
      // The visible rows are also marked in the DOM; the hidden one is not.
      expect(rowById(1).hasClass("multiSelected")).toBe(true);
      expect(rowById(2).hasClass("multiSelected")).toBe(true);
      expect(rowById(3).hasClass("multiSelected")).toBe(false);
    });

    it("preserves an already-selected hidden id alongside the newly-added visible ids", () => {
      rowById(3).attr("filterable", "false"); // hide row 3
      setState({ selectedURLCardIDs: [3] }); // hidden row pre-selected

      selectAllVisibleURLCards();

      const selected = getState().selectedURLCardIDs;
      expect(selected).toContain(3); // hidden selection persists
      expect(selected).toContain(1);
      expect(selected).toContain(2);
    });

    it("dedupes rather than re-adding an already-selected visible id", () => {
      setState({ selectedURLCardIDs: [1] });

      selectAllVisibleURLCards();

      const selected = getState().selectedURLCardIDs;
      expect(selected.filter((id) => id === 1)).toHaveLength(1);
    });

    it("excludes rows hidden by search (searchable=false)", () => {
      rowById(2).attr("searchable", "false");

      selectAllVisibleURLCards();

      expect(getState().selectedURLCardIDs).not.toContain(2);
    });
  });

  describe("pruneRemovedFromSelection", () => {
    it("drops the removed ids, leaves the rest, emits the reduced array", () => {
      setState({ selectedURLCardIDs: [1, 2, 3] });

      const handler = vi.fn();
      const unsubscribe = on(AppEvents.URL_MULTISELECT_CHANGED, handler);

      pruneRemovedFromSelection([2]);

      expect(getState().selectedURLCardIDs).toEqual([1, 3]);
      expect(handler).toHaveBeenCalledWith({ selectedURLCardIDs: [1, 3] });

      unsubscribe();
    });
  });

  describe("reapplyMultiSelectMark", () => {
    it("re-marks a fresh (unmarked) card whose id is in the store (deck-diff survival)", () => {
      setState({ selectedURLCardIDs: [2] });
      const freshCard = rowById(2);
      expect(freshCard.hasClass("multiSelected")).toBe(false);

      reapplyMultiSelectMark(freshCard);

      expect(freshCard.hasClass("multiSelected")).toBe(true);
      expect(freshCard.attr("aria-checked")).toBe("true");
    });

    it("leaves a card whose id is NOT in the store unmarked", () => {
      setState({ selectedURLCardIDs: [2] });
      const otherCard = rowById(1);

      reapplyMultiSelectMark(otherCard);

      expect(otherCard.hasClass("multiSelected")).toBe(false);
    });
  });

  describe("reapplyAllMultiSelectMarks", () => {
    it("marks every row whose id is in the store and strips the rest", () => {
      // Pre-mark a row that is NOT in the selection to prove it gets stripped.
      rowById(1).addClass("multiSelected").attr("aria-checked", "true");
      setState({ selectedURLCardIDs: [2, 3] });

      reapplyAllMultiSelectMarks();

      expect(rowById(1).hasClass("multiSelected")).toBe(false);
      expect(rowById(1).attr("aria-checked")).toBe("false");
      expect(rowById(2).hasClass("multiSelected")).toBe(true);
      expect(rowById(2).attr("aria-checked")).toBe("true");
      expect(rowById(3).hasClass("multiSelected")).toBe(true);
      expect(rowById(3).attr("aria-checked")).toBe("true");
    });

    it("strips all marks when the selection is empty", () => {
      rowById(2).addClass("multiSelected").attr("aria-checked", "true");

      reapplyAllMultiSelectMarks();

      expect($(".urlRow.multiSelected").length).toBe(0);
    });
  });

  describe("getSelectedURLCardIDs", () => {
    it("returns the current selection from the store", () => {
      setState({ selectedURLCardIDs: [1, 3] });
      expect(getSelectedURLCardIDs()).toEqual([1, 3]);
    });
  });
});
