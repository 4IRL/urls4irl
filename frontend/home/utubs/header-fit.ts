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

// Debounce window (ms) for the resize listener that re-fits the header/subheader.
const RESIZE_DEBOUNCE_MS = 150;

// Guards initURLDeckHeaderFit() so the single window resize listener is
// attached exactly once even if init is called more than once.
let headerFitInitialized = false;

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

/**
 * Measure a single element's natural single-line width, compute the fitted font
 * via computeFittedFontPx, and write it to the element's inline style.fontSize.
 * Thin DOM layer over the pure math — uses native DOM APIs only (no jQuery).
 */
export function fitElementFont({
  element,
  baseFontPx,
  minFontPx,
}: {
  element: HTMLElement;
  baseFontPx: number;
  minFontPx: number;
}): void {
  // Skip hidden/disconnected elements (e.g. a deck not currently shown):
  // measuring them yields 0-width geometry and would produce a wrong fit.
  // offsetParent is null for any element in a display:none subtree (the case
  // that matters for hidden decks), so it reliably detects that here.
  const isVisible = element.offsetParent !== null;
  if (!isVisible) return;

  // Need the parent to measure available width; a disconnected element has none.
  if (!element.parentElement) return;

  // Available width = parent's content width minus the width of every sibling
  // sharing the parent's flex space (e.g. the pencil-icon span next to the title).
  const rawContainerWidthPx = element.parentElement.clientWidth;
  let siblingWidthPx = 0;
  for (const child of element.parentElement.children) {
    if (child !== element) siblingWidthPx += (child as HTMLElement).offsetWidth;
  }
  const containerWidthPx = rawContainerWidthPx - siblingWidthPx;

  // IMPORTANT: steps 2-4 (set whiteSpace nowrap -> read scrollWidth -> restore
  // whiteSpace) must stay synchronous — no await, setTimeout, or
  // requestAnimationFrame between them; any async gap renders the nowrap state
  // visible as a one-frame flicker.
  element.style.fontSize = baseFontPx + "px";
  const previousWhiteSpace = element.style.whiteSpace;
  element.style.whiteSpace = "nowrap";
  const contentWidthPx = element.scrollWidth;
  element.style.whiteSpace = previousWhiteSpace;

  const fittedPx = computeFittedFontPx({
    contentWidthPx,
    containerWidthPx,
    baseFontPx,
    minFontPx,
  });
  // The element was already set to base before measuring, so only write on a
  // change to avoid a redundant style mutation when the text already fits.
  if (fittedPx !== baseFontPx) element.style.fontSize = fittedPx + "px";
}

/**
 * Re-fit both the selected UTub's title (#URLDeckHeader) and description
 * (#URLDeckSubheader) to their current container width. The single no-arg entry
 * point every text-write call site invokes after changing the displayed text.
 */
export function fitUTubHeaderAndSubheader(): void {
  const headerElement = document.getElementById("URLDeckHeader");
  if (headerElement)
    fitElementFont({
      element: headerElement,
      baseFontPx: TITLE_MAX_FONT_PX,
      minFontPx: TITLE_MIN_FONT_PX,
    });

  const subheaderElement = document.getElementById("URLDeckSubheader");
  if (subheaderElement)
    fitElementFont({
      element: subheaderElement,
      baseFontPx: DESC_MAX_FONT_PX,
      minFontPx: DESC_MIN_FONT_PX,
    });
}

/**
 * Attach the single debounced window resize listener that re-fits the header and
 * subheader, and run one immediate fit so the initial render is sized correctly.
 *
 * This is the first window-resize listener in the home view. matchMedia
 * (used elsewhere for breakpoint crossings) is insufficient here: it fires only
 * when a breakpoint is crossed, not on the continuous width changes that change
 * how much text fits on one line, so a dedicated resize listener is required.
 */
export function initURLDeckHeaderFit(): void {
  if (headerFitInitialized) return;
  headerFitInitialized = true;

  let resizeDebounceTimer: ReturnType<typeof setTimeout> | undefined;
  window.addEventListener("resize", () => {
    if (resizeDebounceTimer !== undefined) clearTimeout(resizeDebounceTimer);
    resizeDebounceTimer = setTimeout(
      fitUTubHeaderAndSubheader,
      RESIZE_DEBOUNCE_MS,
    );
  });

  fitUTubHeaderAndSubheader();
}
