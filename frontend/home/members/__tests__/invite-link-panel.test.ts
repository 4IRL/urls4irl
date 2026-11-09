import {
  getForcedClosedToken,
  initInviteLinkPanel,
  isInviteLinkPanelOpen,
  announceInviteLinkPanel,
  resetInviteLinkPanel,
  resyncInviteLinkPanel,
  syncInviteLinkTrigger,
} from "../invite-link-panel.js";
import {
  getInviteLink,
  type InviteLink,
  type InviteLinkLoadFailure,
} from "../invite-link-client.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { emit } from "../../../lib/metrics-client.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { updateUTubOnFindingStaleData } from "../../utubs/stale-data.js";
import { canManageInviteLink } from "../../utubs/policy.js";
import { AppEvents, emit as emitAppEvent, on } from "../../../lib/event-bus.js";
import { hideAndResetMemberCombobox } from "../member-combobox.js";
import { closeMemberNameFilter } from "../search.js";

vi.mock("../invite-link-client.js", () => ({
  getInviteLink: vi.fn(),
  INVITE_LINK_LOCKED_ERROR_CODE: 3,
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

async function settle() {
  await vi.advanceTimersByTimeAsync(0);
}

function becomeManager({ utubID = 1 }: { utubID?: number } = {}) {
  setState({
    activeUTubID: utubID,
    isCurrentUserOwner: true,
    isCoCreator: false,
    isCurrentUTubLocked: false,
  });
}

function trigger() {
  return $("#memberBtnInviteLink");
}

function announcement() {
  return $("#MemberRowActionAnnouncement");
}

async function openWith(link: InviteLink | null) {
  vi.mocked(getInviteLink).mockResolvedValue(link);
  trigger().trigger("click");
  await settle();
}

describe("canManageInviteLink", () => {
  const base = {
    isCurrentUserOwner: false,
    isCoCreator: false,
    isCurrentUTubLocked: false,
    activeUTubID: 1 as number | null,
  };

  it.each([
    ["owner", { isCurrentUserOwner: true }, true],
    ["co-owner", { isCoCreator: true }, true],
    ["plain member", {}, false],
    [
      "locked owner",
      { isCurrentUserOwner: true, isCurrentUTubLocked: true },
      false,
    ],
    [
      "locked co-owner",
      { isCoCreator: true, isCurrentUTubLocked: true },
      false,
    ],
    [
      "owner with no UTub",
      { isCurrentUserOwner: true, activeUTubID: null },
      false,
    ],
  ])("%s -> %s", (_name, overrides, expected) => {
    expect(canManageInviteLink({ ...base, ...overrides })).toBe(expected);
  });

  it("fails closed on missing or unknown values", () => {
    expect(
      canManageInviteLink({
        isCurrentUserOwner: undefined,
        isCoCreator: undefined,
        isCurrentUTubLocked: undefined,
        activeUTubID: 1,
      } as never),
    ).toBe(false);
    expect(
      canManageInviteLink({
        ...base,
        isCurrentUserOwner: true,
        isCurrentUTubLocked: undefined,
      } as never),
    ).toBe(false);
    expect(
      canManageInviteLink({
        ...base,
        isCurrentUserOwner: "yes",
      } as never),
    ).toBe(false);
  });
});

describe("invite link panel", () => {
  let unsubscribe: () => void;

  beforeEach(() => {
    vi.useFakeTimers();
    // jsdom has no layout: model `.hidden` (an element or any ancestor) as
    // not rendered so the focus fallback can tell a hidden control apart.
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
          title="Invite link" aria-expanded="false" aria-controls="MemberInvitePanel"></button>
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
    becomeManager();
    unsubscribe = initInviteLinkPanel();
  });

  afterEach(() => {
    unsubscribe();
    resetInviteLinkPanel();
    vi.useRealTimers();
    delete (HTMLElement.prototype as unknown as Record<string, unknown>)
      .offsetParent;
  });

  describe("trigger gate", () => {
    it("shows the trigger for an owner and co-owner of an unlocked UTub", () => {
      expect(trigger().hasClass("hidden")).toBe(false);
      setState({ isCurrentUserOwner: false, isCoCreator: true });
      expect(trigger().hasClass("hidden")).toBe(false);
    });

    it("hides the trigger for a plain member, a locked UTub and no UTub", () => {
      setState({ isCurrentUserOwner: false, isCoCreator: false });
      expect(trigger().hasClass("hidden")).toBe(true);
      becomeManager();
      expect(trigger().hasClass("hidden")).toBe(false);
      setState({ isCurrentUTubLocked: true });
      expect(trigger().hasClass("hidden")).toBe(true);
      setState({ isCurrentUTubLocked: false });
      expect(trigger().hasClass("hidden")).toBe(false);
      setState({ activeUTubID: null });
      syncInviteLinkTrigger();
      expect(trigger().hasClass("hidden")).toBe(true);
    });

    it("has a native title equal to its aria-label", () => {
      expect(trigger().attr("title")).toBe(trigger().attr("aria-label"));
    });
  });

  describe("state renders", () => {
    it("renders Loading, focuses the heading at once and emits the open metric", async () => {
      const pending = deferred<InviteLink | null>();
      vi.mocked(getInviteLink).mockReturnValue(pending.promise);
      trigger().trigger("click");

      expect($("#MemberInvitePanel").hasClass("hidden")).toBe(false);
      expect($("#MemberInvitePanel").attr("aria-busy")).toBe("true");
      expect($("#MemberInvitePanelBody").text()).toBe(
        strings.INVITE_LINK_PANEL_LOADING,
      );
      expect(document.activeElement?.id).toBe("MemberInvitePanelHeading");
      expect(trigger().attr("aria-expanded")).toBe("true");
      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_INVITE_PANEL_OPEN,
      });

      pending.resolve(null);
      await settle();
      expect($("#MemberInvitePanel").attr("aria-busy")).toBeUndefined();
    });

    it("renders the empty state with 7 days and Unlimited selected, focusing Expires", async () => {
      await openWith(null);

      expect($("#MemberInvitePanelBody").text()).toContain(
        strings.INVITE_LINK_PANEL_EMPTY_HINT,
      );
      expect($("#inviteLinkExpiresSelect").val()).toBe("7");
      expect($("#inviteLinkUsesSelect").val()).toBe("");
      expect($("#inviteLinkCreateBtn").text()).toBe(
        strings.INVITE_LINK_PANEL_CREATE_LINK,
      );
      expect(document.activeElement?.id).toBe("inviteLinkExpiresSelect");
    });

    it("renders a live link with the URL, meta and disabled uses below the joined count", async () => {
      await openWith(liveLink());

      expect($("#inviteLinkUrlInput").val()).toBe(
        `${window.location.origin}/invite/abcdefghijklmnopqrstuv`,
      );
      expect($("#inviteLinkUrlInput").prop("readOnly")).toBe(true);
      expect($("#MemberInvitePanelBody .invitePanelMeta").text()).toMatch(
        /^Created by alice · expires .+ · 3 joined$/,
      );
      const disabled = $("#inviteLinkUsesSelect option:disabled")
        .map(
          (_i: number, option: HTMLElement) =>
            (option as HTMLOptionElement).value,
        )
        .get();
      expect(disabled).toEqual(["1"]);
      expect($("#inviteLinkUsesSelect").val()).toBe("10");
      expect($("#MemberInvitePanelBody").text()).toContain(
        "3 people have joined, so the limit can't go below 3.",
      );
      const expiresFirst = $("#inviteLinkExpiresSelect option").first();
      expect(expiresFirst.prop("selected")).toBe(true);
      expect(expiresFirst.prop("disabled")).toBe(true);
      expect($("#inviteLinkCopyBtn").length).toBe(1);
      expect($("#inviteLinkNewBtn").length).toBe(1);
      expect($("#inviteLinkRevokeBtn").length).toBe(1);
      expect(document.activeElement?.id).toBe("inviteLinkUrlInput");
    });

    it("omits Created by when the creator is unknown and the floor hint when nothing is disabled", async () => {
      await openWith(
        liveLink({ creatorUsername: null, useCount: 0, maxUses: null }),
      );

      expect($("#MemberInvitePanelBody .invitePanelMeta").text()).toMatch(
        /^expires .+ · 0 joined$/,
      );
      expect($("#inviteLinkUsesSelect option:disabled").length).toBe(0);
      expect($("#MemberInvitePanelBody").text()).not.toContain(
        "people have joined",
      );
    });

    it("renders the creator name as text, never markup", async () => {
      await openWith(liveLink({ creatorUsername: "<img src=x>" }));

      expect($("#MemberInvitePanelBody img").length).toBe(0);
      expect($("#MemberInvitePanelBody .invitePanelMeta").text()).toContain(
        "<img src=x>",
      );
    });

    it.each([
      ["expired", {}, /^This link expired on .+\.$/],
      [
        "used_up",
        { maxUses: 5, useCount: 5 },
        /^This link reached its limit of 5 uses\.$/,
      ],
      [
        "creator_demoted",
        {},
        new RegExp(strings.INVITE_LINK_PANEL_DEAD_CREATOR_DEMOTED),
      ],
    ] as const)(
      "renders the %s dead state with no selects",
      async (status, extra, reason) => {
        await openWith(liveLink({ status, ...extra }));

        expect($("#MemberInvitePanelBody .invitePanelHint").text()).toMatch(
          reason,
        );
        expect($("#MemberInvitePanelBody select").length).toBe(0);
        expect($("#inviteLinkUrlInput").length).toBe(0);
        expect($("#inviteLinkCreateBtn").length).toBe(1);
        expect($("#MemberInvitePanelBody .invitePanelMeta").text()).toMatch(
          /^Created by alice · \d+ joined$/,
        );
        expect(document.activeElement?.id).toBe("inviteLinkCreateBtn");
      },
    );

    it("announces a dead reason once on open", async () => {
      await openWith(liveLink({ status: "creator_demoted" }));
      await settle();

      expect(announcement().text()).toBe(
        strings.INVITE_LINK_PANEL_DEAD_CREATOR_DEMOTED,
      );
    });
  });

  describe("GET failures", () => {
    it("renders load-failed with Try again for a 500, focusing Try again", async () => {
      vi.mocked(getInviteLink).mockRejectedValue({
        kind: "failed",
      } satisfies InviteLinkLoadFailure);
      trigger().trigger("click");
      await settle();

      expect($("#MemberInvitePanelBody").text()).toContain(
        strings.INVITE_LINK_PANEL_LOAD_FAILED,
      );
      expect(document.activeElement?.id).toBe("inviteLinkTryAgainBtn");
      expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
    });

    it("closes, announces and refreshes the UTub on a 404", async () => {
      vi.mocked(getInviteLink).mockRejectedValue({
        kind: "denied",
        errorCode: null,
      } satisfies InviteLinkLoadFailure);
      trigger().trigger("click");
      await settle();

      expect(isInviteLinkPanelOpen()).toBe(false);
      expect($("#MemberInvitePanel").hasClass("hidden")).toBe(true);
      expect(announcement().text()).toBe(strings.INVITE_LINK_PANEL_MANAGE_LOST);
      expect(announcement().attr("aria-live")).toBe("assertive");
      expect(updateUTubOnFindingStaleData).toHaveBeenCalledWith({ utubID: 1 });
    });

    it("uses the locked message for a 403 carrying the locked code", async () => {
      vi.mocked(getInviteLink).mockRejectedValue({
        kind: "denied",
        errorCode: 3,
      } satisfies InviteLinkLoadFailure);
      trigger().trigger("click");
      await settle();

      expect(announcement().text()).toBe(strings.UTUB_IS_LOCKED);
    });

    it("Try again re-renders Loading with no retry control, focuses the heading, then settles", async () => {
      vi.mocked(getInviteLink).mockRejectedValueOnce({
        kind: "failed",
      } satisfies InviteLinkLoadFailure);
      trigger().trigger("click");
      await settle();

      const retry = deferred<InviteLink | null>();
      vi.mocked(getInviteLink).mockReturnValue(retry.promise);
      $("#inviteLinkTryAgainBtn").trigger("click");

      expect($("#inviteLinkTryAgainBtn").length).toBe(0);
      expect($("#MemberInvitePanelBody").text()).toBe(
        strings.INVITE_LINK_PANEL_LOADING,
      );
      expect(document.activeElement?.id).toBe("MemberInvitePanelHeading");

      retry.resolve(liveLink());
      await settle();
      expect(document.activeElement?.id).toBe("inviteLinkUrlInput");
    });
  });

  describe("open settle focus guard", () => {
    it("leaves focus alone when the user moved it out of the panel", async () => {
      const pending = deferred<InviteLink | null>();
      vi.mocked(getInviteLink).mockReturnValue(pending.promise);
      trigger().trigger("click");
      $("#MemberDeckHeaderAndCaret")[0].focus();

      pending.resolve(liveLink());
      await settle();

      expect(document.activeElement?.id).toBe("MemberDeckHeaderAndCaret");
    });

    it("moves focus to the entering target when focus is inside the panel", async () => {
      const pending = deferred<InviteLink | null>();
      vi.mocked(getInviteLink).mockReturnValue(pending.promise);
      trigger().trigger("click");

      pending.resolve(null);
      await settle();

      expect(document.activeElement?.id).toBe("inviteLinkExpiresSelect");
    });
  });

  describe("resync", () => {
    it("applies the entering-focus rule even after focus left, and announces once", async () => {
      await openWith(liveLink());
      $("#MemberDeckHeaderAndCaret")[0].focus();

      vi.mocked(getInviteLink).mockResolvedValue(null);
      resyncInviteLinkPanel({ message: "Resynced." });
      await settle();

      expect(document.activeElement?.id).toBe("inviteLinkExpiresSelect");
      expect(announcement().text()).toBe("Resynced.");
    });

    it("composes the message with the dead reason in one write when landing dead", async () => {
      await openWith(liveLink());

      vi.mocked(getInviteLink).mockResolvedValue(
        liveLink({ status: "expired" }),
      );
      resyncInviteLinkPanel({ message: "This invite link no longer works." });
      await settle();

      expect(announcement().text()).toMatch(
        /^This invite link no longer works\. This link expired on .+\.$/,
      );
    });
  });

  describe("stale responses", () => {
    it("paints nothing when the UTub switched mid-GET", async () => {
      const pending = deferred<InviteLink | null>();
      vi.mocked(getInviteLink).mockReturnValue(pending.promise);
      trigger().trigger("click");

      setState({ activeUTubID: 2 });
      resetInviteLinkPanel();
      pending.resolve(liveLink());
      await settle();

      expect($("#MemberInvitePanelBody").children().length).toBe(0);
      expect($("#inviteLinkUrlInput").length).toBe(0);
    });

    it("drops a response that started before a close and reopen", async () => {
      const first = deferred<InviteLink | null>();
      vi.mocked(getInviteLink).mockReturnValueOnce(first.promise);
      trigger().trigger("click");
      trigger().trigger("click");

      const second = deferred<InviteLink | null>();
      vi.mocked(getInviteLink).mockReturnValueOnce(second.promise);
      trigger().trigger("click");
      first.resolve(liveLink({ token: "x".repeat(22) }));
      await settle();
      expect($("#inviteLinkUrlInput").length).toBe(0);

      second.resolve(null);
      await settle();
      expect($("#inviteLinkExpiresSelect").length).toBe(1);
    });

    it("keeps the resync's render when an older in-flight load lands last", async () => {
      const older = deferred<InviteLink | null>();
      vi.mocked(getInviteLink).mockReturnValueOnce(older.promise);
      trigger().trigger("click");

      const newer = deferred<InviteLink | null>();
      vi.mocked(getInviteLink).mockReturnValueOnce(newer.promise);
      resyncInviteLinkPanel({ message: "Resynced." });
      newer.resolve(null);
      await settle();
      expect($("#inviteLinkExpiresSelect").length).toBe(1);

      older.resolve(liveLink({ token: "y".repeat(22) }));
      await settle();
      expect($("#inviteLinkUrlInput").length).toBe(0);
      expect($("#inviteLinkExpiresSelect").length).toBe(1);
    });
  });

  describe("close paths", () => {
    it("Escape consumes the event, closes the panel and returns focus to the trigger", async () => {
      await openWith(liveLink());
      const outer = vi.fn();
      document.addEventListener("keydown", outer);

      const event = new KeyboardEvent("keydown", {
        key: "Escape",
        bubbles: true,
        cancelable: true,
      });
      $("#inviteLinkUrlInput")[0].dispatchEvent(event);
      document.removeEventListener("keydown", outer);

      expect(event.defaultPrevented).toBe(true);
      expect(outer).not.toHaveBeenCalled();
      expect(isInviteLinkPanelOpen()).toBe(false);
      expect($("#MemberInvitePanel").hasClass("hidden")).toBe(true);
      expect(trigger().attr("aria-expanded")).toBe("false");
      expect(document.activeElement?.id).toBe("memberBtnInviteLink");
      expect($("#MemberInvitePanelBody").children().length).toBe(0);
    });

    it("the trigger toggles the panel and never pushes history", async () => {
      const length = window.history.length;
      await openWith(null);
      expect(isInviteLinkPanelOpen()).toBe(true);
      trigger().trigger("click");
      expect(isInviteLinkPanelOpen()).toBe(false);
      expect(window.history.length).toBe(length);
    });

    it("a user close announces nothing", async () => {
      await openWith(null);
      trigger().trigger("click");
      await settle();

      expect(announcement().text()).toBe("");
    });

    it("a UTub switch or deselect closes silently with no forced-close mark", async () => {
      await openWith(liveLink());
      setState({ activeUTubID: 2 });
      resetInviteLinkPanel();
      await settle();

      expect(isInviteLinkPanelOpen()).toBe(false);
      expect(announcement().text()).toBe("");
      expect(getForcedClosedToken()).toBeNull();
    });

    it("a same-UTub rebuild closes silently", async () => {
      await openWith(liveLink());
      resetInviteLinkPanel();
      await settle();

      expect(isInviteLinkPanelOpen()).toBe(false);
      expect(announcement().text()).toBe("");
      expect(trigger().attr("aria-expanded")).toBe("false");
    });
  });

  describe("cross-feature exclusion", () => {
    it("opening closes the add form, the filter and the Members gear", async () => {
      const gearCloser = vi.fn();
      const stopListening = on(AppEvents.INVITE_PANEL_OPENED, gearCloser);
      await openWith(null);
      stopListening();

      expect(hideAndResetMemberCombobox).toHaveBeenCalledTimes(1);
      expect(closeMemberNameFilter).toHaveBeenCalledTimes(1);
      expect(gearCloser).toHaveBeenCalledTimes(1);
    });

    it("opens with another home form open and both stay", async () => {
      emitAppEvent(AppEvents.FORM_MODE_CHANGED, { openForm: "url_create" });
      const formChanged = vi.fn();
      const off = on(AppEvents.FORM_MODE_CHANGED, formChanged);
      await openWith(null);
      off();

      expect(isInviteLinkPanelOpen()).toBe(true);
      // Opening never touches the other home form (nothing closes it).
      expect(formChanged).not.toHaveBeenCalled();
    });

    it("a later non-null FORM_MODE_CHANGED closes silently without moving focus", async () => {
      await openWith(liveLink());
      $("#MemberDeckHeaderAndCaret")[0].focus();

      emitAppEvent(AppEvents.FORM_MODE_CHANGED, { openForm: "url_create" });
      await settle();

      expect(isInviteLinkPanelOpen()).toBe(false);
      expect(announcement().text()).toBe("");
      expect(document.activeElement?.id).toBe("MemberDeckHeaderAndCaret");
    });

    it("FORM_MODE_CHANGED with null leaves it open", async () => {
      await openWith(null);
      emitAppEvent(AppEvents.FORM_MODE_CHANGED, { openForm: null });

      expect(isInviteLinkPanelOpen()).toBe(true);
    });

    it.each([
      [AppEvents.MEMBER_ADD_OPENED],
      [AppEvents.MEMBER_FILTER_OPENED],
    ] as const)("%s closes silently", async (eventName) => {
      await openWith(null);
      $("#MemberDeckHeaderAndCaret")[0].focus();
      emitAppEvent(eventName);
      await settle();

      expect(isInviteLinkPanelOpen()).toBe(false);
      expect(announcement().text()).toBe("");
      expect(document.activeElement?.id).toBe("MemberDeckHeaderAndCaret");
    });

    it("the Members gear closes it silently; the utubs and tags gears do not", async () => {
      await openWith(null);
      emitAppEvent(AppEvents.PANEL_SETTINGS_OPENED, { panel: "utubs" });
      emitAppEvent(AppEvents.PANEL_SETTINGS_OPENED, { panel: "tags" });
      expect(isInviteLinkPanelOpen()).toBe(true);

      $("#MemberDeckHeaderAndCaret")[0].focus();
      emitAppEvent(AppEvents.PANEL_SETTINGS_OPENED, { panel: "members" });
      await settle();

      expect(isInviteLinkPanelOpen()).toBe(false);
      expect(announcement().text()).toBe("");
      expect(document.activeElement?.id).toBe("MemberDeckHeaderAndCaret");
    });

    it.each(["url-deck", "utub-deck", "no-utub", "trash"] as const)(
      "a mobile switch to %s closes it and focus lands on the deck header",
      async (target) => {
        await openWith(liveLink());
        expect(document.activeElement?.id).toBe("inviteLinkUrlInput");

        emitAppEvent(AppEvents.MOBILE_DECK_SWITCHED, { target });

        expect(isInviteLinkPanelOpen()).toBe(false);
        expect(document.activeElement?.id).toBe("MemberDeckHeaderAndCaret");
      },
    );

    it.each(["member-deck", "desktop"] as const)(
      "a mobile switch to %s leaves it open",
      async (target) => {
        await openWith(null);
        emitAppEvent(AppEvents.MOBILE_DECK_SWITCHED, { target });

        expect(isInviteLinkPanelOpen()).toBe(true);
      },
    );

    it("collapsing the Members deck closes it; other decks and expanding do not", async () => {
      await openWith(liveLink());
      emitAppEvent(AppEvents.DECK_COLLAPSE_CHANGED, {
        deck: "utubs",
        collapsed: true,
      });
      emitAppEvent(AppEvents.DECK_COLLAPSE_CHANGED, {
        deck: "members",
        collapsed: false,
      });
      expect(isInviteLinkPanelOpen()).toBe(true);

      emitAppEvent(AppEvents.DECK_COLLAPSE_CHANGED, {
        deck: "members",
        collapsed: true,
      });

      expect(isInviteLinkPanelOpen()).toBe(false);
      expect(document.activeElement?.id).toBe("MemberDeckHeaderAndCaret");
    });

    it("the unsubscribe removes the bus subscriptions", async () => {
      await openWith(null);
      unsubscribe();
      emitAppEvent(AppEvents.MEMBER_ADD_OPENED);

      expect(isInviteLinkPanelOpen()).toBe(true);
    });
  });

  describe("forced close", () => {
    it("closes and announces when the viewer is demoted while open", async () => {
      await openWith(liveLink());
      setState({ isCurrentUserOwner: false, isCoCreator: false });
      await settle();

      expect(isInviteLinkPanelOpen()).toBe(false);
      expect(announcement().text()).toBe(
        strings.INVITE_LINK_PANEL_FORCED_CLOSE,
      );
      expect(trigger().hasClass("hidden")).toBe(true);
    });

    it("closes and announces when the UTub is locked while open", async () => {
      await openWith(liveLink());
      setState({ isCurrentUTubLocked: true });
      await settle();

      expect(isInviteLinkPanelOpen()).toBe(false);
      expect(announcement().text()).toBe(
        strings.INVITE_LINK_PANEL_FORCED_CLOSE,
      );
    });

    it("records the pre-bump token on a forced close and leaves it null on a silent close", async () => {
      await openWith(liveLink());
      setState({ isCurrentUTubLocked: true });
      const token = getForcedClosedToken();
      expect(token).not.toBeNull();

      resetInviteLinkPanel();
      expect(getForcedClosedToken()).toBeNull();

      setState({ isCurrentUTubLocked: false });
      await openWith(null);
      trigger().trigger("click");
      expect(getForcedClosedToken()).toBeNull();
    });

    it("a demotion delivered as setState then a same-UTub rebuild announces exactly once", async () => {
      await openWith(liveLink());
      const writes: string[] = [];
      const observer = new MutationObserver(() =>
        writes.push(announcement().text()),
      );
      observer.observe(announcement()[0], {
        childList: true,
        characterData: true,
        subtree: true,
      });

      setState({ isCurrentUserOwner: false, isCoCreator: false });
      resetInviteLinkPanel();
      await settle();
      await Promise.resolve();
      observer.disconnect();

      expect(announcement().text()).toBe(
        strings.INVITE_LINK_PANEL_FORCED_CLOSE,
      );
      expect(
        writes.filter((text) => text === strings.INVITE_LINK_PANEL_FORCED_CLOSE)
          .length,
      ).toBe(1);
    });

    it("lands focus on the deck header when it was inside the panel or on the trigger", async () => {
      await openWith(liveLink());
      expect(document.activeElement?.id).toBe("inviteLinkUrlInput");
      setState({ isCurrentUTubLocked: true });
      expect(document.activeElement?.id).toBe("MemberDeckHeaderAndCaret");

      setState({ isCurrentUTubLocked: false });
      trigger()[0].focus();
      setState({ isCurrentUserOwner: false, isCoCreator: false });
      expect(document.activeElement?.id).toBe("MemberDeckHeaderAndCaret");
    });
  });

  describe("announce helper", () => {
    it("re-announces an identical consecutive message and still writes after a close", async () => {
      announceInviteLinkPanel({ message: "Same." });
      await settle();
      expect(announcement().text()).toBe("Same.");

      announceInviteLinkPanel({ message: "Same." });
      expect(announcement().text()).toBe("");
      await settle();
      expect(announcement().text()).toBe("Same.");

      await openWith(null);
      announceInviteLinkPanel({ message: "After close." });
      resetInviteLinkPanel();
      await settle();
      expect(announcement().text()).toBe("After close.");
    });

    it("also writes #MobilePanelAnnouncement when the Members deck is not displayed", async () => {
      $("#MemberDeck").css("display", "none");
      announceInviteLinkPanel({ message: "Mobile." });
      await settle();

      expect($("#MobilePanelAnnouncement").text()).toBe("Mobile.");
      expect(announcement().text()).toBe("Mobile.");
    });

    it("leaves #MobilePanelAnnouncement empty when the Members deck is displayed", async () => {
      $("#MemberDeck").css("display", "block");
      announceInviteLinkPanel({ message: "Desktop." });
      await settle();

      expect($("#MobilePanelAnnouncement").text()).toBe("");
      expect(announcement().text()).toBe("Desktop.");
    });
  });

  it("keeps the store gate consistent with the rendered trigger", () => {
    expect(canManageInviteLink(getState())).toBe(true);
    expect(trigger().hasClass("hidden")).toBe(false);
  });
});
