/**
 * Pure-function bar geometry for SVG `<rect>` chart elements.
 *
 * No DOM access. Given a data point, its index in a series, and a vertical
 * scale function, returns the four attributes required to draw the bar.
 */

const BAR_GAP_FRACTION = 0.9;

/**
 * Compute the four SVG `<rect>` attributes for a single bar.
 *
 * Bar column width = `width / total * 0.9` (leaves a 10% gap between bars).
 * Bar X = `index * (width / total)` (no leading gap; consistent column origin).
 * Bar Y = `scaleY(value)` (mapped through caller's vertical scale).
 * Bar height = `height - scaleY(value)` so the rect grows downward from the
 * data point's mapped Y to the chart baseline.
 */
export function buildBarAttrs({
  value,
  index,
  total,
  width,
  height,
  scaleY,
}: {
  value: number;
  index: number;
  total: number;
  width: number;
  height: number;
  scaleY: (n: number) => number;
}): { x: number; y: number; width: number; height: number } {
  if (total <= 0) {
    return { x: 0, y: height, width: 0, height: 0 };
  }

  const columnWidth = width / total;
  const barWidth = columnWidth * BAR_GAP_FRACTION;
  const barX = index * columnWidth;
  const barY = scaleY(value);
  const barHeight = Math.max(0, height - barY);

  return { x: barX, y: barY, width: barWidth, height: barHeight };
}

type StackedBarSegment = { value: number; className: string };

/**
 * Compute the rect attributes for a vertical stacked bar at column `index`.
 *
 * Walks `segments` bottom-to-top, accumulating the running total and emitting
 * one rect per segment with `y = height - scaleY(runningTotal + value)` and
 * `height = scaleY(value) - scaleY(0)` (equivalent to the unscaled delta after
 * accounting for the chart's flipped vertical axis). The caller is responsible
 * for skipping segments whose `height === 0`; this primitive returns every
 * segment so callers can inspect zero-value entries (e.g., for accessibility
 * announcements) without re-doing the layout math.
 *
 * Column geometry (`x`, `width`) matches `buildBarAttrs` so single-bar and
 * stacked-bar charts share consistent column placement at the same `index`/
 * `total`/`width` triple.
 */
export function buildStackedBarSegments({
  segments,
  index,
  total,
  width,
  height: _height,
  scaleY,
}: {
  segments: readonly StackedBarSegment[];
  index: number;
  total: number;
  width: number;
  height: number;
  scaleY: (n: number) => number;
}): ReadonlyArray<{
  x: number;
  y: number;
  width: number;
  height: number;
  className: string;
}> {
  if (segments.length === 0) {
    return [];
  }
  if (total <= 0) {
    return [];
  }

  const columnWidth = width / total;
  const barWidth = columnWidth * BAR_GAP_FRACTION;
  const barX = index * columnWidth;

  const rects: {
    x: number;
    y: number;
    width: number;
    height: number;
    className: string;
  }[] = [];
  let cumulativeValue = 0;
  for (const segment of segments) {
    const segmentTop = cumulativeValue + segment.value;
    const segmentY = scaleY(segmentTop);
    const segmentHeight = Math.max(
      0,
      scaleY(cumulativeValue) - scaleY(segmentTop),
    );
    rects.push({
      x: barX,
      y: segmentY,
      width: barWidth,
      height: segmentHeight,
      className: segment.className,
    });
    cumulativeValue = segmentTop;
  }
  return rects;
}
