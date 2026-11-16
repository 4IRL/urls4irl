import {
  initInviteLinkPanel,
  isInviteLinkPanelOpen,
  resetInviteLinkPanel,
} from "../invite-link-panel.js";
import {
  getInviteLink,
  replaceInviteLink,
  revokeInviteLink,
  updateInviteLink,
  type InviteLink,
  type InviteLinkMutationFailure,
} from "../invite-link-client.js";
import {
  INVITE_MODAL_FIXTURE,
  installModalMock,
} from "../../../__tests__/helpers/invite-modal.js";
import { APP_CONFIG } from "../../../lib/config.js";
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
const SWITCH_ID = "inviteLinkPreviewSwitch";
const ENDS = "2099-01-03T12:00:00Z";
// Mirrors the panel's rule: the year shows only when it differs from now's.
// Evaluated lazily so it sees the faked system time.
function endsLabel(): string {
  const date = new Date(ENDS);
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    ...(sameYear ? {} : { year: "numeric" }),
  });
}

function liveLink(overrides: Partial<InviteLink> = {}): InviteLink {
  return {
    token: "abcdefghijklmnopqrstuv",
    status: "live",
    expiresAt: "2099-01-05T00:00:00Z",
    maxUses: 10,
    useCount: 3,
    createdAt: "2099-01-01T00:00:00Z",
    creatorUsername: "alice",
    previewEnabled: false,
    previewWindowDays: 3,
    previewEndsAt: null,
    previewEffectiveEnabled: false,
    previewEffectiveEndsAt: null,
    ...overrides,
  };
}

function onLink(overrides: Partial<InviteLink> = {}): InviteLink {
  return liveLink({
    previewEnabled: true,
    previewEndsAt: ENDS,
    previewEffectiveEnabled: true,
    previewEffectiveEndsAt: ENDS,
    ...overrides,
  });
}

