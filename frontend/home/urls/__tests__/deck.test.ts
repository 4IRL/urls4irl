import type { UtubUrlItem, UtubTag } from "../../../types/url.js";

import { updateURLDeck } from "../deck.js";
import { applyDeckDiff } from "../../../logic/apply-deck-diff.js";
import { getState } from "../../../store/app-store.js";
import {
  createURLBlock,
  updateURLAfterFindingStaleData,
} from "../cards/cards.js";
import { reapplyURLSearchFilter } from "../search.js";

vi.mock("../../../logic/apply-deck-diff.js", () => ({
  applyDeckDiff: vi.fn(),
}));

vi.mock("../cards/cards.js", () => ({
  createURLBlock: vi.fn(() => window.jQuery('<div class="urlRow"></div>')),
  updateURLAfterFindingStaleData: vi.fn(),
  newURLInputRemoveEventListeners: vi.fn(),
  newURLInputAddEventListeners: vi.fn(),
  setFocusEventListenersOnURLCard: vi.fn(),
}));

vi.mock("../update-description.js", () => ({
  setupUpdateUTubDescriptionEventListeners: vi.fn(),
  updateUTubDescriptionHideInput: vi.fn(),
  removeEventListenersForShowCreateUTubDescIfEmptyDesc: vi.fn(),
  showCreateDescriptionButtonAlways: vi.fn(),
  updateUTubDescriptionShowInput: vi.fn(),
}));

vi.mock("../update-name.js", () => ({
  setupUpdateUTubNameEventListeners: vi.fn(),
  setUTubNameAndDescription: vi.fn(),
  updateUTubNameHideInput: vi.fn(),
}));

vi.mock("../create-btns.js", () => ({
  createURLShowInputEventListeners: vi.fn(),
}));

vi.mock("../empty-state.js", () => ({
  showURLsEmptyState: vi.fn(),
  hideURLsEmptyState: vi.fn(),
}));

vi.mock("../utils.js", () => ({
  bindSwitchURLKeyboardEventListeners: vi.fn(),
  getNumOfURLs: vi.fn(() => 0),
  getNumOfVisibleURLs: vi.fn(() => 0),
}));

vi.mock("../cards/create.js", () => ({
  resetNewURLForm: vi.fn(),
}));

vi.mock("../search.js", () => ({
  reapplyURLSearchFilter: vi.fn(),
  setURLSearchEventListener: vi.fn(),
  showURLSearchIcon: vi.fn(),
  hideURLSearchIcon: vi.fn(),
  disableURLSearch: vi.fn(),
  closeURLSearchAndEraseInput: vi.fn(),
  collapseURLSearchInput: vi.fn(),
  temporarilyHideSearchForEdit: vi.fn(),
}));

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [] })),
  setState: vi.fn(),
  resetStore: vi.fn(),
}));

const $ = window.jQuery;

const SAMPLE_URL_1: UtubUrlItem = {
  utubUrlID: 1,
  urlString: "https://one.com",
  urlTitle: "One",
  utubUrlTagIDs: [],
  canDelete: true,
};

const SAMPLE_URL_2: UtubUrlItem = {
  utubUrlID: 2,
  urlString: "https://two.com",
  urlTitle: "Two",
  utubUrlTagIDs: [],
  canDelete: true,
};

const SAMPLE_TAGS: UtubTag[] = [{ id: 10, tagString: "tag-a", tagApplied: 0 }];

