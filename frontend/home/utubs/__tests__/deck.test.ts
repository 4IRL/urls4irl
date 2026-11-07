import utubDeckTemplate from "../../../../backend/templates/components/home/UTubDeck/UTubDeck.html?raw";

import { makeUtubSummaryItem } from "../../../__tests__/helpers/utub-summary.js";
import { createUTubSelector } from "../selectors.js";
import {
  buildUTubDeck,
  resetUTubDeck,
  setUTubDeckOnUTubSelected,
  setUTubDeckWhenNoUTubSelected,
  setUTubEventListenersOnInitialPageLoad,
} from "../deck.js";
import {
  applyAlternatingUTubSelectorBackground,
  setUTubNameFilterToggleListeners,
} from "../search.js";
import { updateUTubDeckCount } from "../utils.js";

vi.mock("../selectors.js", () => ({
  createUTubSelector: vi.fn(),
  setUTubSelectorEventListeners: vi.fn(),
}));
vi.mock("../search.js", () => ({
  applyAlternatingUTubSelectorBackground: vi.fn(),
  hideUTubSearchBar: vi.fn(),
  setUTubNameFilterToggleListeners: vi.fn(),
  setUTubSelectorSearchEventListener: vi.fn(),
  showUTubSearchBar: vi.fn(),
}));
vi.mock("../delete.js", () => ({ setDeleteEventListeners: vi.fn() }));
vi.mock("../utils.js", () => ({ updateUTubDeckCount: vi.fn() }));
vi.mock("../../btns-forms.js", () => ({ hideInputs: vi.fn() }));
vi.mock("../../../store/app-store.js", () => ({ setState: vi.fn() }));

const $ = window.jQuery;

// Owner sees Delete, member sees Leave — both buttons live in the UTub deck.
const UTUB_DECK_HTML = `
  <div id="listUTubs">
    <div class="UTubSelector" utubid="42"></div>
  </div>
  <button id="utubBtnDelete" class="hidden"></button>
  <button id="memberSelfBtnDelete" class="hidden"></button>
`;

describe("UTub deck role-dependent action buttons", () => {
  beforeEach(() => {
    document.body.innerHTML = UTUB_DECK_HTML;
    vi.clearAllMocks();
  });

  it("shows Delete and hides Leave for the UTub owner", () => {
    setUTubDeckOnUTubSelected(42, true);

    expect($("#utubBtnDelete").hasClass("hidden")).toBe(false);
    expect($("#memberSelfBtnDelete").hasClass("hidden")).toBe(true);
  });

  it("shows Leave and hides Delete for a non-owner member", () => {
    setUTubDeckOnUTubSelected(42, false);

    expect($("#utubBtnDelete").hasClass("hidden")).toBe(true);
    expect($("#memberSelfBtnDelete").hasClass("hidden")).toBe(false);
  });

  it("hides both Delete and Leave when no UTub is selected", () => {
    $("#utubBtnDelete").removeClass("hidden");
    $("#memberSelfBtnDelete").removeClass("hidden");

    setUTubDeckWhenNoUTubSelected();

    expect($("#utubBtnDelete").hasClass("hidden")).toBe(true);
    expect($("#memberSelfBtnDelete").hasClass("hidden")).toBe(true);
  });

  it("hides both Delete and Leave when the deck is reset", () => {
    $("#utubBtnDelete").removeClass("hidden");
    $("#memberSelfBtnDelete").removeClass("hidden");

    resetUTubDeck();

    expect($("#utubBtnDelete").hasClass("hidden")).toBe(true);
    expect($("#memberSelfBtnDelete").hasClass("hidden")).toBe(true);
  });
});

describe("buildUTubDeck — pin divider", () => {
  beforeEach(() => {
    document.body.innerHTML = UTUB_DECK_HTML;
    vi.clearAllMocks();
    vi.mocked(createUTubSelector).mockImplementation(({ utubID, isPinned }) =>
      $(
        `<span class="UTubSelector" utubid="${utubID}">${
          isPinned ? '<svg class="UTubPinIcon"></svg>' : ""
        }</span>`,
      ),
    );
  });

  function children(): string[] {
    return $("#listUTubs")
      .children()
      .map((_, element) => element.id || `row${$(element).attr("utubid")}`)
      .get();
  }

  it("passes isPinned to every row and places one divider after the pinned rows", () => {
    buildUTubDeck([
      makeUtubSummaryItem({ id: 1, isPinned: true }),
      makeUtubSummaryItem({ id: 2 }),
    ]);

    expect(
      vi.mocked(createUTubSelector).mock.calls.map(([args]) => args.isPinned),
    ).toEqual([true, false]);
    expect(children()).toEqual(["row1", "UTubPinDivider", "row2"]);
    const divider = $("#UTubPinDivider");
    expect(divider.hasClass("hidden")).toBe(false);
    expect(divider.attr("aria-hidden")).toBe("true");
    expect(divider.attr("role")).toBeUndefined();
  });

  it("recreates exactly one hidden divider for an empty deck", () => {
    buildUTubDeck([]);

    expect(children()).toEqual(["UTubPinDivider"]);
    expect($("#UTubPinDivider").hasClass("hidden")).toBe(true);
  });

  it("keeps exactly one divider across repeated rebuilds", () => {
    buildUTubDeck([makeUtubSummaryItem({ id: 1, isPinned: true })]);
    buildUTubDeck([
      makeUtubSummaryItem({ id: 1, isPinned: true }),
      makeUtubSummaryItem({ id: 2 }),
    ]);

    expect($("#listUTubs > #UTubPinDivider").length).toBe(1);
    expect(children()).toEqual(["row1", "UTubPinDivider", "row2"]);
  });

  it("renders the Jinja deck divider aria-hidden with no role", () => {
    const tag = utubDeckTemplate
      .split("\n")
      .filter((line: string) => line.includes('id="UTubPinDivider"'));

    expect(tag.length).toBe(2);
    for (const line of tag) {
      expect(line).toContain('aria-hidden="true"');
      expect(line).not.toContain("role=");
    }
  });
});

describe("UTub deck initial page-load wiring", () => {
  beforeEach(() => {
    document.body.innerHTML = UTUB_DECK_HTML;
    vi.clearAllMocks();
  });

  it("wires the name-filter toggle and refreshes the deck count", () => {
    setUTubEventListenersOnInitialPageLoad();

    expect(setUTubNameFilterToggleListeners).toHaveBeenCalledTimes(1);
    expect(updateUTubDeckCount).toHaveBeenCalledTimes(1);
  });

  it("zebra-stripes the server-rendered rows on initial page load", () => {
    setUTubEventListenersOnInitialPageLoad();

    expect(
      vi.mocked(applyAlternatingUTubSelectorBackground),
    ).toHaveBeenCalledTimes(1);
  });

  it("repositions a misplaced pin divider on initial page load", () => {
    document.body.innerHTML = `
      <div id="listUTubs">
        <div class="UTubSelector" utubid="1"><svg class="UTubPinIcon"></svg></div>
        <div class="UTubSelector" utubid="2"></div>
        <div id="UTubPinDivider" class="UTubPinDivider hidden" aria-hidden="true"></div>
      </div>
    `;

    setUTubEventListenersOnInitialPageLoad();

    const ids = $("#listUTubs")
      .children()
      .map((_, element) => element.id || `row${$(element).attr("utubid")}`)
      .get();
    expect(ids).toEqual(["row1", "UTubPinDivider", "row2"]);
    expect($("#UTubPinDivider").hasClass("hidden")).toBe(false);
  });
});
