import { createTagBadgesAndWrap } from "../tags.js";

vi.mock("../create.js", () => ({
  createURLTag: vi.fn(),
  hideAndResetCreateURLTagForm: vi.fn(),
}));

vi.mock("../delete.js", () => ({
  deleteURLTag: vi.fn(),
}));

const $ = window.jQuery;

describe("createTagBadgesAndWrap - missing tag ID guard", () => {
  beforeEach(() => {
    document.body.innerHTML = `<div class="urlRow"></div>`;
  });

  it("skips tag IDs that are not present in dictTags and throws no error", () => {
    const urlCard = $(".urlRow");
    const dictTags = [{ id: 1, tagString: "exists" }];
    const tagArray = [999]; // 999 is absent from dictTags

    let wrap;
    expect(() => {
      wrap = createTagBadgesAndWrap(dictTags, tagArray, urlCard, 42);
    }).not.toThrow();

    // Wrap was created but no badges appended since the one tag ID was missing
    expect(wrap.hasClass("urlTagsContainer")).toBe(true);
    expect(wrap.children().length).toBe(0);
  });

  it("appends a badge only for tag IDs that exist in dictTags", () => {
    const urlCard = $(".urlRow");
    const dictTags = [
      { id: 1, tagString: "exists" },
      { id: 2, tagString: "other" },
    ];
    const tagArray = [1, 999, 2]; // 999 missing; 1 and 2 present

    const wrap = createTagBadgesAndWrap(dictTags, tagArray, urlCard, 42);

    expect(wrap.children().length).toBe(2);
  });
});
