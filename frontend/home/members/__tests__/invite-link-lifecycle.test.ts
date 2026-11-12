import {
  initInviteLinkPanel,
  isInviteLinkPanelOpen,
  resetInviteLinkPanel,
} from "../invite-link-panel.js";
import {
  createInviteLink,
  getInviteLink,
  replaceExpiryDays,
  replaceInviteLink,
  revokeInviteLink,
  type InviteLink,
  type InviteLinkMutationFailure,
} from "../invite-link-client.js";
import {
  dismissInviteModal,
  INVITE_MODAL_FIXTURE,
  installModalMock,
} from "../../../__tests__/helpers/invite-modal.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { updateUTubOnFindingStaleData } from "../../utubs/stale-data.js";
import { AppEvents, emit as emitAppEvent } from "../../../lib/event-bus.js";

vi.mock("../invite-link-client.js", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../invite-link-client.js")>()),
  getInviteLink: vi.fn(),
  createInviteLink: vi.fn(),
  replaceInviteLink: vi.fn(),
  revokeInviteLink: vi.fn(),
}));
vi.mock("../../utubs/stale-data.js", () => ({
  updateUTubOnFindingStaleData: vi.fn(),
}));
vi.mock("../../../lib/metrics-client.js", () => ({ emit: vi.fn() }));
vi.mock("../member-combobox.js", () => ({
  hideAndResetMemberCombobox: vi.fn(),
}));
vi.mock("../search.js", () => ({ closeMemberNameFilter: vi.fn() }));

const $ = window.jQuery;
const strings = APP_CONFIG.strings;
const DAY_MS = 86_400_000;
const NOW = Date.parse("2099-01-01T00:00:00Z");

function liveLink(overrides: Partial<InviteLink> = {}): InviteLink {
  return {
    token: "abcdefghijklmnopqrstuv",
    status: "live",
    expiresAt: "2099-01-05T00:00:00Z",
    maxUses: 10,
    useCount: 3,
    createdAt: "2099-01-01T00:00:00Z",
    creatorUsername: "alice",
    ...overrides,
  };
}

function deadLink(): InviteLink {
  return liveLink({ status: "expired", expiresAt: "2098-12-01T00:00:00Z" });
}

