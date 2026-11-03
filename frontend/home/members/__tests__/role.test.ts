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
  setState({
    members: [{ id: memberID, username, memberRole, joinedAt: null }],
  });
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

  it("a second toggle on the SAME row revokes — the click handler reads the post-swap store role, not the stale creation-time role", () => {
    // Regression guard for the stale-closure critical: createMemberBadge binds
    // the .memberRowMenuItemRole click ONCE at row creation. swapMemberRoleInRow
    // re-renders the row in place (no full deck rebuild), so the handler is never
    // rebound. Driving the REAL click wiring twice proves the handler sources the
    // current role from the store at click time — a stale closure would recompute
    // a grant on the second click and PATCH member_role: CO_CREATOR again.
    seedMemberRow(5, "u5", MEMBER);
    const roleItem = $(`.member[memberid="5"] .memberRowMenuItemRole`);

    // (1) First toggle via the real click wiring: grant (member → co-owner).
    mockAjaxSuccess();
    roleItem.trigger("click");
    $("#modalSubmit").trigger("click");

    expect(vi.mocked(ajaxCall)).toHaveBeenLastCalledWith(
      "patch",
      "/utubs/1/members/5",
      { member_role: CO_CREATOR },
    );
    // Store now reflects the post-swap role the second click must read.
    expect(
      getState().members.find((member) => member.id === 5)?.memberRole,
    ).toBe(CO_CREATOR);

    // (2) Second toggle on the SAME row (handler never rebound): revoke.
    mockAjaxSuccess();
    roleItem.trigger("click");
    $("#modalSubmit").trigger("click");

    expect(vi.mocked(ajaxCall)).toHaveBeenLastCalledWith(
      "patch",
      "/utubs/1/members/5",
      { member_role: MEMBER },
    );
    expect(
      getState().members.find((member) => member.id === 5)?.memberRole,
    ).toBe(MEMBER);
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

describe("modifyMemberRole — live reorder, position clause and scroll", () => {
  type SeedMember = {
    id: number;
    username: string;
    memberRole: string;
    joinedAt?: string | null;
  };

  function seedMembers(
    members: SeedMember[],
    memberSort: "name_az" | "role_then_name" | "recently_joined",
  ): void {
    members.forEach((member) => {
      $("#listMembers").append(
        createMemberBadge({
          memberID: member.id,
          username: member.username,
          memberRole: member.memberRole,
          isCurrentUserOwner: true,
          utubID: 1,
        }),
      );
    });
    setState({
      members: members.map((member) => ({
        ...member,
        joinedAt: member.joinedAt ?? null,
      })),
      preferences: { ...getState().preferences, memberSort },
    });
  }

  function confirmRoleChange({
    memberID,
    currentRole,
  }: {
    memberID: number;
    currentRole: string;
  }): void {
    mockAjaxSuccess();
    modifyMemberRoleShowModal({ memberID, currentRole, utubID: 1 });
    $("#modalSubmit").trigger("click");
  }

  function listedIDs(): number[] {
    return $("#listMembers > .member")
      .toArray()
      .map((row) => Number(row.getAttribute("memberid")));
  }

  function mockRowRect({
    memberID,
    top,
    bottom,
  }: {
    memberID: number;
    top: number;
    bottom: number;
  }): void {
    const row = $(`.member[memberid="${memberID}"]`)[0];
    row.getBoundingClientRect = () =>
      ({ top, bottom, left: 0, right: 0, width: 0, height: 0 }) as DOMRect;
  }

  beforeEach(() => {
    document.body.innerHTML = ROLE_HTML;
    vi.clearAllMocks();
    resetStore();
    installModalStub();
    vi.mocked(is429Handled).mockReturnValue(false);
    vi.mocked(isUtubLockedHandled).mockReturnValue(false);
    // #listMembers is the scroll container the deck measures rows against.
    $("#listMembers")[0].style.overflowY = "auto";
    $("#listMembers")[0].getBoundingClientRect = () =>
      ({
        top: 0,
        bottom: 100,
        left: 0,
        right: 0,
        width: 0,
        height: 100,
      }) as DOMRect;
  });

  it("grant under role_then_name moves the row into the co-owner group and announces it", () => {
    seedMembers(
      [
        { id: 1, username: "amy", memberRole: MEMBER },
        { id: 2, username: "bob", memberRole: MEMBER },
        { id: 3, username: "cat", memberRole: MEMBER },
      ],
      "role_then_name",
    );

    confirmRoleChange({ memberID: 3, currentRole: MEMBER });

    expect(listedIDs()).toEqual([3, 1, 2]);
    expect($("#MemberRowActionAnnouncement").text()).toBe(
      `cat is now a co-owner. ${APP_CONFIG.strings.MEMBER_ROLE_CHANGE_GRANT_POSITION}`,
    );
  });

  it("revoke under role_then_name moves the row back and announces the members group", () => {
    seedMembers(
      [
        { id: 1, username: "zed", memberRole: CO_CREATOR },
        { id: 2, username: "amy", memberRole: MEMBER },
      ],
      "role_then_name",
    );

    confirmRoleChange({ memberID: 1, currentRole: CO_CREATOR });

    expect(listedIDs()).toEqual([2, 1]);
    expect($("#MemberRowActionAnnouncement").text()).toBe(
      `zed is no longer a co-owner. ${APP_CONFIG.strings.MEMBER_ROLE_CHANGE_REVOKE_POSITION}`,
    );
  });

  it.each(["name_az", "recently_joined"] as const)(
    "adds no position clause under %s",
    (memberSort) => {
      seedMembers(
        [
          { id: 1, username: "amy", memberRole: MEMBER },
          { id: 2, username: "bob", memberRole: MEMBER },
          { id: 3, username: "cat", memberRole: MEMBER },
        ],
        memberSort,
      );

      confirmRoleChange({ memberID: 3, currentRole: MEMBER });

      expect($("#MemberRowActionAnnouncement").text()).toBe(
        "cat is now a co-owner.",
      );
    },
  );

  it("adds no clause under role_then_name when the row did not move", () => {
    seedMembers(
      [
        { id: 1, username: "amy", memberRole: CO_CREATOR },
        { id: 2, username: "bob", memberRole: MEMBER },
      ],
      "role_then_name",
    );

    confirmRoleChange({ memberID: 1, currentRole: CO_CREATOR });

    expect(listedIDs()).toEqual([1, 2]);
    expect($("#MemberRowActionAnnouncement").text()).toBe(
      "amy is no longer a co-owner.",
    );
  });

  it("still announces the clause for a filter-hidden row and never scrolls to it", () => {
    seedMembers(
      [
        { id: 1, username: "amy", memberRole: MEMBER },
        { id: 2, username: "bob", memberRole: MEMBER },
      ],
      "role_then_name",
    );
    const row = $(`.member[memberid="2"]`)[0];
    row.classList.add("hidden");
    row.scrollIntoView = vi.fn();
    mockRowRect({ memberID: 2, top: 500, bottom: 540 });

    confirmRoleChange({ memberID: 2, currentRole: MEMBER });

    expect(row.scrollIntoView).not.toHaveBeenCalled();
    expect($("#MemberRowActionAnnouncement").text()).toBe(
      `bob is now a co-owner. ${APP_CONFIG.strings.MEMBER_ROLE_CHANGE_GRANT_POSITION}`,
    );
  });

  it("scrolls only the moved role-changed row, and only when it is hidden", () => {
    seedMembers(
      [
        { id: 1, username: "amy", memberRole: MEMBER },
        { id: 2, username: "bob", memberRole: MEMBER },
      ],
      "role_then_name",
    );
    const bystander = $(`.member[memberid="1"]`)[0];
    const changed = $(`.member[memberid="2"]`)[0];
    bystander.scrollIntoView = vi.fn();
    changed.scrollIntoView = vi.fn();
    mockRowRect({ memberID: 1, top: 500, bottom: 540 });
    mockRowRect({ memberID: 2, top: 500, bottom: 540 });

    confirmRoleChange({ memberID: 2, currentRole: MEMBER });

    expect(changed.scrollIntoView).toHaveBeenCalledTimes(1);
    expect(bystander.scrollIntoView).not.toHaveBeenCalled();
  });

  it("does not scroll a moved row that stays visible", () => {
    seedMembers(
      [
        { id: 1, username: "amy", memberRole: MEMBER },
        { id: 2, username: "bob", memberRole: MEMBER },
      ],
      "role_then_name",
    );
    const changed = $(`.member[memberid="2"]`)[0];
    changed.scrollIntoView = vi.fn();
    mockRowRect({ memberID: 2, top: 10, bottom: 40 });

    confirmRoleChange({ memberID: 2, currentRole: MEMBER });

    expect(changed.scrollIntoView).not.toHaveBeenCalled();
  });

  it("does not scroll a row that did not move, even when it is out of view", () => {
    seedMembers(
      [
        { id: 1, username: "amy", memberRole: MEMBER },
        { id: 2, username: "bob", memberRole: MEMBER },
      ],
      "name_az",
    );
    const changed = $(`.member[memberid="2"]`)[0];
    changed.scrollIntoView = vi.fn();
    mockRowRect({ memberID: 2, top: 500, bottom: 540 });

    confirmRoleChange({ memberID: 2, currentRole: MEMBER });

    expect(listedIDs()).toEqual([1, 2]);
    expect(changed.scrollIntoView).not.toHaveBeenCalled();
  });

  it("runs setState, the swap and the reorder before the scroll, and the announcement last", () => {
    seedMembers(
      [
        { id: 1, username: "amy", memberRole: MEMBER },
        { id: 2, username: "bob", memberRole: MEMBER },
      ],
      "role_then_name",
    );
    const changed = $(`.member[memberid="2"]`)[0];
    mockRowRect({ memberID: 2, top: 500, bottom: 540 });
    let orderAtScroll: number[] = [];
    let storeRoleAtScroll = "";
    let iconAtScroll = 0;
    let announcementAtScroll = "unset";
    changed.scrollIntoView = vi.fn(() => {
      orderAtScroll = listedIDs();
      storeRoleAtScroll =
        getState().members.find((member) => member.id === 2)?.memberRole ?? "";
      iconAtScroll = $(
        `.member[memberid="2"] svg.bi-diamond-half.memberRole`,
      ).length;
      announcementAtScroll = $("#MemberRowActionAnnouncement").text();
    });

    confirmRoleChange({ memberID: 2, currentRole: MEMBER });

    expect(orderAtScroll).toEqual([2, 1]);
    expect(storeRoleAtScroll).toBe(CO_CREATOR);
    expect(iconAtScroll).toBe(1);
    expect(announcementAtScroll).toBe("");
    expect($("#MemberRowActionAnnouncement").text()).not.toBe("");
  });

  it("leaves focus outside #listMembers alone (the confirm modal owns it)", () => {
    seedMembers(
      [
        { id: 1, username: "amy", memberRole: MEMBER },
        { id: 2, username: "bob", memberRole: MEMBER },
      ],
      "role_then_name",
    );
    const submit = $("#modalSubmit")[0];
    mockAjaxSuccess();
    modifyMemberRoleShowModal({ memberID: 2, currentRole: MEMBER, utubID: 1 });
    submit.focus();
    $("#modalSubmit").trigger("click");

    expect(listedIDs()).toEqual([2, 1]);
    expect(document.activeElement).toBe(submit);
  });
});
