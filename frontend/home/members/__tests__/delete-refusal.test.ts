import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../lib/ajax.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { getState } from "../../../store/app-store.js";
import { learnPolicyOff } from "../../utubs/policy.js";
import { updateUTubOnFindingStaleData } from "../../utubs/stale-data.js";
import {
  CO_OWNER_REMOVE_NOT_ALLOWED_ERROR_CODE,
  removeMemberShowModal,
} from "../delete.js";
import { announceMemberRowAction } from "../notice.js";
import { bindMemberRowModalFocusRestore } from "../row-menu.js";

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));
vi.mock("../../utub-locked.js", () => ({
  isUtubLockedHandled: vi.fn(() => false),
}));
vi.mock("../../../lib/metrics-client.js", () => ({ emit: vi.fn() }));
vi.mock("../deck.js", () => ({ setMemberDeckForUTub: vi.fn() }));
vi.mock("../../btns-forms.js", () => ({ hideInputs: vi.fn() }));
vi.mock("../../urls/cards/selection.js", () => ({ deselectAllURLs: vi.fn() }));
vi.mock("../../utubs/utils.js", () => ({ getNumOfUTubs: vi.fn(() => 1) }));
vi.mock("../../utubs/deck.js", () => ({
  hideInputsAndUpdateUTubDeck: vi.fn(),
  resetUTubDeckIfNoUTubs: vi.fn(),
}));
vi.mock("../../init.js", () => ({ setUIWhenNoUTubSelected: vi.fn() }));
vi.mock("../../tags/sheet.js", () => ({
  isTagSheetOpen: vi.fn(() => false),
  closeTagSheet: vi.fn(),
}));
vi.mock("../../utubs/row-counts.js", () => ({ applyRowCountDelta: vi.fn() }));
vi.mock("../notice.js", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../notice.js")>();
  return {
    ...actual,
    announceMemberRowAction: vi.fn(actual.announceMemberRowAction),
  };
});
vi.mock("../../utubs/policy.js", () => ({ learnPolicyOff: vi.fn() }));
vi.mock("../../utubs/stale-data.js", () => ({
  updateUTubOnFindingStaleData: vi.fn(),
}));
vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ members: [], activeUTubID: 42 })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const DECK_HTML = `
  <div id="confirmModal">
    <div id="confirmModalTitle"></div>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <div id="modalRedirect"></div>
  </div>
  <button type="button" id="MemberDeckHeaderAndCaret"></button>
  <div id="MemberDeckNotice" class="hidden"></div>
  <span id="MemberRowActionAnnouncement" aria-live="off"></span>
  <div id="listMembers">
    <span class="member" memberid="9">
      <span class="member-right"><button class="memberRowKebab memberRowKebab--coOwner" id="k9">k</button></span>
    </span>
  </div>
  <button id="leaveBtn" type="button"></button>
`;

function failWith({
  status = 403,
  body,
}: {
  status?: number;
  body: Record<string, unknown>;
}): void {
  const xhr = createMockXhr({
    status,
    responseJSON: body,
    getResponseHeader: () => "application/json",
  });
  vi.mocked(ajaxCall).mockReturnValue(
    createMockJqXHRChainable({
      fail: (cb: unknown) => {
        (cb as (xhr: JQuery.jqXHR) => void)(xhr);
      },
    }),
  );
}

function confirmCoOwnerRemove(): void {
  removeMemberShowModal({ memberID: 9, utubID: 42, intent: "remove" });
  $("#modalSubmit").trigger("click");
}

