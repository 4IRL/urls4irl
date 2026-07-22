import {
  createURLStringAndUpdateBlock,
  modifyURLStringForDisplay,
} from "../url-string.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../update-string.js", () => ({
  updateURL: vi.fn(),
  hideAndResetUpdateURLStringForm: vi.fn(),
  isURLStringSubmitInFlight: vi.fn(() => false),
}));

vi.mock("../access.js", () => ({ accessLink: vi.fn() }));

vi.mock("../url-context.js", () => ({
  isURLSearchActive: vi.fn(() => false),
  getActiveTagCount: vi.fn(() => 0),
}));

const $ = window.jQuery;

describe("modifyURLStringForDisplay", () => {
  it("strips https:// prefix", () => {
    expect(modifyURLStringForDisplay("https://example.com")).toBe(
      "example.com",
    );
  });

  it("strips http:// prefix", () => {
    expect(modifyURLStringForDisplay("http://example.com")).toBe("example.com");
  });

  it("strips www. prefix alone", () => {
    expect(modifyURLStringForDisplay("www.example.com")).toBe("example.com");
  });

  it("strips https://www. combined prefix", () => {
    expect(modifyURLStringForDisplay("https://www.example.com")).toBe(
      "example.com",
    );
  });

  it("strips http://www. combined prefix", () => {
    expect(modifyURLStringForDisplay("http://www.example.com")).toBe(
      "example.com",
    );
  });

  it("preserves path after stripping https://", () => {
    expect(modifyURLStringForDisplay("https://example.com/path/to/page")).toBe(
      "example.com/path/to/page",
    );
  });

  it("preserves path after stripping https://www.", () => {
    expect(modifyURLStringForDisplay("https://www.example.com/path")).toBe(
      "example.com/path",
    );
  });

  it("does not strip non-http protocols", () => {
    expect(modifyURLStringForDisplay("ftp://example.com")).toBe(
      "ftp://example.com",
    );
  });

  it("returns string unchanged when no recognisable prefix is present", () => {
    expect(modifyURLStringForDisplay("example.com")).toBe("example.com");
  });

  it("returns empty string for empty input", () => {
    expect(modifyURLStringForDisplay("")).toBe("");
  });
});

describe("createUpdateURLStringInput - Saved✓ tick slot structure", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function mountStringBlock(): JQuery {
    document.body.innerHTML = `<div class="urlRow" utuburlid="1" urlSelected="true" filterable="true"></div>`;
    const urlCard = $(".urlRow");
    urlCard.append(
      createURLStringAndUpdateBlock("https://example.com", urlCard, 1),
    );
    return urlCard;
  }

  it("hangs .field-saved-tick-slot directly off the wrap as a SIBLING of the inner input row (not nested inside it)", () => {
    const urlCard = mountStringBlock();
    const wrap = urlCard.find(".updateUrlStringWrap");
    const tickSlot = wrap.find(".field-saved-tick-slot");

    expect(tickSlot.length).toBe(1);
    // Core invariant: the tick slot's parent is the wrap itself, so it renders
    // below the input row (guards against a future edit nesting it too deep).
    expect(tickSlot.parent().is(wrap)).toBe(true);

    // The input container moved one level deeper into the new inner row, so it
    // is no longer a direct child of the wrap (the > width selector was updated
    // to a descendant selector to match — Step 3 CSS fix).
    expect(wrap.children(".text-input-container").length).toBe(0);
    expect(wrap.find(".text-input-container").length).toBe(1);

    const tick = tickSlot.find(".field-saved-tick");
    expect(tick.length).toBe(1);
    expect(tick.hasClass("opa-0")).toBe(true);
    expect(tick.attr("aria-hidden")).toBe("true");
  });
});
