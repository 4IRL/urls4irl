import { APP_CONFIG } from "../../../lib/config.js";
import {
  showTagDeckEmptyState,
  hideTagDeckEmptyState,
} from "../empty-state.js";
import { setTagDeckOnUTubSelected } from "../deck.js";

vi.mock("../tags.js", () => ({
  buildTagFilterInDeck: vi.fn(() =>
    window.jQuery("<div class='tagFilter'></div>"),
  ),
}));

vi.mock("../create.js", () => ({
  createUTubTagHideInput: vi.fn(),
  removeCreateUTubTagEventListeners: vi.fn(),
  resetCreateUTubTagFailErrors: vi.fn(),
  resetNewUTubTagForm: vi.fn(),
  setupOpenCreateUTubTagEventListeners: vi.fn(),
}));

vi.mock("../update-all.js", () => ({
  closeUTubTagBtnMenuOnUTubTags: vi.fn(),
  setTagDeckBtnsOnUpdateAllUTubTagsClosed: vi.fn(),
  setUnselectUpdateUTubTagEventListeners: vi.fn(),
}));

vi.mock("../unselect-all.js", () => ({
  disableUnselectAllButtonAfterTagFilterRemoved: vi.fn(),
  resetCountOfTagFiltersApplied: vi.fn(),
}));

vi.mock("../search.js", () => ({
  applyAlternatingTagBackground: vi.fn(),
  setTagSelectorSearchEventListener: vi.fn(),
  setTagNameFilterToggleListeners: vi.fn(),
  showTagFilterBar: vi.fn(),
  hideTagFilterBar: vi.fn(),
  resetTagFilter: vi.fn(),
  reapplyTagFilter: vi.fn(),
}));

const $ = window.jQuery;

const EMPTY_STATE_HTML = `
  <div id="TagDeck">
    <div class="flex-column content">
      <div id="listTags"></div>
      <div id="noTagsEmptyState" class="hidden flex-column align-center">
        <p id="noTagsSubheader"></p>
      </div>
    </div>
    <button id="utubTagBtnCreate" class="hidden"></button>
    <button id="unselectAllTagFilters" class="hidden"></button>
    <button id="utubTagBtnUpdateAllOpen" class="hidden"></button>
  </div>
`;

describe("Tag deck empty state", () => {
  beforeEach(() => {
    document.body.innerHTML = EMPTY_STATE_HTML;
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  describe("showTagDeckEmptyState helper", () => {
    it("shows wrapper and sets subheader text", () => {
      showTagDeckEmptyState();

      expect($("#noTagsEmptyState").hasClass("hidden")).toBe(false);
      expect($("#noTagsSubheader").text()).toBe(
        APP_CONFIG.strings.TAG_DECK_NO_TAGS,
      );
    });
  });

  describe("hideTagDeckEmptyState helper", () => {
    it("hides wrapper and clears subheader text", () => {
      showTagDeckEmptyState();

      hideTagDeckEmptyState();

      expect($("#noTagsEmptyState").hasClass("hidden")).toBe(true);
      expect($("#noTagsSubheader").text()).toBe("");
    });
  });

  describe("setTagDeckOnUTubSelected with 0 tags", () => {
    it("shows empty state wrapper with TAG_DECK_NO_TAGS text", () => {
      setTagDeckOnUTubSelected([], 1);

      expect($("#noTagsEmptyState").hasClass("hidden")).toBe(false);
      expect($("#noTagsSubheader").text()).toBe(
        APP_CONFIG.strings.TAG_DECK_NO_TAGS,
      );
    });
  });

  describe("setTagDeckOnUTubSelected with tags", () => {
    const mockTags = [{ id: 1, tagString: "tag-one", tagApplied: 1 }];

    it("hides empty state wrapper and clears text", () => {
      setTagDeckOnUTubSelected(mockTags, 1);

      expect($("#noTagsEmptyState").hasClass("hidden")).toBe(true);
      expect($("#noTagsSubheader").text()).toBe("");
    });
  });
});
