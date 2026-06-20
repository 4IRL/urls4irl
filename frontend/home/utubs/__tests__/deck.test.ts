import {
  resetUTubDeck,
  setUTubDeckOnUTubSelected,
  setUTubDeckWhenNoUTubSelected,
} from "../deck.js";

vi.mock("../selectors.js", () => ({
  createUTubSelector: vi.fn(),
  setUTubSelectorEventListeners: vi.fn(),
}));
vi.mock("../search.js", () => ({
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
