import { patchUtubSettings } from "../../panel-settings/client.js";
import {
  _resetRegistryForTests,
  getSections,
} from "../../panel-settings/registry.js";
import type {
  PanelSection,
  SectionContext,
} from "../../panel-settings/types.js";
import { EMPTY_UTUB_SETTINGS } from "../../../types/settings.js";
import { registerMembersPermissionsSettingsSection } from "../permissions-settings-section.js";

vi.mock("../../panel-settings/client.js", () => ({
  patchUtubSettings: vi.fn(),
}));

const REMOVE = "#membersPermissionsCoOwnersRemoveSwitch";
const ADD = "#membersPermissionsMembersAddSwitch";
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

  function renderWith(ctx: SectionContext): void {
    host.innerHTML = "";
    section.render({ container: host, ctx });
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

  afterEach(() => unregister());

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
    for (const selector of [REMOVE, ADD]) {
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
            co_owners_can_remove: true,
            members_can_add: false,
            hide_member_list: false,
          },
        },
      }),
    );
    expect(control(REMOVE).getAttribute("aria-checked")).toBe("true");
    expect(control(ADD).getAttribute("aria-checked")).toBe("false");
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
    for (const selector of [REMOVE, ADD]) {
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
  });
});
