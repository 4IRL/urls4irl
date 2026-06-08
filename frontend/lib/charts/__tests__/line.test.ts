import { buildPolylinePoints } from "../line.js";
import { linearScale } from "../scale.js";

const CHART_WIDTH = 400;
const CHART_HEIGHT = 200;

function buildScaleY(): (n: number) => number {
  return linearScale({ domain: [0, 100], range: [CHART_HEIGHT, 0] });
}

describe("buildPolylinePoints", () => {
  it("returns an empty string for an empty series", () => {
    const points = buildPolylinePoints({
      values: [],
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY: buildScaleY(),
    });
    expect(points).toBe("");
  });

  it("places a single point at x = 0", () => {
    const points = buildPolylinePoints({
      values: [42],
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY: buildScaleY(),
    });
    // scaleY(42) with domain [0,100] -> range [200,0] = 200 - 42 * 2 = 116.
    expect(points).toBe("0,116");
  });

  it("evenly spaces x positions and maps y through scaleY", () => {
    const points = buildPolylinePoints({
      values: [0, 50, 100],
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY: buildScaleY(),
    });
    // 3 values -> step = width / 2 = 200.
    // y values: 200, 100, 0.
    expect(points).toBe("0,200 200,100 400,0");
  });

  it("emits flat-line points for an all-zero series at the baseline", () => {
    const points = buildPolylinePoints({
      values: [0, 0, 0, 0],
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY: buildScaleY(),
    });
    expect(points).toBe(
      "0,200 133.33333333333334,200 266.6666666666667,200 400,200",
    );
  });

  it("anchors the last point at x = width", () => {
    const points = buildPolylinePoints({
      values: [10, 20, 30, 40, 50],
      width: CHART_WIDTH,
      height: CHART_HEIGHT,
      scaleY: buildScaleY(),
    });
    const segments = points.split(" ");
    const [lastX] = segments[segments.length - 1]!.split(",");
    expect(Number(lastX)).toBe(CHART_WIDTH);
  });
});
