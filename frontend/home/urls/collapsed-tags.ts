import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { makeDebouncer } from "../../lib/debounce.js";
import { fillTemplate } from "../../lib/string-template.js";
import { getState } from "../../store/app-store.js";
import { effectiveTagDisplaySettings } from "../tags/display-settings.js";

const log = debug("urls-collapsed-tags");

const DECK_SELECTOR = "#URLDeck";
const COLLAPSED_TAGS_ATTR = "data-collapsed-tags";
const ROW_SELECTOR = ".urlRow";
const TAGS_CONTAINER_SELECTOR = ".urlTagsContainer";
const MORE_CLASS = "tagBadgeMore";
const OVERFLOW_CLASS = "tagBadgeOverflow";
const RESIZE_DEBOUNCE_MS = 150;
// Transient drop badges are never counted or hidden.
const TRANSIENT_BADGE_SELECTOR = ".tagDropGhost, .tagDropExisting";
const LINE_VIEW_MODES = ["title_line", "url_line"];

type CollapsedTagsMode = "off" | "one_line" | "all";

let observer: MutationObserver | null = null;

/** The deck attribute value for the resolved settings. Unknown values are "off". */
function resolveCollapsedTagsMode(): CollapsedTagsMode {
  if (getState().activeUTubID === null) return "off";
  const { showTagsOnCollapsed, collapsedTagsStyle } =
    effectiveTagDisplaySettings();
  if (!showTagsOnCollapsed) return "off";
  if (collapsedTagsStyle === "one_line") return "one_line";
  if (collapsedTagsStyle === "all") return "all";
  return "off";
}

/** Mirrors the resolved collapsed-tags setting onto `#URLDeck` for the CSS. */
export function applyCollapsedTagsAttr(): void {
  const deck = document.querySelector<HTMLElement>(DECK_SELECTOR);
  if (deck === null) {
    log("applyCollapsedTagsAttr: #URLDeck missing, skipping");
    return;
  }
  deck.setAttribute(COLLAPSED_TAGS_ATTR, resolveCollapsedTagsMode());
}

function isRowVisible(row: HTMLElement): boolean {
  return (
    row.getAttribute("filterable") !== "false" &&
    row.getAttribute("searchable") !== "false"
  );
}

function candidateBadges(container: Element): HTMLElement[] {
  return Array.from(
    container.querySelectorAll<HTMLElement>(":scope > .tagBadge"),
  ).filter(
    (badge) =>
      !badge.classList.contains(MORE_CLASS) &&
      !badge.matches(TRANSIENT_BADGE_SELECTOR),
  );
}

function buildMoreBadge(): {
  badge: HTMLElement;
  setCount: (count: number) => void;
} {
  const badge = document.createElement("span");
  badge.className = `tagBadge ${MORE_CLASS}`;
  const visual = document.createElement("span");
  visual.setAttribute("aria-hidden", "true");
  const spoken = document.createElement("span");
  spoken.className = "visually-hidden";
  badge.append(visual, spoken);
  const setCount = (count: number): void => {
    visual.textContent = `+${count}`;
    spoken.textContent =
      count === 1
        ? APP_CONFIG.strings.TAG_MORE_COUNT_ONE
        : fillTemplate({
            template: APP_CONFIG.strings.TAG_MORE_COUNT,
            values: { n: String(count) },
          });
  };
  return { badge, setCount };
}

function clearOverflow(container: Element): void {
  container
    .querySelectorAll(`:scope > .${MORE_CLASS}`)
    .forEach((more) => more.remove());
  container
    .querySelectorAll(`:scope > .${OVERFLOW_CLASS}`)
    .forEach((badge) => badge.classList.remove(OVERFLOW_CLASS));
}

/** Hides the badges that wrap past the first line and appends a "+N" badge. */
function applyOneLineOverflow(container: HTMLElement): void {
  const badges = candidateBadges(container);
  if (badges.length < 2) return;
  const firstTop = badges[0].offsetTop;
  // Measure every badge before hiding any: hiding reflows the line, so a shorter
  // later badge could otherwise move up and stay visible.
  const wrapped = badges.map((badge) => badge.offsetTop > firstTop);
  badges.forEach((badge, index) => {
    if (wrapped[index]) badge.classList.add(OVERFLOW_CLASS);
  });
  let hiddenCount = badges.filter((badge) =>
    badge.classList.contains(OVERFLOW_CLASS),
  ).length;
  if (hiddenCount === 0) return;

  const { badge: more, setCount } = buildMoreBadge();
  setCount(hiddenCount);
  container.append(more);
  // "+N" itself must fit on the first line: hide trailing badges until it does.
  let lastVisible = badges.length - hiddenCount - 1;
  while (more.offsetTop > firstTop && lastVisible > 0) {
    badges[lastVisible].classList.add(OVERFLOW_CLASS);
    lastVisible -= 1;
    hiddenCount += 1;
    setCount(hiddenCount);
  }
}

function syncRow({
  row,
  mode,
}: {
  row: HTMLElement;
  mode: CollapsedTagsMode;
}): void {
  const container = row.querySelector<HTMLElement>(TAGS_CONTAINER_SELECTOR);
  if (container === null) return;
  const isCollapsed = row.getAttribute("urlSelected") !== "true";
  if (isCollapsed) {
    // Selection restores tabindex 0 through enableTabbingOnURLCardElements.
    row
      .querySelectorAll(".urlTagBtnDelete")
      .forEach((button) => button.setAttribute("tabindex", "-1"));
  }
  clearOverflow(container);
  if (!isCollapsed || mode !== "one_line" || !isRowVisible(row)) return;
  applyOneLineOverflow(container);
}

function observe(): void {
  if (observer === null) return;
  const deck = document.querySelector(DECK_SELECTOR);
  if (deck !== null) {
    observer.observe(deck, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["urlSelected", "filterable", "searchable"],
    });
  }
  observer.observe(document.body, {
    attributes: true,
    attributeFilter: ["data-view", "data-density"],
  });
}

/**
 * Recomputes every visible collapsed row's one-line overflow ("+N" badge) and
 * keeps collapsed badge delete buttons out of the tab order. Our own DOM writes
 * are not observed.
 */
export function refreshCollapsedTagOverflow(): void {
  observer?.disconnect();
  try {
    const mode = resolveCollapsedTagsMode();
    const lineView = LINE_VIEW_MODES.includes(document.body.dataset.view ?? "");
    document
      .querySelectorAll<HTMLElement>(`${DECK_SELECTOR} ${ROW_SELECTOR}`)
      .forEach((row) => syncRow({ row, mode: lineView ? "off" : mode }));
  } finally {
    observe();
  }
}

/**
 * Re-runs the overflow on a debounced resize and on any DOM change that can move
 * a badge: add, remove or rename, card select or deselect, filter or search
 * reveal, view or density change.
 */
export function initCollapsedTagOverflow(): () => void {
  const debouncedRefresh = makeDebouncer(
    refreshCollapsedTagOverflow,
    RESIZE_DEBOUNCE_MS,
  );
  observer?.disconnect();
  observer = new MutationObserver(() => refreshCollapsedTagOverflow());
  window.addEventListener("resize", debouncedRefresh);
  refreshCollapsedTagOverflow();
  return () => {
    window.removeEventListener("resize", debouncedRefresh);
    observer?.disconnect();
    observer = null;
  };
}
