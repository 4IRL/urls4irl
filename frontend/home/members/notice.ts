import { $ } from "../../lib/globals.js";
import { on, AppEvents } from "../../lib/event-bus.js";
import { getState } from "../../store/app-store.js";

// The Members deck's visible refusal notice. It is non-live and never takes
// focus: the spoken announcement lives only in #MemberRowActionAnnouncement, so
// nothing is read twice. It clears only on the next add-open or when the active
// UTub changes; a same-UTub rebuild leaves it in place.

const NOTICE_SELECTOR = "#MemberDeckNotice";
const ANNOUNCEMENT_SELECTOR = "#MemberRowActionAnnouncement";

let _noticeUTubID: number | null = null;

export function showMemberDeckNotice({ message }: { message: string }): void {
  _noticeUTubID = getState().activeUTubID;
  $(NOTICE_SELECTOR).text(message).removeClass("hidden");
}

export function clearMemberDeckNotice(): void {
  $(NOTICE_SELECTOR).text("").addClass("hidden");
}

// Writes the row-action live region. Every write sets `aria-live` explicitly:
// "polite" for an ability flip, "assertive" for a refusal.
export function announceMemberRowAction({
  message,
  politeness,
}: {
  message: string;
  politeness: "polite" | "assertive";
}): void {
  $(ANNOUNCEMENT_SELECTOR).attr("aria-live", politeness).text(message);
}

on(AppEvents.UTUB_SELECTED, ({ utubID }) => {
  if (utubID !== _noticeUTubID) clearMemberDeckNotice();
  _noticeUTubID = utubID;
});
