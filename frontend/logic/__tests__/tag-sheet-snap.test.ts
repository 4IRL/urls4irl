import {
  clamp,
  FLING_VELOCITY_PX_PER_MS,
  resolveExpandableSheetRelease,
  shouldCommitSheetGesture,
  SNAP_DISTANCE_FRACTION,
} from "../tag-sheet-snap.js";

describe("shouldCommitSheetGesture", () => {
  it("commits when draggedFraction meets the snap distance even with zero velocity", () => {
    expect(
      shouldCommitSheetGesture({
        draggedFraction: SNAP_DISTANCE_FRACTION + 0.05,
        velocity: 0,
      }),
    ).toBe(true);
  });

  it("commits when velocity meets the fling threshold even with a small draggedFraction", () => {
    expect(
      shouldCommitSheetGesture({
        draggedFraction: 0.1,
        velocity: FLING_VELOCITY_PX_PER_MS + 0.1,
      }),
    ).toBe(true);
  });

  it("does NOT commit when both draggedFraction and velocity are below threshold (snap-back)", () => {
    expect(
      shouldCommitSheetGesture({
        draggedFraction: SNAP_DISTANCE_FRACTION - 0.05,
        velocity: FLING_VELOCITY_PX_PER_MS - 0.1,
      }),
    ).toBe(false);
  });

  it("commits at exactly the snap distance threshold (boundary equality)", () => {
    expect(
      shouldCommitSheetGesture({
        draggedFraction: SNAP_DISTANCE_FRACTION,
        velocity: 0,
      }),
    ).toBe(true);
  });

  it("commits at exactly the fling velocity threshold (boundary equality)", () => {
    expect(
      shouldCommitSheetGesture({
        draggedFraction: 0,
        velocity: FLING_VELOCITY_PX_PER_MS,
      }),
    ).toBe(true);
  });

  it("does NOT commit with negative velocity (finger reversed) at a small draggedFraction", () => {
    expect(
      shouldCommitSheetGesture({
        draggedFraction: 0.1,
        velocity: -1,
      }),
    ).toBe(false);
  });
});

describe("clamp", () => {
  it("returns max when value is greater than max", () => {
    expect(clamp({ value: 450, min: 0, max: 400 })).toBe(400);
  });

  it("returns min when value is less than min", () => {
    expect(clamp({ value: -10, min: 0, max: 400 })).toBe(0);
  });

  it("returns value unchanged when value is within [min, max]", () => {
    expect(clamp({ value: 200, min: 0, max: 400 })).toBe(200);
  });
});

describe("resolveExpandableSheetRelease", () => {
  // range = 300: expand/collapse threshold 105px; dismiss from expanded needs
  // 300 + 140 (35% of the 400 default) of downward travel.
  const heights = { defaultHeight: 400, expandedHeight: 700 };
  const resolve = (args: {
    expanded: boolean;
    delta: number;
    velocity?: number;
  }) => resolveExpandableSheetRelease({ velocity: 0, ...heights, ...args });

  it("expands from default on a long upward drag", () => {
    expect(resolve({ expanded: false, delta: -150 })).toBe("expanded");
  });

  it("expands from default on an upward fling", () => {
    expect(
      resolve({
        expanded: false,
        delta: -20,
        velocity: -(FLING_VELOCITY_PX_PER_MS + 0.1),
      }),
    ).toBe("expanded");
  });

  it("stays default on a short slow upward drag", () => {
    expect(resolve({ expanded: false, delta: -30 })).toBe("default");
  });

  it("stays default when there is no room to expand", () => {
    expect(
      resolveExpandableSheetRelease({
        expanded: false,
        delta: -300,
        velocity: 0,
        defaultHeight: 700,
        expandedHeight: 700,
      }),
    ).toBe("default");
  });

  it("dismisses from default on a long or fast downward drag", () => {
    expect(resolve({ expanded: false, delta: 200 })).toBe("dismiss");
    expect(
      resolve({
        expanded: false,
        delta: 20,
        velocity: FLING_VELOCITY_PX_PER_MS,
      }),
    ).toBe("dismiss");
  });

  it("stays default on a short slow downward drag", () => {
    expect(resolve({ expanded: false, delta: 30 })).toBe("default");
  });

  it("returns from expanded to default on a medium downward drag", () => {
    expect(resolve({ expanded: true, delta: 150 })).toBe("default");
  });

  it("returns from expanded to default (not dismiss) on a fling that has not passed default", () => {
    expect(
      resolve({
        expanded: true,
        delta: 40,
        velocity: FLING_VELOCITY_PX_PER_MS + 0.5,
      }),
    ).toBe("default");
  });

  it("stays expanded on a short downward drag and on any upward drag", () => {
    expect(resolve({ expanded: true, delta: 40 })).toBe("expanded");
    expect(resolve({ expanded: true, delta: -200 })).toBe("expanded");
  });

  it("dismisses from expanded only when dragged well past default", () => {
    expect(resolve({ expanded: true, delta: 300 + 50 })).toBe("default");
    expect(resolve({ expanded: true, delta: 300 + 200 })).toBe("dismiss");
  });

  it("dismisses from expanded on a fling that has passed default", () => {
    expect(
      resolve({
        expanded: true,
        delta: 300 + 20,
        velocity: FLING_VELOCITY_PX_PER_MS,
      }),
    ).toBe("dismiss");
  });

  it("fails closed to default for unusable heights", () => {
    expect(
      resolveExpandableSheetRelease({
        expanded: true,
        delta: 900,
        velocity: 2,
        defaultHeight: 0,
        expandedHeight: 700,
      }),
    ).toBe("default");
  });
});
