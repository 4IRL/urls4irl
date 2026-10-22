// Selection indicator overlay for the UTub menu: a bar (and, in later steps, a
// shimmer) positioned over the selected row. The module never owns the
// `active` class; it follows it with a MutationObserver on #listUTubs, which
// sees every writer (selectUTub, setUTubDeckOnUTubSelected, transfer, ...).
// Positions are measured only when the selection or layout changes, and only
// transform / opacity are ever written.

const INDICATOR_ID = "UTubSelectionIndicator";
const LIST_ID = "listUTubs";
const ROW_SELECTOR = ".UTubSelector";
const ACTIVE_ROW_SELECTOR = ".UTubSelector.active";
const BAR_SELECTOR = ".utubSelectionBar";
const SHIMMER_CLIP_SELECTOR = ".utubSelectionShimmerClip";
const ANNOUNCE_CLASS = "utubSelectedAnnounce";
const VISIBLE_CLASS = "isVisible";
const IDLE_CLASS = "isIdle";

export const STRETCH_MS = 420;
export const STRETCH_EASING = "cubic-bezier(.5, 0, .2, 1)";
export const STRETCH_MID_OFFSET = 0.45;
export const IDLE_REARM_MS = 300;

type PlacedBox = { utubid: string; top: number; height: number };

// The #listUTubs element the module is currently bound to (idempotency key).
let boundList: HTMLElement | null = null;
let mutationObserver: MutationObserver | null = null;
let pendingFrameId: number | null = null;
let pendingAnimate = false;
let lastPlaced: PlacedBox | null = null;
let stretchAnimation: Animation | null = null;

function getIndicator(): HTMLElement | null {
  return document.getElementById(INDICATOR_ID);
}

function isRendered(row: HTMLElement): boolean {
  return row.offsetParent !== null && row.offsetHeight !== 0;
}

function removeAnnounceNodes({
  list,
  keepIn,
}: {
  list: HTMLElement;
  keepIn: HTMLElement | null;
}): void {
  for (const node of list.querySelectorAll(`.${ANNOUNCE_CLASS}`)) {
    if (keepIn === null || node.parentElement !== keepIn) node.remove();
  }
}

// Keeps aria-current on exactly the active row and the single visually-hidden
// "selected" node inside it (or nowhere). Writes only when something differs,
// so the observer sync triggered by these writes changes nothing.
function syncAria({
  list,
  activeRow,
  label,
  showAnnounce,
}: {
  list: HTMLElement;
  activeRow: HTMLElement | null;
  label: string;
  showAnnounce: boolean;
}): void {
  for (const row of list.querySelectorAll<HTMLElement>(ROW_SELECTOR)) {
    if (row === activeRow) {
      if (row.getAttribute("aria-current") !== "true")
        row.setAttribute("aria-current", "true");
    } else if (row.hasAttribute("aria-current")) {
      row.removeAttribute("aria-current");
    }
  }

  const announceHost = showAnnounce ? activeRow : null;
  removeAnnounceNodes({ list, keepIn: announceHost });
  if (announceHost === null) return;
  const hasNode = Array.from(announceHost.children).some((child) =>
    child.classList.contains(ANNOUNCE_CLASS),
  );
  if (hasNode) return;
  const node = document.createElement("span");
  node.className = `visually-hidden ${ANNOUNCE_CLASS}`;
  node.textContent = label;
  announceHost.appendChild(node);
}

function hideIndicator({
  indicator,
  bar,
  clip,
}: {
  indicator: HTMLElement;
  bar: HTMLElement | null;
  clip: HTMLElement | null;
}): void {
  cancelStretch();
  indicator.classList.remove(VISIBLE_CLASS, IDLE_CLASS);
  for (const part of [bar, clip]) {
    if (part === null) continue;
    part.style.transform = "translateY(0)";
    part.style.height = "";
  }
  lastPlaced = null;
}

