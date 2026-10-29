import type { UtubSortValue } from "../../types/preferences.js";
import type { UtubSummaryItem } from "../../types/utub.js";

import { $ } from "../../lib/globals.js";
import { getState, setState } from "../../store/app-store.js";
import { applyAlternatingUTubSelectorBackground } from "./search.js";

// Leaf module: imports only types, the store and search.ts. It must not import
// deck.ts, utils.ts or list-preferences.ts (list-preferences.ts imports this).

function toMillis(timestamp: string): number {
  return new Date(timestamp).getTime();
}

function recencyMillis(utub: UtubSummaryItem): number {
  const updated = toMillis(utub.lastUpdated);
  if (utub.lastOpenedAt === null) return updated;
  return Math.max(toMillis(utub.lastOpenedAt), updated);
}

// Approximates Python's str.casefold(): the upper/lower round trip performs the
// full case mapping ("ß" -> "SS" -> "ss") that a bare toLowerCase() skips. Folds
// per code point so toLowerCase() never applies the context-dependent final-sigma
// rule, and maps a final "ς" to "σ" like casefold().
function foldName(name: string): string {
  return Array.from(name, (char) => char.toUpperCase().toLowerCase())
    .join("")
    .replace(/ς/g, "σ");
}

// Orders by Unicode code point like Python's str comparison. A plain `<` compares
// UTF-16 code units, which puts astral characters (surrogate pairs) before
// U+E000-U+FFFF. Never localeCompare / Intl.Collator, which diverge on accents.
function compareCodePoints({
  left,
  right,
}: {
  left: string;
  right: string;
}): number {
  let leftIndex = 0;
  let rightIndex = 0;
  while (leftIndex < left.length && rightIndex < right.length) {
    const leftPoint = left.codePointAt(leftIndex) as number;
    const rightPoint = right.codePointAt(rightIndex) as number;
    if (leftPoint !== rightPoint) return leftPoint < rightPoint ? -1 : 1;
    const width = leftPoint > 0xffff ? 2 : 1;
    leftIndex += width;
    rightIndex += width;
  }
  if (leftIndex < left.length) return 1;
  if (rightIndex < right.length) return -1;
  return 0;
}

// Descending comparison of two numbers, so the larger one sorts first.
function descending({
  first,
  second,
}: {
  first: number;
  second: number;
}): number {
  return second - first;
}

// Mirrors the server's sort rules (see _sort_summary_memberships): the chosen
// key, then utub id ascending as the final tie-break.
export function compareUTubs({
  left,
  right,
  sort,
}: {
  left: UtubSummaryItem;
  right: UtubSummaryItem;
  sort: UtubSortValue;
}): number {
  let primary = 0;
  switch (sort) {
    case "last_opened": {
      // Opened rows first by open time; never-opened rows after, by created.
      const leftOpened = left.lastOpenedAt;
      const rightOpened = right.lastOpenedAt;
      if (leftOpened !== null && rightOpened !== null) {
        primary = descending({
          first: toMillis(leftOpened),
          second: toMillis(rightOpened),
        });
      } else if (leftOpened !== null || rightOpened !== null) {
        primary = leftOpened !== null ? -1 : 1;
      } else {
        primary = descending({
          first: toMillis(left.createdAt),
          second: toMillis(right.createdAt),
        });
      }
      break;
    }
    case "name_az":
      primary = compareCodePoints({
        left: foldName(left.name),
        right: foldName(right.name),
      });
      break;
    case "newest_created":
      primary = descending({
        first: toMillis(left.createdAt),
        second: toMillis(right.createdAt),
      });
      break;
    case "oldest_created":
      primary = toMillis(left.createdAt) - toMillis(right.createdAt);
      break;
    case "recent_activity":
    default:
      primary = descending({
        first: recencyMillis(left),
        second: recencyMillis(right),
      });
      break;
  }
  return primary !== 0 ? primary : left.id - right.id;
}

// Stamps a UTub's lastOpenedAt with the current time in the store only (no deck
// reorder), so a later switch to a time-based sort orders from fresh data.
export function markUTubOpened({ utubID }: { utubID: number }): void {
  const openedAt = new Date().toISOString();
  setState({
    utubs: getState().utubs.map((utub) =>
      utub.id === utubID ? { ...utub, lastOpenedAt: openedAt } : utub,
    ),
  });
}

