import { patchUtubSettings } from "../../panel-settings/client.js";
import {
  _resetRegistryForTests,
  getSections,
} from "../../panel-settings/registry.js";
import type {
  PanelSection,
  SectionContext,
} from "../../panel-settings/types.js";
import {
  EMPTY_UTUB_SETTINGS,
  type ResolvedUtubSettings,
} from "../../../types/settings.js";
import { registerTagsPermissionsSettingsSection } from "../permissions-settings-section.js";

vi.mock("../../panel-settings/client.js", () => ({
  patchUtubSettings: vi.fn(),
}));

const TAG = "#tagsPermissionsMembersCanTagSwitch";
const DELETE = "#tagsPermissionsMembersCanDeleteSwitch";
const HINT = "#tagsPermissionsMembersCanDeleteHint";
const NOTE_ID = "panelSettingsNote-tags-permissions";

function settingsWith({
  tag,
  del,
}: {
  tag: boolean;
  del: boolean;
}): ResolvedUtubSettings {
  return {
    ...EMPTY_UTUB_SETTINGS,
    tags: { members_can_tag: tag, members_can_delete_tags: del },
  };
}

describe("Tag permissions settings section", () => {
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
    unregister = registerTagsPermissionsSettingsSection();
    section = getSections("tags")[0];
  });

  afterEach(() => unregister());

  it("registers as a manager-write, all-visible utub section on the tags panel", () => {
    expect(section.id).toBe("tags-permissions");
    expect(section.panel).toBe("tags");
    expect(section.scope).toBe("utub");
    expect(section.writeAccess).toBeUndefined();
    expect(section.visibleTo).toBeUndefined();
    expect(section.title).toBe("Tag permissions");
  });

  describe("render", () => {
    it("defaults both switches on and enabled for a manager", () => {
      renderWith(ctxFor());
      for (const selector of [TAG, DELETE]) {
        expect(control(selector).getAttribute("aria-checked")).toBe("true");
        expect(control(selector).hasAttribute("aria-disabled")).toBe(false);
      }
      expect(control(HINT).hidden).toBe(true);
    });

    it("labels the controls and links their descriptions", () => {
      renderWith(ctxFor());
      expect(host.textContent).toContain("Members can tag");
      expect(host.textContent).toContain("Members can delete tags");
      expect(control(TAG).getAttribute("aria-describedby")).toBe(
        "tagsPermissionsMembersCanTagDesc",
      );
      expect(control(DELETE).getAttribute("aria-describedby")).toBe(
        "tagsPermissionsMembersCanDeleteDesc",
      );
    });

    it("reflects stored values", () => {
      renderWith(ctxFor({ settings: settingsWith({ tag: true, del: false }) }));
      expect(control(TAG).getAttribute("aria-checked")).toBe("true");
      expect(control(DELETE).getAttribute("aria-checked")).toBe("false");
      expect(control(DELETE).hasAttribute("aria-disabled")).toBe(false);
    });

    it("shows Delete off, disabled and explained while Tagging is off", () => {
      renderWith(ctxFor({ settings: settingsWith({ tag: false, del: true }) }));
      expect(control(TAG).getAttribute("aria-checked")).toBe("false");
      expect(control(DELETE).getAttribute("aria-checked")).toBe("false");
      expect(control(DELETE).getAttribute("aria-disabled")).toBe("true");
      expect(control(HINT).hidden).toBe(false);
      expect(control(HINT).textContent).toBe(
        'Turn on "Members can tag" first.',
      );
      expect(control(DELETE).getAttribute("aria-describedby")).toContain(
        "tagsPermissionsMembersCanDeleteHint",
      );
    });

    it("keeps the disabled Delete switch focusable", () => {
      renderWith(ctxFor({ settings: settingsWith({ tag: false, del: true }) }));
      const deleteSwitch = control(DELETE);
      deleteSwitch.focus();
      expect(document.activeElement).toBe(deleteSwitch);
      expect(deleteSwitch.tagName).toBe("BUTTON");
    });

    it("is read-only, described by the note and inert when canWrite is false", () => {
      renderWith(ctxFor({ canWrite: false }));
      for (const selector of [TAG, DELETE]) {
        const element = control(selector);
        expect(element.getAttribute("aria-disabled")).toBe("true");
        expect(element.getAttribute("aria-describedby")).toContain(NOTE_ID);
        element.click();
        expect(element.getAttribute("aria-checked")).toBe("true");
      }
      expect(submit).not.toHaveBeenCalled();
    });

    it("fails closed when canWrite is not an explicit true", () => {
      renderWith(ctxFor({ canWrite: undefined as unknown as boolean }));
      expect(control(TAG).getAttribute("aria-disabled")).toBe("true");
      control(TAG).click();
      expect(submit).not.toHaveBeenCalled();
    });

    it("shows no hint to a read-only viewer when Tagging is off", () => {
      renderWith(
        ctxFor({
          canWrite: false,
          settings: settingsWith({ tag: false, del: true }),
        }),
      );
      expect(control(HINT).hidden).toBe(true);
      expect(control(DELETE).getAttribute("aria-checked")).toBe("false");
    });
  });

  describe("toggles", () => {
    it("submits only its own key per flip", () => {
      renderWith(ctxFor());
      control(DELETE).click();
      expect(submit).toHaveBeenLastCalledWith({
        patch: { members_can_delete_tags: false },
      });
      expect(control(DELETE).getAttribute("aria-checked")).toBe("false");
      control(TAG).click();
      expect(submit).toHaveBeenLastCalledWith({
        patch: { members_can_tag: false },
      });
      expect(submit).toHaveBeenCalledTimes(2);
    });

    it("forces Delete off and disabled when Tagging is turned off", () => {
      renderWith(ctxFor());
      control(TAG).click();
      expect(control(DELETE).getAttribute("aria-checked")).toBe("false");
      expect(control(DELETE).getAttribute("aria-disabled")).toBe("true");
      expect(control(HINT).hidden).toBe(false);
      control(DELETE).click();
      expect(submit).toHaveBeenCalledTimes(1);
    });

    it("restores the stored Delete value when Tagging comes back on", () => {
      renderWith(ctxFor());
      control(TAG).click();
      control(TAG).click();
      expect(control(TAG).getAttribute("aria-checked")).toBe("true");
      expect(control(DELETE).getAttribute("aria-checked")).toBe("true");
      expect(control(DELETE).hasAttribute("aria-disabled")).toBe(false);
      expect(control(HINT).hidden).toBe(true);
      expect(submit).toHaveBeenLastCalledWith({
        patch: { members_can_tag: true },
      });
    });

    it("restores a stored-off Delete as off", () => {
      renderWith(
        ctxFor({ settings: settingsWith({ tag: false, del: false }) }),
      );
      control(TAG).click();
      expect(control(DELETE).getAttribute("aria-checked")).toBe("false");
      expect(control(DELETE).hasAttribute("aria-disabled")).toBe(false);
    });

    it("renders native buttons so Enter and Space activate them (asserted in Playwright)", () => {
      renderWith(ctxFor());
      for (const selector of [TAG, DELETE]) {
        expect(control(selector).tagName).toBe("BUTTON");
        expect(control(selector).getAttribute("type")).toBe("button");
      }
    });

    it("keeps a toggled-off Delete off after Tagging goes off and on", () => {
      renderWith(ctxFor());
      control(DELETE).click();
      control(TAG).click();
      control(TAG).click();
      expect(control(DELETE).getAttribute("aria-checked")).toBe("false");
      expect(control(DELETE).hasAttribute("aria-disabled")).toBe(false);
    });
  });

  describe("save", () => {
    it("patches the tags panel with the given keys", async () => {
      vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
      await section.save({ utubID: 3, patch: { members_can_tag: true } });
      expect(patchUtubSettings).toHaveBeenCalledWith({
        utubID: 3,
        panel: "tags",
        patch: { members_can_tag: true },
      });
    });

    it.each([
      [{ members_can_tag: true }, "Members can now tag."],
      [
        { members_can_tag: false },
        "Members can no longer tag. Deleting tags is unavailable too.",
      ],
      [{ members_can_delete_tags: true }, "Members can now delete tags."],
      [
        { members_can_delete_tags: false },
        "Members can no longer delete tags.",
      ],
    ])("announces the notice for %j", async (patch, notice) => {
      vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
      const result = await section.save({ utubID: 3, patch });
      expect(result).toEqual({ outcome: "ok", notice });
    });

    it("joins both notices for a coalesced on/on patch", async () => {
      vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
      const result = await section.save({
        utubID: 3,
        patch: { members_can_tag: true, members_can_delete_tags: false },
      });
      expect(result).toEqual({
        outcome: "ok",
        notice: "Members can now tag. Members can no longer delete tags.",
      });
    });

    it("announces only the combined notice when a coalesced patch turns Tagging off", async () => {
      vi.mocked(patchUtubSettings).mockResolvedValue({ outcome: "ok" });
      const result = await section.save({
        utubID: 3,
        patch: { members_can_tag: false, members_can_delete_tags: true },
      });
      expect(result).toEqual({
        outcome: "ok",
        notice: "Members can no longer tag. Deleting tags is unavailable too.",
      });
    });

    it.each(["forbidden", "locked", "error", "gone", "invalid"] as const)(
      "passes a %s outcome through without a notice",
      async (outcome) => {
        vi.mocked(patchUtubSettings).mockResolvedValue({ outcome });
        const result = await section.save({
          utubID: 3,
          patch: { members_can_tag: false },
        });
        expect(result).toEqual({ outcome });
      },
    );

    it("errors without a UTub and sends nothing", async () => {
      const result = await section.save({
        utubID: null,
        patch: { members_can_tag: true },
      });
      expect(result).toEqual({ outcome: "error" });
      expect(patchUtubSettings).not.toHaveBeenCalled();
    });
  });
});
