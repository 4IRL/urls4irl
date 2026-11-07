import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";

// Leaf module: imports only globals and config, so sort.ts and selectors.ts can
// both use it. The marker is two siblings placed before `.memberRole` in the row
// (never inside it, which stale-data.ts replaces): the pin icon and its
// visually-hidden label. Markup is identical to UTubCard.html.

const PIN_ICON_SVG =
  `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-pin-fill UTubPinIcon" viewBox="0 0 16 16" aria-hidden="true">` +
  `<path d="M4.146.146A.5.5 0 0 1 4.5 0h7a.5.5 0 0 1 .5.5c0 .68-.342 1.174-.646 1.479-.126.125-.25.224-.354.298v4.431l.078.048c.203.127.476.314.751.555C12.36 7.775 13 8.527 13 9.5a.5.5 0 0 1-.5.5h-4v4.5c0 .276-.224 1.5-.5 1.5s-.5-1.224-.5-1.5V10h-4a.5.5 0 0 1-.5-.5c0-.973.64-1.725 1.17-2.189A6 6 0 0 1 5 6.708V2.277a3 3 0 0 1-.354-.298C4.342 1.674 4 1.179 4 .5a.5.5 0 0 1 .146-.354"/>` +
  `</svg>`;

// The bare icon (aria-hidden, no label) for surfaces that name the UTub themselves.
export function makeUTubPinIcon(): JQuery<HTMLElement> {
  return $(PIN_ICON_SVG);
}

export function makeUTubPinMarker(): JQuery<HTMLElement> {
  const label = $(document.createElement("span"))
    .addClass("visually-hidden UTubPinnedLabel")
    .text(APP_CONFIG.strings.UTUB_PINNED_ROW_LABEL);
  return $(PIN_ICON_SVG).add(label);
}

export function rowHasPinMarker(row: JQuery<HTMLElement>): boolean {
  return row.children(".UTubPinIcon").length > 0;
}

// Adds or removes a row's pin marker, keeping exactly one marker when pinned.
export function setRowPinMarker({
  row,
  isPinned,
}: {
  row: JQuery<HTMLElement>;
  isPinned: boolean;
}): void {
  row.children(".UTubPinIcon, .UTubPinnedLabel").remove();
  if (!isPinned) return;
  const roleIcon = row.children(".memberRole");
  if (roleIcon.length > 0) {
    roleIcon.first().before(makeUTubPinMarker());
  } else {
    row.append(makeUTubPinMarker());
  }
}