// Re-appends the existing rows in the store's sorted order in one pass,
// preserving .hidden, .active and listeners, then restripes. A moved node drops
// focus to body, so a focused row is re-focused afterwards. Scrolling is the
// caller's job.
export function reorderUTubDeck(sort: UtubSortValue): void {
  const sorted = [...getState().utubs].sort((left, right) =>
    compareUTubs({ left, right, sort }),
  );
  setState({ utubs: sorted });

  const parent = $("#listUTubs");
  const focused = document.activeElement;
  const rowsByID = new Map<string, HTMLElement>();
  parent.children(".UTubSelector").each((_, row) => {
    rowsByID.set(String($(row).attr("utubid")), row);
  });

  let position = 0;
  const reappend = (row: HTMLElement): void => {
    $(row).attr("position", position);
    parent.append(row);
    position += 1;
  };
  for (const utub of sorted) {
    const row = rowsByID.get(String(utub.id));
    if (row === undefined) continue;
    rowsByID.delete(String(utub.id));
    reappend(row);
  }
  // Rows the store does not know about keep their relative order at the end.
  rowsByID.forEach(reappend);

  applyAlternatingUTubSelectorBackground();

  if (
    focused instanceof HTMLElement &&
    focused.classList.contains("UTubSelector") &&
    document.activeElement !== focused
  ) {
    focused.focus({ preventScroll: true });
  }
}

// Rule-based, never a client-vs-server timestamp comparison, so a skewed client
// clock cannot misplace a just-created UTub: it is the newest on every
// time-based sort (first), the youngest on oldest_created (last), and only
// name_az compares (names need no clock).
function newUTubInsertIndex({
  utub,
  utubs,
  sort,
}: {
  utub: UtubSummaryItem;
  utubs: UtubSummaryItem[];
  sort: UtubSortValue;
}): number {
  switch (sort) {
    case "oldest_created":
      return utubs.length;
    case "name_az": {
      const index = utubs.findIndex(
        (other) => compareUTubs({ left: utub, right: other, sort }) < 0,
      );
      return index === -1 ? utubs.length : index;
    }
    case "recent_activity":
    case "last_opened":
    case "newest_created":
    default:
      return 0;
  }
}

// Inserts a freshly created UTub's row into both the store and the deck at its
// sorted place, renumbers the position attributes and restripes.
export function insertNewUTubRow({
  utub,
  row,
  sort,
}: {
  utub: UtubSummaryItem;
  row: JQuery<HTMLElement>;
  sort: UtubSortValue;
}): void {
  const utubs = getState().utubs;
  const index = newUTubInsertIndex({ utub, utubs, sort });
  setState({
    utubs: [...utubs.slice(0, index), utub, ...utubs.slice(index)],
  });

  const parent = $("#listUTubs");
  const existing = parent.children(".UTubSelector");
  if (index < existing.length) {
    $(existing[index]).before(row);
  } else {
    parent.append(row);
  }
  parent.children(".UTubSelector").each((position, element) => {
    $(element).attr("position", position);
  });
  applyAlternatingUTubSelectorBackground();
}

function nearestScrollParent(row: HTMLElement): HTMLElement {
  let current = row.parentElement;
  while (current !== null) {
    const overflowY = window.getComputedStyle(current).overflowY;
    if (overflowY === "auto" || overflowY === "scroll") return current;
    current = current.parentElement;
  }
  return $("#listUTubs")[0];
}

function scrollRowIntoView(row: HTMLElement): void {
  // jsdom does not implement scrollIntoView.
  if (typeof row.scrollIntoView !== "function") return;
  row.scrollIntoView({ block: "nearest", behavior: "instant" });
}

// Scrolls a UTub's row into view unconditionally, unless a name filter hides it.
// Never moves focus.
export function scrollUTubRowIntoView({ utubID }: { utubID: number }): void {
  const row = $(`#listUTubs > .UTubSelector[utubid="${utubID}"]`)[0];
  if (row === undefined || row.classList.contains("hidden")) return;
  scrollRowIntoView(row);
}

// After a sort change: scrolls the active row back only if it left the deck's
// scroll viewport. Does nothing when it is visible or no row is active. Never
// moves focus.
export function scrollActiveUTubIntoViewIfHidden(): void {
  const row = $("#listUTubs > .UTubSelector.active")[0];
  if (row === undefined) return;
  const rowRect = row.getBoundingClientRect();
  const viewport = nearestScrollParent(row).getBoundingClientRect();
  if (rowRect.top >= viewport.top && rowRect.bottom <= viewport.bottom) return;
  scrollRowIntoView(row);
}

// After a user rename: under name_az moves the row to its new place and scrolls
// it into view when that place changed. Other sorts keep the order until a rebuild.
export function reorderAfterRename({ utubID }: { utubID: number }): void {
  const sort = getState().preferences.utubSort;
  if (sort !== "name_az") return;
  const indexOf = (): number =>
    getState().utubs.findIndex((utub) => utub.id === utubID);
  const before = indexOf();
  reorderUTubDeck(sort);
  if (indexOf() !== before) scrollUTubRowIntoView({ utubID });
}

// Stale-data name sync: sets the row text, then reorders under name_az. Never
// scrolls; reorderUTubDeck keeps focus on a moved focused row.
export function syncRowNameAndOrder({
  utubID,
  utubName,
}: {
  utubID: number;
  utubName: string;
}): void {
  $(`.UTubSelector[utubid="${utubID}"] .UTubName`).text(utubName);
  const sort = getState().preferences.utubSort;
  if (sort === "name_az") reorderUTubDeck(sort);
}
