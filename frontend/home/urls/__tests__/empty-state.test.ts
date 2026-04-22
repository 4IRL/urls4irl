import { APP_CONFIG } from "../../../lib/config.js";
import { showURLsEmptyState, hideURLsEmptyState } from "../empty-state.js";
import { setURLDeckOnUTubSelected, resetURLDeckOnDeleteUTub } from "../deck.js";

vi.mock("../create-btns.js", () => ({
  createURLShowInputEventListeners: vi.fn(),
}));

vi.mock("../update-description.js", () => ({
  setupUpdateUTubDescriptionEventListeners: vi.fn(),
  updateUTubDescriptionHideInput: vi.fn(),
  removeEventListenersForShowCreateUTubDescIfEmptyDesc: vi.fn(),
}));

vi.mock("../update-name.js", () => ({
  setupUpdateUTubNameEventListeners: vi.fn(),
  setUTubNameAndDescription: vi.fn(),
}));

vi.mock("../cards/cards.js", () => ({
  createURLBlock: vi.fn(() => window.jQuery("<div class='urlRow'></div>")),
  updateURLAfterFindingStaleData: vi.fn(),
  newURLInputRemoveEventListeners: vi.fn(),
}));

vi.mock("../cards/create.js", () => ({
  resetNewURLForm: vi.fn(),
}));

vi.mock("../search.js", () => ({
  showURLSearchIcon: vi.fn(),
  hideURLSearchIcon: vi.fn(),
  disableURLSearch: vi.fn(),
  setURLSearchEventListener: vi.fn(),
  reapplyURLSearchFilter: vi.fn(),
}));

vi.mock("../utils.js", () => ({
  bindSwitchURLKeyboardEventListeners: vi.fn(),
}));

const $ = window.jQuery;

const EMPTY_STATE_HTML = `
  <div id="URLDeck">
    <div id="URLDeckHeaderWrap">
      <h2 id="URLDeckHeader">URLs</h2>
      <div id="URLDeckSubheader"></div>
      <div id="UTubDescriptionSubheaderWrap"></div>
    </div>
    <div class="flex-column content">
      <div id="noURLsEmptyState" class="hidden">
        <p id="noURLsSubheader"></p>
        <div id="urlBtnDeckCreateWrap" class="flex-column align-center">
          <button id="urlBtnDeckCreate" class="btn btn-success btn-sm">Add URL</button>
        </div>
      </div>
      <p id="URLSearchNoResults" class="hidden"></p>
      <p id="URLTagFilterNoResults" class="hidden"></p>
      <div id="listURLs">
        <div id="createURLWrap" class="hidden"></div>
      </div>
    </div>
    <button id="urlBtnCreate" class="hidden"></button>
  </div>
`;

describe("UTub empty state", () => {
  beforeEach(() => {
    document.body.innerHTML = EMPTY_STATE_HTML;
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  describe("showURLsEmptyState helper", () => {
    it("shows wrapper, sets subheader text, and sets button text", () => {
      showURLsEmptyState();

      expect($("#noURLsEmptyState").hasClass("hidden")).toBe(false);
      expect($("#noURLsSubheader").text()).toBe(
        APP_CONFIG.strings.UTUB_NO_URLS,
      );
      expect($("#urlBtnDeckCreate").text()).toBe(
        APP_CONFIG.strings.ADD_URL_BUTTON,
      );
    });
  });

  describe("hideURLsEmptyState helper", () => {
    it("hides wrapper and clears subheader text", () => {
      $("#noURLsEmptyState").removeClass("hidden");
      $("#noURLsSubheader").text(APP_CONFIG.strings.UTUB_NO_URLS);

      hideURLsEmptyState();

      expect($("#noURLsEmptyState").hasClass("hidden")).toBe(true);
      expect($("#noURLsSubheader").text()).toBe("");
    });
  });

  describe("setURLDeckOnUTubSelected with 0 URLs", () => {
    it("shows empty state wrapper with UTUB_NO_URLS text", () => {
      setURLDeckOnUTubSelected(1, "Test UTub", [], []);

      expect($("#noURLsEmptyState").hasClass("hidden")).toBe(false);
      expect($("#noURLsSubheader").text()).toBe(
        APP_CONFIG.strings.UTUB_NO_URLS,
      );
    });
  });

  describe("setURLDeckOnUTubSelected with URLs", () => {
    const mockURLs = [
      {
        utubUrlID: 1,
        urlString: "https://example.com",
        urlTitle: "Example",
        urlTagIDs: [],
      },
    ];

    it("hides empty state wrapper and clears text", () => {
      setURLDeckOnUTubSelected(1, "Test UTub", mockURLs, []);

      expect($("#noURLsEmptyState").hasClass("hidden")).toBe(true);
      expect($("#noURLsSubheader").text()).toBe("");
    });
  });

  describe("resetURLDeckOnDeleteUTub", () => {
    it("hides empty state wrapper and clears text", () => {
      $("#noURLsSubheader").text(APP_CONFIG.strings.UTUB_NO_URLS);
      $("#noURLsEmptyState").removeClass("hidden");

      resetURLDeckOnDeleteUTub();

      expect($("#noURLsEmptyState").hasClass("hidden")).toBe(true);
      expect($("#noURLsSubheader").text()).toBe("");
    });
  });
});
