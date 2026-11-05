import { readTagCount, writeTagCount } from "../utils.js";

const STYLES = ["in_view_total", "total_only", "hidden"] as const;

function buildChip(): JQuery {
  return $(
    '<div class="tagFilter"><div class="tagCountWrap">' +
      '<span class="tagAppliedToUrlsCount">' +
      '<span class="tagCountInView">3</span>' +
      '<span class="tagCountSep"> / </span>' +
      '<span class="tagCountTotal">7</span>' +
      "</span></div></div>",
  );
}

describe("readTagCount / writeTagCount", () => {
  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("reads the two numbers off their spans", () => {
    expect(readTagCount(buildChip())).toEqual({ inView: 3, total: 7 });
  });

  it.each(STYLES)("round-trips a written count in the %s style", (style) => {
    document.body.innerHTML = `<div id="TagDeck" data-tag-count-style="${style}"></div>`;
    const chip = buildChip();
    $("#TagDeck").append(chip);

    writeTagCount({ chip, inView: 5, total: 9 });

    expect(readTagCount(chip)).toEqual({ inView: 5, total: 9 });
    expect(chip.find(".tagCountInView").text()).toBe("5");
    expect(chip.find(".tagCountTotal").text()).toBe("9");
  });

  it.each(["total_only", "hidden"] as const)(
    "still updates the in-view span while the style is %s",
    (style) => {
      document.body.innerHTML = `<div id="TagDeck" data-tag-count-style="${style}"></div>`;
      const chip = buildChip();
      $("#TagDeck").append(chip);

      writeTagCount({ chip, inView: 0, total: 7 });

      expect(chip.find(".tagCountInView").text()).toBe("0");
    },
  );

  it("returns null for a chip with no count markup", () => {
    expect(readTagCount($('<div class="tagFilter"></div>'))).toBeNull();
  });

  it("returns null when a number span is not numeric", () => {
    const chip = buildChip();
    chip.find(".tagCountInView").text("malformed");
    expect(readTagCount(chip)).toBeNull();
  });
});