describe("removeMemberFail — co-owner refusals", () => {
  let assignSpy: ReturnType<typeof vi.spyOn>;
  let modalHides: number;

  beforeEach(() => {
    document.body.innerHTML = DECK_HTML;
    vi.clearAllMocks();
    vi.mocked(getState).mockReturnValue({
      members: [],
      activeUTubID: 42,
    } as unknown as ReturnType<typeof getState>);
    modalHides = 0;
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
      action?: string,
    ) {
      if (action === "hide") modalHides += 1;
      return this;
    };
    assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
  });

  afterEach(() => {
    assignSpy.mockRestore();
  });

  function expectOneRefusal(message: string): void {
    expect(assignSpy).not.toHaveBeenCalled();
    expect(modalHides).toBeGreaterThan(0);
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(false);
    expect($("#MemberDeckNotice").text()).toBe(message);
    expect($("#MemberRowActionAnnouncement").text()).toBe(message);
    expect($("#MemberRowActionAnnouncement").attr("aria-live")).toBe(
      "assertive",
    );
    // Exactly one write to the live region.
    expect(announceMemberRowAction).toHaveBeenCalledTimes(1);
    expect(announceMemberRowAction).toHaveBeenCalledWith({
      message,
      politeness: "assertive",
    });
    expect(updateUTubOnFindingStaleData).toHaveBeenCalledTimes(1);
    expect(updateUTubOnFindingStaleData).toHaveBeenCalledWith({ utubID: 42 });
  }

  it("errorCode 8 learns the setting off, shows the reason, announces once and refreshes without a redirect", () => {
    expect(CO_OWNER_REMOVE_NOT_ALLOWED_ERROR_CODE).toBe(8);
    failWith({ body: { errorCode: 8, message: "x" } });

    confirmCoOwnerRemove();

    expectOneRefusal(APP_CONFIG.strings.CO_OWNER_REMOVE_NOT_ALLOWED);
    expect(learnPolicyOff).toHaveBeenCalledTimes(1);
    expect(learnPolicyOff).toHaveBeenCalledWith({
      utubID: 42,
      key: "members.co_owners_can_remove",
    });
  });

  it("the co-owner-target 403 (message only) shows the message, learns nothing and refreshes", () => {
    failWith({
      body: { message: APP_CONFIG.strings.CO_OWNER_CANNOT_REMOVE_CO_OWNER },
    });

    confirmCoOwnerRemove();

    expectOneRefusal(APP_CONFIG.strings.CO_OWNER_CANNOT_REMOVE_CO_OWNER);
    expect(learnPolicyOff).not.toHaveBeenCalled();
  });

  it("a stale demoted co-owner's INVALID_PERMISSION_TO_REMOVE 403 does not redirect, announces once and refreshes", () => {
    failWith({
      body: { message: APP_CONFIG.strings.INVALID_PERMISSION_TO_REMOVE },
    });

    confirmCoOwnerRemove();

    expectOneRefusal(APP_CONFIG.strings.INVALID_PERMISSION_TO_REMOVE);
    expect(learnPolicyOff).not.toHaveBeenCalled();
  });

  it("CANNOT_REMOVE_OWNER and other message-only 403s still redirect to the error page", () => {
    failWith({ body: { message: "The UTub owner cannot be removed." } });

    confirmCoOwnerRemove();

    expect(assignSpy).toHaveBeenCalledWith(APP_CONFIG.routes.errorPage);
    expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
    expect(learnPolicyOff).not.toHaveBeenCalled();
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(true);
  });

  it("a non-403 failure still redirects", () => {
    failWith({ status: 500, body: { errorCode: 8 } });

    confirmCoOwnerRemove();

    expect(assignSpy).toHaveBeenCalledWith(APP_CONFIG.routes.errorPage);
  });

  it("writes no notice into a UTub the viewer already left", () => {
    vi.mocked(getState).mockReturnValue({
      members: [],
      activeUTubID: 7,
    } as unknown as ReturnType<typeof getState>);
    failWith({ body: { errorCode: 8 } });

    confirmCoOwnerRemove();

    expect(assignSpy).not.toHaveBeenCalled();
    expect(modalHides).toBeGreaterThan(0);
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(true);
    expect(learnPolicyOff).not.toHaveBeenCalled();
    expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
  });

  it("focus lands on the member's row when its kebab is hidden by the learn", () => {
    failWith({ body: { errorCode: 8 } });
    confirmCoOwnerRemove();
    // The learn hides the co-owner kebab (display:none in CSS): not focusable.
    ($("#k9").get(0) as HTMLElement).style.visibility = "hidden";

    $("#confirmModal").trigger("hidden.bs.modal");

    const row = $('.member[memberid="9"]').get(0);
    expect(document.activeElement).toBe(row);
  });

  it("focus lands on the deck header when the row is gone (never body)", () => {
    failWith({
      body: { message: APP_CONFIG.strings.CO_OWNER_CANNOT_REMOVE_CO_OWNER },
    });
    confirmCoOwnerRemove();
    $("#listMembers").empty();

    $("#confirmModal").trigger("hidden.bs.modal");

    expect(document.activeElement).toBe(
      document.getElementById("MemberDeckHeaderAndCaret"),
    );
  });
});

describe("Leave after a cancelled Remove", () => {
  beforeEach(() => {
    document.body.innerHTML = DECK_HTML;
    vi.clearAllMocks();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
  });

  it("does not move focus to the old member's row or the header", () => {
    // A Remove was opened (arming the restore) and cancelled without a close
    // handler consuming it; then the viewer opens Leave and cancels it.
    bindMemberRowModalFocusRestore(9);
    removeMemberShowModal({ memberID: 1, utubID: 42, intent: "leave" });
    document.getElementById("leaveBtn")!.focus();

    $("#confirmModal").trigger("hidden.bs.modal");

    expect(document.activeElement).toBe(document.getElementById("leaveBtn"));
  });

  it("keeps the remove restore armed when the intent is remove", () => {
    bindMemberRowModalFocusRestore(9);
    removeMemberShowModal({ memberID: 9, utubID: 42, intent: "remove" });
    document.getElementById("leaveBtn")!.focus();

    $("#confirmModal").trigger("hidden.bs.modal");

    // The restore ran: focus returns to the member's (visible) kebab.
    expect(document.activeElement).toBe(document.getElementById("k9"));
  });
});
