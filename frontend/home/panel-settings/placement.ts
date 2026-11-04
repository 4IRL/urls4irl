export interface PlacementRect {
  top: number;
  bottom: number;
  left: number;
  right: number;
}

export interface PopoverPlacement {
  left: number;
  top: number;
  /** Set only when the card must shrink (and scroll) to avoid its gear. */
  maxHeight: number | null;
  side: "below" | "above";
}

/**
 * Pure desktop popover placement. The card never covers its gear: below the
 * gear when its natural height fits, else above, else on the roomier side with
 * a max-height so the card scrolls instead of overlapping. Right edges align
 * with the gear; the horizontal position is clamped into the viewport.
 */
export function computePopoverPlacement({
  gearRect,
  width,
  naturalHeight,
  viewportWidth,
  viewportHeight,
  margin,
  gap,
}: {
  gearRect: PlacementRect;
  width: number;
  naturalHeight: number;
  viewportWidth: number;
  viewportHeight: number;
  margin: number;
  gap: number;
}): PopoverPlacement {
  const maxLeft = Math.max(margin, viewportWidth - width - margin);
  const left = Math.min(Math.max(gearRect.right - width, margin), maxLeft);

  const roomBelow = Math.max(
    0,
    viewportHeight - gearRect.bottom - gap - margin,
  );
  const roomAbove = Math.max(0, gearRect.top - gap - margin);

  if (naturalHeight <= roomBelow) {
    return {
      left,
      top: gearRect.bottom + gap,
      maxHeight: null,
      side: "below",
    };
  }
  if (naturalHeight <= roomAbove) {
    return {
      left,
      top: gearRect.top - gap - naturalHeight,
      maxHeight: null,
      side: "above",
    };
  }
  if (roomBelow >= roomAbove) {
    return {
      left,
      top: gearRect.bottom + gap,
      maxHeight: roomBelow,
      side: "below",
    };
  }
  return {
    left,
    top: gearRect.top - gap - roomAbove,
    maxHeight: roomAbove,
    side: "above",
  };
}
