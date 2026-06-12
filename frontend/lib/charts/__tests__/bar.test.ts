import { buildBarAttrs, buildStackedBarSegments } from "../bar.js";
import { linearScale } from "../scale.js";

const CHART_WIDTH = 400;
const CHART_HEIGHT = 200;

function buildScaleY(): (n: number) => number {
  return linearScale({ domain: [0, 100], range: [CHART_HEIGHT, 0] });
}

describe("buildBarAttrs", () => {
  it("places the first bar at x = 0 with the expected column width and gap", () => {
    const scaleY = buildScaleY();
    const attrs = buildBarAttrs({
      value: 50,
      index: 0,
      total: 4,
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY,
    });
    expect(attrs.x).toBe(0);
    // 400 / 4 = 100 column width × 0.9 = 90 bar width.
    expect(attrs.width).toBe(90);
    expect(attrs.y).toBe(100);
    expect(attrs.height).toBe(100);
  });

  it("advances X by one column width per index", () => {
    const scaleY = buildScaleY();
    const second = buildBarAttrs({
      value: 25,
      index: 1,
      total: 4,
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY,
    });
    const third = buildBarAttrs({
      value: 75,
      index: 2,
      total: 4,
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY,
    });
    expect(second.x).toBe(100);
    expect(third.x).toBe(200);
  });

  it("produces zero-height bars for zero values (visual baseline)", () => {
    const scaleY = buildScaleY();
    const allZero = [0, 0, 0].map((value, index) =>
      buildBarAttrs({
        value,
        index,
        total: 3,
        width: CHART_WIDTH,
        height: CHART_HEIGHT,
        scaleY,
      }),
    );
    for (const attrs of allZero) {
      expect(attrs.height).toBe(0);
      expect(attrs.y).toBe(CHART_HEIGHT);
    }
  });

  it("handles a single-point series (total = 1) without divide errors", () => {
    const scaleY = buildScaleY();
    const attrs = buildBarAttrs({
      value: 100,
      index: 0,
      total: 1,
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY,
    });
    expect(attrs.x).toBe(0);
    expect(attrs.width).toBe(CHART_WIDTH * 0.9);
    expect(attrs.y).toBe(0);
    expect(attrs.height).toBe(CHART_HEIGHT);
  });

  it("returns a zero-size bar when total <= 0 (empty series guard)", () => {
    const scaleY = buildScaleY();
    const attrs = buildBarAttrs({
      value: 50,
      index: 0,
      total: 0,
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY,
    });
    expect(attrs.x).toBe(0);
    expect(attrs.width).toBe(0);
    expect(attrs.height).toBe(0);
    expect(attrs.y).toBe(CHART_HEIGHT);
  });
});

describe("buildStackedBarSegments", () => {
  it("returns [] for an empty segment list", () => {
    const scaleY = buildScaleY();
    const rects = buildStackedBarSegments({
      segments: [],
      index: 0,
      total: 4,
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY,
    });
    expect(rects).toEqual([]);
  });

  it("matches buildBarAttrs for a single-segment column at the same value", () => {
    const scaleY = buildScaleY();
    const singleAttrs = buildBarAttrs({
      value: 50,
      index: 1,
      total: 4,
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY,
    });
    const stacked = buildStackedBarSegments({
      segments: [{ value: 50, className: "swatch--solo" }],
      index: 1,
      total: 4,
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY,
    });
    expect(stacked.length).toBe(1);
    const [stackedRect] = stacked;
    expect(stackedRect.x).toBe(singleAttrs.x);
    expect(stackedRect.width).toBe(singleAttrs.width);
    expect(stackedRect.y).toBe(singleAttrs.y);
    expect(stackedRect.height).toBe(singleAttrs.height);
    expect(stackedRect.className).toBe("swatch--solo");
  });

  it("stacks two segments bottom-to-top so the upper segment's y is above the lower's y", () => {
    const scaleY = buildScaleY();
    const stacked = buildStackedBarSegments({
      segments: [
        { value: 20, className: "swatch--bottom" },
        { value: 30, className: "swatch--top" },
      ],
      index: 0,
      total: 2,
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY,
    });
    expect(stacked.length).toBe(2);
    const [bottomRect, topRect] = stacked;
    // SVG y-axis grows downward, so a "higher" rect in viewer space has a
    // SMALLER y. The top segment must satisfy y2 < y1 when stacked above.
    expect(topRect.y).toBeLessThan(bottomRect.y);
    // The top of the bottom rect equals the bottom of the top rect when they
    // share a column — the seam is exactly `bottomRect.y` and the next rect's
    // (y + height) should land on the same coordinate.
    expect(topRect.y + topRect.height).toBeCloseTo(bottomRect.y);
  });

  it("preserves the per-segment className verbatim", () => {
    const scaleY = buildScaleY();
    const stacked = buildStackedBarSegments({
      segments: [
        { value: 10, className: "swatch--fetch-desktop" },
        { value: 10, className: "swatch--fetch-mobile" },
        { value: 10, className: "swatch--beacon-desktop" },
        { value: 10, className: "swatch--beacon-mobile" },
      ],
      index: 0,
      total: 1,
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY,
    });
    expect(stacked.map((rect) => rect.className)).toEqual([
      "swatch--fetch-desktop",
      "swatch--fetch-mobile",
      "swatch--beacon-desktop",
      "swatch--beacon-mobile",
    ]);
  });

  it("never lets the total stack height exceed the container height", () => {
    const scaleY = buildScaleY();
    const stacked = buildStackedBarSegments({
      segments: [
        { value: 30, className: "swatch--a" },
        { value: 30, className: "swatch--b" },
        { value: 30, className: "swatch--c" },
      ],
      index: 0,
      total: 1,
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY,
    });
    const totalHeight = stacked.reduce((sum, rect) => sum + rect.height, 0);
    expect(totalHeight).toBeLessThanOrEqual(CHART_HEIGHT);
  });
});
