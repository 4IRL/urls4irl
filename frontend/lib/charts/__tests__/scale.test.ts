import { linearScale, niceTicks } from "../scale.js";

describe("linearScale", () => {
  it("maps a midpoint domain value to a midpoint range value", () => {
    const scale = linearScale({ domain: [0, 100], range: [0, 1] });
    expect(scale(50)).toBe(0.5);
  });

  it("maps the domain min/max to the range min/max", () => {
    const scale = linearScale({ domain: [10, 20], range: [100, 200] });
    expect(scale(10)).toBe(100);
    expect(scale(20)).toBe(200);
  });

  it("returns the range midpoint for any input when the domain is collapsed", () => {
    const scale = linearScale({ domain: [5, 5], range: [0, 200] });
    expect(scale(5)).toBe(100);
    expect(scale(999)).toBe(100);
    expect(scale(-42)).toBe(100);
  });

  it("supports inverted ranges (e.g. SVG y-axis top-down)", () => {
    const scale = linearScale({ domain: [0, 10], range: [240, 0] });
    expect(scale(0)).toBe(240);
    expect(scale(10)).toBe(0);
    expect(scale(5)).toBe(120);
  });
});

describe("niceTicks", () => {
  it("produces a clean 0/25/50/75/100 tick series for 0..95 at count=5", () => {
    expect(niceTicks({ min: 0, max: 95, count: 5 })).toEqual([
      0, 25, 50, 75, 100,
    ]);
  });

  it("handles negative min values", () => {
    const ticks = niceTicks({ min: -3, max: 4, count: 5 });
    expect(ticks[0]).toBeLessThanOrEqual(-3);
    expect(ticks[ticks.length - 1]!).toBeGreaterThanOrEqual(4);
    // All steps equal — this is what makes the ticks "nice".
    const stepSize = ticks[1]! - ticks[0]!;
    for (let pairIndex = 1; pairIndex < ticks.length - 1; pairIndex += 1) {
      expect(ticks[pairIndex + 1]! - ticks[pairIndex]!).toBeCloseTo(
        stepSize,
        10,
      );
    }
    // Zero must appear in any tick series that spans a sign change.
    expect(ticks).toContain(0);
  });

  it("collapses to a single tick when min === max", () => {
    expect(niceTicks({ min: 7, max: 7, count: 5 })).toEqual([7]);
    expect(niceTicks({ min: 0, max: 0, count: 4 })).toEqual([0]);
  });

  it("produces sub-unit ticks for fractional ranges without FP drift", () => {
    const ticks = niceTicks({ min: 0, max: 1, count: 5 });
    expect(ticks[0]).toBe(0);
    expect(ticks[ticks.length - 1]!).toBeGreaterThanOrEqual(1);
    // No tick should carry visible floating-point noise like 0.30000000000000004.
    for (const tickValue of ticks) {
      expect(Number(tickValue.toFixed(10))).toBe(tickValue);
    }
  });
});
