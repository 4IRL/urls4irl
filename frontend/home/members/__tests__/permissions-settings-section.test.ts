import { announceSettingsStatus } from "../../panel-settings/announce.js";
import { patchUtubSettings } from "../../panel-settings/client.js";
import {
  _resetRegistryForTests,
  getSections,
} from "../../panel-settings/registry.js";
import type {
  PanelSection,
  SectionContext,
} from "../../panel-settings/types.js";
import { setState } from "../../../store/app-store.js";
import {
  EMPTY_UTUB_SETTINGS,
  type ResolvedUtubSettings,
} from "../../../types/settings.js";
import { registerMembersPermissionsSettingsSection } from "../permissions-settings-section.js";

vi.mock("../../panel-settings/client.js", () => ({
  patchUtubSettings: vi.fn(),
}));

const REMOVE = "#membersPermissionsCoOwnersRemoveSwitch";
const ADD = "#membersPermissionsMembersAddSwitch";
const HIDE = "#membersPermissionsHideListSwitch";
const NOTE_ID = "panelSettingsNote-members-permissions";

describe("Members permissions settings section", () => {
  let host: HTMLElement;
  let section: PanelSection;
  let unregister: () => void;
  let submit: ReturnType<typeof vi.fn>;

  function ctxFor(overrides: Partial<SectionContext> = {}): SectionContext {
    return {
      settings: null,
      canWrite: true,
      readOnlyNoteId: NOTE_ID,
      submit,
      ...overrides,
    } as SectionContext;
  }

  const cleanups: Array<() => void> = [];

  function renderWith(ctx: SectionContext): void {
    host.innerHTML = "";
    const cleanup = section.render({ container: host, ctx });
    if (typeof cleanup === "function") cleanups.push(cleanup);
  }

  function control(selector: string): HTMLElement {
    return document.querySelector<HTMLElement>(selector)!;
  }

  beforeEach(() => {
    _resetRegistryForTests();
    vi.clearAllMocks();
    document.body.innerHTML = "";
    host = document.createElement("div");
    document.body.append(host);
    submit = vi.fn();
    unregister = registerMembersPermissionsSettingsSection();
    section = getSections("members")[0];
  });

  afterEach(() => {
    // Detach each render's document listeners so renders never leak across tests.
    for (const cleanup of cleanups.splice(0)) cleanup();
    unregister();
  });

  it("registers as an owner-write, managers-visible utub section", () => {
    expect(section.id).toBe("members-permissions");
    expect(section.panel).toBe("members");
    expect(section.scope).toBe("utub");
    expect(section.writeAccess).toBe("owner");
    expect(section.visibleTo).toBe("managers");
    expect(section.title).toBe("Member permissions");
  });

  it("renders enabled switches defaulting to off for the owner", () => {
    renderWith(ctxFor());
    for (const selector of [REMOVE, ADD, HIDE]) {
      expect(control(selector).getAttribute("aria-checked")).toBe("false");
      expect(control(selector).hasAttribute("aria-disabled")).toBe(false);
    }
  });

  it("reflects stored values", () => {
    renderWith(
      ctxFor({
        settings: {
          ...EMPTY_UTUB_SETTINGS,
          members: {
            ...EMPTY_UTUB_SETTINGS.members,
            co_owners_can_remove: true,
            members_can_add: false,
            hide_member_list: true,
          },
        },
      }),
    );
    expect(control(REMOVE).getAttribute("aria-checked")).toBe("true");
    expect(control(ADD).getAttribute("aria-checked")).toBe("false");
    expect(control(HIDE).getAttribute("aria-checked")).toBe("true");
  });

  it("submits the hide_member_list key and announces its notices", async () => {
    renderWith(ctxFor());
    control(HIDE).click();
    expect(submit).toHaveBeenLastCalledWith({
      patch: { hide_member_list: true },
    });
    vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
    const on = await section.save({
      utubID: 3,
      patch: { hide_member_list: true },
    });
    expect(on).toEqual({
      outcome: "ok",
      notice: "Members now see only the owner, co-owners and themselves",
    });
    const off = await section.save({
      utubID: 3,
      patch: { hide_member_list: false },
    });
    expect(off).toEqual({
      outcome: "ok",
      notice: "Members can now see everyone in this UTub",
    });
  });

  it("submits exactly one key per flip", () => {
    renderWith(ctxFor());
    control(REMOVE).click();
    expect(submit).toHaveBeenLastCalledWith({
      patch: { co_owners_can_remove: true },
    });
    expect(control(REMOVE).getAttribute("aria-checked")).toBe("true");
    control(ADD).click();
    expect(submit).toHaveBeenLastCalledWith({
      patch: { members_can_add: true },
    });
    control(ADD).click();
    expect(submit).toHaveBeenLastCalledWith({
      patch: { members_can_add: false },
    });
  });

  it("is read-only, described by the note, and inert when canWrite is false", () => {
    renderWith(ctxFor({ canWrite: false }));
    for (const selector of [REMOVE, ADD, HIDE]) {
      const element = control(selector);
      expect(element.getAttribute("aria-disabled")).toBe("true");
      expect(element.getAttribute("aria-describedby")).toContain(NOTE_ID);
      element.click();
      expect(element.getAttribute("aria-checked")).toBe("false");
    }
    expect(submit).not.toHaveBeenCalled();
  });

  describe("save", () => {
    it("patches the members panel and returns the matching notice", async () => {
      vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
      const result = await section.save({
        utubID: 3,
        patch: { co_owners_can_remove: true },
      });
      expect(patchUtubSettings).toHaveBeenCalledWith({
        utubID: 3,
        panel: "members",
        patch: { co_owners_can_remove: true },
      });
      expect(result).toEqual({
        outcome: "ok",
        notice: "Co-owners can now remove members",
      });
    });

    it("announces the off notices and joins a coalesced patch", async () => {
      vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
      const result = await section.save({
        utubID: 3,
        patch: { co_owners_can_remove: false, members_can_add: false },
      });
      expect(result).toEqual({
        outcome: "ok",
        notice:
          "Co-owners can no longer remove members. Members can no longer add members",
      });
    });

    it.each(["forbidden", "locked", "error"] as const)(
      "passes a %s outcome through without a notice",
      async (outcome) => {
        vi.mocked(patchUtubSettings).mockResolvedValue({ outcome });
        const result = await section.save({
          utubID: 3,
          patch: { members_can_add: true },
        });
        expect(result).toEqual({ outcome });
      },
    );

    it("errors without a UTub and sends nothing", async () => {
      const result = await section.save({
        utubID: null,
        patch: { members_can_add: true },
      });
      expect(result).toEqual({ outcome: "error" });
      expect(patchUtubSettings).not.toHaveBeenCalled();
    });

    it("joins the creators notice and the revoked/ended sentences", async () => {
      vi.mocked(patchUtubSettings).mockResolvedValue({
        outcome: "ok",
        inviteLinkRevoked: true,
        invitePreviewEnded: true,
      });
      const result = await section.save({
        utubID: 3,
        patch: { invite_link_creators: "owner_only" },
      });
      expect(result).toMatchObject({
        notice:
          "Only the owner can create invite links. A co-owner's invite link stopped working. The current preview ended",
      });
    });

    it("omits the side-effect sentences when the booleans are absent or false", async () => {
      vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
      const result = await section.save({
        utubID: 3,
        patch: { invite_link_creators: "no_one" },
      });
      expect(result).toEqual({
        outcome: "ok",
        notice: "No one can create invite links",
      });
      const preview = await section.save({
        utubID: 3,
        patch: { co_owners_can_enable_preview: true },
      });
      expect(preview).toEqual({
        outcome: "ok",
        notice: "Co-owners can now turn on previews",
      });
    });
  });

  describe("invite link creators row", () => {
    const SELECT = "#membersPermissionsInviteCreatorsSelect";
    const APPLY = "#membersPermissionsInviteCreatorsApplyButton";
    const WARNING = "#membersPermissionsInviteCreatorsWarning";
    const NOT_APPLIED = "#membersPermissionsInviteCreatorsNotApplied";
    const PREVIEW = "#membersPermissionsCoOwnersPreviewSwitch";

    function creatorsCtx(stored: string, overrides = {}): SectionContext {
      return ctxFor({
        settings: {
          ...EMPTY_UTUB_SETTINGS,
          members: {
            ...EMPTY_UTUB_SETTINGS.members,
            invite_link_creators: stored,
          },
        } as SectionContext["settings"],
        ...overrides,
      });
    }

    function pick(value: string): void {
      const select = control(SELECT) as HTMLSelectElement;
      select.value = value;
      select.dispatchEvent(new Event("change"));
    }

    beforeEach(() => {
      vi.useFakeTimers();
      const region = document.createElement("div");
      region.id = "PanelSettingsAnnouncement";
      document.body.append(region);
      Element.prototype.scrollIntoView = vi.fn();
    });

    afterEach(() => {
      // Flush pending announcements so the shared announce state is clean.
      vi.runOnlyPendingTimers();
      vi.useRealTimers();
    });

    it("renders the select, options in order, and the preview switch", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      const select = control(SELECT) as HTMLSelectElement;
      expect(Array.from(select.options).map((option) => option.value)).toEqual([
        "owner_and_co_owners",
        "owner_only",
        "no_one",
      ]);
      expect(select.value).toBe("owner_and_co_owners");
      expect(select.getAttribute("aria-describedby")).toBe(
        "membersPermissionsInviteCreatorsDesc",
      );
      expect(control(PREVIEW).getAttribute("aria-checked")).toBe("false");
      expect(document.querySelector(WARNING)).toBeNull();
      expect(document.querySelector(APPLY)).toBeNull();
    });

    it("shows the settled description for the stored value without a warning", () => {
      renderWith(creatorsCtx("no_one"));
      expect(
        control("#membersPermissionsInviteCreatorsDesc").textContent,
      ).toContain("No one sees the invite button.");
      expect(document.querySelector(WARNING)).toBeNull();
    });

    it("submits the preview switch key", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      control(PREVIEW).click();
      expect(submit).toHaveBeenLastCalledWith({
        patch: { co_owners_can_enable_preview: true },
      });
    });

    it.each([
      ["owner_and_co_owners", "owner_only"],
      ["owner_and_co_owners", "no_one"],
      ["owner_only", "no_one"],
    ])("stages the tightening %s to %s instead of saving", (from, to) => {
      renderWith(creatorsCtx(from));
      pick(to);
      vi.advanceTimersByTime(1000);
      expect(submit).not.toHaveBeenCalled();
      expect(control(WARNING).textContent).not.toBe("");
      expect(control(NOT_APPLIED).textContent).toBe("Not applied yet.");
      expect(control(APPLY).textContent).toBe("Apply");
      expect(control(SELECT).getAttribute("aria-describedby")).toBe(
        "membersPermissionsInviteCreatorsDesc membersPermissionsInviteCreatorsWarning membersPermissionsInviteCreatorsNotApplied",
      );
      expect(control(APPLY).getAttribute("aria-describedby")).toBe(
        "membersPermissionsInviteCreatorsWarning",
      );
      expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({
        block: "nearest",
      });
    });

    it.each([
      ["no_one", "owner_only"],
      ["owner_only", "owner_and_co_owners"],
      ["no_one", "owner_and_co_owners"],
    ])("autosaves the relax %s to %s with no warning", (from, to) => {
      renderWith(creatorsCtx(from));
      pick(to);
      expect(submit).toHaveBeenCalledWith({
        patch: { invite_link_creators: to },
        debounce: true,
      });
      expect(document.querySelector(WARNING)).toBeNull();
      expect(document.querySelector(APPLY)).toBeNull();
    });

    it("announces the stage message once, debounced to the latest", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      pick("no_one");
      vi.advanceTimersByTime(1000);
      expect(
        document.querySelector("#PanelSettingsAnnouncement")!.textContent,
      ).toContain("The current link stops working");
    });

    it("Apply sends the staged value immediately, once, and locks the select", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      const apply = control(APPLY) as HTMLButtonElement;
      apply.click();
      apply.click();
      expect(submit).toHaveBeenCalledTimes(1);
      expect(submit).toHaveBeenCalledWith({
        patch: { invite_link_creators: "owner_only" },
        debounce: false,
      });
      expect(apply.disabled).toBe(true);
      expect(apply.getAttribute("aria-busy")).toBe("true");
      expect(document.activeElement).toBe(control(SELECT));
      expect(control(SELECT).getAttribute("aria-disabled")).toBe("true");
      expect(document.querySelector(NOT_APPLIED)).toBeNull();
      // A change while in flight reverts and sends nothing.
      pick("no_one");
      expect((control(SELECT) as HTMLSelectElement).value).toBe("owner_only");
      expect(submit).toHaveBeenCalledTimes(1);
    });

    it.each(["forbidden", "locked", "error"] as const)(
      "tears the staging down and reverts after a %s Apply outcome",
      async (outcome) => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        (control(APPLY) as HTMLButtonElement).click();
        vi.mocked(patchUtubSettings).mockResolvedValue({ outcome });
        await section.save({
          utubID: 3,
          patch: { invite_link_creators: "owner_only" },
        });
        expect(document.querySelector(WARNING)).toBeNull();
        expect(document.querySelector(APPLY)).toBeNull();
        const select = control(SELECT) as HTMLSelectElement;
        expect(select.value).toBe("owner_and_co_owners");
        expect(select.hasAttribute("aria-disabled")).toBe(false);
        expect(select.getAttribute("aria-describedby")).toBe(
          "membersPermissionsInviteCreatorsDesc",
        );
      },
    );

    it("shows the new stored value and description after an ok Apply", async () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      (control(APPLY) as HTMLButtonElement).click();
      vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
      setState({
        settings: {
          ...EMPTY_UTUB_SETTINGS,
          members: {
            ...EMPTY_UTUB_SETTINGS.members,
            invite_link_creators: "owner_only",
          },
        } as ResolvedUtubSettings,
      });
      await section.save({
        utubID: 3,
        patch: { invite_link_creators: "owner_only" },
      });
      expect(document.querySelector(APPLY)).toBeNull();
      expect((control(SELECT) as HTMLSelectElement).value).toBe("owner_only");
      expect(control("#membersPermissionsInviteCreatorsDesc").textContent).toBe(
        "Only the owner sees the invite button.",
      );
    });

    it("another key's save leaves a staged value alone", async () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "error" });
      await section.save({
        utubID: 3,
        patch: { co_owners_can_enable_preview: true },
      });
      expect(document.querySelector(APPLY)).not.toBeNull();
      expect((control(SELECT) as HTMLSelectElement).value).toBe("owner_only");
    });

    it("discards on focus moving outside the pair and announces it", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      const outside = document.createElement("button");
      document.body.append(outside);
      control(SELECT).focus();
      outside.focus();
      vi.advanceTimersByTime(10);
      expect(document.querySelector(APPLY)).toBeNull();
      expect((control(SELECT) as HTMLSelectElement).value).toBe(
        "owner_and_co_owners",
      );
      expect(submit).not.toHaveBeenCalled();
      expect(
        document.querySelector("#PanelSettingsAnnouncement")!.textContent,
      ).toBe("Change not applied.");
    });

    it("does not discard when focus moves from the select to Apply", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      control(SELECT).focus();
      control(APPLY).focus();
      vi.advanceTimersByTime(10);
      expect(document.querySelector(APPLY)).not.toBeNull();
    });

    it("discards on a mouse pointerdown outside the section", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      document.body.dispatchEvent(
        new MouseEvent("pointerdown", { bubbles: true }),
      );
      expect(document.querySelector(APPLY)).toBeNull();
    });

    it("Escape discards only, keeps the event from the shell, then passes through", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      const event = new KeyboardEvent("keydown", {
        key: "Escape",
        bubbles: true,
        cancelable: true,
      });
      const bubbled = vi.fn();
      document.addEventListener("keydown", bubbled);
      control(SELECT).dispatchEvent(event);
      expect(document.querySelector(APPLY)).toBeNull();
      expect(bubbled).not.toHaveBeenCalled();
      control(SELECT).dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
      expect(bubbled).toHaveBeenCalledTimes(1);
      document.removeEventListener("keydown", bubbled);
    });

    it("the cleanup announces Change not applied for a staged value", () => {
      section = getSections("members")[0];
      host.innerHTML = "";
      const cleanup = section.render({
        container: host,
        ctx: creatorsCtx("owner_and_co_owners"),
      }) as () => void;
      pick("owner_only");
      cleanup();
      vi.advanceTimersByTime(10);
      expect(
        document.querySelector("#PanelSettingsAnnouncement")!.textContent,
      ).toBe("Change not applied.");
    });

    it("re-picking the baseline clears silently and sends nothing", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      pick("owner_and_co_owners");
      vi.advanceTimersByTime(1000);
      expect(document.querySelector(APPLY)).toBeNull();
      expect(submit).not.toHaveBeenCalled();
      expect(
        document.querySelector("#PanelSettingsAnnouncement")!.textContent,
      ).toBe("");
    });

    it("re-picking the stored value with an autosave pending submits the stored value", () => {
      renderWith(creatorsCtx("no_one"));
      pick("owner_only");
      pick("no_one");
      expect(submit).toHaveBeenLastCalledWith({
        patch: { invite_link_creators: "no_one" },
        debounce: true,
      });
      expect(document.querySelector(APPLY)).toBeNull();
    });

    it("classifies against the pending value, not the stored one", () => {
      renderWith(creatorsCtx("owner_only"));
      pick("owner_and_co_owners");
      expect(submit).toHaveBeenCalledTimes(1);
      // Pending autosave to owner_and_co_owners: no_one is a tightening of it.
      pick("no_one");
      expect(submit).toHaveBeenCalledTimes(1);
      expect(document.querySelector(APPLY)).not.toBeNull();
    });

    it("an autosaving pick while staged keeps the picked value and sends it", () => {
      renderWith(creatorsCtx("owner_only"));
      pick("no_one");
      expect(document.querySelector(APPLY)).not.toBeNull();
      pick("owner_and_co_owners");
      expect(document.querySelector(APPLY)).toBeNull();
      expect((control(SELECT) as HTMLSelectElement).value).toBe(
        "owner_and_co_owners",
      );
      expect(submit).toHaveBeenCalledWith({
        patch: { invite_link_creators: "owner_and_co_owners" },
        debounce: true,
      });
    });

    it("re-picking stored while staged and an autosave pends keeps the stored value", () => {
      renderWith(creatorsCtx("no_one"));
      pick("owner_only");
      pick("no_one");
      expect((control(SELECT) as HTMLSelectElement).value).toBe("no_one");
    });

    it("an autosave resolving after Apply is pressed leaves Apply's staging alone", async () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("no_one");
      (control(APPLY) as HTMLButtonElement).click();
      vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "error" });
      await section.save({
        utubID: 3,
        patch: { invite_link_creators: "owner_and_co_owners" },
      });
      expect(control(APPLY)).not.toBeNull();
      expect(control(SELECT).getAttribute("aria-disabled")).toBe("true");
      await section.save({
        utubID: 3,
        patch: { invite_link_creators: "no_one" },
      });
      expect(document.querySelector(APPLY)).toBeNull();
      expect((control(SELECT) as HTMLSelectElement).value).toBe(
        "owner_and_co_owners",
      );
    });

    it("Escape on Apply discards, focuses the select and announces", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      control(APPLY).dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
      vi.advanceTimersByTime(10);
      expect(document.querySelector(APPLY)).toBeNull();
      expect(document.activeElement).toBe(control(SELECT));
      expect(
        document.querySelector("#PanelSettingsAnnouncement")!.textContent,
      ).toBe("Change not applied.");
    });

    it("Escape while Apply is in flight is not intercepted", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      (control(APPLY) as HTMLButtonElement).click();
      const bubbled = vi.fn();
      document.addEventListener("keydown", bubbled);
      control(SELECT).dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
      document.removeEventListener("keydown", bubbled);
      expect(bubbled).toHaveBeenCalledTimes(1);
      expect(document.querySelector(APPLY)).not.toBeNull();
    });

    it("while Apply is in flight a focus-leave and an outside press discard nothing", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      (control(APPLY) as HTMLButtonElement).click();
      const outside = document.createElement("button");
      document.body.append(outside);
      outside.focus();
      document.body.dispatchEvent(
        new MouseEvent("pointerdown", { bubbles: true }),
      );
      vi.advanceTimersByTime(10);
      expect(document.querySelector(WARNING)).not.toBeNull();
      expect((control(SELECT) as HTMLSelectElement).value).toBe("owner_only");
      expect(
        document.querySelector("#PanelSettingsAnnouncement")!.textContent,
      ).not.toContain("Change not applied.");
    });

    describe("pointer types", () => {
      function pointer({
        type,
        x,
        y,
        pointerType,
      }: {
        type: string;
        x: number;
        y: number;
        pointerType: string;
      }): void {
        const event = new MouseEvent(type, {
          bubbles: true,
          clientX: x,
          clientY: y,
        });
        Object.defineProperty(event, "pointerType", { value: pointerType });
        document.body.dispatchEvent(event);
      }

      it("discards on a pen pointerdown outside", () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        pointer({ type: "pointerdown", x: 0, y: 0, pointerType: "pen" });
        expect(document.querySelector(APPLY)).toBeNull();
      });

      it("discards on a touch tap outside within the threshold", () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        pointer({ type: "pointerdown", x: 5, y: 5, pointerType: "touch" });
        expect(document.querySelector(APPLY)).not.toBeNull();
        pointer({ type: "pointerup", x: 8, y: 6, pointerType: "touch" });
        expect(document.querySelector(APPLY)).toBeNull();
      });

      it("keeps the staging for a touch that moves beyond the threshold", () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        pointer({ type: "pointerdown", x: 5, y: 5, pointerType: "touch" });
        pointer({ type: "pointerup", x: 5, y: 60, pointerType: "touch" });
        expect(document.querySelector(APPLY)).not.toBeNull();
      });

      it("keeps the staging for a touch ending in pointercancel", () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        pointer({ type: "pointerdown", x: 5, y: 5, pointerType: "touch" });
        pointer({ type: "pointercancel", x: 5, y: 5, pointerType: "touch" });
        pointer({ type: "pointerup", x: 5, y: 5, pointerType: "touch" });
        expect(document.querySelector(APPLY)).not.toBeNull();
      });
    });

    it("a press on Apply with a null relatedTarget is not read as leaving", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      const apply = control(APPLY) as HTMLButtonElement;
      apply.dispatchEvent(new MouseEvent("mousedown", { bubbles: true }));
      control(SELECT).focus();
      document.body.focus();
      control(SELECT).dispatchEvent(new FocusEvent("focusout"));
      vi.advanceTimersByTime(10);
      expect(document.querySelector(APPLY)).not.toBeNull();
      apply.click();
      expect(submit).toHaveBeenCalledTimes(1);
    });

    it("a stored-value change alone does not discard, and Apply sends the staged value", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      setState({
        settings: {
          ...EMPTY_UTUB_SETTINGS,
          members: {
            ...EMPTY_UTUB_SETTINGS.members,
            invite_link_creators: "no_one",
          },
        } as ResolvedUtubSettings,
      });
      vi.advanceTimersByTime(10);
      (control(APPLY) as HTMLButtonElement).click();
      expect(submit).toHaveBeenCalledWith({
        patch: { invite_link_creators: "owner_only" },
        debounce: false,
      });
    });

    it("is read-only: aria-disabled, described by the note, reverts, no Apply", () => {
      renderWith(creatorsCtx("owner_and_co_owners", { canWrite: false }));
      const select = control(SELECT) as HTMLSelectElement;
      expect(select.getAttribute("aria-disabled")).toBe("true");
      expect(select.getAttribute("aria-describedby")).toBe(
        `membersPermissionsInviteCreatorsDesc ${NOTE_ID}`,
      );
      pick("no_one");
      expect(select.value).toBe("owner_and_co_owners");
      expect(submit).not.toHaveBeenCalled();
      expect(document.querySelector(WARNING)).toBeNull();
      expect(document.querySelector(APPLY)).toBeNull();
      expect(control(PREVIEW).getAttribute("aria-disabled")).toBe("true");
    });

    function liveRegion(): string {
      return document.querySelector("#PanelSettingsAnnouncement")!.textContent!;
    }

    function storeCreators(value: string): void {
      setState({
        settings: {
          ...EMPTY_UTUB_SETTINGS,
          members: {
            ...EMPTY_UTUB_SETTINGS.members,
            invite_link_creators: value,
          },
        } as ResolvedUtubSettings,
      });
    }

    function pointerEvent({
      type,
      target,
    }: {
      type: string;
      target: Element;
    }): void {
      target.dispatchEvent(new MouseEvent(type, { bubbles: true }));
    }

    it("shows each target's own warning text", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      expect(control(WARNING).textContent).toBe(
        "A link a co-owner made stops working, even if you change this back.",
      );
      pick("no_one");
      expect(control(WARNING).textContent).toBe(
        "The current link stops working, even if you change this back. No one sees the invite button.",
      );
    });

    it("shows the settled description for owner_only", () => {
      renderWith(creatorsCtx("owner_only"));
      expect(control("#membersPermissionsInviteCreatorsDesc").textContent).toBe(
        "Only the owner sees the invite button.",
      );
    });

    it("coalesces arrow-key steps and announces only the latest stage message", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      vi.advanceTimersByTime(100);
      pick("no_one");
      vi.advanceTimersByTime(100);
      pick("owner_only");
      vi.advanceTimersByTime(1000);
      expect(liveRegion()).toContain("A link a co-owner made stops working");
    });

    it("a discard cancels the pending stage announcement", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      control(SELECT).dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
      vi.advanceTimersByTime(1000);
      expect(liveRegion()).toBe("Change not applied.");
    });

    it("pressing Apply inside the debounce window never announces the stage message", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      pick("owner_only");
      vi.advanceTimersByTime(100);
      (control(APPLY) as HTMLButtonElement).click();
      vi.advanceTimersByTime(1000);
      expect(liveRegion()).toBe("");
    });

    it("restores aria-describedby exactly after a discard", () => {
      renderWith(creatorsCtx("owner_and_co_owners"));
      const before = control(SELECT).getAttribute("aria-describedby");
      pick("owner_only");
      pick("owner_and_co_owners");
      expect(control(SELECT).getAttribute("aria-describedby")).toBe(before);
      pick("no_one");
      control(SELECT).dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
      expect(control(SELECT).getAttribute("aria-describedby")).toBe(before);
    });

    it("an autosave pick while staged cancels the stage and announces it", () => {
      renderWith(creatorsCtx("owner_only"));
      pick("no_one");
      pick("owner_and_co_owners");
      vi.advanceTimersByTime(1000);
      expect(liveRegion()).toBe("Change not applied.");
    });

    it("a discard with an autosave pending shows the pending value, then the stored one after it settles", async () => {
      renderWith(creatorsCtx("no_one"));
      pick("owner_and_co_owners");
      expect(submit).toHaveBeenLastCalledWith({
        patch: { invite_link_creators: "owner_and_co_owners" },
        debounce: true,
      });
      // A tightening of the pending value (not of the stored one) stages.
      pick("owner_only");
      expect(document.querySelector(APPLY)).not.toBeNull();
      control(SELECT).dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
      expect((control(SELECT) as HTMLSelectElement).value).toBe(
        "owner_and_co_owners",
      );
      storeCreators("owner_and_co_owners");
      vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
      await section.save({
        utubID: 3,
        patch: { invite_link_creators: "owner_and_co_owners" },
      });
      expect((control(SELECT) as HTMLSelectElement).value).toBe(
        "owner_and_co_owners",
      );
    });

    it("clears lastSubmitted only when the saved value equals it", async () => {
      renderWith(creatorsCtx("no_one"));
      pick("owner_and_co_owners");
      vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "error" });
      // An unrelated older save resolves while owner_and_co_owners pends.
      await section.save({
        utubID: 3,
        patch: { invite_link_creators: "owner_only" },
      });
      // Baseline is still the pending pick, so owner_only is a tightening.
      pick("owner_only");
      expect(document.querySelector(APPLY)).not.toBeNull();
      control(SELECT).dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
      // The newer save resolving clears it: the baseline is the stored no_one.
      await section.save({
        utubID: 3,
        patch: { invite_link_creators: "owner_and_co_owners" },
      });
      submit.mockClear();
      pick("owner_only");
      expect(document.querySelector(APPLY)).toBeNull();
      expect(submit).toHaveBeenLastCalledWith({
        patch: { invite_link_creators: "owner_only" },
        debounce: true,
      });
    });

    it("re-picking the stored value while the autosave is in flight submits the stored value", () => {
      renderWith(creatorsCtx("no_one"));
      pick("owner_only");
      vi.advanceTimersByTime(1000);
      pick("no_one");
      expect(submit).toHaveBeenLastCalledWith({
        patch: { invite_link_creators: "no_one" },
        debounce: true,
      });
    });

    describe("applyPressed", () => {
      it("is cleared by the deferred document pointerup so a later focus-leave discards", () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        const apply = control(APPLY);
        apply.focus();
        pointerEvent({ type: "mousedown", target: apply });
        pointerEvent({ type: "pointerup", target: document.body });
        vi.advanceTimersByTime(10);
        const outside = document.createElement("button");
        document.body.append(outside);
        outside.focus();
        vi.advanceTimersByTime(10);
        expect(document.querySelector(APPLY)).toBeNull();
      });

      it("a pointercancel on Apply clears it", () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        const apply = control(APPLY);
        apply.focus();
        pointerEvent({ type: "mousedown", target: apply });
        pointerEvent({ type: "pointercancel", target: apply });
        const outside = document.createElement("button");
        document.body.append(outside);
        outside.focus();
        vi.advanceTimersByTime(10);
        expect(document.querySelector(APPLY)).toBeNull();
      });

      it("a discard clears it", () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        pointerEvent({ type: "mousedown", target: control(APPLY) });
        control(SELECT).dispatchEvent(
          new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
        );
        pick("owner_only");
        control(SELECT).focus();
        const outside = document.createElement("button");
        document.body.append(outside);
        outside.focus();
        vi.advanceTimersByTime(10);
        expect(document.querySelector(APPLY)).toBeNull();
      });

      it("does not discard when focusout has a null relatedTarget and body is active", () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        control(SELECT).focus();
        (document.activeElement as HTMLElement).blur();
        vi.advanceTimersByTime(10);
        expect(document.querySelector(APPLY)).not.toBeNull();
      });
    });

    describe("save outcomes", () => {
      it("a stale Apply outcome tears the staging down and reverts", async () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        (control(APPLY) as HTMLButtonElement).click();
        vi.mocked(patchUtubSettings).mockResolvedValue({
          outcome: "stale",
          failed: false,
        });
        await section.save({
          utubID: 3,
          patch: { invite_link_creators: "owner_only" },
        });
        expect(document.querySelector(APPLY)).toBeNull();
        expect((control(SELECT) as HTMLSelectElement).value).toBe(
          "owner_and_co_owners",
        );
      });

      it.each(["error", "forbidden"] as const)(
        "no stray Change not applied follows a %s Apply outcome",
        async (outcome) => {
          renderWith(creatorsCtx("owner_and_co_owners"));
          pick("owner_only");
          (control(APPLY) as HTMLButtonElement).click();
          vi.mocked(patchUtubSettings).mockResolvedValue({ outcome });
          await section.save({
            utubID: 3,
            patch: { invite_link_creators: "owner_only" },
          });
          for (const cleanup of cleanups.splice(0)) cleanup();
          vi.advanceTimersByTime(1000);
          expect(liveRegion()).toBe("");
        },
      );

      it("focus is on the select after Apply in the failure outcome", async () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        control(APPLY).focus();
        (control(APPLY) as HTMLButtonElement).click();
        vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "error" });
        await section.save({
          utubID: 3,
          patch: { invite_link_creators: "owner_only" },
        });
        expect(document.activeElement).toBe(control(SELECT));
      });

      it("a later re-pick of the previous value after an ok Apply is sent, not read as stored", async () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        (control(APPLY) as HTMLButtonElement).click();
        storeCreators("owner_only");
        vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
        await section.save({
          utubID: 3,
          patch: { invite_link_creators: "owner_only" },
        });
        submit.mockClear();
        pick("owner_and_co_owners");
        expect(submit).toHaveBeenCalledWith({
          patch: { invite_link_creators: "owner_and_co_owners" },
          debounce: true,
        });
      });

      it("an ok switch save and an ok autosave while staged leave the staging alone, and onSettled refreshes the baseline", async () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
        storeCreators("no_one");
        await section.save({
          utubID: 3,
          patch: { co_owners_can_enable_preview: true },
        });
        expect(document.querySelector(APPLY)).not.toBeNull();
        expect((control(SELECT) as HTMLSelectElement).value).toBe("owner_only");
        expect(
          control("#membersPermissionsInviteCreatorsDesc").textContent,
        ).toContain("No one sees the invite button.");
        await section.save({
          utubID: 3,
          patch: { invite_link_creators: "no_one" },
        });
        expect(document.querySelector(APPLY)).not.toBeNull();
        expect((control(SELECT) as HTMLSelectElement).value).toBe("owner_only");
      });

      it("an autosave of the select failing while staged leaves the staging alone", async () => {
        renderWith(creatorsCtx("no_one"));
        pick("owner_and_co_owners");
        pick("owner_only");
        vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "error" });
        await section.save({
          utubID: 3,
          patch: { invite_link_creators: "owner_and_co_owners" },
        });
        expect(document.querySelector(APPLY)).not.toBeNull();
      });

      it("a switch save resolving before Apply is sent does not clear the in-flight state", async () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        const apply = control(APPLY) as HTMLButtonElement;
        apply.click();
        vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
        await section.save({
          utubID: 3,
          patch: { co_owners_can_enable_preview: true },
        });
        expect(apply.disabled).toBe(true);
        expect(control(SELECT).getAttribute("aria-disabled")).toBe("true");
      });

      it("a coalesced patch carrying both keys while Apply is in flight tears down", async () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        (control(APPLY) as HTMLButtonElement).click();
        vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "error" });
        await section.save({
          utubID: 3,
          patch: {
            invite_link_creators: "owner_only",
            co_owners_can_enable_preview: true,
          },
        });
        expect(document.querySelector(APPLY)).toBeNull();
        expect((control(SELECT) as HTMLSelectElement).value).toBe(
          "owner_and_co_owners",
        );
      });

      it("onSettled is unregistered by the cleanup: a late save changes nothing", async () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        const description = control("#membersPermissionsInviteCreatorsDesc");
        const before = description.textContent;
        for (const cleanup of cleanups.splice(0)) cleanup();
        storeCreators("no_one");
        vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
        await section.save({
          utubID: 3,
          patch: { invite_link_creators: "no_one" },
        });
        expect(description.textContent).toBe(before);
        expect((control(SELECT) as HTMLSelectElement).value).toBe(
          "owner_and_co_owners",
        );
      });
    });

    describe("while Apply is in flight", () => {
      function applyInFlight(): void {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        control(APPLY).focus();
        (control(APPLY) as HTMLButtonElement).click();
      }

      it("a touch tap outside discards nothing", () => {
        applyInFlight();
        const down = new MouseEvent("pointerdown", {
          bubbles: true,
          clientX: 1,
          clientY: 1,
        });
        Object.defineProperty(down, "pointerType", { value: "touch" });
        document.body.dispatchEvent(down);
        const up = new MouseEvent("pointerup", {
          bubbles: true,
          clientX: 1,
          clientY: 1,
        });
        Object.defineProperty(up, "pointerType", { value: "touch" });
        document.body.dispatchEvent(up);
        expect(document.querySelector(WARNING)).not.toBeNull();
        expect((control(SELECT) as HTMLSelectElement).value).toBe("owner_only");
      });

      it("a close (cleanup) announces nothing", () => {
        applyInFlight();
        for (const cleanup of cleanups.splice(0)) cleanup();
        vi.advanceTimersByTime(1000);
        expect(liveRegion()).toBe("");
      });
    });

    describe("cleanup announce joins a pending shell message", () => {
      it("reads Save failed. Change not applied. when the shell message is pending", () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        vi.advanceTimersByTime(1000);
        announceSettingsStatus({ message: "Save failed" });
        for (const cleanup of cleanups.splice(0)) cleanup();
        vi.advanceTimersByTime(10);
        expect(liveRegion()).toBe("Save failed. Change not applied.");
      });

      it("reads Change not applied. alone with no shell message pending", () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        vi.advanceTimersByTime(1000);
        for (const cleanup of cleanups.splice(0)) cleanup();
        vi.advanceTimersByTime(10);
        expect(liveRegion()).toBe("Change not applied.");
      });

      it("a focusout from the torn-down render's select does not overwrite the joined message", () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        vi.advanceTimersByTime(1000);
        const oldSelect = control(SELECT) as HTMLSelectElement;
        oldSelect.focus();
        announceSettingsStatus({ message: "Save failed" });
        for (const cleanup of cleanups.splice(0)) cleanup();
        // The shell then swaps in a new select, focuses it and removes the old one,
        // whose focusout schedules the old render's settle check after cleanup.
        const newSelect = document.createElement("select");
        host.append(newSelect);
        newSelect.focus();
        oldSelect.remove();
        oldSelect.dispatchEvent(new FocusEvent("focusout", { bubbles: true }));
        vi.advanceTimersByTime(10);
        expect(liveRegion()).toBe("Save failed. Change not applied.");
        vi.advanceTimersByTime(1000);
        expect(liveRegion()).toBe("Save failed. Change not applied.");
      });

      it("does not announce when the section element is detached", () => {
        renderWith(creatorsCtx("owner_and_co_owners"));
        pick("owner_only");
        vi.advanceTimersByTime(1000);
        host.remove();
        for (const cleanup of cleanups.splice(0)) cleanup();
        vi.advanceTimersByTime(10);
        expect(liveRegion()).not.toContain("Change not applied.");
      });
    });
  });
});
