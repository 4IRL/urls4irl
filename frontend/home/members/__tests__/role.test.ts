import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { isUtubLockedHandled } from "../../utub-locked.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { createMemberBadge } from "../members.js";
import { modifyMemberRoleShowModal } from "../role.js";

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));
vi.mock("../../utub-locked.js", () => ({
  isUtubLockedHandled: vi.fn(() => false),
}));
vi.mock("../../../lib/metrics-client.js", () => ({ emit: vi.fn() }));

const $ = window.jQuery;
const { MEMBER, CO_CREATOR } = APP_CONFIG.constants.MEMBER_ROLES;

const ROLE_HTML = `
  <div id="confirmModal">
    <div id="confirmModalTitle"></div>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <div id="modalRedirect"></div>
  </div>
  <div id="displayMemberWrap">
    <div id="UTubOwner"></div>
    <div id="listMembers"></div>
  </div>
  <span id="MemberRowActionAnnouncement" class="visually-hidden" aria-live="polite"></span>
`;

function installModalStub(): void {
  ($.fn as unknown as Record<string, unknown>).modal = function (this: JQuery) {
    return this;
  };
}

// Seed a real member row (via createMemberBadge, owner viewer) plus the matching
// store entry, so the success handler's store lookup + swapMemberRoleInRow have
// real targets.
function seedMemberRow(
  memberID: number,
  username: string,
  memberRole: string,
): void {
  $("#listMembers").append(
    createMemberBadge({
      memberID,
      username,
      memberRole,
      isCurrentUserOwner: true,
      utubID: 1,
    }),
  );
  setState({ members: [{ id: memberID, username, memberRole }] });
}

function mockAjaxSuccess(): void {
  vi.mocked(ajaxCall).mockReturnValue(
    createMockJqXHRChainable({
      done: (cb: unknown) =>
        (cb as (_r: unknown, _t: unknown, xhr: JQuery.jqXHR) => void)(
          {},
          "success",
          createMockXhr({ status: 200 }),
        ),
    }),
  );
}

function mockAjaxFailure(props: Record<string, unknown>): void {
  vi.mocked(ajaxCall).mockReturnValue(
    createMockJqXHRChainable({
      fail: (cb: unknown) =>
        (cb as (xhr: JQuery.jqXHR) => void)(
          createMockXhr({
            getResponseHeader: () => "application/json",
            ...props,
          }),
        ),
    }),
  );
}

