import type { UtubDetail } from "../../../types/utub.js";
import type { OwnershipTransferredResponse } from "../transfer.js";

import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { isUtubLockedHandled } from "../../utub-locked.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { getUTubInfo } from "../../utubs/selectors.js";
import { getAllUTubs } from "../../utubs/utils.js";
import { transferOwnershipShowModal } from "../transfer.js";

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));
vi.mock("../../utub-locked.js", () => ({
  isUtubLockedHandled: vi.fn(() => false),
}));
vi.mock("../../../lib/metrics-client.js", () => ({ emit: vi.fn() }));

// buildSelectedUTub is kept REAL (its real setState flips isCurrentUserOwner/
// isCoCreator so the final setUTubDeckOnUTubSelected re-call reads the demoted
// role); only getUTubInfo is stubbed so the reconciliation resolves a fixed,
// already-transferred UTub payload.
vi.mock("../../utubs/selectors.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../utubs/selectors.js")
  >("../../utubs/selectors.js");
  return { ...actual, getUTubInfo: vi.fn() };
});

// getAllUTubs is stubbed to resolve the post-transfer summary list; buildUTubDeck
// / createUTubSelector stay REAL so the left UTub-deck DOM actually rebuilds and
// the demoted user's role icon can be asserted at the DOM level.
vi.mock("../../utubs/utils.js", async () => {
  const actual = await vi.importActual<typeof import("../../utubs/utils.js")>(
    "../../utubs/utils.js",
  );
  return { ...actual, getAllUTubs: vi.fn() };
});

// buildSelectedUTub's incidental collaborators (header fit / description button /
// mobile history) are irrelevant to what this suite asserts — stub them so the
// real buildSelectedUTub runs without a full URL-deck DOM fixture.
vi.mock("../../utubs/header-fit.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../utubs/header-fit.js")
  >("../../utubs/header-fit.js");
  return { ...actual, fitUTubHeaderAndSubheader: vi.fn() };
});
vi.mock("../../urls/update-description.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../urls/update-description.js")
  >("../../urls/update-description.js");
  return {
    ...actual,
    removeEventListenersForShowCreateUTubDescIfEmptyDesc: vi.fn(),
    showCreateDescriptionButtonAlways: vi.fn(),
  };
});
vi.mock("../../mobile.js", async () => {
  const actual =
    await vi.importActual<typeof import("../../mobile.js")>("../../mobile.js");
  return { ...actual, isMobile: () => false };
});

// buildSelectedUTub emits UTUB_SELECTED; its real subscribers (URL deck, etc.)
// need a full home DOM this suite deliberately doesn't stand up. Stub only the
// event-bus emit (keep on/AppEvents real) — the reconciliation this suite
// asserts runs through direct calls (buildSelectedUTub → setUTubDeckOnUTubSelected)
// and the getAllUTubs → buildUTubDeck refetch, never through that event.
vi.mock("../../../lib/event-bus.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../../lib/event-bus.js")
  >("../../../lib/event-bus.js");
  return { ...actual, emit: vi.fn() };
});

const $ = window.jQuery;

const TRANSFER_HTML = `
  <div id="confirmModal">
    <div id="confirmModalTitle"></div>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <div id="modalRedirect"></div>
  </div>
  <h2 id="MemberDeckHeader" tabindex="-1">Members</h2>
  <button id="memberBtnTransferOwner"></button>
  <button id="sentinelFocus"></button>
  <span id="MemberRowActionAnnouncement" class="visually-hidden" aria-live="polite"></span>
  <span id="UTubDeckCount"></span>
  <div id="listUTubs"></div>
  <button id="utubBtnDelete" class="visible"></button>
  <button id="memberSelfBtnDelete" class="hidden"></button>
  <span id="URLDeckLockIcon" class="hidden"></span>
  <h2 id="URLDeckSubheader"></h2>
  <div id="UTubDescriptionSubheaderWrap"></div>
  <button id="URLDeckSubheaderCreateDescription"></button>
  <div id="URLDeckNoDescription"></div>
  <input id="utubDescriptionUpdate" />
`;