function prefersReducedMotion(): boolean {
  return (
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

function cancelStretch(): void {
  if (stretchAnimation === null) return;
  const animation = stretchAnimation;
  stretchAnimation = null;
  animation.cancel();
}

// Reads translateY / scaleY from a computed `matrix(a, b, c, d, tx, ty)`.
// Anything else (`none`, `matrix3d`) yields null and the caller falls back.
function parseBarTransform(
  transform: string,
): { top: number; scaleY: number } | null {
  const matrix = /^matrix\(([^)]+)\)$/.exec(transform.trim());
  if (matrix === null) return null;
  const parts = matrix[1].split(",").map((part) => Number(part));
  if (parts.length !== 6 || !parts.every((part) => Number.isFinite(part)))
    return null;
  return { top: parts[5], scaleY: parts[3] };
}

// The box the bar is rendered at right now (for an interrupted stretch).
function readRunningBox(
  bar: HTMLElement,
): { top: number; height: number } | null {
  const parsed = parseBarTransform(getComputedStyle(bar).transform);
  const inlineHeight = Number.parseFloat(bar.style.height);
  if (parsed === null || !Number.isFinite(inlineHeight)) return null;
  return { top: parsed.top, height: parsed.scaleY * inlineHeight };
}

// Old box, in order: running stretch's computed box; a fresh measure of the
// previous UTub's row if still rendered; the stored lastPlaced box.
function chooseOldBox({
  list,
  bar,
  previous,
}: {
  list: HTMLElement;
  bar: HTMLElement;
  previous: PlacedBox;
}): { top: number; height: number } {
  if (stretchAnimation !== null) {
    const running = readRunningBox(bar);
    if (running !== null) return running;
  }
  for (const row of list.querySelectorAll<HTMLElement>(ROW_SELECTOR)) {
    if (row.getAttribute("utubid") !== previous.utubid) continue;
    if (isRendered(row))
      return { top: row.offsetTop, height: row.offsetHeight };
    break;
  }
  return { top: previous.top, height: previous.height };
}

function startStretch({
  list,
  bar,
  previous,
  target,
}: {
  list: HTMLElement;
  bar: HTMLElement;
  previous: PlacedBox;
  target: PlacedBox;
}): void {
  // Read the start box before cancel() and before the new inline writes.
  const oldBox = chooseOldBox({ list, bar, previous });
  cancelStretch();
  const unionTop = Math.min(oldBox.top, target.top);
  const unionBottom = Math.max(
    oldBox.top + oldBox.height,
    target.top + target.height,
  );
  const frame = ({ top, height }: { top: number; height: number }): string =>
    `translateY(${top}px) scaleY(${height / target.height})`;

  // Final state first, so cancelling the animation leaves the bar on target.
  bar.style.height = `${target.height}px`;
  bar.style.transform = `translateY(${target.top}px) scaleY(1)`;

  const animation = bar.animate(
    [
      { transform: frame(oldBox) },
      {
        transform: frame({ top: unionTop, height: unionBottom - unionTop }),
        offset: STRETCH_MID_OFFSET,
      },
      { transform: frame(target) },
    ],
    { duration: STRETCH_MS, easing: STRETCH_EASING },
  );
  stretchAnimation = animation;
  // A cancelled animation rejects `finished` with AbortError; ignore it.
  animation.finished
    .then(() => {
      if (stretchAnimation === animation) stretchAnimation = null;
    })
    .catch(() => undefined);
}

function placeIndicator({
  indicator,
  list,
  bar,
  clip,
  row,
  animate,
}: {
  indicator: HTMLElement;
  list: HTMLElement;
  bar: HTMLElement | null;
  clip: HTMLElement | null;
  row: HTMLElement;
  animate: boolean;
}): void {
  const target: PlacedBox = {
    utubid: row.getAttribute("utubid") ?? "",
    top: row.offsetTop,
    height: row.offsetHeight,
  };
  const wasVisible = indicator.classList.contains(VISIBLE_CLASS);
  // An unchanged target is a no-op for every `animate` value: no cancel, no
  // restart of a running stretch, no redundant style writes.
  if (
    lastPlaced !== null &&
    lastPlaced.utubid === target.utubid &&
    lastPlaced.top === target.top &&
    lastPlaced.height === target.height &&
    wasVisible
  )
    return;

  // A stretch starts only for a different UTub between two rendered rows.
  const previous = lastPlaced;
  const stretches =
    animate &&
    wasVisible &&
    previous !== null &&
    previous.utubid !== target.utubid &&
    bar !== null &&
    typeof bar.animate === "function" &&
    !prefersReducedMotion();

  if (stretches) {
    startStretch({ list, bar, previous, target });
  } else {
    cancelStretch();
    if (bar !== null) {
      bar.style.height = `${target.height}px`;
      bar.style.transform = `translateY(${target.top}px) scaleY(1)`;
    }
  }
  if (clip !== null) {
    clip.style.height = `${target.height}px`;
    clip.style.transform = `translateY(${target.top}px)`;
  }
  indicator.classList.add(VISIBLE_CLASS);
  lastPlaced = target;
}

function applySelection(): void {
  const animate = pendingAnimate;
  pendingAnimate = false;
  const indicator = getIndicator();
  const list = document.getElementById(LIST_ID);
  if (indicator === null || list === null || list !== boundList) return;

  const bar = indicator.querySelector<HTMLElement>(BAR_SELECTOR);
  const clip = indicator.querySelector<HTMLElement>(SHIMMER_CLIP_SELECTOR);
  const activeRow = list.querySelector<HTMLElement>(ACTIVE_ROW_SELECTOR);
  const shouldShow = activeRow !== null && isRendered(activeRow);

  syncAria({
    list,
    activeRow,
    label: indicator.dataset.selectedLabel ?? "",
    showAnnounce: shouldShow,
  });

  if (activeRow === null || !shouldShow) {
    hideIndicator({ indicator, bar, clip });
    return;
  }
  placeIndicator({ indicator, list, bar, clip, row: activeRow, animate });
}

/**
 * Request a placement of the indicator on the active row. Requests within one
 * frame collapse into a single rAF sync whose `animate` is the OR of them.
 */
export function syncUTubSelectionIndicator({
  animate,
}: {
  animate: boolean;
}): void {
  // Before init (or after teardown) there is nothing bound: silent no-op.
  if (boundList === null || getIndicator() === null) return;
  pendingAnimate = pendingAnimate || animate;
  if (pendingFrameId !== null) return;
  pendingFrameId = requestAnimationFrame(() => {
    pendingFrameId = null;
    applySelection();
  });
}

function teardown(): void {
  if (mutationObserver !== null) {
    mutationObserver.disconnect();
    mutationObserver = null;
  }
  if (pendingFrameId !== null) {
    cancelAnimationFrame(pendingFrameId);
    pendingFrameId = null;
  }
  pendingAnimate = false;
  cancelStretch();
  lastPlaced = null;
  boundList = null;
  getIndicator()?.classList.remove(VISIBLE_CLASS, IDLE_CLASS);
}

/**
 * Bind the indicator to #listUTubs. Idempotent for the same element; a
 * replaced #listUTubs first tears down the old bindings.
 */
export function initUTubSelectionIndicator(): void {
  const list = document.getElementById(LIST_ID);
  if (getIndicator() === null || list === null) return;
  if (boundList === list) return;
  teardown();

  boundList = list;
  if (typeof MutationObserver !== "undefined") {
    mutationObserver = new MutationObserver(() =>
      syncUTubSelectionIndicator({ animate: true }),
    );
    mutationObserver.observe(list, {
      subtree: true,
      childList: true,
      attributes: true,
      attributeFilter: ["class"],
    });
  }
  syncUTubSelectionIndicator({ animate: false });
}

/** Test-only: the one internal teardown (releases registrations, resets state). */
export function resetUTubSelectionIndicatorForTests(): void {
  teardown();
}
