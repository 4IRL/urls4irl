import {
  clamp,
  FLING_VELOCITY_PX_PER_MS,
  shouldCommitSwipeGesture,
  SNAP_DISTANCE_FRACTION,
} from "../url-swipe-snap.js";

describe("shouldCommitSwipeGesture", () => {
  it("does NOT commit when draggedFraction is below threshold alone (velocity 0)", () => {
    expect(
      shouldCommitSwipeGesture({
        draggedFraction: SNAP_DISTANCE_FRACTION - 0.05,
        velocity: 0,
      }),
    ).toBe(false);
  });

  it("commits when velocity meets the fling threshold alone with a small draggedFraction", () => {
    expect(
      shouldCommitSwipeGesture({
        draggedFraction: 0.1,
        velocity: FLING_VELOCITY_PX_PER_MS + 0.1,
      }),
    ).toBe(true);
  });

  it("does NOT commit when both draggedFraction and velocity are below threshold (snap-back)", () => {
    expect(
      shouldCommitSwipeGesture({
        draggedFraction: SNAP_DISTANCE_FRACTION - 0.05,
        velocity: FLING_VELOCITY_PX_PER_MS - 0.1,
      }),
    ).toBe(false);
  });

  it("commits at exactly the snap distance threshold (boundary equality)", () => {
    expect(
      shouldCommitSwipeGesture({
        draggedFraction: SNAP_DISTANCE_FRACTION,
        velocity: 0,
      }),
    ).toBe(true);
  });

  it("commits at exactly the fling velocity threshold (boundary equality)", () => {
    expect(
      shouldCommitSwipeGesture({
        draggedFraction: 0,
        velocity: FLING_VELOCITY_PX_PER_MS,
      }),
    ).toBe(true);
  });

  it("does NOT commit with negative velocity (finger reversed) at a small draggedFraction", () => {
    expect(
      shouldCommitSwipeGesture({
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