describe("updateURLDeck", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = `
      <div id="SearchURLWrap"></div>
      <div id="listURLs"></div>
    `;
    vi.mocked(getState).mockReturnValue({
      urls: [SAMPLE_URL_1],
    } as unknown as ReturnType<typeof getState>);
  });

  it("calls applyDeckDiff once with correct URL deck config", () => {
    const updatedUrls: UtubUrlItem[] = [SAMPLE_URL_1, SAMPLE_URL_2];
    updateURLDeck(updatedUrls, SAMPLE_TAGS, 42);

    expect(vi.mocked(applyDeckDiff)).toHaveBeenCalledTimes(1);
    const config = vi.mocked(applyDeckDiff).mock.calls[0][0];
    expect(config.oldItems).toEqual([SAMPLE_URL_1]);
    expect(config.newItems).toEqual(updatedUrls);
    expect(config.getID(SAMPLE_URL_1)).toBe(1);
    expect(config.getID(SAMPLE_URL_2)).toBe(2);
    expect(typeof config.removeElement).toBe("function");
    expect(typeof config.addElement).toBe("function");
    expect(typeof config.updateElement).toBe("function");
  });

  it("delegates removeElement to fadeOut/remove on .urlRow with utuburlid", () => {
    document.body.innerHTML = `
      <div id="SearchURLWrap"></div>
      <div id="listURLs">
        <div class="urlRow" utuburlid="1"></div>
      </div>
    `;
    // Override fadeOut so the post-fade callback fires synchronously
    ($.fn as unknown as Record<string, unknown>).fadeOut = function (
      this: JQuery,
      _duration: unknown,
      callback?: () => void,
    ) {
      if (typeof callback === "function") callback();
      return this;
    };

    updateURLDeck([SAMPLE_URL_1], SAMPLE_TAGS, 42);
    const config = vi.mocked(applyDeckDiff).mock.calls[0][0];

    config.removeElement(1);

    expect(document.querySelector('.urlRow[utuburlid="1"]')).toBeNull();
  });

  it("delegates addElement to createURLBlock/append into URL deck", () => {
    document.body.innerHTML = `
      <div id="SearchURLWrap"></div>
      <div id="listURLs"></div>
    `;
    const newURLBlock = $('<div class="urlRow" utuburlid="2"></div>');
    vi.mocked(createURLBlock).mockReturnValueOnce(newURLBlock);

    updateURLDeck([SAMPLE_URL_1, SAMPLE_URL_2], SAMPLE_TAGS, 42);
    const config = vi.mocked(applyDeckDiff).mock.calls[0][0];

    config.addElement(SAMPLE_URL_2);

    expect(vi.mocked(createURLBlock)).toHaveBeenCalledWith(
      SAMPLE_URL_2,
      SAMPLE_TAGS,
      42,
    );
    expect(
      document.querySelector('#listURLs .urlRow[utuburlid="2"]'),
    ).not.toBeNull();
    expect(document.querySelector('#listURLs [utuburlid="2"]')).not.toBeNull();
  });

  it("delegates updateElement to refreshURLBlock for the matching URL", () => {
    document.body.innerHTML = `
      <div id="SearchURLWrap"></div>
      <div id="listURLs">
        <div class="urlRow" utuburlid="1"></div>
      </div>
    `;
    const updatedURL: UtubUrlItem = {
      ...SAMPLE_URL_1,
      urlTitle: "Updated Title",
    };

    updateURLDeck([updatedURL], SAMPLE_TAGS, 42);
    const config = vi.mocked(applyDeckDiff).mock.calls[0][0];

    expect(config.updateElement).toBeDefined();
    config.updateElement!(1, updatedURL);

    expect(vi.mocked(updateURLAfterFindingStaleData)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(updateURLAfterFindingStaleData)).toHaveBeenCalledWith(
      expect.anything(),
      updatedURL,
      SAMPLE_TAGS,
      42,
    );
  });

  it("calls reapplyURLSearchFilter when #SearchURLWrap has visible-flex class", () => {
    document.body.innerHTML = `
      <div id="SearchURLWrap" class="visible-flex"></div>
      <div id="listURLs"></div>
    `;

    updateURLDeck([SAMPLE_URL_1], SAMPLE_TAGS, 42);

    expect(vi.mocked(reapplyURLSearchFilter)).toHaveBeenCalledTimes(1);
  });

  it("does NOT call reapplyURLSearchFilter when #SearchURLWrap lacks visible-flex class", () => {
    document.body.innerHTML = `
      <div id="SearchURLWrap"></div>
      <div id="listURLs"></div>
    `;

    updateURLDeck([SAMPLE_URL_1], SAMPLE_TAGS, 42);

    expect(vi.mocked(reapplyURLSearchFilter)).not.toHaveBeenCalled();
  });
});
