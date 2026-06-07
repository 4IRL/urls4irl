import { buildAxisTicks, formatBucketLabel } from "../axis.js";
import { linearScale } from "../scale.js";

describe("buildAxisTicks", () => {
  it("returns an empty array when no ticks are supplied", () => {
    const result = buildAxisTicks({
      ticks: [],
      scale: linearScale({ domain: [0, 100], range: [0, 200] }),
      axisLength: 200,
    });
    expect(result).toEqual([]);
  });

  it("maps each tick through the scale and stringifies the label", () => {
    const scale = linearScale({ domain: [0, 100], range: [0, 200] });
    const result = buildAxisTicks({
      ticks: [0, 50, 100],
      scale,
      axisLength: 200,
    });
    expect(result).toEqual([
      { position: 0, label: "0" },
      { position: 100, label: "50" },
      { position: 200, label: "100" },
    ]);
  });

  it("supports a single tick (collapsed domain)", () => {
    const scale = linearScale({ domain: [5, 5], range: [0, 200] });
    const result = buildAxisTicks({
      ticks: [5],
      scale,
      axisLength: 200,
    });
    expect(result).toEqual([{ position: 100, label: "5" }]);
  });
});

describe("formatBucketLabel", () => {
  it("renders hour resolution as HH:MM in UTC", () => {
    expect(
      formatBucketLabel({ iso: "2026-06-06T14:00:00Z", resolution: "hour" }),
    ).toBe("14:00");
  });

  it("renders day resolution as 'MMM DD' in UTC", () => {
    expect(
      formatBucketLabel({ iso: "2026-06-06T00:00:00Z", resolution: "day" }),
    ).toBe("Jun 06");
  });

  it("does not drift across local-time-zone boundaries (midnight UTC)", () => {
    // 00:00 UTC must format as "00:00" regardless of host TZ.
    expect(
      formatBucketLabel({ iso: "2026-06-06T00:00:00Z", resolution: "hour" }),
    ).toBe("00:00");
  });

  it("handles end-of-day timestamps in day resolution", () => {
    expect(
      formatBucketLabel({ iso: "2026-12-31T23:59:00Z", resolution: "day" }),
    ).toBe("Dec 31");
  });
});
