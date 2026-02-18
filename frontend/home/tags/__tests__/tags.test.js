import { buildTagFilterInDeck } from "../tags.js";

vi.mock("../delete.js", () => ({ deleteUTubTagShowModal: vi.fn() }));
vi.mock("../unselect-all.js", () => ({
  enableUnselectAllButtonAfterTagFilterApplied: vi.fn(),
  disableUnselectAllButtonAfterTagFilterRemoved: vi.fn(),
}));
vi.mock("../../urls/cards/filtering.js", () => ({
  updateURLsAndTagSubheaderWhenTagSelected: vi.fn(),
}));

const $ = window.jQuery;

describe("buildTagFilterInDeck", () => {
  describe("element structure", () => {
    it("returns a jQuery element", () => {
      const el = buildTagFilterInDeck(1, 10, "my-tag");
      expect(el.length).toBe(1);
    });

    it("has tagFilter, pointerable, unselected, col-12 classes", () => {
      const el = buildTagFilterInDeck(1, 10, "my-tag");
      expect(el.hasClass("tagFilter")).toBe(true);
      expect(el.hasClass("pointerable")).toBe(true);
      expect(el.hasClass("unselected")).toBe(true);
      expect(el.hasClass("col-12")).toBe(true);
    });

    it("sets data-utub-tag-id attribute to tagID", () => {
      const el = buildTagFilterInDeck(1, 42, "my-tag");
      expect(el.attr("data-utub-tag-id")).toBe("42");
    });

    it("sets tabindex to 0", () => {
      const el = buildTagFilterInDeck(1, 10, "my-tag");
      expect(el.attr("tabindex")).toBe("0");
    });

    it("contains a span with the tag string as its text content", () => {
      const el = buildTagFilterInDeck(1, 10, "cool-tag");
      expect(el.children("span").first().text()).toBe("cool-tag");
    });

    it("contains a .tagCountWrap container", () => {
      const el = buildTagFilterInDeck(1, 10, "tag");
      expect(el.find(".tagCountWrap").length).toBe(1);
    });

    it("contains a .tagMenuWrap container with the hidden class", () => {
      const el = buildTagFilterInDeck(1, 10, "tag");
      const menuWrap = el.find(".tagMenuWrap");
      expect(menuWrap.length).toBe(1);
      expect(menuWrap.hasClass("hidden")).toBe(true);
    });

    it("contains a .utubTagBtnDelete button", () => {
      const el = buildTagFilterInDeck(1, 10, "tag");
      expect(el.find(".utubTagBtnDelete").length).toBe(1);
    });
  });

  describe("url count display", () => {
    it("shows '0 / 0' when urlCount defaults to 0", () => {
      const el = buildTagFilterInDeck(1, 10, "tag");
      expect(el.find(".tagAppliedToUrlsCount").text()).toBe("0 / 0");
    });

    it("shows 'N / N' when urlCount is provided", () => {
      const el = buildTagFilterInDeck(1, 10, "tag", 7);
      expect(el.find(".tagAppliedToUrlsCount").text()).toBe("7 / 7");
    });

    it("uses the same value for both the visible and total count", () => {
      const el = buildTagFilterInDeck(1, 10, "tag", 3);
      expect(el.find(".tagAppliedToUrlsCount").text()).toBe("3 / 3");
    });
  });
});
