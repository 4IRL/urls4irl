import { computeFittedFontPx } from "../header-fit.js";

describe("computeFittedFontPx", () => {
  const baseFontPx = 32;
  const minFontPx = 16;

  describe("content already fits at base font", () => {
    it("returns baseFontPx when content is narrower than the container", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 100,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(baseFontPx);
    });

    it("returns baseFontPx when content exactly equals the container (no upscaling above base)", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 200,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(baseFontPx);
    });
  });

  describe("content overflows the container", () => {
    it("scales font proportionally (content 2x container -> half base, still above min)", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 400,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(16);
    });

    it("rounds the scaled font to the nearest integer pixel", () => {
      // 32 * 200 / 300 = 21.333... -> rounds to 21
      expect(
        computeFittedFontPx({
          contentWidthPx: 300,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(21);
    });

    it("never returns below minFontPx when the proportional value would dip under it", () => {
      // 32 * 200 / 500 = 12.8 -> would round to 13, clamped up to min 16
      expect(
        computeFittedFontPx({
          contentWidthPx: 500,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(minFontPx);
    });
  });

  describe("content hugely overflows (wrap-at-min case)", () => {
    it("clamps exactly to minFontPx when content is 10x the container", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 2000,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(minFontPx);
    });
  });

  describe("degenerate inputs are no-ops returning baseFontPx", () => {
    it("returns baseFontPx when containerWidthPx is 0", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 400,
          containerWidthPx: 0,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(baseFontPx);
    });

    it("returns baseFontPx when contentWidthPx is 0", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 0,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(baseFontPx);
    });

    it("returns baseFontPx when contentWidthPx is non-finite (NaN)", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: NaN,
          containerWidthPx: 200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(baseFontPx);
    });

    it("returns baseFontPx when containerWidthPx is non-finite (Infinity)", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 400,
          containerWidthPx: Infinity,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(baseFontPx);
    });

    it("returns baseFontPx when a width is negative", () => {
      expect(
        computeFittedFontPx({
          contentWidthPx: 400,
          containerWidthPx: -200,
          baseFontPx,
          minFontPx,
        }),
      ).toBe(baseFontPx);
    });
  });
});