function installModalStub(): void {
  ($.fn as unknown as Record<string, unknown>).modal = function (this: JQuery) {
    return this;
  };
}

// The acting user (id 1) after handing ownership to user 5: demoted to
// co-owner (isCreator false / isCoCreator true), UTub now owned by 5.
function transferredUtubDetail(): UtubDetail {
  return {
    status: "Success",
    id: 1,
    name: "MyUTub",
    description: "",
    createdAt: "2026-01-01T00:00:00Z",
    isCreator: false,
    isCoCreator: true,
    isLocked: false,
    currentUser: 1,
    createdByUserID: 5,
    urls: [],
    tags: [],
    members: [
      { id: 5, username: "newowner", memberRole: "creator" },
      { id: 1, username: "acting", memberRole: "cocreator" },
    ],
  } as UtubDetail;
}

function transferredSummaryList(): { utubs: unknown[] } {
  return {
    utubs: [
      { id: 1, name: "MyUTub", memberRole: "cocreator", isLocked: false },
    ],
  };
}

const SUCCESS_RESPONSE: OwnershipTransferredResponse = {
  utubID: 1,
  newOwner: { id: 5, username: "newowner", memberRole: "creator" },
  previousOwner: { id: 1, username: "acting", memberRole: "cocreator" },
} as OwnershipTransferredResponse;