function deferred<Value>() {
  let resolve!: (value: Value) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<Value>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

function failure(
  status: number,
  errorCode: number | null,
): InviteLinkMutationFailure {
  return { kind: "error", status, errorCode };
}

async function settle() {
  await vi.advanceTimersByTimeAsync(0);
}

function announcement() {
  return $("#MemberRowActionAnnouncement").text();
}

async function openWith(link: InviteLink | null) {
  vi.mocked(getInviteLink).mockResolvedValue(link);
  $("#memberBtnInviteLink").trigger("click");
  await settle();
}

async function click(selector: string) {
  $(selector).trigger("click");
  await settle();
}

// Bootstrap hides the modal on Escape.
function pressEscape() {
  dismissInviteModal();
}

async function confirmNewLink() {
  await click("#inviteLinkNewBtn");
  await click("#inviteLinkConfirmActionBtn");
}

async function confirmRevoke() {
  await click("#inviteLinkRevokeBtn");
  await click("#inviteLinkConfirmActionBtn");
}

describe("invite link lifecycle (create, New link, Revoke)", () => {
  let unsubscribe: () => void;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    Object.defineProperty(HTMLElement.prototype, "offsetParent", {
      configurable: true,
      get(this: HTMLElement) {
        return this.closest(".hidden") === null ? document.body : null;
      },
    });
    document.body.innerHTML = INVITE_MODAL_FIXTURE;
    installModalMock();
    vi.clearAllMocks();
    resetStore();
    setState({
      activeUTubID: 1,
      isCurrentUserOwner: true,
      isCoCreator: false,
      isCurrentUTubLocked: false,
    });
    unsubscribe = initInviteLinkPanel();
  });

  afterEach(() => {
    unsubscribe();
    resetInviteLinkPanel();
    vi.useRealTimers();
    delete (HTMLElement.prototype as unknown as Record<string, unknown>)
      .offsetParent;
  });

  describe("create", () => {
    it("posts the selected settings, renders live, focuses Copy and announces", async () => {
      await openWith(null);
      $("#inviteLinkExpiresSelect").val("30");
      $("#inviteLinkUsesSelect").val("5");
      vi.mocked(createInviteLink).mockResolvedValue(liveLink());

      await click("#inviteLinkCreateBtn");

      expect(createInviteLink).toHaveBeenCalledWith({
        utubID: 1,
        expiresInDays: 30,
        maxUses: 5,
      });
      expect($("#inviteLinkUrlInput").length).toBe(1);
      expect(document.activeElement?.id).toBe("inviteLinkCopyBtn");
      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_CREATED);
    });

    it("from a dead link posts the defaults (7 days, unlimited)", async () => {
      await openWith(deadLink());
      vi.mocked(createInviteLink).mockResolvedValue(liveLink());

      await click("#inviteLinkCreateBtn");

      expect(createInviteLink).toHaveBeenCalledWith({
        utubID: 1,
        expiresInDays: 7,
        maxUses: null,
      });
      expect(document.activeElement?.id).toBe("inviteLinkCopyBtn");
    });
  });

  describe("inline confirm", () => {
    it("Revoke asks first, focuses Cancel and sends nothing until confirmed", async () => {
      await openWith(liveLink());

      await click("#inviteLinkRevokeBtn");

      const group = $("#inviteLinkModal [role='group']");
      expect(group.length).toBe(1);
      expect(group.attr("aria-label")).toBe(
        strings.INVITE_LINK_PANEL_CONFIRM_GROUP_LABEL,
      );
      expect(document.activeElement?.id).toBe("inviteLinkConfirmCancelBtn");
      expect(announcement()).toBe(
        strings.INVITE_LINK_PANEL_CONFIRM_REVOKE_QUESTION,
      );
      expect(revokeInviteLink).not.toHaveBeenCalled();
    });

    it("Cancel and the first Escape restore the footer and focus the origin; a second Escape closes", async () => {
      await openWith(liveLink());

      await click("#inviteLinkNewBtn");
      await click("#inviteLinkConfirmCancelBtn");
      expect($("#inviteLinkNewBtn").length).toBe(1);
      expect($("#inviteLinkConfirmActionBtn").length).toBe(0);
      expect(document.activeElement?.id).toBe("inviteLinkNewBtn");

      await click("#inviteLinkRevokeBtn");
      pressEscape();
      expect($("#inviteLinkConfirmActionBtn").length).toBe(0);
      expect(document.activeElement?.id).toBe("inviteLinkRevokeBtn");
      expect(isInviteLinkPanelOpen()).toBe(true);

      pressEscape();
      expect(isInviteLinkPanelOpen()).toBe(false);
      expect(document.activeElement?.id).toBe("memberBtnInviteLink");
    });

    it("a restored footer's buttons still work", async () => {
      await openWith(liveLink());
      await click("#inviteLinkRevokeBtn");
      await click("#inviteLinkConfirmCancelBtn");

      await click("#inviteLinkNewBtn");

      expect($("#inviteLinkConfirmActionBtn").text()).toBe(
        strings.INVITE_LINK_PANEL_CONFIRM_NEW_ACTION,
      );
    });
  });

  describe("revoke", () => {
    it("shows the empty state, focuses Create link and announces", async () => {
      await openWith(liveLink());
      vi.mocked(revokeInviteLink).mockResolvedValue(true);

      await confirmRevoke();

      expect(revokeInviteLink).toHaveBeenCalledWith({ utubID: 1 });
      expect($("#inviteLinkCreateBtn").length).toBe(1);
      expect($("#inviteLinkUrlInput").length).toBe(0);
      expect(document.activeElement?.id).toBe("inviteLinkCreateBtn");
      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_REVOKED);
    });
  });

  describe("New link", () => {
    it("renders the new token live, focuses Copy and announces", async () => {
      await openWith(liveLink());
      vi.mocked(replaceInviteLink).mockResolvedValue(
        liveLink({ token: "zzzzzzzzzzzzzzzzzzzzzz" }),
      );

      await confirmNewLink();

      expect(($("#inviteLinkUrlInput").val() as string).endsWith("zzzz")).toBe(
        true,
      );
      expect(document.activeElement?.id).toBe("inviteLinkCopyBtn");
      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_REPLACED);
    });

    // [remaining ms, expected expires_in_days]
    const boundaries: Array<[string, number, number]> = [
      ["just over 0", 1, 1],
      ["exactly 1 day", DAY_MS, 1],
      ["just over 1 day", DAY_MS + 1, 7],
      ["exactly 7 days", 7 * DAY_MS, 7],
      ["just over 7 days", 7 * DAY_MS + 1, 30],
      ["exactly 30 days", 30 * DAY_MS, 30],
    ];

    it("a link whose expiry is already past replaces with expires_in_days 1", () => {
      expect(
        replaceExpiryDays({
          expiresAt: new Date(NOW - DAY_MS).toISOString(),
          now: NOW,
        }),
      ).toBe(1);
    });

    it.each(
      boundaries.flatMap(([name, remaining, days]) =>
        [null, 5].map((maxUses) => [name, remaining, days, maxUses] as const),
      ),
    )(
      "replace body with remaining %s (%i ms) sends expires_in_days %i, max_uses %s",
      async (_name, remaining, days, maxUses) => {
        await openWith(
          liveLink({
            expiresAt: new Date(NOW + remaining).toISOString(),
            maxUses,
            useCount: 0,
          }),
        );
        vi.mocked(replaceInviteLink).mockResolvedValue(liveLink());

        await confirmNewLink();

        expect(replaceInviteLink).toHaveBeenCalledWith({
          utubID: 1,
          expiresInDays: days,
          maxUses,
        });
      },
    );
  });

  describe("error dispatch", () => {
    it.each([
      ["replace", "#inviteLinkNewBtn"],
      ["revoke", "#inviteLinkRevokeBtn"],
    ] as const)(
      "%s code 1 resyncs (re-GET) and announces the revoked message",
      async (_kind, opener) => {
        await openWith(liveLink());
        vi.mocked(replaceInviteLink).mockRejectedValue(failure(404, 1));
        vi.mocked(revokeInviteLink).mockRejectedValue(failure(404, 1));
        vi.mocked(getInviteLink).mockResolvedValue(null);

        await click(opener);
        await click("#inviteLinkConfirmActionBtn");

        expect(getInviteLink).toHaveBeenCalledTimes(2);
        expect($("#inviteLinkCreateBtn").length).toBe(1);
        expect(document.activeElement?.id).toBe("inviteLinkExpiresSelect");
        expect(announcement()).toBe(strings.INVITE_LINK_PANEL_RESYNC_REVOKED);
      },
    );

    it("create code 4 resyncs into the live state", async () => {
      await openWith(null);
      vi.mocked(createInviteLink).mockRejectedValue(failure(409, 4));
      vi.mocked(getInviteLink).mockResolvedValue(liveLink());

      await click("#inviteLinkCreateBtn");

      expect($("#inviteLinkUrlInput").length).toBe(1);
      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_RESYNC_LIVE_EXISTS);
    });

    it.each([
      ["code 1", 1, "revoked"],
      ["code 4", 4, "live exists"],
    ])(
      "%s resync landing dead makes one composed announcement write",
      async (_name, code) => {
        // revoke (code 1) and create (code 4) both land on a dead row.
        if (code === 1) {
          await openWith(liveLink());
          vi.mocked(revokeInviteLink).mockRejectedValue(failure(404, 1));
        } else {
          await openWith(null);
          vi.mocked(createInviteLink).mockRejectedValue(failure(409, 4));
        }
        vi.mocked(getInviteLink).mockResolvedValue(deadLink());
        // The confirm question is announced when it opens: not part of the resync.
        if (code === 1) await click("#inviteLinkRevokeBtn");
        const writes: string[] = [];
        const region = $("#MemberRowActionAnnouncement")[0];
        const observer = new MutationObserver(() => {
          if (region.textContent) writes.push(region.textContent);
        });
        observer.observe(region, { childList: true, characterData: true });

        if (code === 1) await click("#inviteLinkConfirmActionBtn");
        else await click("#inviteLinkCreateBtn");
        await Promise.resolve();
        observer.disconnect();

        const message =
          code === 1
            ? strings.INVITE_LINK_PANEL_RESYNC_REVOKED
            : strings.INVITE_LINK_PANEL_RESYNC_LIVE_EXISTS;
        expect(announcement().startsWith(message)).toBe(true);
        expect(announcement()).toContain("This link expired on");
        expect(writes.filter((text) => text.length > 0)).toHaveLength(1);
      },
    );

    it("a resync re-GET that fails with 500 shows load-failed", async () => {
      await openWith(liveLink());
      vi.mocked(revokeInviteLink).mockRejectedValue(failure(404, 1));
      vi.mocked(getInviteLink).mockRejectedValue({ kind: "failed" });

      await confirmRevoke();

      expect($("#inviteLinkTryAgainBtn").length).toBe(1);
      expect(isInviteLinkPanelOpen()).toBe(true);
    });

    it("a resync re-GET that is denied closes the panel", async () => {
      await openWith(liveLink());
      vi.mocked(revokeInviteLink).mockRejectedValue(failure(404, 1));
      vi.mocked(getInviteLink).mockRejectedValue({
        kind: "denied",
        errorCode: null,
      });

      await confirmRevoke();

      expect(isInviteLinkPanelOpen()).toBe(false);
      expect(updateUTubOnFindingStaleData).toHaveBeenCalledWith({ utubID: 1 });
    });

    it("code 3 (locked) closes the panel, announces the lock and refreshes the UTub", async () => {
      await openWith(liveLink());
      vi.mocked(revokeInviteLink).mockRejectedValue(failure(403, 3));

      await confirmRevoke();

      expect(isInviteLinkPanelOpen()).toBe(false);
      expect(announcement()).toBe(strings.UTUB_IS_LOCKED);
      expect(updateUTubOnFindingStaleData).toHaveBeenCalledWith({ utubID: 1 });
    });

    it.each([
      ["plain 403", 403],
      ["404 without a code", 404],
    ])(
      "%s closes the panel with the manage-lost message and refreshes",
      async (_name, status) => {
        await openWith(liveLink());
        vi.mocked(replaceInviteLink).mockRejectedValue(failure(status, null));

        await confirmNewLink();

        expect(isInviteLinkPanelOpen()).toBe(false);
        expect(announcement()).toBe(strings.INVITE_LINK_PANEL_MANAGE_LOST);
        expect(updateUTubOnFindingStaleData).toHaveBeenCalledWith({
          utubID: 1,
        });
      },
    );

    it.each([
      ["400 code 2", failure(400, 2)],
      ["500", failure(500, null)],
      ["timeout", failure(0, null)],
    ])(
      "%s shows the inline error, keeps the panel state and unlocks",
      async (_name, rejection) => {
        await openWith(liveLink());
        vi.mocked(revokeInviteLink).mockRejectedValue(rejection);

        await confirmRevoke();

        expect($("#inviteLinkInlineError").text()).toBe(
          strings.INVITE_LINK_PANEL_ERROR_GENERIC,
        );
        expect(announcement()).toBe(strings.INVITE_LINK_PANEL_ERROR_GENERIC);
        expect(isInviteLinkPanelOpen()).toBe(true);
        expect($("#inviteLinkConfirmActionBtn").length).toBe(1);
        expect($("[aria-disabled]").length).toBe(0);
        expect(getInviteLink).toHaveBeenCalledTimes(1);
        expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
      },
    );

    it("429 changes nothing and unlocks", async () => {
      await openWith(liveLink());
      vi.mocked(revokeInviteLink).mockRejectedValue({ kind: "rate_limited" });

      await confirmRevoke();

      expect($("#inviteLinkInlineError").length).toBe(0);
      expect($("[aria-disabled]").length).toBe(0);
      expect(isInviteLinkPanelOpen()).toBe(true);
    });

    it("a CSRF HTML 403 replaces the body", async () => {
      await openWith(liveLink());
      vi.mocked(revokeInviteLink).mockRejectedValue({
        kind: "csrf",
        html: "<p id='csrfPage'>expired</p>",
      });

      await confirmRevoke();

      expect($("#csrfPage").length).toBe(1);
    });
  });

  describe("in-flight locking", () => {
    it("locks controls with aria-disabled, sends one request and keeps focus", async () => {
      await openWith(null);
      const pending = deferred<InviteLink>();
      vi.mocked(createInviteLink).mockReturnValue(pending.promise);
      $("#inviteLinkCreateBtn")[0].focus();

      await click("#inviteLinkCreateBtn");
      await click("#inviteLinkCreateBtn");

      expect(createInviteLink).toHaveBeenCalledTimes(1);
      expect($("#inviteLinkCreateBtn").attr("aria-disabled")).toBe("true");
      expect($("#inviteLinkCreateBtn").prop("disabled")).toBe(false);
      expect(document.activeElement?.id).toBe("inviteLinkCreateBtn");

      pending.resolve(liveLink());
      await settle();
      expect($("[aria-disabled]").length).toBe(0);
    });

    it("locks the confirm action but not Cancel", async () => {
      await openWith(liveLink());
      const pending = deferred<true>();
      vi.mocked(revokeInviteLink).mockReturnValue(pending.promise);

      await confirmRevoke();

      expect($("#inviteLinkConfirmActionBtn").attr("aria-disabled")).toBe(
        "true",
      );
      expect($("#inviteLinkConfirmCancelBtn").attr("aria-disabled")).toBe(
        undefined,
      );
      await click("#inviteLinkConfirmActionBtn");
      expect(revokeInviteLink).toHaveBeenCalledTimes(1);
    });

    it("closing mid-request and reopening leaves no residue after the late response", async () => {
      await openWith(null);
      const pending = deferred<InviteLink>();
      vi.mocked(createInviteLink).mockReturnValue(pending.promise);
      await click("#inviteLinkCreateBtn");

      pressEscape();
      expect(isInviteLinkPanelOpen()).toBe(false);
      await openWith(null);
      pending.resolve(liveLink());
      await settle();

      expect($("[aria-disabled]").length).toBe(0);
      expect($("#inviteLinkModal").attr("aria-busy")).toBeUndefined();
      // The late response was dropped: still the empty state.
      expect($("#inviteLinkUrlInput").length).toBe(0);
      // And a fresh request is allowed.
      vi.mocked(createInviteLink).mockResolvedValue(liveLink());
      await click("#inviteLinkCreateBtn");
      expect(createInviteLink).toHaveBeenCalledTimes(2);
    });
  });

  describe("Escape during a lifecycle request", () => {
    it("closes the panel directly (confirm not cancelled first) and still announces the outcome", async () => {
      await openWith(liveLink());
      const pending = deferred<true>();
      vi.mocked(revokeInviteLink).mockReturnValue(pending.promise);
      await confirmRevoke();
      expect($("#inviteLinkConfirmActionBtn").length).toBe(1);

      pressEscape();

      expect(isInviteLinkPanelOpen()).toBe(false);
      pending.resolve(true);
      await settle();
      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_REVOKED);
      // Dropped render: the closed panel stays empty.
      expect($("#inviteLinkModalBody").children().length).toBe(0);
    });

    it("the in-flight flag is cleared by the close", async () => {
      await openWith(liveLink());
      vi.mocked(revokeInviteLink).mockReturnValue(deferred<true>().promise);
      await confirmRevoke();
      pressEscape();

      await openWith(liveLink());
      await click("#inviteLinkRevokeBtn");
      // A confirm opens (the guard is not left set by the closed session).
      expect($("#inviteLinkConfirmActionBtn").length).toBe(1);
    });
  });

  describe("outcome announcements after the panel moved on", () => {
    it("forced close: a late success is silent, a late error is still announced", async () => {
      await openWith(null);
      const pending = deferred<InviteLink>();
      vi.mocked(createInviteLink).mockReturnValue(pending.promise);
      await click("#inviteLinkCreateBtn");

      setState({ isCurrentUserOwner: false, isCoCreator: false });
      await settle();
      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_FORCED_CLOSE);

      pending.resolve(liveLink());
      await settle();
      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_FORCED_CLOSE);
    });

    it("forced close: a late 500 still announces the error", async () => {
      await openWith(null);
      const pending = deferred<InviteLink>();
      vi.mocked(createInviteLink).mockReturnValue(pending.promise);
      await click("#inviteLinkCreateBtn");

      setState({ isCurrentUserOwner: false, isCoCreator: false });
      await settle();
      pending.reject(failure(500, null));
      await settle();

      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_ERROR_GENERIC);
    });

    it("a reopened panel's own create announces its success", async () => {
      await openWith(null);
      vi.mocked(createInviteLink).mockReturnValue(
        deferred<InviteLink>().promise,
      );
      await click("#inviteLinkCreateBtn");
      setState({ isCurrentUserOwner: false, isCoCreator: false });
      await settle();
      setState({ isCurrentUserOwner: true });
      await settle();

      await openWith(null);
      vi.mocked(createInviteLink).mockResolvedValue(liveLink());
      await click("#inviteLinkCreateBtn");

      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_CREATED);
    });

    it("a mobile deck switch with the Members deck hidden writes the outcome to the mobile region", async () => {
      await openWith(null);
      const pending = deferred<InviteLink>();
      vi.mocked(createInviteLink).mockReturnValue(pending.promise);
      await click("#inviteLinkCreateBtn");

      ($("#MemberDeck")[0] as HTMLElement).style.display = "none";
      emitAppEvent(AppEvents.MOBILE_DECK_SWITCHED, { target: "url-deck" });
      pending.resolve(liveLink());
      await settle();
      expect($("#MobilePanelAnnouncement").text()).toBe(
        strings.INVITE_LINK_PANEL_CREATED,
      );

      const failing = deferred<InviteLink>();
      vi.mocked(createInviteLink).mockReturnValue(failing.promise);
      ($("#MemberDeck")[0] as HTMLElement).style.display = "";
      ($("#MemberDeck")[0] as HTMLElement).style.display = "none";
      await openWith(null);
      await click("#inviteLinkCreateBtn");
      emitAppEvent(AppEvents.MOBILE_DECK_SWITCHED, { target: "url-deck" });
      failing.reject(failure(500, null));
      await settle();
      expect($("#MobilePanelAnnouncement").text()).toBe(
        strings.INVITE_LINK_PANEL_ERROR_GENERIC,
      );
    });

    it("an active-UTub change alone (no reset) drops the response silently", async () => {
      await openWith(null);
      const pending = deferred<InviteLink>();
      vi.mocked(createInviteLink).mockReturnValue(pending.promise);
      await click("#inviteLinkCreateBtn");

      setState({ activeUTubID: 2 });
      pending.resolve(liveLink());
      await settle();

      expect(announcement()).toBe("");
      expect($("#inviteLinkUrlInput").length).toBe(0);
    });

    it("Cancel is a no-op while a lifecycle request is in flight and the lock survives", async () => {
      await openWith(liveLink());
      vi.mocked(revokeInviteLink).mockReturnValue(deferred<true>().promise);
      await confirmRevoke();

      await click("#inviteLinkConfirmCancelBtn");

      expect($("#inviteLinkConfirmActionBtn").length).toBe(1);
      expect($("#inviteLinkConfirmActionBtn").attr("aria-disabled")).toBe(
        "true",
      );
    });

    it("a UTub switch mid-mutation announces nothing", async () => {
      await openWith(null);
      const pending = deferred<InviteLink>();
      vi.mocked(createInviteLink).mockReturnValue(pending.promise);
      await click("#inviteLinkCreateBtn");

      resetInviteLinkPanel();
      setState({ activeUTubID: 2 });
      pending.resolve(liveLink());
      await settle();

      expect(announcement()).toBe("");
      expect(getState().activeUTubID).toBe(2);
    });
  });
});
