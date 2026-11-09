import {
  initInviteLinkPanel,
  isInviteLinkPanelOpen,
  resetInviteLinkPanel,
} from "../invite-link-panel.js";
import {
  createInviteLink,
  getInviteLink,
  replaceInviteLink,
  updateInviteLink,
  type InviteLink,
  type InviteLinkMutationFailure,
} from "../invite-link-client.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { emit as emitMetric } from "../../../lib/metrics-client.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { resetStore, setState } from "../../../store/app-store.js";
import { updateUTubOnFindingStaleData } from "../../utubs/stale-data.js";

vi.mock("../invite-link-client.js", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../invite-link-client.js")>()),
  getInviteLink: vi.fn(),
  createInviteLink: vi.fn(),
  replaceInviteLink: vi.fn(),
  revokeInviteLink: vi.fn(),
  updateInviteLink: vi.fn(),
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

// A native `change`, as the browser fires on a user pick.
async function pick(selector: string, value: string) {
  const select = document.querySelector(selector) as HTMLSelectElement;
  select.value = value;
  select.dispatchEvent(new Event("change", { bubbles: true }));
  await settle();
}

function pressEscape() {
  const event = $.Event("keydown", { key: "Escape" });
  $(
    (document.activeElement ?? $("#MemberInvitePanel")[0]) as HTMLElement,
  ).trigger(event);
}

function selectEl(id: string): HTMLSelectElement {
  return document.getElementById(id) as HTMLSelectElement;
}

describe("invite link settings saves and copy", () => {
  let unsubscribe: () => void;
  let changeSpy: ReturnType<typeof vi.fn<(event: Event) => void>>;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    Object.defineProperty(HTMLElement.prototype, "offsetParent", {
      configurable: true,
      get(this: HTMLElement) {
        return this.closest(".hidden") === null ? document.body : null;
      },
    });
    document.body.innerHTML = `
      <div id="MemberDeck">
        <button id="MemberDeckHeaderAndCaret"></button>
        <button id="memberBtnInviteLink" class="hidden" aria-label="Invite link"
          aria-expanded="false" aria-controls="MemberInvitePanel"></button>
        <section id="MemberInvitePanel" class="hidden">
          <h3 id="MemberInvitePanelHeading" tabindex="-1">Invite link</h3>
          <div id="MemberInvitePanelBody"></div>
        </section>
        <span id="MemberRowActionAnnouncement" aria-live="polite"></span>
      </div>
      <span id="MobilePanelAnnouncement" aria-live="polite"></span>
    `;
    vi.clearAllMocks();
    resetStore();
    setState({
      activeUTubID: 1,
      isCurrentUserOwner: true,
      isCoCreator: false,
      isCurrentUTubLocked: false,
    });
    unsubscribe = initInviteLinkPanel();
    // Counts native `change` events: a programmatic restore must fire none.
    changeSpy = vi.fn<(event: Event) => void>();
    document
      .getElementById("MemberInvitePanelBody")
      ?.addEventListener("change", changeSpy);
  });

  afterEach(() => {
    unsubscribe();
    resetInviteLinkPanel();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    delete (HTMLElement.prototype as unknown as Record<string, unknown>)
      .offsetParent;
  });

  describe("saving", () => {
    it("PATCHes only the changed field, keeps focus, then updates in place and announces", async () => {
      await openWith(liveLink());
      const pending = deferred<InviteLink>();
      vi.mocked(updateInviteLink).mockReturnValue(pending.promise);
      selectEl("inviteLinkExpiresSelect").focus();

      await pick("#inviteLinkExpiresSelect", "30");

      expect(updateInviteLink).toHaveBeenCalledWith({
        utubID: 1,
        body: { expires_in_days: 30 },
      });
      const expires = selectEl("inviteLinkExpiresSelect");
      expect(expires.getAttribute("aria-busy")).toBe("true");
      expect($("#inviteLinkSaving").text()).toBe(
        strings.INVITE_LINK_PANEL_SAVING,
      );
      expect($("#inviteLinkRevokeBtn").attr("aria-disabled")).toBe("true");
      expect(document.activeElement).toBe(expires);

      pending.resolve(liveLink({ expiresAt: "2099-01-31T12:00:00Z" }));
      await settle();

      expect(selectEl("inviteLinkExpiresSelect")).toBe(expires);
      expect(expires.hasAttribute("aria-busy")).toBe(false);
      expect($("#inviteLinkSaving").length).toBe(0);
      expect($("#inviteLinkRevokeBtn").attr("aria-disabled")).toBeUndefined();
      expect(expires.value).toBe("");
      expect(expires.options[0].text).toContain("Jan");
      expect($(".invitePanelMeta").text()).toContain("Jan 31");
      expect(document.activeElement).toBe(expires);
      expect(announcement()).toContain("Link now expires");
      expect(changeSpy).toHaveBeenCalledTimes(1); // only the user's own pick
    });

    it("sends Unlimited as max_uses null", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockResolvedValue(
        liveLink({ maxUses: null }),
      );

      await pick("#inviteLinkUsesSelect", "");

      expect(updateInviteLink).toHaveBeenCalledWith({
        utubID: 1,
        body: { max_uses: null },
      });
      expect(announcement()).toBe(
        "Use limit set to " + strings.INVITE_LINK_PANEL_USES_UNLIMITED + ".",
      );
    });

    it("ignores a second change mid-save: no second PATCH, the select shows the pending value", async () => {
      await openWith(liveLink());
      const pending = deferred<InviteLink>();
      vi.mocked(updateInviteLink).mockReturnValue(pending.promise);

      await pick("#inviteLinkUsesSelect", "25");
      await pick("#inviteLinkUsesSelect", "5");
      expect(updateInviteLink).toHaveBeenCalledTimes(1);
      expect(selectEl("inviteLinkUsesSelect").value).toBe("25");

      await pick("#inviteLinkExpiresSelect", "1");
      expect(updateInviteLink).toHaveBeenCalledTimes(1);
      expect(selectEl("inviteLinkExpiresSelect").value).toBe("");

      pending.resolve(liveLink({ maxUses: 25 }));
      await settle();
      expect(selectEl("inviteLinkUsesSelect").value).toBe("25");
    });

    it("ignores a change while a lifecycle request is in flight", async () => {
      await openWith(null);
      // Empty-state selects are plain inputs read by Create link: never PATCH.
      await pick("#inviteLinkUsesSelect", "5");
      expect(updateInviteLink).not.toHaveBeenCalled();

      vi.mocked(createInviteLink).mockResolvedValue(liveLink());
      await click("#inviteLinkCreateBtn");

      // Live state: start a New link request and change a select meanwhile.
      await click("#inviteLinkNewBtn");
      const pending = deferred<InviteLink>();
      vi.mocked(replaceInviteLink).mockReturnValue(pending.promise);
      await click("#inviteLinkConfirmActionBtn");

      await pick("#inviteLinkUsesSelect", "25");
      expect(updateInviteLink).not.toHaveBeenCalled();
      expect(selectEl("inviteLinkUsesSelect").value).toBe("10");
    });

    it("a 200 with a non-live status renders the dead state and announces the reason only", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockResolvedValue(
        liveLink({ status: "used_up", maxUses: 3 }),
      );

      await pick("#inviteLinkUsesSelect", "3");

      expect($("#inviteLinkUrlInput").length).toBe(0);
      expect(document.activeElement?.id).toBe("inviteLinkCreateBtn");
      expect(announcement()).toBe("This link reached its limit of 3 uses.");
      expect(announcement()).not.toContain("Use limit set");
    });

    it("disables Uses options below the joined count up front", async () => {
      await openWith(liveLink({ useCount: 5 }));

      const disabled = Array.from(selectEl("inviteLinkUsesSelect").options)
        .filter((option) => option.disabled)
        .map((option) => option.value);
      expect(disabled).toEqual(["1"]);
      expect($("#inviteLinkUsesFloorHint").length).toBe(1);
    });

    it("a shortened Expires is saved with no warning", async () => {
      await openWith(liveLink({ expiresAt: "2099-01-30T00:00:00Z" }));
      vi.mocked(updateInviteLink).mockResolvedValue(liveLink());

      await pick("#inviteLinkExpiresSelect", "1");

      expect(updateInviteLink).toHaveBeenCalledWith({
        utubID: 1,
        body: { expires_in_days: 1 },
      });
      expect($("#inviteLinkConfirmActionBtn").length).toBe(0);
    });
  });

  describe("PATCH error dispatch", () => {
    it.each([
      ["500", failure(500, null)],
      ["timeout", failure(0, null)],
      ["400 code 2", failure(400, 2)],
    ])(
      "%s restores the committed value with an inline error and no change event",
      async (_name, error) => {
        await openWith(liveLink());
        vi.mocked(updateInviteLink).mockRejectedValue(error);
        selectEl("inviteLinkUsesSelect").focus();

        await pick("#inviteLinkUsesSelect", "25");

        const uses = selectEl("inviteLinkUsesSelect");
        expect(uses.value).toBe("10");
        expect($("#inviteLinkInlineError").text()).toBe(
          strings.INVITE_LINK_PANEL_ERROR_GENERIC,
        );
        expect(uses.getAttribute("aria-describedby")).toBe(
          "inviteLinkInlineError",
        );
        expect($("#inviteLinkSaving").length).toBe(0);
        expect(uses.hasAttribute("aria-busy")).toBe(false);
        expect(document.activeElement).toBe(uses);
        expect(changeSpy).toHaveBeenCalledTimes(1); // only the user's own pick
        expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
      },
    );

    it("code 1 resyncs to the empty state", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockRejectedValue(failure(404, 1));
      vi.mocked(getInviteLink).mockResolvedValue(null);

      await pick("#inviteLinkUsesSelect", "25");

      expect($("#inviteLinkCreateBtn").length).toBe(1);
      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_RESYNC_REVOKED);
    });

    it("code 5 resyncs to the dead state with one composed announcement", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockRejectedValue(failure(409, 5));
      vi.mocked(getInviteLink).mockResolvedValue(
        liveLink({ status: "expired", expiresAt: "2098-12-01T00:00:00Z" }),
      );

      await pick("#inviteLinkUsesSelect", "25");

      expect(document.activeElement?.id).toBe("inviteLinkCreateBtn");
      expect(announcement()).toBe(
        `${strings.INVITE_LINK_PANEL_RESYNC_DEAD_UPDATE} ${$("#MemberInvitePanelBody .invitePanelHint").text()}`,
      );
    });

    it("a plain 403 closes the panel and refreshes the UTub", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockRejectedValue(failure(403, null));

      await pick("#inviteLinkUsesSelect", "25");

      expect(isInviteLinkPanelOpen()).toBe(false);
      expect(updateUTubOnFindingStaleData).toHaveBeenCalledWith({ utubID: 1 });
    });

    it("a PATCH response dropped after a close and reopen does nothing", async () => {
      await openWith(liveLink());
      const pending = deferred<InviteLink>();
      vi.mocked(updateInviteLink).mockReturnValue(pending.promise);
      await pick("#inviteLinkUsesSelect", "25");

      pressEscape();
      await openWith(liveLink());
      vi.mocked(getInviteLink).mockClear();
      pending.reject(failure(403, null));
      await settle();

      expect(isInviteLinkPanelOpen()).toBe(true);
      expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
      expect(getInviteLink).not.toHaveBeenCalled();
      expect($("#inviteLinkSaving").length).toBe(0);
      expect($("#MemberInvitePanel [aria-busy]").length).toBe(0);
      expect($("#MemberInvitePanel [aria-disabled]").length).toBe(0);
    });

    it("a PATCH response dropped after a UTub switch announces and refreshes nothing", async () => {
      await openWith(liveLink());
      const pending = deferred<InviteLink>();
      vi.mocked(updateInviteLink).mockReturnValue(pending.promise);
      await pick("#inviteLinkUsesSelect", "25");

      setState({ activeUTubID: 2 });
      resetInviteLinkPanel();
      pending.reject(failure(404, null));
      await settle();

      expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
      expect(announcement()).toBe("");
    });
  });

  describe("code 6 restore", () => {
    it("restores the value, flags the select and refreshes the count in place", async () => {
      await openWith(liveLink({ useCount: 3 }));
      vi.mocked(updateInviteLink).mockRejectedValue(failure(400, 6));
      vi.mocked(getInviteLink).mockResolvedValue(liveLink({ useCount: 7 }));
      const uses = selectEl("inviteLinkUsesSelect");
      uses.focus();

      await pick("#inviteLinkUsesSelect", "5");

      expect(selectEl("inviteLinkUsesSelect")).toBe(uses);
      expect(uses.value).toBe("10");
      expect(uses.getAttribute("aria-invalid")).toBe("true");
      expect(uses.getAttribute("aria-describedby")).toBe(
        "inviteLinkInlineError",
      );
      expect($("#inviteLinkInlineError").text()).toBe(
        "7 people have already joined. Choose a limit of at least 7.",
      );
      expect(
        Array.from(uses.options)
          .filter((option) => option.disabled)
          .map((option) => option.value),
      ).toEqual(["1", "5"]);
      expect(document.activeElement).toBe(uses);
      expect(changeSpy).toHaveBeenCalledTimes(1);
    });

    it("the next successful save clears the invalid state", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockRejectedValueOnce(failure(400, 6));
      vi.mocked(getInviteLink).mockResolvedValue(liveLink());
      await pick("#inviteLinkUsesSelect", "5");

      vi.mocked(updateInviteLink).mockResolvedValue(liveLink({ maxUses: 25 }));
      await pick("#inviteLinkUsesSelect", "25");

      expect(
        selectEl("inviteLinkUsesSelect").hasAttribute("aria-invalid"),
      ).toBe(false);
      expect($("#inviteLinkInlineError").length).toBe(0);
    });

    it("a refresh GET returning null resyncs to the empty state with one announcement", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockRejectedValue(failure(400, 6));
      vi.mocked(getInviteLink).mockResolvedValue(null);

      await pick("#inviteLinkUsesSelect", "5");

      expect($("#inviteLinkInlineError").length).toBe(0);
      expect(document.activeElement?.id).toBe("inviteLinkExpiresSelect");
      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_RESYNC_REVOKED);
    });

    it("a refresh GET returning a dead link resyncs with the reason alone", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockRejectedValue(failure(400, 6));
      vi.mocked(getInviteLink).mockResolvedValue(
        liveLink({ status: "expired", expiresAt: "2098-12-01T00:00:00Z" }),
      );

      await pick("#inviteLinkUsesSelect", "5");

      expect($("#inviteLinkInlineError").length).toBe(0);
      expect(document.activeElement?.id).toBe("inviteLinkCreateBtn");
      expect(announcement()).toBe(
        $("#MemberInvitePanelBody .invitePanelHint").text(),
      );
    });

    it("a failing refresh GET is silent and leaves the restored state", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockRejectedValue(failure(400, 6));
      vi.mocked(getInviteLink).mockRejectedValue({ kind: "failed" });

      await pick("#inviteLinkUsesSelect", "5");

      expect(selectEl("inviteLinkUsesSelect").value).toBe("10");
      expect($("#inviteLinkInlineError").text()).toBe(
        "3 people have already joined. Choose a limit of at least 3.",
      );
    });
  });

  describe("confirm during a save", () => {
    it("Cancel stays usable and the action button stays locked", async () => {
      await openWith(liveLink());
      await click("#inviteLinkRevokeBtn");
      const pending = deferred<InviteLink>();
      vi.mocked(updateInviteLink).mockReturnValue(pending.promise);
      await pick("#inviteLinkUsesSelect", "25");

      expect($("#inviteLinkConfirmActionBtn").attr("aria-disabled")).toBe(
        "true",
      );
      await click("#inviteLinkConfirmCancelBtn");
      expect($("#inviteLinkConfirmActionBtn").length).toBe(0);
      expect($("#inviteLinkRevokeBtn").length).toBe(1);
      expect(isInviteLinkPanelOpen()).toBe(true);
    });

    it("the first Escape cancels the confirm without closing the panel", async () => {
      await openWith(liveLink());
      await click("#inviteLinkNewBtn");
      vi.mocked(updateInviteLink).mockReturnValue(
        deferred<InviteLink>().promise,
      );
      await pick("#inviteLinkUsesSelect", "25");

      pressEscape();

      expect($("#inviteLinkConfirmActionBtn").length).toBe(0);
      expect(isInviteLinkPanelOpen()).toBe(true);
    });
  });

  describe("copy", () => {
    function stubClipboard(writeText: (() => Promise<void>) | null) {
      vi.stubGlobal("navigator", {
        clipboard: writeText === null ? undefined : { writeText },
      });
    }

    it("copies the link, labels Copied for 1500 ms, announces and emits success", async () => {
      const writeText = vi.fn().mockResolvedValue(undefined);
      stubClipboard(writeText);
      await openWith(liveLink());

      await click("#inviteLinkCopyBtn");

      expect(writeText).toHaveBeenCalledWith(
        `${window.location.origin}/invite/abcdefghijklmnopqrstuv`,
      );
      expect($("#inviteLinkCopyBtn").text()).toBe(
        strings.INVITE_LINK_PANEL_COPIED,
      );
      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_COPY_SUCCESS);
      expect(emitMetric).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_INVITE_LINK_COPY,
        result: "success",
      });
      await vi.advanceTimersByTimeAsync(1500);
      expect($("#inviteLinkCopyBtn").text()).toBe(
        strings.INVITE_LINK_PANEL_COPY,
      );
    });

    it("falls back when the write rejects: input focused and selected, hint announced", async () => {
      stubClipboard(() => Promise.reject(new Error("denied")));
      await openWith(liveLink());

      await click("#inviteLinkCopyBtn");

      const input = document.getElementById(
        "inviteLinkUrlInput",
      ) as HTMLInputElement;
      expect(document.activeElement).toBe(input);
      expect(input.selectionStart).toBe(0);
      expect(input.selectionEnd).toBe(input.value.length);
      expect($("#inviteLinkCopyHint").text()).toBe(
        strings.INVITE_LINK_PANEL_COPY_FALLBACK,
      );
      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_COPY_FALLBACK);
      expect(emitMetric).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_INVITE_LINK_COPY,
        result: "fallback",
      });
    });

    it("falls back when the Clipboard API is missing", async () => {
      stubClipboard(null);
      await openWith(liveLink());

      await click("#inviteLinkCopyBtn");

      expect(document.activeElement?.id).toBe("inviteLinkUrlInput");
      const copyEmits = vi
        .mocked(emitMetric)
        .mock.calls.filter(
          ([payload]) => payload.event === UI_EVENTS.UI_INVITE_LINK_COPY,
        );
      expect(copyEmits).toEqual([
        [{ event: UI_EVENTS.UI_INVITE_LINK_COPY, result: "fallback" }],
      ]);
    });

    it("reports failure and keeps focus on Copy when selecting throws", async () => {
      stubClipboard(null);
      await openWith(liveLink());
      const input = document.getElementById(
        "inviteLinkUrlInput",
      ) as HTMLInputElement;
      input.select = () => {
        throw new Error("no select");
      };
      document.getElementById("inviteLinkCopyBtn")?.focus();

      await click("#inviteLinkCopyBtn");

      expect(document.activeElement?.id).toBe("inviteLinkCopyBtn");
      expect(emitMetric).toHaveBeenCalledTimes(2); // panel open + copy
      expect(emitMetric).toHaveBeenLastCalledWith({
        event: UI_EVENTS.UI_INVITE_LINK_COPY,
        result: "failure",
      });
    });

    it("clears the Copied revert timer on close", async () => {
      stubClipboard(vi.fn().mockResolvedValue(undefined));
      await openWith(liveLink());
      await click("#inviteLinkCopyBtn");

      expect(vi.getTimerCount()).toBe(1); // the Copied revert timer
      pressEscape();
      expect(vi.getTimerCount()).toBe(0);
      expect(isInviteLinkPanelOpen()).toBe(false);
    });
  });
});
