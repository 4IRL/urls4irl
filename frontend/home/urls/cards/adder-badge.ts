import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { getState } from "../../../store/app-store.js";
import type { MemberItem } from "../../../types/member.js";
import type { DateFormatValue } from "../../../types/preferences.js";

// Formats an ISO-8601 timestamp string into the user's stored DateFormat
// preference. Uses UTC calendar components so the rendered date is deterministic
// regardless of the viewer's local timezone (added_at is stored as UTC).
//   iso → YYYY-MM-DD | us → MM/DD/YYYY | eu → DD/MM/YYYY
export function formatDateByPreference(
  isoDate: string,
  dateFormat: DateFormatValue,
): string {
  const date = new Date(isoDate);
  const year = `${date.getUTCFullYear()}`;
  const month = `${date.getUTCMonth() + 1}`.padStart(2, "0");
  const day = `${date.getUTCDate()}`.padStart(2, "0");
  switch (dateFormat) {
    case "us":
      return `${month}/${day}/${year}`;
    case "eu":
      return `${day}/${month}/${year}`;
    case "iso":
    default:
      return `${year}-${month}-${day}`;
  }
}

// Resolve the display username of the member who added a URL from a member
// list (the store's current UTub members unless a `members` override is given).
// Returns null if that user is not a member (e.g. removed after adding the URL)
// so the badge can show "a former member" rather than a dangling id or a
// tombstone username.
function resolveAdderUsername({
  addedByUserID,
  members,
}: {
  addedByUserID: number;
  members?: MemberItem[];
}): string | null {
  const adder = (members ?? getState().members).find(
    (member) => member.id === addedByUserID,
  );
  return adder ? adder.username : null;
}

// Secondary/metadata date-added badge for a URL card. Two placements share this
// builder and are swapped by viewport + selection state (see .urlDateAddedBadge*
// in urls.css):
//   - "urlDateAddedBadgeInline"  — desktop only, COLLAPSED cards: a terse
//     date-only badge inline at the URL-string row's lower-right, so it costs no
//     card height and leaves long URLs their room (withAdder = false).
//   - "urlDateAddedBadgeStacked" — EXPANDED cards on both desktop and mobile:
//     a full-width row below the buttons row carrying the full attribution
//     (withAdder = true).
// A <time> element carries the machine-readable ISO value in `datetime` and an
// unambiguous accessible name in `aria-label`. With `withAdder`, the visible
// text attributes the URL to the member who added it — "Added by <username> ·
// <date>" — or "Added by a former member · <date>" when the adder is not in the
// member list (never the departed user's name); without it, the badge is always
// the date-only "Added: <date>" form. The date is formatted per the stored
// DateFormat preference. `members` overrides the store's member list for cards
// built while the store still holds the pre-refresh members (stale-data path).
export function createURLDateAddedBadge({
  addedAt,
  addedByUserID,
  placementClass,
  withAdder,
  members,
}: {
  addedAt: string;
  addedByUserID: number;
  placementClass: string;
  withAdder: boolean;
  members?: MemberItem[];
}): JQuery<HTMLElement> {
  const formattedDate = formatDateByPreference(
    addedAt,
    getState().preferences.dateFormat,
  );
  // Static label words come from the backend strings bridge; the dynamic
  // username/date (and the "·" separator punctuation) are composed here so the
  // exact rendered output is preserved: "Added by <user> · <date>" /
  // "Added by a former member · <date>" / "Added: <date>" (visible),
  // "Added by <user> on <date>" / "Added by a former member on <date>" /
  // "Added <date>" (aria).
  const addedBy = APP_CONFIG.strings.URL_ADDED_BY;
  const addedOn = APP_CONFIG.strings.URL_ADDED_ON;
  const addedLabel = APP_CONFIG.strings.URL_DATE_ADDED_LABEL;
  const addedAriaPrefix = APP_CONFIG.strings.URL_DATE_ADDED_ARIA;
  let visibleText = `${addedLabel} ${formattedDate}`;
  let accessibleLabel = `${addedAriaPrefix} ${formattedDate}`;
  if (withAdder) {
    const adderName =
      resolveAdderUsername({ addedByUserID, members }) ??
      APP_CONFIG.strings.URL_ADDED_BY_FORMER_MEMBER;
    visibleText = `${addedBy} ${adderName} · ${formattedDate}`;
    accessibleLabel = `${addedBy} ${adderName} ${addedOn} ${formattedDate}`;
  }
  return $(document.createElement("time"))
    .addClass(`urlDateAddedBadge ${placementClass}`)
    .attr({ datetime: addedAt, "aria-label": accessibleLabel })
    .text(visibleText);
}

// Re-render the expanded-card (stacked) attribution badge of every rendered card
// whose URL was added by `addedByUserID`, in place (no deck rebuild). Used after
// a member is removed so the remover's open cards switch to "a former member".
export function refreshStackedAdderBadges(addedByUserID: number): void {
  getState()
    .urls.filter((url) => url.addedByUserID === addedByUserID)
    .forEach((url) => {
      $(
        `.urlRow[utuburlid="${url.utubUrlID}"] .urlDateAddedBadgeStacked`,
      ).replaceWith(
        createURLDateAddedBadge({
          addedAt: url.addedAt,
          addedByUserID: url.addedByUserID,
          placementClass: "urlDateAddedBadgeStacked",
          withAdder: true,
        }),
      );
    });
}
