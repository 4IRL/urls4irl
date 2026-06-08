/**
 * Draggable splitter between the Top-events table and the Timeseries chart in
 * each metrics-dashboard `.content-row`. Reads/writes the left-pane width as
 * a percentage to a single CSS custom property on `<html>` so all three
 * category tabs share one width, and persists the value to localStorage.
 *
 * Keyboard support: Left/Right arrows nudge, Home/End jump to the clamp ends.
 * Below the stacked-layout breakpoint the resizer is hidden via CSS and the
 * pointer/keyboard handlers no-op naturally (events never fire).
 */

const STORAGE_KEY = "metrics:left-pane-pct";
const CONTAINER_SELECTOR = ".content-row";
const RESIZER_SELECTOR = ".content-row__resizer";
const CSS_VAR = "--metrics-left-pane";
const DRAGGING_CLASS = "is-dragging";
// Container-level state so future drag-only container styling can be added
// independently of the handle's hover state.
const RESIZING_CLASS = "is-resizing";
const BOUND_ATTR = "data-pane-resizer-bound";
const MIN_PCT = 25;
const MAX_PCT = 75;
const KEY_STEP_PCT = 2;
const DEFAULT_PCT = (1.4 / 2.4) * 100;

function clampPct({ pct }: { pct: number }): number {
  if (pct < MIN_PCT) return MIN_PCT;
  if (pct > MAX_PCT) return MAX_PCT;
  return pct;
}

function readStoredPct(): number | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === null) return null;
    const value = Number(raw);
    if (!Number.isFinite(value)) return null;
    return clampPct({ pct: value });
  } catch {
    return null;
  }
}

function writeStoredPct({ pct }: { pct: number }): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, String(pct));
  } catch {
    // localStorage may be disabled (private mode, quota) — silently ignore.
  }
}

function applyPct({ pct }: { pct: number }): void {
  document.documentElement.style.setProperty(CSS_VAR, `${pct}%`);
  const rounded = String(Math.round(pct));
  document
    .querySelectorAll<HTMLElement>(RESIZER_SELECTOR)
    .forEach((resizer) => {
      resizer.setAttribute("aria-valuenow", rounded);
    });
}

function pctFromPointer({
  pointerX,
  container,
}: {
  pointerX: number;
  container: HTMLElement;
}): number {
  const rect = container.getBoundingClientRect();
  if (rect.width === 0) return readStoredPct() ?? DEFAULT_PCT;
  const relativeX = pointerX - rect.left;
  return clampPct({ pct: (relativeX / rect.width) * 100 });
}

function bindResizer({ resizer }: { resizer: HTMLElement }): void {
  const containerOrNull = resizer.closest<HTMLElement>(CONTAINER_SELECTOR);
  if (containerOrNull === null) return;
  const container: HTMLElement = containerOrNull;

  function handlePointerMove(event: PointerEvent): void {
    applyPct({ pct: pctFromPointer({ pointerX: event.clientX, container }) });
  }

  function handlePointerUp(event: PointerEvent): void {
    if (typeof resizer.releasePointerCapture === "function") {
      try {
        resizer.releasePointerCapture(event.pointerId);
      } catch {
        // Capture may already be released (cancel/lostpointercapture).
      }
    }
    resizer.removeEventListener("pointermove", handlePointerMove);
    resizer.removeEventListener("pointerup", handlePointerUp);
    resizer.removeEventListener("pointercancel", handlePointerUp);
    resizer.classList.remove(DRAGGING_CLASS);
    container.classList.remove(RESIZING_CLASS);
    const finalPct = pctFromPointer({
      pointerX: event.clientX,
      container,
    });
    writeStoredPct({ pct: finalPct });
  }

  resizer.addEventListener("pointerdown", (event: PointerEvent) => {
    if (event.button !== 0) return;
    event.preventDefault();
    if (typeof resizer.setPointerCapture === "function") {
      try {
        resizer.setPointerCapture(event.pointerId);
      } catch {
        // Pointer capture is best-effort; absence is non-fatal in JSDOM.
      }
    }
    resizer.classList.add(DRAGGING_CLASS);
    container.classList.add(RESIZING_CLASS);
    resizer.addEventListener("pointermove", handlePointerMove);
    resizer.addEventListener("pointerup", handlePointerUp);
    resizer.addEventListener("pointercancel", handlePointerUp);
  });

  resizer.addEventListener("keydown", (event: KeyboardEvent) => {
    let next: number | null = null;
    const current = readStoredPct() ?? DEFAULT_PCT;
    switch (event.key) {
      case "ArrowLeft":
        next = current - KEY_STEP_PCT;
        break;
      case "ArrowRight":
        next = current + KEY_STEP_PCT;
        break;
      case "Home":
        next = MIN_PCT;
        break;
      case "End":
        next = MAX_PCT;
        break;
    }
    if (next === null) return;
    event.preventDefault();
    const clamped = clampPct({ pct: next });
    applyPct({ pct: clamped });
    writeStoredPct({ pct: clamped });
  });
}

export function initPaneResizers(): void {
  applyPct({ pct: readStoredPct() ?? DEFAULT_PCT });
  document
    .querySelectorAll<HTMLElement>(RESIZER_SELECTOR)
    .forEach((resizer) => {
      if (resizer.hasAttribute(BOUND_ATTR)) return;
      resizer.setAttribute(BOUND_ATTR, "true");
      bindResizer({ resizer });
    });
}

/**
 * Test-only helper: clear stored width, drop the CSS var, and unmark any
 * resizers as bound so the next initPaneResizers() rebinds cleanly.
 */
export function _resetPaneResizersForTests(): void {
  document.documentElement.style.removeProperty(CSS_VAR);
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
  const boundSelector = "[" + BOUND_ATTR + "]";
  const boundElements: NodeListOf<HTMLElement> =
    document.querySelectorAll(boundSelector);
  boundElements.forEach((element: HTMLElement): void => {
    element.removeAttribute(BOUND_ATTR);
  });
}
