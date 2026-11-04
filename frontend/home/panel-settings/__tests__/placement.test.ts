import { describe, expect, it } from "vitest";
import { computePopoverPlacement } from "../placement.js";
import type { PlacementRect } from "../placement.js";

const BASE = {
  width: 340,
  viewportWidth: 1280,
  viewportHeight: 900,
  margin: 8,
  gap: 6,
};

function gearAt({ top, right }: { top: number; right: number }): PlacementRect {
  return { top, bottom: top + 30, left: right - 30, right };
}

function overlapsGear({
  placement,
  gearRect,
  height,
}: {
  placement: { left: number; top: number };
  gearRect: PlacementRect;
  height: number;
}): boolean {
  const horizontal =
    placement.left < gearRect.right &&
    placement.left + BASE.width > gearRect.left;
  const vertical =
    placement.top < gearRect.bottom && placement.top + height > gearRect.top;
  return horizontal && vertical;
}

describe("computePopoverPlacement", () => {
  it("goes below the gear when the natural height fits", () => {
    const gearRect = gearAt({ top: 100, right: 900 });
    const placement = computePopoverPlacement({
      ...BASE,
      gearRect,
      naturalHeight: 300,
    });
    expect(placement).toEqual({
      left: 560,
      top: 136,
      maxHeight: null,
      side: "below",
    });
  });

  it("flips above when it does not fit below but fits above", () => {
    const gearRect = gearAt({ top: 617, right: 900 });
    const placement = computePopoverPlacement({
      ...BASE,
      gearRect,
      naturalHeight: 400,
    });
    expect(placement.side).toBe("above");
    expect(placement.maxHeight).toBeNull();
    expect(placement.top).toBe(617 - 6 - 400);
    expect(overlapsGear({ placement, gearRect, height: 400 })).toBe(false);
  });

  it("uses the larger side with a max-height when neither fits", () => {
    const gearRect = gearAt({ top: 617, right: 900 });
    const placement = computePopoverPlacement({
      ...BASE,
      gearRect,
      naturalHeight: 800,
    });
    // above: 617 - 6 - 8 = 603; below: 900 - 647 - 6 - 8 = 239
    expect(placement.side).toBe("above");
    expect(placement.maxHeight).toBe(603);
    expect(placement.top).toBe(8);
    expect(overlapsGear({ placement, gearRect, height: 603 })).toBe(false);
  });

  it("caps below when the gear is near the top and the card is too tall", () => {
    const gearRect = gearAt({ top: 40, right: 900 });
    const placement = computePopoverPlacement({
      ...BASE,
      gearRect,
      naturalHeight: 2000,
    });
    expect(placement.side).toBe("below");
    expect(placement.top).toBe(76);
    expect(placement.maxHeight).toBe(900 - 70 - 6 - 8);
  });

  it("clamps horizontally into the viewport on both sides", () => {
    const left = computePopoverPlacement({
      ...BASE,
      gearRect: gearAt({ top: 100, right: 100 }),
      naturalHeight: 200,
    });
    expect(left.left).toBe(8);
    const right = computePopoverPlacement({
      ...BASE,
      gearRect: gearAt({ top: 100, right: 1400 }),
      naturalHeight: 200,
    });
    expect(right.left).toBe(1280 - 340 - 8);
  });

  it("never overlaps the gear across a sweep of positions and heights", () => {
    for (let top = 0; top <= 870; top += 29) {
      for (const naturalHeight of [100, 350, 600, 1200]) {
        const gearRect = gearAt({ top, right: 900 });
        const placement = computePopoverPlacement({
          ...BASE,
          gearRect,
          naturalHeight,
        });
        const height = Math.min(
          naturalHeight,
          placement.maxHeight ?? naturalHeight,
        );
        expect(overlapsGear({ placement, gearRect, height })).toBe(false);
      }
    }
  });
});