describe("modifyMemberRole — grant/revoke co-owner", () => {
  beforeEach(() => {
    document.body.innerHTML = ROLE_HTML;
    vi.clearAllMocks();
    resetStore();
    installModalStub();
    vi.mocked(is429Handled).mockReturnValue(false);
    vi.mocked(isUtubLockedHandled).mockReturnValue(false);
  });

  it("toggles aria-live assertive→polite across a failure THEN a success in the same flow (DD-23)", () => {
    seedMemberRow(5, "u5", MEMBER);

    // (1) Failure first (400 with a server message) — assertive, leaving the
    // live region in a genuinely non-default state.
    mockAjaxFailure({
      status: 400,
      responseJSON: { message: "You can't change the owner." },
    });
    modifyMemberRoleShowModal({ memberID: 5, currentRole: MEMBER, utubID: 1 });
    $("#modalSubmit").trigger("click");

    expect($("#MemberRowActionAnnouncement").attr("aria-live")).toBe(
      "assertive",
    );
    expect($("#MemberRowActionAnnouncement").text()).toBe(
      "You can't change the owner.",
    );

    // (2) Success (grant) — patch args, local role set, icon + menu-item swap,
    // grant-template announcement, and a genuine transition back to polite.
    mockAjaxSuccess();
    modifyMemberRoleShowModal({ memberID: 5, currentRole: MEMBER, utubID: 1 });
    $("#modalSubmit").trigger("click");

    expect(vi.mocked(ajaxCall)).toHaveBeenLastCalledWith(
      "patch",
      "/utubs/1/members/5",
      { member_role: CO_CREATOR },
    );
    expect(
      getState().members.find((member) => member.id === 5)?.memberRole,
    ).toBe(CO_CREATOR);
    expect(
      $(`.member[memberid="5"] svg.bi-diamond-half.memberRole`).length,
    ).toBe(1);
    expect($(`.member[memberid="5"] .memberRowMenuItemRole span`).text()).toBe(
      APP_CONFIG.strings.REVOKE_CO_OWNER_ACTION,
    );
    expect($("#MemberRowActionAnnouncement").text()).toBe(
      "u5 is now a co-owner.",
    );
    expect($("#MemberRowActionAnnouncement").attr("aria-live")).toBe("polite");
  });

  it("revokes a co-owner: patches member, swaps to people-fill + Make label, revoke announcement", () => {
    seedMemberRow(7, "coOwner", CO_CREATOR);
    mockAjaxSuccess();

    modifyMemberRoleShowModal({
      memberID: 7,
      currentRole: CO_CREATOR,
      utubID: 1,
    });
    $("#modalSubmit").trigger("click");

    expect(vi.mocked(ajaxCall)).toHaveBeenLastCalledWith(
      "patch",
      "/utubs/1/members/7",
      { member_role: MEMBER },
    );
    expect(
      $(`.member[memberid="7"] svg.bi-people-fill.memberRole`).length,
    ).toBe(1);
    expect($(`.member[memberid="7"] .memberRowMenuItemRole span`).text()).toBe(
      APP_CONFIG.strings.MAKE_CO_OWNER_ACTION,
    );
    expect($("#MemberRowActionAnnouncement").text()).toBe(
      "coOwner is no longer a co-owner.",
    );
    expect($("#MemberRowActionAnnouncement").attr("aria-live")).toBe("polite");
  });

  it("emits the show + confirm UI metrics", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");
    seedMemberRow(5, "u5", MEMBER);
    mockAjaxSuccess();

    modifyMemberRoleShowModal({ memberID: 5, currentRole: MEMBER, utubID: 1 });
    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_MEMBER_ROLE_CHANGE_SHOWN,
    });

    $("#modalSubmit").trigger("click");
    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_MEMBER_ROLE_CHANGE_CONFIRMED,
    });
  });

  it("surfaces a 404 server message assertively without redirecting", () => {
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      seedMemberRow(5, "u5", MEMBER);
      mockAjaxFailure({
        status: 404,
        responseJSON: { message: "That member is not in this UTub." },
      });

      modifyMemberRoleShowModal({
        memberID: 5,
        currentRole: MEMBER,
        utubID: 1,
      });
      $("#modalSubmit").trigger("click");

      expect($("#MemberRowActionAnnouncement").attr("aria-live")).toBe(
        "assertive",
      );
      expect($("#MemberRowActionAnnouncement").text()).toBe(
        "That member is not in this UTub.",
      );
      expect(assignSpy).not.toHaveBeenCalled();
      // Submit re-enabled after the failure.
      expect($("#modalSubmit").prop("disabled")).toBe(false);
    } finally {
      assignSpy.mockRestore();
    }
  });

  it("swaps the page body on a 403 invalid-CSRF html response", () => {
    seedMemberRow(5, "u5", MEMBER);
    mockAjaxFailure({
      status: 403,
      getResponseHeader: () => "text/html; charset=utf-8",
      responseText: `<div id="csrfReload">reload</div>`,
    });

    modifyMemberRoleShowModal({ memberID: 5, currentRole: MEMBER, utubID: 1 });
    $("#modalSubmit").trigger("click");

    expect($("#csrfReload").length).toBe(1);
  });

  it("early-returns on a 429 without announcing or redirecting", () => {
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      vi.mocked(is429Handled).mockReturnValue(true);
      seedMemberRow(5, "u5", MEMBER);
      mockAjaxFailure({ status: 429 });

      modifyMemberRoleShowModal({
        memberID: 5,
        currentRole: MEMBER,
        utubID: 1,
      });
      $("#modalSubmit").trigger("click");

      expect($("#MemberRowActionAnnouncement").text()).toBe("");
      expect(assignSpy).not.toHaveBeenCalled();
    } finally {
      assignSpy.mockRestore();
    }
  });

  it("early-returns on a locked-UTub 403 without announcing or redirecting", () => {
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      vi.mocked(isUtubLockedHandled).mockReturnValue(true);
      seedMemberRow(5, "u5", MEMBER);
      mockAjaxFailure({ status: 403 });

      modifyMemberRoleShowModal({
        memberID: 5,
        currentRole: MEMBER,
        utubID: 1,
      });
      $("#modalSubmit").trigger("click");

      expect($("#MemberRowActionAnnouncement").text()).toBe("");
      expect(assignSpy).not.toHaveBeenCalled();
    } finally {
      assignSpy.mockRestore();
    }
  });

  it("redirects to the error page on an unexpected 500", () => {
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      seedMemberRow(5, "u5", MEMBER);
      mockAjaxFailure({ status: 500 });

      modifyMemberRoleShowModal({
        memberID: 5,
        currentRole: MEMBER,
        utubID: 1,
      });
      $("#modalSubmit").trigger("click");

      expect(assignSpy).toHaveBeenCalledWith(APP_CONFIG.routes.errorPage);
    } finally {
      assignSpy.mockRestore();
    }
  });
});
