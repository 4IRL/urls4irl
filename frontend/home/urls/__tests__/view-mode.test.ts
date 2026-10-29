import {
  isViewMode,
  isWideViewport,
  normalizeViewMode,
  renderedViewMode,
} from "../view-mode.js";

describe("view-mode helpers", () => {
  const originalMatchMedia = window.matchMedia;

  afterEach(() => {
    window.matchMedia = originalMatchMedia;
  });

  it("validates the four known view modes only", () => {
    for (const mode of ["list", "title_line", "url_line", "cards"]) {
      expect(isViewMode(mode)).toBe(true);
    }
    expect(isViewMode("compact")).toBe(false);
    expect(isViewMode(null)).toBe(false);
  });

  it("normalizes an unknown value to list", () => {
    expect(normalizeViewMode("url_line")).toBe("url_line");
    expect(normalizeViewMode("compact")).toBe("list");
    expect(normalizeViewMode(undefined)).toBe("list");
  });

  it("queries exactly (min-width: 992px) and reports its result", () => {
    const matchMedia = vi.fn(() => ({ matches: true }));
    window.matchMedia = matchMedia as unknown as typeof window.matchMedia;
    expect(isWideViewport()).toBe(true);
    expect(matchMedia).toHaveBeenCalledWith("(min-width: 992px)");
  });

  it("is not wide when matchMedia is missing", () => {
    (window as { matchMedia?: unknown }).matchMedia = undefined;
    expect(isWideViewport()).toBe(false);
    expect(renderedViewMode("cards")).toBe("list");
  });
});
