import {
  setUIWhenNoUTubSelected,
  resetHomePageToInitialState,
} from "../init.js";

const mockHideInputs = vi.fn();
const mockSetTagDeckSubheaderWhenNoUTubSelected = vi.fn();
const mockResetTagDeckIfNoUTubSelected = vi.fn();
const mockSetURLDeckWhenNoUTubSelected = vi.fn();
const mockSetMemberDeckWhenNoUTubSelected = vi.fn();
const mockResetMemberDeck = vi.fn();
const mockGetAllUTubs = vi.fn();
const mockBuildUTubDeck = vi.fn();

vi.mock("../btns-forms.js", () => ({
  hideInputs: (...args: unknown[]) => mockHideInputs(...args),
}));
vi.mock("../tags/deck.js", () => ({
  setTagDeckSubheaderWhenNoUTubSelected: (...args: unknown[]) =>
    mockSetTagDeckSubheaderWhenNoUTubSelected(...args),
  resetTagDeckIfNoUTubSelected: (...args: unknown[]) =>
    mockResetTagDeckIfNoUTubSelected(...args),
}));
vi.mock("../urls/deck.js", () => ({
  setURLDeckWhenNoUTubSelected: (...args: unknown[]) =>
    mockSetURLDeckWhenNoUTubSelected(...args),
}));
vi.mock("../members/deck.js", () => ({
  setMemberDeckWhenNoUTubSelected: (...args: unknown[]) =>
    mockSetMemberDeckWhenNoUTubSelected(...args),
  resetMemberDeck: (...args: unknown[]) => mockResetMemberDeck(...args),
}));
vi.mock("../utubs/utils.js", () => ({
  getAllUTubs: (...args: unknown[]) => mockGetAllUTubs(...args),
}));
vi.mock("../utubs/deck.js", () => ({
  buildUTubDeck: (...args: unknown[]) => mockBuildUTubDeck(...args),
}));

const $ = window.jQuery;

const INIT_HTML = `
  <div class="dynamic-subheader height-2p5rem"></div>
  <div class="sidePanelTitle"></div>
  <div class="UTubSelector active focus" tabindex="0"></div>
  <div class="UTubSelector" tabindex="0"></div>
`;

describe("init", () => {
  beforeEach(() => {
    document.body.innerHTML = INIT_HTML;
    vi.clearAllMocks();
  });

  describe("setUIWhenNoUTubSelected", () => {
    it("calls all reset functions and removes active state from UTub selectors", () => {
      setUIWhenNoUTubSelected();

      expect(mockHideInputs).toHaveBeenCalled();
      expect(mockSetTagDeckSubheaderWhenNoUTubSelected).toHaveBeenCalled();
      expect(mockResetTagDeckIfNoUTubSelected).toHaveBeenCalled();
      expect(mockSetURLDeckWhenNoUTubSelected).toHaveBeenCalled();
      expect(mockSetMemberDeckWhenNoUTubSelected).toHaveBeenCalled();
      expect(mockResetMemberDeck).toHaveBeenCalled();
      expect($(".dynamic-subheader").hasClass("height-2p5rem")).toBe(false);
      expect($(".sidePanelTitle").hasClass("pad-b-0-25rem")).toBe(true);
      expect($(".UTubSelector.active").length).toBe(0);
    });

    it("is a no-op for active classes when no UTub selector is active", () => {
      $(".UTubSelector").removeClass("active").removeClass("focus");

      setUIWhenNoUTubSelected();

      expect($(".UTubSelector.active").length).toBe(0);
      expect(mockHideInputs).toHaveBeenCalled();
    });
  });

  describe("resetHomePageToInitialState", () => {
    it("calls setUIWhenNoUTubSelected then rebuilds UTub deck from fetched data", async () => {
      const fakeUtubData = { utubs: [{ id: 1, name: "Test" }] };
      mockGetAllUTubs.mockResolvedValue(fakeUtubData);

      resetHomePageToInitialState();

      await vi.waitFor(() => {
        expect(mockGetAllUTubs).toHaveBeenCalled();
      });

      expect(mockHideInputs).toHaveBeenCalled();
      expect(mockBuildUTubDeck).toHaveBeenCalledWith(fakeUtubData.utubs);
      expect(mockSetMemberDeckWhenNoUTubSelected).toHaveBeenCalled();
      expect(mockSetTagDeckSubheaderWhenNoUTubSelected).toHaveBeenCalled();
    });

    it("still calls setUIWhenNoUTubSelected when getAllUTubs returns empty data", async () => {
      const emptyUtubData = { utubs: [] };
      mockGetAllUTubs.mockResolvedValue(emptyUtubData);

      resetHomePageToInitialState();

      expect(mockHideInputs).toHaveBeenCalled();

      await vi.waitFor(() => {
        expect(mockGetAllUTubs).toHaveBeenCalled();
      });

      expect(mockBuildUTubDeck).toHaveBeenCalledWith([]);
    });
  });
});
