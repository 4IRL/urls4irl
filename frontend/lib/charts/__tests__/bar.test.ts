import { buildBarAttrs } from "../bar.js";
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