// Stored on, but the window has already lapsed: effective off.
function lapsedLink(): InviteLink {
  return liveLink({
    previewEnabled: true,
    previewEndsAt: "2098-12-31T00:00:00Z",
    previewEffectiveEnabled: false,
    previewEffectiveEndsAt: "2098-12-31T00:00:00Z",
  });
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

async function clickSwitch() {
  $(`#${SWITCH_ID}`).trigger("click");
  await settle();
}

function switchEl(): HTMLElement {
  return document.getElementById(SWITCH_ID) as HTMLElement;
}

function selectEl(id: string): HTMLSelectElement {
  return document.getElementById(id) as HTMLSelectElement;
}

function previewBlock(): HTMLElement {
  return document.querySelector(".invitePanelPreview") as HTMLElement;
}

describe("invite link preview switch", () => {
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
    changeSpy = vi.fn<(event: Event) => void>();
    document
      .getElementById("inviteLinkModalBody")
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

  describe("render", () => {
    it("renders an off switch with its description and no warning", async () => {
      await openWith(liveLink());

      const element = switchEl();
      expect(element.getAttribute("role")).toBe("switch");
      expect(element.getAttribute("aria-checked")).toBe("false");
      expect(element.getAttribute("aria-labelledby")).toBe(
        "inviteLinkPreviewLabel",
      );
      expect(element.getAttribute("aria-describedby")).toBe(
        "inviteLinkPreviewDesc",
      );
      expect($("#inviteLinkPreviewLabel").text()).toBe(
        strings.INVITE_LINK_PANEL_PREVIEW_LABEL,
      );
      expect($("#inviteLinkPreviewDesc").text()).toBe(
        strings.INVITE_LINK_PANEL_PREVIEW_DESC,
      );
      expect(
        $("#inviteLinkPreviewLabel").find("#inviteLinkPreviewDesc").length,
      ).toBe(0);
      expect($("#inviteLinkPreviewWarning").length).toBe(0);
      expect(
        previewBlock().querySelector(".invitePanelPreviewRow")?.children,
      ).toHaveLength(2);
    });

    it("renders an on switch with the warning and the date", async () => {
      await openWith(onLink());

      expect(switchEl().getAttribute("aria-checked")).toBe("true");
      expect(switchEl().getAttribute("aria-describedby")).toBe(
        "inviteLinkPreviewDesc inviteLinkPreviewWarning",
      );
      const warning = document.getElementById("inviteLinkPreviewWarning");
      expect(warning?.textContent).toContain(endsLabel());
      expect(warning?.textContent).toContain("without an account");
      expect(previewBlock().lastElementChild).toBe(warning);
    });

    it("keys on the effective state: a lapsed stored-on link renders off", async () => {
      await openWith(lapsedLink());

      expect(switchEl().getAttribute("aria-checked")).toBe("false");
      expect($("#inviteLinkPreviewWarning").length).toBe(0);
    });

    it.each([
      ["empty", null],
      ["dead", liveLink({ status: "expired" })],
    ])("renders no preview controls in the %s state", async (_name, link) => {
      await openWith(link);
      expect($(".invitePanelPreview").length).toBe(0);
      expect(document.getElementById(SWITCH_ID)).toBeNull();
    });

    it("renders no preview controls while loading", async () => {
      vi.mocked(getInviteLink).mockReturnValue(new Promise(() => {}));
      $("#memberBtnInviteLink").trigger("click");
      await settle();
      expect($(".invitePanelPreview").length).toBe(0);
    });

    it("renders no preview controls in the failed state", async () => {
      vi.mocked(getInviteLink).mockRejectedValue({ kind: "failed" });
      $("#memberBtnInviteLink").trigger("click");
      await settle();
      expect($("#inviteLinkTryAgainBtn").length).toBe(1);
      expect($(".invitePanelPreview").length).toBe(0);
    });

    it("a switch click with no live link does nothing", async () => {
      await openWith(null);
      await clickSwitch();
      expect(updateInviteLink).not.toHaveBeenCalled();
    });

    it("New link (replace) renders preview off with no warning", async () => {
      await openWith(onLink());
      vi.mocked(replaceInviteLink).mockResolvedValue(liveLink());
      $("#inviteLinkNewBtn").trigger("click");
      await settle();
      $("#inviteLinkConfirmActionBtn").trigger("click");
      await settle();

      expect(switchEl().getAttribute("aria-checked")).toBe("false");
      expect($("#inviteLinkPreviewWarning").length).toBe(0);
    });
  });

  describe("saving", () => {
    it("sends exactly one PATCH, locks while in flight and keeps focus", async () => {
      await openWith(liveLink());
      const pending = deferred<InviteLink>();
      vi.mocked(updateInviteLink).mockReturnValue(pending.promise);
      switchEl().focus();

      await clickSwitch();
      await clickSwitch();

      expect(changeSpy).not.toHaveBeenCalled();
      expect(updateInviteLink).toHaveBeenCalledTimes(1);
      expect(updateInviteLink).toHaveBeenCalledWith({
        utubID: 1,
        body: { preview_enabled: true },
      });
      const element = switchEl();
      expect(element.getAttribute("aria-busy")).toBe("true");
      expect(element.getAttribute("aria-checked")).toBe("true");
      expect((element as HTMLButtonElement).disabled).toBe(false);
      expect(document.activeElement).toBe(element);

      // A select change mid-save sends nothing and fires no extra change.
      const uses = selectEl("inviteLinkUsesSelect");
      uses.value = "25";
      uses.dispatchEvent(new Event("change", { bubbles: true }));
      await settle();
      expect(updateInviteLink).toHaveBeenCalledTimes(1);
      expect(uses.value).toBe("10");

      pending.resolve(onLink());
      await settle();
      expect(element.hasAttribute("aria-busy")).toBe(false);
    });

    it("puts the saving indicator after the row, never inside it", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockReturnValue(
        deferred<InviteLink>().promise,
      );

      await clickSwitch();

      const row = previewBlock().querySelector(".invitePanelPreviewRow");
      expect(row?.nextElementSibling?.id).toBe("inviteLinkSaving");
      expect(row?.children).toHaveLength(2);
    });

    it("announces PREVIEW_ON with the date in one write and keeps focus", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockResolvedValue(onLink());
      switchEl().focus();

      await clickSwitch();

      expect(announcement()).toBe(`Preview on until ${endsLabel()}.`);
      expect(document.activeElement).toBe(switchEl());
      expect(switchEl().getAttribute("aria-checked")).toBe("true");
      expect($("#inviteLinkSaving").length).toBe(0);
    });

    it("announces PREVIEW_OFF when turned off", async () => {
      await openWith(onLink());
      vi.mocked(updateInviteLink).mockResolvedValue(liveLink());

      await clickSwitch();

      expect(updateInviteLink).toHaveBeenCalledWith({
        utubID: 1,
        body: { preview_enabled: false },
      });
      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_PREVIEW_OFF);
      expect(switchEl().getAttribute("aria-checked")).toBe("false");
    });

    it("a lapsed mid-session switch turns off when clicked", async () => {
      await openWith(onLink());
      vi.setSystemTime(Date.parse("2099-01-04T00:00:00Z"));
      vi.mocked(updateInviteLink).mockResolvedValue(lapsedLink());

      await clickSwitch();

      expect(updateInviteLink).toHaveBeenCalledWith({
        utubID: 1,
        body: { preview_enabled: false },
      });
      expect(switchEl().getAttribute("aria-checked")).toBe("false");
      expect($("#inviteLinkPreviewWarning").length).toBe(0);
      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_PREVIEW_OFF);
    });

    it("inserts and removes the warning in place without replacing the switch", async () => {
      await openWith(liveLink());
      const original = switchEl();
      original.focus();
      vi.mocked(updateInviteLink).mockResolvedValueOnce(onLink());

      await clickSwitch();

      expect(switchEl()).toBe(original);
      const warning = document.getElementById("inviteLinkPreviewWarning");
      expect(warning).not.toBeNull();
      expect(previewBlock().lastElementChild).toBe(warning);
      expect(original.getAttribute("aria-describedby")).toBe(
        "inviteLinkPreviewDesc inviteLinkPreviewWarning",
      );
      expect(document.activeElement).toBe(original);

      vi.mocked(updateInviteLink).mockResolvedValueOnce(liveLink());
      await clickSwitch();

      expect(switchEl()).toBe(original);
      expect($("#inviteLinkPreviewWarning").length).toBe(0);
      expect(original.getAttribute("aria-describedby")).toBe(
        "inviteLinkPreviewDesc",
      );
      expect(document.activeElement).toBe(original);
    });

    it("a response dropped after a UTub switch changes nothing", async () => {
      await openWith(liveLink());
      const pending = deferred<InviteLink>();
      vi.mocked(updateInviteLink).mockReturnValue(pending.promise);
      await clickSwitch();

      setState({ activeUTubID: 2 });
      resetInviteLinkPanel();
      pending.resolve(onLink());
      await settle();

      expect(announcement()).toBe("");
      expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
    });
  });

  describe("lifecycle guards", () => {
    it("a click during a New link request sends nothing and does not flip", async () => {
      await openWith(liveLink());
      $("#inviteLinkNewBtn").trigger("click");
      await settle();
      vi.mocked(replaceInviteLink).mockReturnValue(
        deferred<InviteLink>().promise,
      );
      $("#inviteLinkConfirmActionBtn").trigger("click");
      await settle();

      await clickSwitch();

      expect(updateInviteLink).not.toHaveBeenCalled();
      expect(switchEl().getAttribute("aria-checked")).toBe("false");
      expect(changeSpy).not.toHaveBeenCalled();
    });

    it("a click during a Revoke request sends nothing", async () => {
      await openWith(liveLink());
      $("#inviteLinkRevokeBtn").trigger("click");
      await settle();
      vi.mocked(revokeInviteLink).mockReturnValue(deferred<true>().promise);
      $("#inviteLinkConfirmActionBtn").trigger("click");
      await settle();

      await clickSwitch();

      expect(updateInviteLink).not.toHaveBeenCalled();
      expect(switchEl().getAttribute("aria-checked")).toBe("false");
      expect(changeSpy).not.toHaveBeenCalled();
    });
  });

  describe("failures", () => {
    it.each([
      ["500", failure(500, null)],
      ["timeout", failure(0, null)],
    ])(
      "%s restores the committed value and describes the switch with the error",
      async (_name, error) => {
        await openWith(liveLink());
        vi.mocked(updateInviteLink).mockRejectedValue(error);
        switchEl().focus();

        await clickSwitch();

        expect(switchEl().getAttribute("aria-checked")).toBe("false");
        expect($("#inviteLinkInlineError").text()).toBe(
          strings.INVITE_LINK_PANEL_ERROR_GENERIC,
        );
        expect(switchEl().getAttribute("aria-describedby")).toBe(
          "inviteLinkInlineError inviteLinkPreviewDesc",
        );
        expect(document.activeElement).toBe(switchEl());
        expect(changeSpy).not.toHaveBeenCalled();
        expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
      },
    );

    it("keeps the warning id after the error id when the warning exists", async () => {
      await openWith(onLink());
      vi.mocked(updateInviteLink).mockRejectedValue(failure(500, null));

      await clickSwitch();

      expect(switchEl().getAttribute("aria-checked")).toBe("true");
      expect(switchEl().getAttribute("aria-describedby")).toBe(
        "inviteLinkInlineError inviteLinkPreviewDesc inviteLinkPreviewWarning",
      );
    });

    it("a 429 restores with no inline error", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockRejectedValue({ kind: "rate_limited" });

      await clickSwitch();

      expect(switchEl().getAttribute("aria-checked")).toBe("false");
      expect($("#inviteLinkInlineError").length).toBe(0);
    });

    it("code 1 resyncs to the empty state", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockRejectedValue(failure(404, 1));
      vi.mocked(getInviteLink).mockResolvedValue(null);

      await clickSwitch();

      expect($("#inviteLinkCreateBtn").length).toBe(1);
      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_RESYNC_REVOKED);
    });

    it("code 5 resyncs to the dead state", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockRejectedValue(failure(409, 5));
      vi.mocked(getInviteLink).mockResolvedValue(
        liveLink({ status: "expired", expiresAt: "2098-12-01T00:00:00Z" }),
      );

      await clickSwitch();

      expect(document.activeElement?.id).toBe("inviteLinkCreateBtn");
      expect(announcement()).toContain(
        strings.INVITE_LINK_PANEL_RESYNC_DEAD_UPDATE,
      );
    });

    it("a 403 closes the panel and refreshes the UTub", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockRejectedValue(failure(403, null));

      await clickSwitch();

      expect(isInviteLinkPanelOpen()).toBe(false);
      expect(updateUTubOnFindingStaleData).toHaveBeenCalledWith({ utubID: 1 });
      expect(announcement()).toBe(strings.INVITE_LINK_PANEL_MANAGE_LOST);
    });

    it("a locked 403 announces the lock", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockRejectedValue(failure(403, 3));

      await clickSwitch();

      expect(isInviteLinkPanelOpen()).toBe(false);
      expect(announcement()).toBe(strings.UTUB_IS_LOCKED);
    });

    it("a 404 closes through the denied path", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockRejectedValue(failure(404, null));

      await clickSwitch();

      expect(updateUTubOnFindingStaleData).toHaveBeenCalledWith({ utubID: 1 });
    });

    it("a csrf failure replaces the page body", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockRejectedValue({
        kind: "csrf",
        html: "<main id='csrfPage'>expired</main>",
      });

      await clickSwitch();

      expect(document.getElementById("csrfPage")).not.toBeNull();
    });
  });

  describe("aria-describedby convergence", () => {
    it.each([
      ["off", liveLink(), onLink()],
      ["on", onLink(), liveLink()],
    ])(
      "an error cleared by a successful switch save leaves the %s state clean",
      async (_name, start, next) => {
        await openWith(start);
        vi.mocked(updateInviteLink).mockRejectedValueOnce(failure(500, null));
        await clickSwitch();
        expect(switchEl().getAttribute("aria-describedby")).toContain(
          "inviteLinkInlineError",
        );

        vi.mocked(updateInviteLink).mockResolvedValueOnce(next);
        await clickSwitch();

        const expected = next.previewEffectiveEnabled
          ? "inviteLinkPreviewDesc inviteLinkPreviewWarning"
          : "inviteLinkPreviewDesc";
        expect($("#inviteLinkInlineError").length).toBe(0);
        expect(switchEl().getAttribute("aria-describedby")).toBe(expected);
        expect(switchEl().hasAttribute("aria-invalid")).toBe(false);
      },
    );

    it.each([
      ["off", liveLink(), "inviteLinkPreviewDesc"],
      ["on", onLink(), "inviteLinkPreviewDesc inviteLinkPreviewWarning"],
    ])(
      "an error cleared by another control's save keeps the Desc ids (%s)",
      async (_name, start, expected) => {
        await openWith(start);
        vi.mocked(updateInviteLink).mockRejectedValueOnce(failure(500, null));
        await clickSwitch();

        vi.mocked(updateInviteLink).mockResolvedValueOnce({
          ...start,
          maxUses: 25,
        });
        const uses = selectEl("inviteLinkUsesSelect");
        uses.value = "25";
        uses.dispatchEvent(new Event("change", { bubbles: true }));
        await settle();

        expect($("#inviteLinkInlineError").length).toBe(0);
        expect(switchEl().getAttribute("aria-describedby")).toBe(expected);
        expect(switchEl().hasAttribute("aria-invalid")).toBe(false);
      },
    );
  });

  describe("preview length select", () => {
    const WINDOW_ID = "inviteLinkPreviewWindowSelect";
    const HINT_ID = "inviteLinkPreviewWindowHint";
    const TEN_DAYS = "2099-01-11T00:00:00Z";
    const TWO_DAYS = "2099-01-03T00:00:00Z";
    // 1.5 days left: caps a stored 3-day length.
    const SHORT = "2099-01-02T12:00:00Z";
    const OFF_HINT = strings.INVITE_LINK_PANEL_PREVIEW_WINDOW_OFF_HINT;
    const LIMIT_HINT = strings.INVITE_LINK_PANEL_PREVIEW_WINDOW_LIMIT_HINT;

    function label(iso: string): string {
      const date = new Date(iso);
      const sameYear = date.getFullYear() === new Date().getFullYear();
      return date.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        ...(sameYear ? {} : { year: "numeric" }),
      });
    }

    function options(): HTMLOptionElement[] {
      return Array.from(selectEl(WINDOW_ID).options);
    }

    function hint(): HTMLElement | null {
      return document.getElementById(HINT_ID);
    }

    function cappedHint(): string {
      return strings.INVITE_LINK_PANEL_PREVIEW_WINDOW_CAPPED_HINT.replace(
        "{label}",
        "3 days",
      );
    }

    async function pick(id: string, value: string) {
      const select = selectEl(id);
      select.value = value;
      select.dispatchEvent(new Event("change", { bubbles: true }));
      await settle();
    }

    function cappedOn(): InviteLink {
      return onLink({
        expiresAt: SHORT,
        previewEndsAt: "2099-01-04T00:00:00Z",
        previewEffectiveEndsAt: SHORT,
      });
    }

    it("(a) disables lengths longer than the time left and shows the limit hint", async () => {
      await openWith(onLink({ expiresAt: TWO_DAYS }));

      expect(
        options().map((option) => [option.value, option.disabled]),
      ).toEqual([
        ["1", false],
        ["3", true],
        ["7", true],
      ]);
      expect(selectEl(WINDOW_ID).value).toBe("3");
      expect(hint()?.textContent).toBe(LIMIT_HINT);
      expect(previewBlock().children[1]?.contains(selectEl(WINDOW_ID))).toBe(
        true,
      );
    });

    it("(a) disables nothing with 10 days left and shows no hint while on", async () => {
      await openWith(onLink({ expiresAt: TEN_DAYS }));

      expect(options().every((option) => !option.disabled)).toBe(true);
      expect(hint()).toBeNull();
      expect(selectEl(WINDOW_ID).hasAttribute("aria-describedby")).toBe(false);
    });

    it("(b) renders the capped option while off, with the off cue in one element", async () => {
      await openWith(liveLink({ expiresAt: SHORT }));

      const first = options()[0] as HTMLOptionElement;
      expect(first.value).toBe("");
      expect(first.selected).toBe(true);
      expect(first.disabled).toBe(true);
      expect(first.textContent).toBe(`Until ${label(SHORT)} (link expiry)`);
      expect(hint()?.textContent).toBe(`${cappedHint()} ${OFF_HINT}`);
      expect(document.querySelectorAll(`#${HINT_ID}`)).toHaveLength(1);
    });

    it("(b) renders the capped option while on with the capped date in the warning", async () => {
      await openWith(cappedOn());

      const first = options()[0] as HTMLOptionElement;
      expect(first.selected).toBe(true);
      expect(first.disabled).toBe(true);
      expect(first.textContent).toBe(`Until ${label(SHORT)} (link expiry)`);
      expect(hint()?.textContent).toBe(cappedHint());
      expect(
        document.getElementById("inviteLinkPreviewWarning")?.textContent,
      ).toContain(label(SHORT));
    });

    it("(c) shortening Expires while on caps and announces both in one write", async () => {
      await openWith(onLink({ expiresAt: TEN_DAYS }));
      vi.mocked(updateInviteLink).mockResolvedValue(cappedOn());

      await pick("inviteLinkExpiresSelect", "1");

      expect(options()[0]?.selected).toBe(true);
      expect(hint()?.textContent).toBe(cappedHint());
      expect(announcement()).toBe(
        `Link now expires ${label(SHORT)}. Preview now ends ${label(SHORT)}, when the link expires.`,
      );
    });

    it("(c) lengthening Expires restores the stored length and announces the new end", async () => {
      await openWith(cappedOn());
      const restored = onLink({
        expiresAt: TEN_DAYS,
        previewEndsAt: "2099-01-04T00:00:00Z",
        previewEffectiveEndsAt: "2099-01-04T00:00:00Z",
      });
      vi.mocked(updateInviteLink).mockResolvedValue(restored);

      await pick("inviteLinkExpiresSelect", "30");

      expect(selectEl(WINDOW_ID).value).toBe("3");
      expect(options().some((option) => option.value === "")).toBe(false);
      expect(hint()).toBeNull();
      expect(announcement()).toBe(
        `Link now expires ${label(TEN_DAYS)}. Preview now ends ${label("2099-01-04T00:00:00Z")}.`,
      );
    });

    it("(d) appends nothing for an Expires save while off or a uses save", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockResolvedValueOnce(
        liveLink({ expiresAt: TEN_DAYS }),
      );
      await pick("inviteLinkExpiresSelect", "30");
      expect(announcement()).toBe(`Link now expires ${label(TEN_DAYS)}.`);

      vi.mocked(updateInviteLink).mockResolvedValueOnce(
        liveLink({ expiresAt: TEN_DAYS, maxUses: 25 }),
      );
      await pick("inviteLinkUsesSelect", "25");
      expect(announcement()).toBe("Use limit set to 25 uses.");
    });

    it("(d) a uses save with an unchanged effective-on preview announces only USES_SET", async () => {
      await openWith(onLink());
      vi.mocked(updateInviteLink).mockResolvedValue(onLink({ maxUses: 25 }));

      await pick("inviteLinkUsesSelect", "25");

      expect(announcement()).toBe("Use limit set to 25 uses.");
    });

    it.each([
      [
        "Expires",
        "inviteLinkExpiresSelect",
        "30",
        { expiresAt: TEN_DAYS },
        `Link now expires ${label(TEN_DAYS)}.`,
      ],
      [
        "Uses",
        "inviteLinkUsesSelect",
        "25",
        { maxUses: 25 },
        "Use limit set to 25 uses.",
      ],
    ])(
      "(d2) a %s save that finds the window lapsed appends PREVIEW_OFF once",
      async (_name, selectId, value, change, base) => {
        await openWith(onLink());
        vi.mocked(updateInviteLink).mockResolvedValue({
          ...lapsedLink(),
          ...change,
        });

        await pick(selectId, value);

        expect(announcement()).toBe(`${base} Preview off.`);
        expect(switchEl().getAttribute("aria-checked")).toBe("false");
        expect($("#inviteLinkPreviewWarning").length).toBe(0);
      },
    );

    it("(e) a window save with an effective-on response announces the new end", async () => {
      await openWith(onLink());
      vi.mocked(updateInviteLink).mockResolvedValue(
        onLink({
          previewWindowDays: 1,
          previewEndsAt: "2099-01-02T00:00:00Z",
          previewEffectiveEndsAt: "2099-01-02T00:00:00Z",
        }),
      );

      await pick(WINDOW_ID, "1");

      expect(announcement()).toBe(
        `Preview now ends ${label("2099-01-02T00:00:00Z")}.`,
      );
    });

    it("(e) a window save with an effective-off response announces the length only", async () => {
      await openWith(liveLink({ expiresAt: TEN_DAYS }));
      vi.mocked(updateInviteLink).mockResolvedValue(
        liveLink({ expiresAt: TEN_DAYS, previewWindowDays: 7 }),
      );

      await pick(WINDOW_ID, "7");

      expect(announcement()).toBe(`Preview length set to 7 days. ${OFF_HINT}`);
    });

    it("(e) a window save from a lapsed-mid-session switch converges to off", async () => {
      await openWith(onLink({ expiresAt: TEN_DAYS }));
      vi.mocked(updateInviteLink).mockResolvedValue({
        ...lapsedLink(),
        expiresAt: TEN_DAYS,
        previewWindowDays: 7,
      });

      await pick(WINDOW_ID, "7");

      expect(announcement()).toBe(`Preview length set to 7 days. ${OFF_HINT}`);
      expect(switchEl().getAttribute("aria-checked")).toBe("false");
      expect(selectEl(WINDOW_ID).value).toBe("7");
      expect(hint()?.textContent).toBe(OFF_HINT);
    });

    it("(f) sends one PATCH, keeps focus and the busy state, and reverts a change mid-save", async () => {
      await openWith(onLink({ expiresAt: TEN_DAYS }));
      const pending = deferred<InviteLink>();
      vi.mocked(updateInviteLink).mockReturnValue(pending.promise);
      const select = selectEl(WINDOW_ID);
      select.focus();

      await pick(WINDOW_ID, "7");

      expect(updateInviteLink).toHaveBeenCalledTimes(1);
      expect(updateInviteLink).toHaveBeenCalledWith({
        utubID: 1,
        body: { preview_window_days: 7 },
      });
      expect(select.getAttribute("aria-busy")).toBe("true");
      expect(select.disabled).toBe(false);
      expect(document.activeElement).toBe(select);

      await pick(WINDOW_ID, "1");
      expect(updateInviteLink).toHaveBeenCalledTimes(1);
      expect(select.value).toBe("7");

      await pick("inviteLinkUsesSelect", "25");
      expect(updateInviteLink).toHaveBeenCalledTimes(1);
      expect(selectEl("inviteLinkUsesSelect").value).toBe("10");

      pending.resolve(onLink({ expiresAt: TEN_DAYS, previewWindowDays: 7 }));
      await settle();
      expect(select.hasAttribute("aria-busy")).toBe(false);
    });

    it("(f) a failure restores the previous value and the error describes the select", async () => {
      await openWith(liveLink({ expiresAt: TEN_DAYS }));
      vi.mocked(updateInviteLink).mockRejectedValue(failure(500, null));
      changeSpy.mockClear();

      await pick(WINDOW_ID, "7");

      const select = selectEl(WINDOW_ID);
      expect(select.value).toBe("3");
      expect($("#inviteLinkInlineError").length).toBe(1);
      expect(select.getAttribute("aria-describedby")).toBe(
        `inviteLinkInlineError ${HINT_ID}`,
      );
      // Only the user's own change event; the restore fires none.
      expect(changeSpy).toHaveBeenCalledTimes(1);
    });

    it.each([
      ["off, hint exists", liveLink({ expiresAt: TEN_DAYS }), HINT_ID],
      ["on, no hint", onLink({ expiresAt: TEN_DAYS }), null],
    ])(
      "(g) an error cleared on another control leaves only an existing hint id (%s)",
      async (_name, start, expected) => {
        await openWith(start);
        vi.mocked(updateInviteLink).mockRejectedValueOnce(failure(500, null));
        await pick(WINDOW_ID, "7");
        expect(selectEl(WINDOW_ID).getAttribute("aria-describedby")).toBe(
          expected === null
            ? "inviteLinkInlineError"
            : `inviteLinkInlineError ${expected}`,
        );

        vi.mocked(updateInviteLink).mockResolvedValueOnce({
          ...start,
          maxUses: 25,
        });
        await pick("inviteLinkUsesSelect", "25");
        expect(selectEl(WINDOW_ID).getAttribute("aria-describedby")).toBe(
          expected,
        );
      },
    );

    it("(h) ignores the capped first option", async () => {
      await openWith(liveLink({ expiresAt: SHORT }));

      await pick(WINDOW_ID, "");

      expect(updateInviteLink).not.toHaveBeenCalled();
    });

    it("(i) the empty state renders no preview select and its selects never save", async () => {
      await openWith(null);

      expect(document.getElementById(WINDOW_ID)).toBeNull();
      await pick("inviteLinkExpiresSelect", "30");
      await pick("inviteLinkUsesSelect", "25");
      expect(updateInviteLink).not.toHaveBeenCalled();
    });

    it("(j) the off cue stands alone and the select references it", async () => {
      await openWith(liveLink({ expiresAt: TEN_DAYS }));
      expect(hint()?.textContent).toBe(OFF_HINT);
      expect(selectEl(WINDOW_ID).getAttribute("aria-describedby")).toBe(
        HINT_ID,
      );
    });

    it("(j) the off cue follows the limit hint in one element", async () => {
      await openWith(liveLink());
      expect(hint()?.textContent).toBe(`${LIMIT_HINT} ${OFF_HINT}`);
    });

    it("(j) turning the switch on removes the off cue, and the hint stays unchanged while in flight", async () => {
      await openWith(liveLink({ expiresAt: TEN_DAYS }));
      const pending = deferred<InviteLink>();
      vi.mocked(updateInviteLink).mockReturnValue(pending.promise);

      await clickSwitch();
      expect(hint()?.textContent).toBe(OFF_HINT);

      pending.resolve(onLink({ expiresAt: TEN_DAYS }));
      await settle();
      expect(hint()).toBeNull();
      expect(selectEl(WINDOW_ID).hasAttribute("aria-describedby")).toBe(false);
    });

    it("(j) turning the switch off restores the off cue", async () => {
      await openWith(onLink({ expiresAt: TEN_DAYS }));
      vi.mocked(updateInviteLink).mockResolvedValue(
        liveLink({ expiresAt: TEN_DAYS }),
      );

      await clickSwitch();

      expect(hint()?.textContent).toBe(OFF_HINT);
    });

    it("(j) a switch-on response keeps the limit hint when an option is disabled", async () => {
      await openWith(liveLink());
      vi.mocked(updateInviteLink).mockResolvedValue(onLink());

      await clickSwitch();

      expect(hint()?.textContent).toBe(LIMIT_HINT);
    });

    it("(k) keeps a stored option selected even when it is disabled while on", async () => {
      await openWith(onLink({ previewWindowDays: 7 }));

      const selected = options().find((option) => option.selected);
      expect(selected?.value).toBe("7");
      expect(selected?.disabled).toBe(true);
      expect(options().some((option) => option.value === "")).toBe(false);
      expect(
        document.getElementById("inviteLinkPreviewWarning")?.textContent,
      ).toContain(endsLabel());
    });

    it("(k) elapsed window: shorter than the stored length but before expiry, the warning keeps the server date", async () => {
      // Turned on 5 days ago for 7 days: 2 days remain, expiry is later.
      vi.setSystemTime(Date.parse("2099-01-06T00:00:00Z"));
      const end = "2099-01-08T00:00:00Z";
      await openWith(
        onLink({
          previewWindowDays: 7,
          expiresAt: "2099-01-20T00:00:00Z",
          previewEndsAt: end,
          previewEffectiveEndsAt: end,
        }),
      );

      const selected = options().find((option) => option.selected);
      expect(selected?.value).toBe("7");
      expect(options().some((option) => option.value === "")).toBe(false);
      expect(
        document.getElementById("inviteLinkPreviewWarning")?.textContent,
      ).toContain(label(end));
    });

    it("(k) the server's effective fields beat a client clock that says capped", async () => {
      // The clock is past expiry minus the stored length, but the server says
      // the effective end equals the stored end: not capped.
      vi.setSystemTime(Date.parse("2099-01-04T00:00:00Z"));
      await openWith(
        onLink({
          previewWindowDays: 7,
          expiresAt: "2099-01-05T00:00:00Z",
          previewEndsAt: "2099-01-05T00:00:00Z",
          previewEffectiveEndsAt: "2099-01-05T00:00:00Z",
        }),
      );

      expect(options().some((option) => option.value === "")).toBe(false);
      expect(hint()?.textContent).not.toContain("can't outlast");
    });

    it("(c) shortening Expires updates the warning date to the capped end", async () => {
      await openWith(onLink({ expiresAt: TEN_DAYS }));
      vi.mocked(updateInviteLink).mockResolvedValue(cappedOn());

      await pick("inviteLinkExpiresSelect", "1");

      expect(
        document.getElementById("inviteLinkPreviewWarning")?.textContent,
      ).toContain(label(SHORT));
    });

    it("(d) a switch save announces PREVIEW_ON with nothing appended", async () => {
      await openWith(liveLink({ expiresAt: TEN_DAYS }));
      vi.mocked(updateInviteLink).mockResolvedValue(
        onLink({ expiresAt: TEN_DAYS }),
      );

      await clickSwitch();

      expect(announcement()).toBe(`Preview on until ${endsLabel()}.`);
    });

    it("(f) a length change during a lifecycle request reverts without a PATCH", async () => {
      await openWith(onLink({ expiresAt: TEN_DAYS }));
      vi.mocked(revokeInviteLink).mockReturnValue(
        deferred<true>().promise as never,
      );
      $("#inviteLinkRevokeBtn").trigger("click");
      await settle();
      $("#inviteLinkConfirmActionBtn").trigger("click");
      await settle();
      changeSpy.mockClear();

      await pick(WINDOW_ID, "7");

      expect(updateInviteLink).not.toHaveBeenCalled();
      expect(selectEl(WINDOW_ID).value).toBe("3");
      expect(changeSpy).toHaveBeenCalledTimes(1);
    });
  });
});
