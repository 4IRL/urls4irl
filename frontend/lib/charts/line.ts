/**
 * Pure-function line geometry for SVG `<polyline>` chart elements.
 *
 * No DOM access. Returns the `points="x1,y1 x2,y2 ..."` attribute string
 * for a `<polyline>` given a numeric series and a vertical scale function.
 */

/**
 * Build the `points` attribute string for a `<polyline>` from a values series.
 *
 * X positions are evenly spaced across `width` so that the first point sits at
 * `x = 0` and the last point sits at `x = width`. With `values.length === 1`
 * the single point sits at `x = 0`. With an empty `values` array the function
 * returns `""` (an `<polyline>` with no points renders as nothing).
 *
 * Y positions come from the caller-supplied `scaleY` so units / inversion can
 * be handled by the scale rather than baked in here.
 */
export function buildPolylinePoints({
  values,
  width,
  height,
  scaleY,
}: {
  values: number[];
  width: number;
  height: number;
  scaleY: (n: number) => number;
}): string {
  void height;

  if (values.length === 0) {
    return "";
  }

  if (values.length === 1) {
    const onlyValue = values[0]!;
    return `0,${scaleY(onlyValue)}`;
  }

  const stepX = width / (values.length - 1);
  return values
    .map((value, index) => `${index * stepX},${scaleY(value)}`)
    .join(" ");
}
