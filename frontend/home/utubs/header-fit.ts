// Font sizes (px) for the selected UTub's title (#URLDeckHeader) and
// description (#URLDeckSubheader). The fit logic scales each element's font
// down from its max toward its min as the text gets longer; once the min is
// reached, CSS wraps the text to as many lines as needed.
// NOTE: these values are mirrored in backend/utils/strings/ui_testing_strs.py
// (TITLE_MAX_FONT_PX, TITLE_MIN_FONT_PX, DESC_MAX_FONT_PX, DESC_MIN_FONT_PX) for
// Selenium assertions — keep both files in sync when changing any font value.
export const TITLE_MAX_FONT_PX = 32; // ≈ 2rem
export const TITLE_MIN_FONT_PX = 16; // 1rem
export const DESC_MAX_FONT_PX = 20; // ≈ 1.25rem
export const DESC_MIN_FONT_PX = 14; // 0.875rem

/**
 * Compute the font size (px) that scales the text's natural single-line width
 * down to fit its container, clamped to the inclusive range [minFontPx,
 * baseFontPx]. Pure and layout-free so it can be unit-tested deterministically;
 * the real geometry is read by the DOM wrapper that calls this.
 *
 * The font never grows above baseFontPx (text that already fits is left at
 * base) and never shrinks below minFontPx (the "wrap at min" case — CSS then
 * wraps the over-long text). Degenerate inputs (zero, negative, or non-finite
 * widths, e.g. happy-dom returning 0 for scrollWidth) are no-ops that return
 * baseFontPx so the result is never 0, NaN, or Infinity.
 *
 * Examples:
 *   computeFittedFontPx({ contentWidthPx: 100, containerWidthPx: 200, baseFontPx: 32, minFontPx: 16 }) === 32  // already fits
 *   computeFittedFontPx({ contentWidthPx: 400, containerWidthPx: 200, baseFontPx: 32, minFontPx: 16 }) === 16  // 2x over -> half base, hits min
 *   computeFittedFontPx({ contentWidthPx: 300, containerWidthPx: 200, baseFontPx: 32, minFontPx: 16 }) === 21  // 32*200/300 = 21.33 -> rounded
 *   computeFittedFontPx({ contentWidthPx: 2000, containerWidthPx: 200, baseFontPx: 32, minFontPx: 16 }) === 16 // 10x over -> clamped to min
 *   computeFittedFontPx({ contentWidthPx: 400, containerWidthPx: 0, baseFontPx: 32, minFontPx: 16 }) === 32    // degenerate -> base
 */
export function computeFittedFontPx({
  contentWidthPx,
  containerWidthPx,
  baseFontPx,
  minFontPx,
}: {
  contentWidthPx: number;
  containerWidthPx: number;
  baseFontPx: number;
  minFontPx: number;
}): number {
  const hasMeasurableWidths =
    Number.isFinite(contentWidthPx) &&
    Number.isFinite(containerWidthPx) &&
    contentWidthPx > 0 &&
    containerWidthPx > 0;
  if (!hasMeasurableWidths) return baseFontPx;

  if (contentWidthPx <= containerWidthPx) return baseFontPx;

  const scaledFontPx = Math.round(
    (baseFontPx * containerWidthPx) / contentWidthPx,
  );
  return Math.max(minFontPx, scaledFontPx);
}
