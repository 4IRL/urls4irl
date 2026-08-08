import { createURLBlock, formatDateByPreference } from "../cards.js";
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
vi.mock("../../tags/combobox.js", () => ({
  ComboboxMode: { URL: "url", CREATE: "create" },
  createTagComboboxBlock: vi.fn(() =>
    window.jQuery('<div class="urlTagComboboxWrap"></div>'),
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
  addedAt: "2024-03-09T12:00:00+00:00",
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

    it("has flex-column, full-width, pointerable classes", () => {
      const el = createURLBlock(baseURL, [], 10);
      expect(el.hasClass("flex-column")).toBe(true);
      expect(el.hasClass("full-width")).toBe(true);
      expect(el.hasClass("pointerable")).toBe(true);
    });

    it("has urlRowContent wrapping the row's content", () => {
      const el = createURLBlock(baseURL, [], 10);
      const content = el.find("> .urlRowContent");
      expect(content.length).toBe(1);
      expect(content.hasClass("flex-column")).toBe(true);
      expect(content.hasClass("full-width")).toBe(true);
      expect(content.find(".urlString").length).toBe(1);
      expect(content.find(".urlTagsContainer").length).toBe(1);
      expect(content.find(".urlOptions").length).toBe(1);
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

    it("renders .urlRowSwipeReveal when canDelete is true", () => {
      const el = createURLBlock({ ...baseURL, canDelete: true }, [], 10);
      expect(el.find(".urlRowSwipeReveal").length).toBe(1);
      const icon = el.find(".urlRowSwipeRevealIcon");
      expect(icon.length).toBe(1);
      expect(icon.find("svg").length).toBe(1);
    });

    it("does not render .urlRowSwipeReveal when canDelete is false", () => {
      const el = createURLBlock({ ...baseURL, canDelete: false }, [], 10);
      expect(el.find(".urlRowSwipeReveal").length).toBe(0);
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

  describe("date-added badge", () => {
    it("renders an inline <time>.urlDateAddedBadge with datetime, aria-label, and Added-prefixed text", () => {
      const el = createURLBlock(
        { ...baseURL, addedAt: "2024-03-09T12:00:00+00:00" },
        [],
        10,
      );
      const badge = el.find(".urlDateAddedBadgeInline");
      expect(badge.length).toBe(1);
      expect(badge.hasClass("urlDateAddedBadge")).toBe(true);
      expect(badge.prop("tagName")).toBe("TIME");
      expect(badge.attr("datetime")).toBe("2024-03-09T12:00:00+00:00");
      // Visible text is Added-prefixed; default preference is ISO (YYYY-MM-DD).
      expect(badge.text()).toBe("Added: 2024-03-09");
      expect(badge.attr("aria-label")).toBe("Added 2024-03-09");
    });

    it("places the inline badge on the URL-string row, right-most after the URL string", () => {
      const el = createURLBlock(baseURL, [], 10);
      const stringRow = el.find(".urlStringRow");
      expect(stringRow.length).toBe(1);
      // The row lives inside .urlRowContent (above the swipe-reveal layer).
      expect(stringRow.closest(".urlRowContent").length).toBe(1);
      // Inline badge is a direct child of the URL-string row...
      const badge = stringRow.children(".urlDateAddedBadgeInline");
      expect(badge.length).toBe(1);
      // ...and is the right-most (last) element on that row...
      expect(
        stringRow.children().last().hasClass("urlDateAddedBadgeInline"),
      ).toBe(true);
      // ...sitting after the URL-string block (the <a>.urlString).
      expect(stringRow.children().first().hasClass("urlString")).toBe(true);
    });

    it("renders a mobile stacked badge as the last row of the card, below the buttons row", () => {
      const el = createURLBlock(
        { ...baseURL, addedAt: "2024-03-09T12:00:00+00:00" },
        [],
        10,
      );
      const rowContent = el.find(".urlRowContent");
      const stacked = rowContent.children(".urlDateAddedBadgeStacked");
      expect(stacked.length).toBe(1);
      expect(stacked.hasClass("urlDateAddedBadge")).toBe(true);
      expect(stacked.prop("tagName")).toBe("TIME");
      expect(stacked.attr("datetime")).toBe("2024-03-09T12:00:00+00:00");
      expect(stacked.text()).toBe("Added: 2024-03-09");
      // It is the last child of .urlRowContent (after the tags/options row)...
      expect(
        rowContent.children().last().hasClass("urlDateAddedBadgeStacked"),
      ).toBe(true);
      // ...specifically following the buttons row (.tagsAndButtonsWrap).
      expect(stacked.prev().hasClass("tagsAndButtonsWrap")).toBe(true);
    });
  });
});

describe("formatDateByPreference", () => {
  const FIXTURE_ISO = "2024-03-09T12:00:00+00:00";
  const expectedByFormat = {
    iso: "2024-03-09",
    us: "03/09/2024",
    eu: "09/03/2024",
  } as const;

  it.each(["iso", "us", "eu"] as const)(
    "formats a fixed ISO date for '%s'",
    (dateFormat) => {
      expect(formatDateByPreference(FIXTURE_ISO, dateFormat)).toBe(
        expectedByFormat[dateFormat],
      );
    },
  );
});