function mockAjaxSuccess(response: OwnershipTransferredResponse): void {
  vi.mocked(ajaxCall).mockReturnValue(
    createMockJqXHRChainable({
      done: (cb: unknown) =>
        (cb as (_r: unknown, _t: unknown, xhr: JQuery.jqXHR) => void)(
          response,
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

const flush = (): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, 0));

describe("transferOwnership — confirm + PATCH + reconciliation", () => {
  beforeEach(() => {
    document.body.innerHTML = TRANSFER_HTML;
    vi.clearAllMocks();
    resetStore();
    installModalStub();
    window.history.replaceState(null, "", "/");
    setState({ activeUTubID: 1, isCurrentUserOwner: true, utubOwnerID: 1 });
    vi.mocked(is429Handled).mockReturnValue(false);
    vi.mocked(isUtubLockedHandled).mockReturnValue(false);
    vi.mocked(getUTubInfo).mockResolvedValue(transferredUtubDetail());
    vi.mocked(getAllUTubs).mockResolvedValue(transferredSummaryList() as never);
  });

  it("PATCHes the endpoint, reconciles both decks in order, announces, then focuses the header on modal close", async () => {
    mockAjaxSuccess(SUCCESS_RESPONSE);

    transferOwnershipShowModal({
      newOwnerId: 5,
      newOwnerUsername: "newowner",
      utubID: 1,
      opener: "#memberBtnTransferOwner",
    });
    $("#modalSubmit").trigger("click");

    // PATCH shape (sync).
    expect(vi.mocked(ajaxCall)).toHaveBeenLastCalledWith(
      "patch",
      "/utubs/1/owner",
      {
        new_owner_id: 5,
      },
    );

    // Announcement is set synchronously in the success handler.
    expect($("#MemberRowActionAnnouncement").text()).toBe(
      "newowner is now the owner. You're a co-owner.",
    );
    expect($("#MemberRowActionAnnouncement").attr("aria-live")).toBe("polite");

    // Let the sequenced reconciliation promises resolve.
    await flush();

    // DD-13 sequencing: the select-rebuild fetch resolves strictly BEFORE the
    // left-deck summary refetch is invoked.
    expect(vi.mocked(getUTubInfo).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(getAllUTubs).mock.invocationCallOrder[0],
    );

    // Left UTub-deck selector rebuilt from the summary list — its role icon now
    // reflects the demoted (co-owner) role at the rendered-DOM level.
    expect($(`.UTubSelector[utubid="1"] svg.bi-diamond-half`).length).toBe(1);
    // DD-9: the .active class re-add survives buildUTubDeck's rebuild.
    expect($(`.UTubSelector[utubid="1"]`).hasClass("active")).toBe(true);

    // DD-13: the final setUTubDeckOnUTubSelected re-call ran last with the new
    // (demoted) role — owner Delete gone, member Leave shown.
    expect($("#utubBtnDelete").hasClass("hidden")).toBe(true);
    expect($("#memberSelfBtnDelete").hasClass("visible")).toBe(true);
    expect(getState().isCurrentUserOwner).toBe(false);

    // Deferred focus (DD-12): only on the modal's own close event, branching on
    // _transferSucceeded — not _transferConfirmed.
    $("#confirmModal").trigger("hidden.bs.modal");
    expect(document.activeElement).toBe(
      document.getElementById("MemberDeckHeader"),
    );
  });

  it("redirects to the error page if the select-rebuild refetch (getUTubInfo) fails after a 200 PATCH", async () => {
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      mockAjaxSuccess(SUCCESS_RESPONSE);
      vi.mocked(getUTubInfo).mockRejectedValueOnce(new Error("boom"));

      transferOwnershipShowModal({
        newOwnerId: 5,
        newOwnerUsername: "newowner",
        utubID: 1,
        opener: "#memberBtnTransferOwner",
      });
      $("#modalSubmit").trigger("click");
      await flush();

      expect(assignSpy).toHaveBeenCalledWith(APP_CONFIG.routes.errorPage);
    } finally {
      assignSpy.mockRestore();
    }
  });

  it("redirects to the error page if the left-deck summary refetch (getAllUTubs) fails after a 200 PATCH", async () => {
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      mockAjaxSuccess(SUCCESS_RESPONSE);
      vi.mocked(getAllUTubs).mockRejectedValueOnce(new Error("boom") as never);

      transferOwnershipShowModal({
        newOwnerId: 5,
        newOwnerUsername: "newowner",
        utubID: 1,
        opener: "#memberBtnTransferOwner",
      });
      $("#modalSubmit").trigger("click");
      await flush();

      expect(assignSpy).toHaveBeenCalledWith(APP_CONFIG.routes.errorPage);
    } finally {
      assignSpy.mockRestore();
    }
  });

  it("emits the shown + confirmed UI metrics", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");
    mockAjaxSuccess(SUCCESS_RESPONSE);

    transferOwnershipShowModal({
      newOwnerId: 5,
      newOwnerUsername: "newowner",
      utubID: 1,
      opener: "#memberBtnTransferOwner",
    });
    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_TRANSFER_OWNER_SHOWN,
    });

    $("#modalSubmit").trigger("click");
    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_TRANSFER_OWNER_CONFIRMED,
    });
  });

  it("on a plain dismiss (no submit): emits CANCEL and restores focus to an HTMLElement opener", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");
    const openerEl = document.getElementById(
      "memberBtnTransferOwner",
    ) as HTMLElement;

    transferOwnershipShowModal({
      newOwnerId: 5,
      newOwnerUsername: "newowner",
      utubID: 1,
      opener: openerEl,
    });
    $("#modalDismiss").trigger("click");
    $("#confirmModal").trigger("hidden.bs.modal");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_TRANSFER_OWNER_CANCEL,
    });
    expect(document.activeElement).toBe(openerEl);
  });

  it("on a plain dismiss: restores focus to a selector-string opener", () => {
    transferOwnershipShowModal({
      newOwnerId: 5,
      newOwnerUsername: "newowner",
      utubID: 1,
      opener: "#memberBtnTransferOwner",
    });
    $("#confirmModal").trigger("hidden.bs.modal");

    expect(document.activeElement).toBe(
      document.getElementById("memberBtnTransferOwner"),
    );
  });

  it("DD-14: a later unrelated close of the shared modal is inert (flags reset + handler unbound)", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    // First: a genuine cancel of the transfer modal fires exactly one CANCEL.
    transferOwnershipShowModal({
      newOwnerId: 5,
      newOwnerUsername: "newowner",
      utubID: 1,
      opener: "#memberBtnTransferOwner",
    });
    $("#confirmModal").trigger("hidden.bs.modal");
    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_TRANSFER_OWNER_CANCEL,
    });

    // Simulate an unrelated later close (role.ts/delete.ts) of the shared modal.
    vi.mocked(emit).mockClear();
    (document.getElementById("sentinelFocus") as HTMLElement).focus();
    $("#confirmModal").trigger("hidden.bs.modal");

    // No second CANCEL, no header focus grab — the handler unbound itself.
    expect(emit).not.toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_TRANSFER_OWNER_CANCEL,
    });
    expect(document.activeElement).toBe(
      document.getElementById("sentinelFocus"),
    );
  });

  it("surfaces a 400 TARGET_ALREADY_OWNER message assertively without redirecting", () => {
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      mockAjaxFailure({
        status: 400,
        responseJSON: { message: "That member already owns this UTub." },
      });

      transferOwnershipShowModal({
        newOwnerId: 5,
        newOwnerUsername: "newowner",
        utubID: 1,
        opener: "#memberBtnTransferOwner",
      });
      $("#modalSubmit").trigger("click");

      expect($("#MemberRowActionAnnouncement").attr("aria-live")).toBe(
        "assertive",
      );
      expect($("#MemberRowActionAnnouncement").text()).toBe(
        "That member already owns this UTub.",
      );
      expect(assignSpy).not.toHaveBeenCalled();
      expect($("#modalSubmit").prop("disabled")).toBe(false);
    } finally {
      assignSpy.mockRestore();
    }
  });

  it("surfaces a 404 member-not-in-UTub message assertively without redirecting", () => {
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      mockAjaxFailure({
        status: 404,
        responseJSON: { message: "That member is not in this UTub." },
      });

      transferOwnershipShowModal({
        newOwnerId: 5,
        newOwnerUsername: "newowner",
        utubID: 1,
        opener: "#memberBtnTransferOwner",
      });
      $("#modalSubmit").trigger("click");

      expect($("#MemberRowActionAnnouncement").text()).toBe(
        "That member is not in this UTub.",
      );
      expect(assignSpy).not.toHaveBeenCalled();
    } finally {
      assignSpy.mockRestore();
    }
  });

  it("swaps the page body on a 403 invalid-CSRF html response", () => {
    mockAjaxFailure({
      status: 403,
      getResponseHeader: () => "text/html; charset=utf-8",
      responseText: `<div id="csrfReload">reload</div>`,
    });

    transferOwnershipShowModal({
      newOwnerId: 5,
      newOwnerUsername: "newowner",
      utubID: 1,
      opener: "#memberBtnTransferOwner",
    });
    $("#modalSubmit").trigger("click");

    expect($("#csrfReload").length).toBe(1);
  });

  it("early-returns on a 429 without announcing or redirecting", () => {
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    try {
      vi.mocked(is429Handled).mockReturnValue(true);
      mockAjaxFailure({ status: 429 });

      transferOwnershipShowModal({
        newOwnerId: 5,
        newOwnerUsername: "newowner",
        utubID: 1,
        opener: "#memberBtnTransferOwner",
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
      mockAjaxFailure({ status: 403 });

      transferOwnershipShowModal({
        newOwnerId: 5,
        newOwnerUsername: "newowner",
        utubID: 1,
        opener: "#memberBtnTransferOwner",
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
      mockAjaxFailure({ status: 500 });

      transferOwnershipShowModal({
        newOwnerId: 5,
        newOwnerUsername: "newowner",
        utubID: 1,
        opener: "#memberBtnTransferOwner",
      });
      $("#modalSubmit").trigger("click");

      expect(assignSpy).toHaveBeenCalledWith(APP_CONFIG.routes.errorPage);
    } finally {
      assignSpy.mockRestore();
    }
  });
});
