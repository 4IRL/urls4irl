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
