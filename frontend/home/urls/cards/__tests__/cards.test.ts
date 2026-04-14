import { createURLBlock } from "../cards.js";
import { createURLTitle, createURLTitleAndUpdateBlock } from "../url-title.js";
import {
  createURLString,
  createURLStringAndUpdateBlock,
} from "../url-string.js";
import { setURLCardSelectionEventListener } from "../selection.js";
import { createGoToURLIcon } from "../corner-access.js";

vi.mock("../selection.js", () => ({
  selectURLCard: vi.fn(),
  setURLCardSelectionEventListener: vi.fn(),
}));
vi.mock("../corner-access.js", () => ({
  createGoToURLIcon: vi.fn(() =>
    window.jQuery('<button class="goToUrlIcon self-start"></button>'),
  ),
}));
vi.mock("../url-title.js", () => ({
  createURLTitle: vi.fn((title) =>
    window.jQuery('<h6 class="urlTitle"></h6>').text(title),
  ),
  createURLTitleAndUpdateBlock: vi.fn(() =>
    window.jQuery('<div class="urlTitleAndUpdateIconWrap"></div>'),
  ),
}));
vi.mock("../url-string.js", () => ({
  createURLString: vi.fn((url) =>
    window.jQuery('<a class="urlString"></a>').attr("href", url),
  ),
  createURLStringAndUpdateBlock: vi.fn(() =>
    window.jQuery('<div class="updateUrlStringWrap"></div>'),
  ),
  modifyURLStringForDisplay: vi.fn((url) => url),
}));
vi.mock("../../tags/tags.js", () => ({
  createTagBadgeInURL: vi.fn(),
  createTagBadgesAndWrap: vi.fn(() =>
    window.jQuery('<div class="urlTagsContainer"></div>'),
  ),
}));
vi.mock("../../tags/create.js", () => ({
  createTagInputBlock: vi.fn(() =>
    window.jQuery('<div class="tagInputBlock"></div>'),
  ),
}));
vi.mock("../options/btns.js", () => ({
  createURLOptionsButtons: vi.fn(() =>
    window.jQuery('<div class="urlOptions"></div>'),
  ),
}));
vi.mock("../create.js", () => ({
  createURL: vi.fn(),
  createURLHideInput: vi.fn(),
  bindCreateURLFocusEventListeners: vi.fn(),
  unbindCreateURLFocusEventListeners: vi.fn(),
  resetCreateURLFailErrors: vi.fn(),
}));

const baseURL = {
  utubUrlID: 1,
  urlTitle: "Test URL",
  urlString: "https://example.com",
  utubUrlTagIDs: [],
  canDelete: false,
};

describe("createURLBlock", () => {
  beforeEach(() => vi.clearAllMocks());

  describe("outer element structure", () => {
    it("returns a div element", () => {
      const el = createURLBlock(baseURL, [], 10);
      expect(el.prop("tagName")).toBe("DIV");
    });

    it("has urlRow class", () => {
      const el = createURLBlock(baseURL, [], 10);
      expect(el.hasClass("urlRow")).toBe(true);
    });

    it("has flex-column, full-width, pad-in-15p, pointerable classes", () => {
      const el = createURLBlock(baseURL, [], 10);
      expect(el.hasClass("flex-column")).toBe(true);
      expect(el.hasClass("full-width")).toBe(true);
      expect(el.hasClass("pad-in-15p")).toBe(true);
      expect(el.hasClass("pointerable")).toBe(true);
    });
  });

  describe("data attributes", () => {
    it("sets utuburlid attribute to the URL's utubUrlID", () => {
      const el = createURLBlock({ ...baseURL, utubUrlID: 99 }, [], 10);
      expect(el.attr("utuburlid")).toBe("99");
    });

    it("sets urlselected to false", () => {
      const el = createURLBlock(baseURL, [], 10);
      expect(el.attr("urlselected")).toBe("false");
    });

    it("sets filterable to true", () => {
      const el = createURLBlock(baseURL, [], 10);
      expect(el.attr("filterable")).toBe("true");
    });

    it("sets data-utub-url-tag-ids to comma-joined tag IDs", () => {
      const el = createURLBlock(
        { ...baseURL, utubUrlTagIDs: [1, 2, 3] },
        [],
        10,
      );
      expect(el.attr("data-utub-url-tag-ids")).toBe("1,2,3");
    });

    it("sets data-utub-url-tag-ids to empty string when the URL has no tags", () => {
      const el = createURLBlock({ ...baseURL, utubUrlTagIDs: [] }, [], 10);
      expect(el.attr("data-utub-url-tag-ids")).toBe("");
    });
  });

  describe("conditional rendering based on canDelete", () => {
    it("uses createURLTitle (not update block) when canDelete is false", () => {
      createURLBlock({ ...baseURL, canDelete: false }, [], 10);
      expect(vi.mocked(createURLTitle)).toHaveBeenCalledOnce();
      expect(vi.mocked(createURLTitleAndUpdateBlock)).not.toHaveBeenCalled();
    });

    it("uses createURLTitleAndUpdateBlock (not simple title) when canDelete is true", () => {
      createURLBlock({ ...baseURL, canDelete: true }, [], 10);
      expect(vi.mocked(createURLTitleAndUpdateBlock)).toHaveBeenCalledOnce();
      expect(vi.mocked(createURLTitle)).not.toHaveBeenCalled();
    });

    it("uses createURLString (not update block) when canDelete is false", () => {
      createURLBlock({ ...baseURL, canDelete: false }, [], 10);
      expect(vi.mocked(createURLString)).toHaveBeenCalledOnce();
      expect(vi.mocked(createURLStringAndUpdateBlock)).not.toHaveBeenCalled();
    });

    it("uses createURLStringAndUpdateBlock (not simple string) when canDelete is true", () => {
      createURLBlock({ ...baseURL, canDelete: true }, [], 10);
      expect(vi.mocked(createURLStringAndUpdateBlock)).toHaveBeenCalledOnce();
      expect(vi.mocked(createURLString)).not.toHaveBeenCalled();
    });
  });

  describe("event listener setup", () => {
    it("calls setURLCardSelectionEventListener with the card element", () => {
      const el = createURLBlock(baseURL, [], 10);
      expect(
        vi.mocked(setURLCardSelectionEventListener),
      ).toHaveBeenCalledOnce();
      expect(vi.mocked(setURLCardSelectionEventListener)).toHaveBeenCalledWith(
        el,
      );
    });

    it("calls createGoToURLIcon with the URL string", () => {
      createURLBlock({ ...baseURL, urlString: "https://example.com" }, [], 10);
      expect(vi.mocked(createGoToURLIcon)).toHaveBeenCalledWith(
        "https://example.com",
      );
    });
  });
});
