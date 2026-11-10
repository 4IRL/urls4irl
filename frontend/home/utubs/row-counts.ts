import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { getState, setState } from "../../store/app-store.js";
import { isMemberListHiddenForViewer } from "./policy.js";

// Leaf module: store, config, policy and jQuery only, so URL/member/trash modules
// can call it without importing the deck or selectors (no import cycle).

// Visually-hidden screen-reader text, e.g. ", 3 URLs, 1 member". The leading
// comma keeps it from running into the UTub name or the selected label. A null
// memberCount (list hidden from the viewer) omits the member clause.
export function makeUTubRowCountsLabel({
  urlCount,
  memberCount,
}: {
  urlCount: number;
  memberCount: number | null;
}): string {
  const { strings } = APP_CONFIG;
  const urlNoun =
    urlCount === 1
      ? strings.UTUB_ROW_URL_SINGULAR
      : strings.UTUB_ROW_URL_PLURAL;
  const urlClause = `, ${urlCount} ${urlNoun}`;
  if (memberCount === null) return urlClause;
  const memberNoun =
    memberCount === 1
      ? strings.UTUB_ROW_MEMBER_SINGULAR
      : strings.UTUB_ROW_MEMBER_PLURAL;
  return `${urlClause}, ${memberCount} ${memberNoun}`;
}

const LINK_ICON_SVG =
  `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="currentColor" class="bi bi-link-45deg" viewBox="0 0 16 16">` +
  `<path d="M4.715 6.542 3.343 7.914a3 3 0 1 0 4.243 4.243l1.828-1.829A3 3 0 0 0 8.586 5.5L8 6.086a1 1 0 0 0-.154.199 2 2 0 0 1 .861 3.337L6.88 11.45a2 2 0 1 1-2.83-2.83l.793-.792a4 4 0 0 1-.128-1.287z"/>` +
  `<path d="M6.586 4.672A3 3 0 0 0 7.414 9.5l.775-.776a2 2 0 0 1-.896-3.346L9.12 3.55a2 2 0 1 1 2.83 2.83l-.793.792c.112.42.155.855.128 1.287l1.372-1.372a3 3 0 1 0-4.243-4.243z"/>` +
  `</svg>`;

const PERSON_ICON_SVG =
  `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" fill="currentColor" class="bi bi-person-fill" viewBox="0 0 16 16">` +
  `<path d="M3 14s-1 0-1-1 1-4 6-4 6 3 6 4-1 1-1 1zm5-6a3 3 0 1 0 0-6 3 3 0 0 0 0 6"/>` +
  `</svg>`;

// Markup identical to the Jinja UTubCard.html counts group. Uses its own class
// (never `memberRole`, which stale-data.ts replaces). A null memberCount omits
// the person-icon segment.
export function makeUTubRowCounts({
  urlCount,
  memberCount,
}: {
  urlCount: number;
  memberCount: number | null;
}): JQuery<HTMLElement> {
  const counts = $(document.createElement("span")).addClass(
    "UTubRowCounts flex-row align-center",
  );
  counts.append(
    $(document.createElement("span"))
      .addClass("visually-hidden")
      .text(makeUTubRowCountsLabel({ urlCount, memberCount })),
  );
  const segments = [{ icon: LINK_ICON_SVG, value: urlCount }];
  if (memberCount !== null) {
    segments.push({ icon: PERSON_ICON_SVG, value: memberCount });
  }
  for (const { icon, value } of segments) {
    counts.append(
      $(document.createElement("span"))
        .addClass("UTubRowCount")
        .attr("aria-hidden", "true")
        .append(icon)
        .append(
          $(document.createElement("span"))
            .addClass("UTubRowCountNum")
            .text(String(value)),
        ),
    );
  }
  return counts;
}

function writeRowCounts({
  utubID,
  urlCount,
  memberCount,
}: {
  utubID: number;
  urlCount: number;
  memberCount: number | null;
}): void {
  const { utubs } = getState();
  const stored = utubs.find((utub) => utub.id === utubID);
  if (stored === undefined) return;
  // An unchanged row writes nothing, so a no-op refresh never churns the store.
  if (stored.urlCount !== urlCount || stored.memberCount !== memberCount) {
    setState({
      utubs: utubs.map((utub) =>
        utub.id === utubID ? { ...utub, urlCount, memberCount } : utub,
      ),
    });
  }

  const counts = $(`.UTubSelector[utubid="${utubID}"] .UTubRowCounts`);
  if (counts.length === 0) return;
  // A live flip of the hide setting changes whether the member segment exists;
  // text-only updates cannot add or remove it, so rebuild the whole group.
  const hasMemberSegment = counts.find(".UTubRowCount").length > 1;
  if (hasMemberSegment !== (memberCount !== null)) {
    counts.replaceWith(makeUTubRowCounts({ urlCount, memberCount }));
    return;
  }
  counts
    .find(".visually-hidden")
    .text(makeUTubRowCountsLabel({ urlCount, memberCount }));
  const numbers = counts.find(".UTubRowCountNum");
  numbers.eq(0).text(String(urlCount));
  if (memberCount !== null) numbers.eq(1).text(String(memberCount));
}

// User-driven paths apply deltas so a restore (which adds a URL the store does
// not hold yet) is never undone by a later recount. A hidden or unknown member
// total is never adjusted: it stays null.
export function applyRowCountDelta({
  utubID,
  urlDelta,
  memberDelta,
}: {
  utubID: number;
  urlDelta: number;
  memberDelta: number;
}): void {
  const utub = getState().utubs.find((item) => item.id === utubID);
  if (utub === undefined) return;
  const { activeUTubID, members } = getState();
  const isActive = utubID === activeUTubID;
  const viewerHidden = isActive && isMemberListHiddenForViewer();
  let memberCount: number | null;
  if (viewerHidden) {
    memberCount = null;
  } else if (utub.memberCount === null) {
    // Active UTub with a now-visible list: the store holds the full members.
    memberCount = isActive ? members.length : null;
  } else {
    memberCount = Math.max(0, utub.memberCount + memberDelta);
  }
  writeRowCounts({
    utubID,
    urlCount: Math.max(0, utub.urlCount + urlDelta),
    memberCount,
  });
}

// Recount from the loaded decks: only for paths that just replaced the store's
// urls/members (UTub selection, a stale-data refresh). Writes null while the
// member list is hidden from the viewer, since the loaded list is filtered.
export function setRowCountsFromStore({ utubID }: { utubID: number }): void {
  const { urls, members } = getState();
  writeRowCounts({
    utubID,
    urlCount: urls.length,
    memberCount: isMemberListHiddenForViewer() ? null : members.length,
  });
}
