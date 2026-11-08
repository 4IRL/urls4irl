import {
  announceMemberRowAction,
  clearMemberDeckNotice,
  showMemberDeckNotice,
} from "../notice.js";
import { AppEvents, emit } from "../../../lib/event-bus.js";
import { resetStore, setState } from "../../../store/app-store.js";

const $ = window.jQuery;

describe("member deck notice", () => {
  beforeEach(() => {
    resetStore();
    document.body.innerHTML = `
      <div id="MemberDeckNotice" class="hidden"></div>
      <span id="MemberRowActionAnnouncement" aria-live="polite"></span>
    `;
  });

  it("shows a message and replaces it on a second show", () => {
    showMemberDeckNotice({ message: "first" });
    showMemberDeckNotice({ message: "second" });

    expect($("#MemberDeckNotice").text()).toBe("second");
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(false);
  });

  it("clears and hides", () => {
    showMemberDeckNotice({ message: "x" });
    clearMemberDeckNotice();

    expect($("#MemberDeckNotice").text()).toBe("");
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(true);
  });

  it("keeps a notice shown before any UTUB_SELECTED was seen through a same-UTub select", () => {
    setState({ activeUTubID: 5 });
    showMemberDeckNotice({ message: "early" });

    emit(AppEvents.UTUB_SELECTED, { utubID: 5 } as never);

    expect($("#MemberDeckNotice").text()).toBe("early");
  });

  it("never moves focus and carries no live-region attributes", () => {
    document.body.insertAdjacentHTML(
      "beforeend",
      `<button id="other"></button>`,
    );
    (document.getElementById("other") as HTMLElement).focus();

    showMemberDeckNotice({ message: "x" });

    expect(document.activeElement?.id).toBe("other");
    const notice = $("#MemberDeckNotice");
    expect(notice.attr("aria-live")).toBeUndefined();
    expect(notice.attr("role")).toBeUndefined();
    expect(notice.attr("tabindex")).toBeUndefined();
  });

  it("stays cleared after leaving the UTub and reselecting it", () => {
    setState({ activeUTubID: 1 });
    emit(AppEvents.UTUB_SELECTED, { utubID: 1 } as never);
    showMemberDeckNotice({ message: "gone" });

    clearMemberDeckNotice();
    setState({ activeUTubID: null });
    emit(AppEvents.UTUB_SELECTED, { utubID: 1 } as never);

    expect($("#MemberDeckNotice").text()).toBe("");
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(true);
  });

  it("clears on a UTub change but not on a same-UTub rebuild", () => {
    setState({ activeUTubID: 1 });
    emit(AppEvents.UTUB_SELECTED, { utubID: 1 } as never);
    showMemberDeckNotice({ message: "kept" });

    emit(AppEvents.UTUB_SELECTED, { utubID: 1 } as never);
    expect($("#MemberDeckNotice").text()).toBe("kept");

    emit(AppEvents.UTUB_SELECTED, { utubID: 2 } as never);
    expect($("#MemberDeckNotice").text()).toBe("");
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(true);
  });

  it("sets aria-live explicitly on every announcement", () => {
    announceMemberRowAction({ message: "refused", politeness: "assertive" });
    expect($("#MemberRowActionAnnouncement").attr("aria-live")).toBe(
      "assertive",
    );
    expect($("#MemberRowActionAnnouncement").text()).toBe("refused");

    announceMemberRowAction({ message: "granted", politeness: "polite" });
    expect($("#MemberRowActionAnnouncement").attr("aria-live")).toBe("polite");
  });
});
