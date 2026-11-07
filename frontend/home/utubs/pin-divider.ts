import { $ } from "../../lib/globals.js";
import { rowHasPinMarker } from "./pin-marker.js";

// Leaf module: imports only globals and pin-marker.ts. The divider is a single
// `#UTubPinDivider` child of `#listUTubs` (never a `.UTubSelector`, so counting,
// search and striping ignore it). It is aria-hidden with no role: each pinned
// row's "Pinned" label conveys the grouping.

const DIVIDER_ID = "UTubPinDivider";

function makeDivider(): JQuery<HTMLElement> {
  return $(document.createElement("div"))
    .attr({ id: DIVIDER_ID, "aria-hidden": "true" })
    .addClass("UTubPinDivider hidden");
}

// Keeps exactly one divider immediately before the first unpinned row (at the
// end when every row is pinned or the deck is empty), shown only while at least
// one visible pinned row and one visible unpinned row exist. Pin state is read
// from each row's marker, so it holds for Jinja- and TS-built rows alike.
export function syncUTubPinDivider(): void {
  const parent = $("#listUTubs");
  if (parent.length === 0) return;

  const dividers = parent.children(`#${DIVIDER_ID}`);
  dividers.slice(1).remove();
  let divider = dividers.first();
  if (divider.length === 0) {
    divider = makeDivider();
    parent.append(divider);
  }

  let visiblePinned = 0;
  let visibleUnpinned = 0;
  let firstUnpinned: JQuery<HTMLElement> | undefined;
  for (const element of parent.children(".UTubSelector").toArray()) {
    const row = $(element);
    const isPinned = rowHasPinMarker(row);
    if (!isPinned && firstUnpinned === undefined) firstUnpinned = row;
    if (row.hasClass("hidden")) continue;
    if (isPinned) visiblePinned += 1;
    else visibleUnpinned += 1;
  }

  if (firstUnpinned === undefined) {
    if (divider.next().length > 0) parent.append(divider);
  } else if (firstUnpinned.prev()[0] !== divider[0]) {
    firstUnpinned.before(divider);
  }

  divider.toggleClass("hidden", visiblePinned === 0 || visibleUnpinned === 0);
}
