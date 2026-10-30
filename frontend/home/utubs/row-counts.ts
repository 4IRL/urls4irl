import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { getState, setState } from "../../store/app-store.js";

// Leaf module: store, config and jQuery only, so URL/member/trash modules can
// call it without importing the deck or selectors (no import cycle).

// Visually-hidden screen-reader text, e.g. ", 3 URLs, 1 member". The leading
// comma keeps it from running into the UTub name or the selected label.
export function makeUTubRowCountsLabel({
  urlCount,
  memberCount,
}: {
  urlCount: number;
  memberCount: number;
}): string {
  const { strings } = APP_CONFIG;
  const urlNoun =
    urlCount === 1
      ? strings.UTUB_ROW_URL_SINGULAR
      : strings.UTUB_ROW_URL_PLURAL;
  const memberNoun =
    memberCount === 1
      ? strings.UTUB_ROW_MEMBER_SINGULAR
      : strings.UTUB_ROW_MEMBER_PLURAL;
  return `, ${urlCount} ${urlNoun}, ${memberCount} ${memberNoun}`;
}

function writeRowCounts({
  utubID,
  urlCount,
  memberCount,
}: {
  utubID: number;
  urlCount: number;
  memberCount: number;
}): void {
  const { utubs } = getState();
  if (!utubs.some((utub) => utub.id === utubID)) return;
  setState({
    utubs: utubs.map((utub) =>
      utub.id === utubID ? { ...utub, urlCount, memberCount } : utub,
    ),
  });

  const counts = $(`.UTubSelector[utubid="${utubID}"] .UTubRowCounts`);
  counts
    .find(".visually-hidden")
    .text(makeUTubRowCountsLabel({ urlCount, memberCount }));
  const numbers = counts.find(".UTubRowCountNum");
  numbers.eq(0).text(String(urlCount));
  numbers.eq(1).text(String(memberCount));
}

// User-driven paths apply deltas so a restore (which adds a URL the store does
// not hold yet) is never undone by a later recount.
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
  writeRowCounts({
    utubID,
    urlCount: Math.max(0, utub.urlCount + urlDelta),
    memberCount: Math.max(0, utub.memberCount + memberDelta),
  });
}

// Recount from the loaded decks: only for paths that just replaced the store's
// urls/members (UTub selection, a stale-data refresh).
export function setRowCountsFromStore({ utubID }: { utubID: number }): void {
  const { urls, members } = getState();
  writeRowCounts({
    utubID,
    urlCount: urls.length,
    memberCount: members.length,
  });
}
