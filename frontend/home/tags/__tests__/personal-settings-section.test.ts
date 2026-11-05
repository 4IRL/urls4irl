import { APP_CONFIG } from "../../../lib/config.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import type { UserPreferences } from "../../../store/app-store.js";
import {
  EMPTY_MEMBER_SETTINGS,
  type ResolvedMemberSettings,
} from "../../../types/settings.js";
import {
  patchMemberSettings,
  patchTagDisplayPreferences,
} from "../../panel-settings/client.js";
import type {
  EchoedTagDisplayPreferences,
  MemberSaveResult,
  TagDisplayPreferencesSaveResult,
} from "../../panel-settings/client.js";
import {
  _resetRegistryForTests,
  getSections,
} from "../../panel-settings/registry.js";
import type {
  PanelSection,
  SaveResult,
  SectionContext,
} from "../../panel-settings/types.js";
import { updateUTubOnFindingStaleData } from "../../utubs/stale-data.js";
import { effectiveTagDisplaySettings } from "../display-settings.js";
import { registerTagsPersonalSettingsSection } from "../personal-settings-section.js";
import {
  buildTagFilterInDeck,
  initTagMatchMode,
  toggleTagFilterSelected,
} from "../tags.js";
import { isPanelSettingsOpen } from "../../panel-settings/state.js";
import { announceSettingsStatus } from "../../panel-settings/announce.js";
import { updateURLsAndTagSubheaderWhenTagSelected } from "../../urls/cards/filtering.js";

vi.mock("../../panel-settings/client.js", () => ({
  patchMemberSettings: vi.fn(),
  patchTagDisplayPreferences: vi.fn(),
}));
vi.mock("../../utubs/stale-data.js", () => ({
  updateUTubOnFindingStaleData: vi.fn(async () => {}),
}));
vi.mock("../delete.js", () => ({ deleteUTubTagShowModal: vi.fn() }));
vi.mock("../unselect-all.js", () => ({
  enableUnselectAllButtonAfterTagFilterApplied: vi.fn(),
  disableUnselectAllButtonAfterTagFilterRemoved: vi.fn(),
}));
vi.mock("../../urls/cards/filtering.js", () => ({
  updateURLsAndTagSubheaderWhenTagSelected: vi.fn(),
}));
vi.mock("../../panel-settings/announce.js", () => ({
  announceSettingsStatus: vi.fn(),
}));
vi.mock("../../panel-settings/state.js", () => ({
  isPanelSettingsOpen: vi.fn(() => false),
}));

const $ = window.jQuery;
const UTUB_ID = 7;
const OTHER_UTUB_ID = 8;
const ANNOUNCEMENT = "#URLTagFilterAnnouncement";

const DEFAULT_ECHO: EchoedTagDisplayPreferences = {
  tagSort: "most_in_view",
  tagMatchMode: "all",
  tagCountStyle: "in_view_total",
  showTagsOnCollapsed: false,
  collapsedTagsStyle: "one_line",
  tagDropOpensUrl: true,
};

function echo(
  overrides: Partial<EchoedTagDisplayPreferences> = {},
): EchoedTagDisplayPreferences {
  return { ...DEFAULT_ECHO, ...overrides };
}

function member(
  tags: Partial<ResolvedMemberSettings["tags"]> = {},
): ResolvedMemberSettings {
  return {
    ...EMPTY_MEMBER_SETTINGS,
    tags: { ...EMPTY_MEMBER_SETTINGS.tags, ...tags },
  };
}

function defaultsOk(
  overrides: Partial<EchoedTagDisplayPreferences> = {},
): TagDisplayPreferencesSaveResult {
  return { outcome: "ok", preferences: echo(overrides) };
}

function overrideOk(
  tags: Partial<ResolvedMemberSettings["tags"]> = {},
): MemberSaveResult {
  return {
    outcome: "ok",
    memberSettings: member(tags) as unknown as Extract<
      MemberSaveResult,
      { outcome: "ok" }
    >["memberSettings"],
  };
}

function byId<Found extends HTMLElement>(id: string): Found {
  return document.getElementById(id) as Found;
}

function choose({ id, value }: { id: string; value: string }): void {
  const select = byId<HTMLSelectElement>(id);
  select.value = value;
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

function preferencesWith(overrides: Partial<UserPreferences>): UserPreferences {
  return { ...getState().preferences, ...overrides };
}

describe("registerTagsPersonalSettingsSection", () => {
  let host: HTMLElement;
  let section: PanelSection;
  let unregister: () => void;
  let submit: ReturnType<typeof vi.fn>;

  function renderSection(): void {
    host.innerHTML = "";
    const ctx: SectionContext = {
      settings: null,
      canWrite: true,
      submit: submit as SectionContext["submit"],
    };
    section.render({ container: host, ctx });
  }

  function setup(slice: ResolvedMemberSettings | null = member()): void {
    setState({ activeUTubID: UTUB_ID, memberSettings: slice });
    renderSection();
  }

  function lastPatch(): unknown {
    return submit.mock.lastCall?.[0].patch;
  }

  beforeEach(() => {
    _resetRegistryForTests();
    resetStore();
    vi.clearAllMocks();
    vi.mocked(isPanelSettingsOpen).mockReturnValue(false);
    document.body.innerHTML = "";
    host = document.createElement("div");
    document.body.append(host);
    submit = vi.fn();
    vi.mocked(patchMemberSettings).mockReset();
    vi.mocked(patchTagDisplayPreferences).mockReset();
    vi.mocked(updateUTubOnFindingStaleData).mockReset();
    vi.mocked(updateUTubOnFindingStaleData).mockResolvedValue(undefined);
    unregister = registerTagsPersonalSettingsSection();
    section = getSections("tags")[0];
  });

  afterEach(() => {
    unregister();
    resetStore();
    document.body.innerHTML = "";
  });

  describe("registration and render", () => {
    it("registers a per-utub user section on the tags panel", () => {
      expect(section).toMatchObject({
        id: "tags-personal",
        panel: "tags",
        scope: "user",
        userKind: "per-utub",
        title: "Your tags",
      });
      expect(section.rerenderOn).toHaveLength(7);
    });

    it("renders every row with the defaults and no override", () => {
      setup();
      expect(host.querySelectorAll(".tagsSettingsRow")).toHaveLength(6);
      expect(
        byId<HTMLSelectElement>("tagsPersonalSortDefaultControl").value,
      ).toBe("most_in_view");
      expect(
        byId<HTMLSelectElement>("tagsPersonalMatchDefaultControl").value,
      ).toBe("all");
      expect(
        byId("tagsPersonalDropDefaultControl").getAttribute("aria-checked"),
      ).toBe("true");
      expect(
        byId("tagsPersonalCollapsedDefaultControl").getAttribute(
          "aria-checked",
        ),
      ).toBe("false");
      expect(byId("tagsPersonalSortOverrideWrap").hidden).toBe(true);
    });

    it("renders overrides expanded with the visible 'This UTub only' label", () => {
      setState({
        preferences: preferencesWith({ tagSort: "newest" }),
      });
      setup(member({ tag_sort: "name_az", tag_drop_opens_url: false }));
      expect(
        byId<HTMLSelectElement>("tagsPersonalSortDefaultControl").value,
      ).toBe("newest");
      expect(
        byId<HTMLSelectElement>("tagsPersonalSortOverrideControl").value,
      ).toBe("name_az");
      expect(byId("tagsPersonalSortOverrideWrap").hidden).toBe(false);
      expect(byId("tagsPersonalSortScopeOverride").textContent).toBe(
        "This UTub only",
      );
      expect(byId("tagsPersonalSortRevealLink").hidden).toBe(true);
      expect(
        byId("tagsPersonalSortRevealLink").getAttribute("aria-expanded"),
      ).toBe("true");
      expect(
        byId("tagsPersonalDropOverrideControl").getAttribute("aria-checked"),
      ).toBe("false");
    });

    it("renders controls enabled in a locked UTub for a non-manager", () => {
      setState({
        isCurrentUTubLocked: true,
        isCurrentUserOwner: false,
        isCoCreator: false,
      });
      setup();
      expect(
        byId("tagsPersonalSortDefaultControl").hasAttribute("aria-disabled"),
      ).toBe(false);
      expect(host.querySelector(".panelSettingsReadOnlyNote")).toBeNull();
    });

    it("renders inert until the member slice arrives", () => {
      setup(null);
      expect(
        byId("tagsPersonalSortDefaultControl").getAttribute("aria-disabled"),
      ).toBe("true");
      choose({ id: "tagsPersonalSortDefaultControl", value: "newest" });
      expect(submit).not.toHaveBeenCalled();
    });

    it("describes the Sort control with its helper line", () => {
      setup();
      const desc = byId("tagsPersonalSortDesc");
      expect(desc.textContent).toBe(
        APP_CONFIG.strings.TAGS_PERSONAL_SETTINGS_SORT_DESC,
      );
      expect(
        byId("tagsPersonalSortDefaultControl").getAttribute("aria-describedby"),
      ).toBe("tagsPersonalSortDesc");
      expect(
        byId("tagsPersonalSortOverrideControl").getAttribute(
          "aria-describedby",
        ),
      ).toBe("tagsPersonalSortDesc");
    });

    it("selectors detect a default and an override change", () => {
      setup();
      const read = () =>
        section.rerenderOn!.map((selector) => selector(getState()));
      const before = read();
      setState({ preferences: preferencesWith({ tagCountStyle: "hidden" }) });
      expect(read()).not.toEqual(before);
      const mid = read();
      setState({ memberSettings: member({ tag_sort: "oldest" }) });
      expect(read()).not.toEqual(mid);
    });
  });

  describe("patch keys", () => {
    it("sends default.<camelCase> for the default control and bumps the version at edit time", () => {
      setup();
      choose({ id: "tagsPersonalSortDefaultControl", value: "name_az" });
      expect(lastPatch()).toEqual({ "default.tagSort": "name_az" });
      expect(getState().tagDisplayVersion).toBe(1);
    });

    it("sends override.<camelCase> on the first change of the override control", () => {
      setup();
      byId("tagsPersonalSortRevealLink").click();
      expect(submit).not.toHaveBeenCalled();
      choose({ id: "tagsPersonalSortOverrideControl", value: "oldest" });
      expect(lastPatch()).toEqual({ "override.tagSort": "oldest" });
      expect(getState().tagDisplayVersion).toBe(0);
    });

    it("sends a switch default as a boolean", () => {
      setup();
      byId("tagsPersonalDropDefaultControl").click();
      expect(lastPatch()).toEqual({ "default.tagDropOpensUrl": false });
    });

    it("sends a switch override as a boolean", () => {
      setup();
      byId("tagsPersonalDropRevealLink").click();
      byId("tagsPersonalDropOverrideControl").click();
      expect(lastPatch()).toEqual({ "override.tagDropOpensUrl": false });
    });

    it("'Use my default here' sends null when an override is stored", () => {
      setup(member({ tag_sort: "name_az" }));
      byId("tagsPersonalSortUseDefault").click();
      expect(lastPatch()).toEqual({ "override.tagSort": null });
    });

    it("'Use my default here' sends nothing for a reveal that was never changed", () => {
      setup();
      byId("tagsPersonalSortRevealLink").click();
      byId("tagsPersonalSortUseDefault").click();
      expect(submit).not.toHaveBeenCalled();
    });
  });

  describe("disclosure, focus and rerender", () => {
    it("reveals without sending, moves focus into the override and toggles aria-expanded", () => {
      setup();
      const link = byId("tagsPersonalSortRevealLink");
      expect(link.getAttribute("aria-controls")).toBe(
        "tagsPersonalSortOverrideWrap",
      );
      expect(link.getAttribute("aria-describedby")).toBe(
        "tagsPersonalSortLabel",
      );
      expect(link.getAttribute("aria-expanded")).toBe("false");
      expect(link.isConnected).toBe(true);

      link.click();

      expect(submit).not.toHaveBeenCalled();
      expect(link.hidden).toBe(true);
      expect(link.getAttribute("aria-expanded")).toBe("true");
      expect(byId("tagsPersonalSortOverrideWrap").hidden).toBe(false);
      expect(document.activeElement).toBe(
        byId("tagsPersonalSortOverrideControl"),
      );
    });

    it("keeps the override wrapper in the DOM while collapsed so aria-controls resolves", () => {
      setup();
      const wrap = byId("tagsPersonalSortOverrideWrap");
      expect(wrap.isConnected).toBe(true);
      expect(wrap.hidden).toBe(true);
      expect(
        document.getElementById(
          byId("tagsPersonalSortRevealLink").getAttribute("aria-controls")!,
        ),
      ).toBe(wrap);
    });

    it("'Use my default here' collapses, re-shows the link and focuses it", () => {
      setup(member({ tag_sort: "name_az" }));
      const useDefault = byId("tagsPersonalSortUseDefault");
      expect(useDefault.getAttribute("aria-describedby")).toBe(
        "tagsPersonalSortLabel",
      );
      useDefault.click();

      const link = byId("tagsPersonalSortRevealLink");
      expect(byId("tagsPersonalSortOverrideWrap").hidden).toBe(true);
      expect(link.hidden).toBe(false);
      expect(link.getAttribute("aria-expanded")).toBe("false");
      expect(document.activeElement).toBe(link);
    });

    it("collapses an unchanged reveal on the next render", () => {
      setup();
      byId("tagsPersonalSortRevealLink").click();
      expect(byId("tagsPersonalSortOverrideWrap").hidden).toBe(false);
      renderSection();
      expect(byId("tagsPersonalSortOverrideWrap").hidden).toBe(true);
    });

    it("does not touch a revealed row on a store change by itself; a later render reflects the store", () => {
      setup();
      byId("tagsPersonalSortRevealLink").click();
      // Nothing in the section re-renders on its own (the shell owns that), so a
      // store change leaves the revealed row and its focus alone.
      setState({ preferences: preferencesWith({ tagSort: "newest" }) });
      expect(byId("tagsPersonalSortOverrideWrap").hidden).toBe(false);
      expect(document.activeElement).toBe(
        byId("tagsPersonalSortOverrideControl"),
      );
      // Once the shell renders after focus leaves, the row reflects the store.
      (document.activeElement as HTMLElement).blur();
      renderSection();
      expect(
        byId<HTMLSelectElement>("tagsPersonalSortDefaultControl").value,
      ).toBe("newest");
    });

    it("mirrors a default change into a revealed override that is not stored", () => {
      setup();
      byId("tagsPersonalSortRevealLink").click();
      choose({ id: "tagsPersonalSortDefaultControl", value: "newest" });
      expect(
        byId<HTMLSelectElement>("tagsPersonalSortOverrideControl").value,
      ).toBe("newest");
      byId("tagsPersonalDropRevealLink").click();
      byId("tagsPersonalDropDefaultControl").click();
      expect(
        byId("tagsPersonalDropOverrideControl").getAttribute("aria-checked"),
      ).toBe("false");
    });

    it("leaves a stored override alone when the default changes", () => {
      setup(member({ tag_sort: "name_az" }));
      choose({ id: "tagsPersonalSortDefaultControl", value: "newest" });
      expect(
        byId<HTMLSelectElement>("tagsPersonalSortOverrideControl").value,
      ).toBe("name_az");
    });

    it("renders the reveal link and 'Use my default here' aria-disabled while inert, and ignores clicks", () => {
      setup(null);
      const link = byId("tagsPersonalSortRevealLink");
      const useDefault = byId("tagsPersonalSortUseDefault");
      expect(link.getAttribute("aria-disabled")).toBe("true");
      expect(useDefault.getAttribute("aria-disabled")).toBe("true");
      link.click();
      expect(byId("tagsPersonalSortOverrideWrap").hidden).toBe(true);
      expect(link.getAttribute("aria-expanded")).toBe("false");
      useDefault.click();
      byId("tagsPersonalDropDefaultControl").click();
      expect(submit).not.toHaveBeenCalled();
    });

    it("leaves the reveal link and 'Use my default here' enabled once the slice is there", () => {
      setup();
      expect(
        byId("tagsPersonalSortRevealLink").hasAttribute("aria-disabled"),
      ).toBe(false);
      expect(
        byId("tagsPersonalSortUseDefault").hasAttribute("aria-disabled"),
      ).toBe(false);
    });

    it("coalesces two rows' flat patches without overwriting each other", () => {
      setup();
      choose({ id: "tagsPersonalSortDefaultControl", value: "name_az" });
      choose({ id: "tagsPersonalCountDefaultControl", value: "hidden" });
      const merged = submit.mock.calls.reduce(
        (all, [args]) => ({ ...all, ...args.patch }),
        {},
      );
      expect(merged).toEqual({
        "default.tagSort": "name_az",
        "default.tagCountStyle": "hidden",
      });
    });
  });

  describe("nested collapsed-tags select", () => {
    function nested() {
      return {
        defaultSelect: byId("tagsPersonalCollapsedStyleDefaultControl"),
        overrideSelect: byId("tagsPersonalCollapsedStyleOverrideControl"),
        note: byId("tagsPersonalCollapsedStyleNote"),
      };
    }

    it("is disabled with the note while the switch resolves off, at render", () => {
      setup();
      const { defaultSelect, overrideSelect, note } = nested();
      expect(defaultSelect.getAttribute("aria-disabled")).toBe("true");
      expect(overrideSelect.getAttribute("aria-disabled")).toBe("true");
      expect(note.hidden).toBe(false);
      expect(defaultSelect.getAttribute("aria-describedby")).toBe(note.id);
    });

    it("is enabled with no note while the switch resolves on, at render", () => {
      setState({ preferences: preferencesWith({ showTagsOnCollapsed: true }) });
      setup();
      const { defaultSelect, note } = nested();
      expect(defaultSelect.hasAttribute("aria-disabled")).toBe(false);
      expect(note.hidden).toBe(true);
      expect(defaultSelect.hasAttribute("aria-describedby")).toBe(false);
    });

    it("updates immediately on the default switch with focus still inside", () => {
      setup();
      const sw = byId("tagsPersonalCollapsedDefaultControl");
      sw.focus();
      sw.click();
      const { defaultSelect, note } = nested();
      expect(document.activeElement).toBe(sw);
      expect(defaultSelect.hasAttribute("aria-disabled")).toBe(false);
      expect(note.hidden).toBe(true);
      sw.click();
      expect(defaultSelect.getAttribute("aria-disabled")).toBe("true");
      expect(note.hidden).toBe(false);
    });

    it("follows the override switch when an override is set, then the default again", () => {
      setState({ preferences: preferencesWith({ showTagsOnCollapsed: true }) });
      setup();
      byId("tagsPersonalCollapsedRevealLink").click();
      byId("tagsPersonalCollapsedOverrideControl").click();
      const { defaultSelect, note } = nested();
      expect(defaultSelect.getAttribute("aria-disabled")).toBe("true");
      expect(note.hidden).toBe(false);

      byId("tagsPersonalCollapsedUseDefault").click();
      expect(defaultSelect.hasAttribute("aria-disabled")).toBe(false);
      expect(note.hidden).toBe(true);
    });

    it("gives render and the handlers the same result", () => {
      setup();
      byId("tagsPersonalCollapsedDefaultControl").click();
      const afterHandler = nested().defaultSelect.hasAttribute("aria-disabled");
      setState({ preferences: preferencesWith({ showTagsOnCollapsed: true }) });
      renderSection();
      expect(nested().defaultSelect.hasAttribute("aria-disabled")).toBe(
        afterHandler,
      );
    });

    it("does not change the select while disabled", () => {
      setup();
      choose({ id: "tagsPersonalCollapsedStyleDefaultControl", value: "all" });
      expect(submit).not.toHaveBeenCalled();
    });
  });

  describe("save: dispatch order and failures", () => {
    beforeEach(() => {
      setup();
    });

    it("sends the default first, then the override as snake_case keys", async () => {
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagSort: "name_az" }),
      );
      vi.mocked(patchMemberSettings).mockResolvedValue(
        overrideOk({ tag_count_style: "hidden" }),
      );

      const result = await section.save({
        utubID: UTUB_ID,
        patch: {
          "override.tagCountStyle": "hidden",
          "default.tagSort": "name_az",
        },
      });

      expect(result).toEqual({ outcome: "ok" });
      expect(patchTagDisplayPreferences).toHaveBeenCalledWith({
        patch: { tagSort: "name_az" },
      });
      expect(patchMemberSettings).toHaveBeenCalledWith({
        utubID: UTUB_ID,
        panel: "tags",
        patch: { tag_count_style: "hidden" },
      });
      expect(
        vi.mocked(patchTagDisplayPreferences).mock.invocationCallOrder[0],
      ).toBeLessThan(
        vi.mocked(patchMemberSettings).mock.invocationCallOrder[0],
      );
      expect(getState().preferences.tagSort).toBe("name_az");
      expect(getState().memberSettings?.tags.tag_count_style).toBe("hidden");
      expect(getState().tagDisplayVersion).toBe(1);
      expect(getState().memberSettingsVersion).toBe(1);
    });

    it("a default failure skips the override and returns the error without a member resync", async () => {
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue({
        outcome: "failed",
        result: { outcome: "error" },
        timedOut: false,
      });

      const result = await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagSort": "newest", "override.tagSort": "oldest" },
      });

      expect(result).toEqual({ outcome: "error", resync: false });
      expect(patchMemberSettings).not.toHaveBeenCalled();
      expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
      expect(getState().preferences.tagSort).toBe("most_in_view");
    });

    it("keeps the edit-time version bump on a failed default save and adds no echo bump", async () => {
      choose({ id: "tagsPersonalSortDefaultControl", value: "newest" });
      expect(getState().tagDisplayVersion).toBe(1);
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue({
        outcome: "failed",
        result: { outcome: "error" },
        timedOut: false,
      });
      await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagSort": "newest" },
      });
      expect(getState().tagDisplayVersion).toBe(1);
      expect(getState().preferences.tagSort).toBe("most_in_view");
    });

    it("a default timeout awaits the resync of the active UTub before returning the error", async () => {
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue({
        outcome: "failed",
        result: { outcome: "error" },
        timedOut: true,
      });
      let resyncFinished = false;
      vi.mocked(updateUTubOnFindingStaleData).mockImplementation(async () => {
        await Promise.resolve();
        resyncFinished = true;
      });

      const pending = section.save({
        utubID: UTUB_ID,
        patch: { "default.tagSort": "newest" },
      });
      const result = await pending;

      expect(updateUTubOnFindingStaleData).toHaveBeenCalledWith({
        utubID: UTUB_ID,
      });
      expect(resyncFinished).toBe(true);
      expect(result).toEqual({ outcome: "error", resync: false });
      expect(patchMemberSettings).not.toHaveBeenCalled();
    });

    it("a timeout with no active UTub skips the resync", async () => {
      setState({ activeUTubID: null });
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue({
        outcome: "failed",
        result: { outcome: "error" },
        timedOut: true,
      });
      const result = await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagSort": "newest" },
      });
      expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
      expect(result.outcome).toBe("error");
    });

    it("an override error resyncs through the queue (no resync:false)", async () => {
      vi.mocked(patchMemberSettings).mockResolvedValue({ outcome: "error" });
      const result = await section.save({
        utubID: UTUB_ID,
        patch: { "override.tagSort": "oldest" },
      });
      expect(result).toEqual({ outcome: "error" });
      expect(patchTagDisplayPreferences).not.toHaveBeenCalled();
    });

    it("default OK then override stale: no memberSettings write, default echo stands", async () => {
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagSort: "newest" }),
      );
      vi.mocked(patchMemberSettings).mockResolvedValue({
        outcome: "stale",
        failed: false,
      });
      const before = getState().memberSettings;

      const result = await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagSort": "newest", "override.tagSort": "oldest" },
      });

      expect(result).toEqual({ outcome: "stale", failed: false });
      expect(getState().memberSettings).toBe(before);
      expect(getState().preferences.tagSort).toBe("newest");
    });

    it("default OK then the active UTub changes before the override write: stale, no write", async () => {
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagSort: "newest" }),
      );
      vi.mocked(patchMemberSettings).mockImplementation(async () => {
        setState({ activeUTubID: OTHER_UTUB_ID });
        return overrideOk({ tag_sort: "oldest" });
      });
      const result = await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagSort": "newest", "override.tagSort": "oldest" },
      });
      expect(result).toEqual({ outcome: "stale", failed: false });
      expect(getState().memberSettings?.tags.tag_sort ?? null).toBeNull();
      expect(getState().preferences.tagSort).toBe("newest");
    });

    it("default OK and override fails: the default keeps the new value, the override is not stored", async () => {
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagSort: "newest" }),
      );
      vi.mocked(patchMemberSettings).mockResolvedValue({ outcome: "error" });

      const result = await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagSort": "newest", "override.tagSort": "oldest" },
      });

      expect(result).toEqual({ outcome: "error" });
      renderSection();
      expect(
        byId<HTMLSelectElement>("tagsPersonalSortDefaultControl").value,
      ).toBe("newest");
      expect(byId("tagsPersonalSortOverrideWrap").hidden).toBe(true);
    });

    it("discards an older default echo that arrives after a newer one, and bumps the version on the accepted echo", async () => {
      const resolvers: Array<(value: TagDisplayPreferencesSaveResult) => void> =
        [];
      vi.mocked(patchTagDisplayPreferences).mockImplementation(
        () =>
          new Promise<TagDisplayPreferencesSaveResult>((resolve) => {
            resolvers.push(resolve);
          }),
      );

      const first = section.save({
        utubID: UTUB_ID,
        patch: { "default.tagSort": "newest" },
      });
      const second = section.save({
        utubID: OTHER_UTUB_ID,
        patch: { "default.tagSort": "oldest" },
      });
      resolvers[1](defaultsOk({ tagSort: "oldest" }));
      await second;
      expect(getState().preferences.tagSort).toBe("oldest");
      expect(getState().tagDisplayVersion).toBe(1);

      resolvers[0](defaultsOk({ tagSort: "newest" }));
      await first;
      expect(getState().preferences.tagSort).toBe("oldest");
      expect(getState().tagDisplayVersion).toBe(1);
    });

    it("a default change is visible in a second UTub with no override", async () => {
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagSort: "newest" }),
      );
      await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagSort": "newest" },
      });
      setState({ activeUTubID: OTHER_UTUB_ID, memberSettings: member() });
      expect(effectiveTagDisplaySettings().tagSort).toBe("newest");
      setState({ memberSettings: member({ tag_sort: "oldest" }) });
      expect(effectiveTagDisplaySettings().tagSort).toBe("oldest");
    });

    it("a save with no recognised keys fails closed", async () => {
      const result = await section.save({
        utubID: UTUB_ID,
        patch: { "default.nope": 1 },
      });
      expect(result).toEqual({ outcome: "error" });
      expect(patchTagDisplayPreferences).not.toHaveBeenCalled();
    });

    it("a save without a UTub fails closed", async () => {
      const result = await section.save({
        utubID: null,
        patch: { "default.tagSort": "newest" },
      });
      expect(result).toEqual({ outcome: "error" });
    });
  });

  describe("save notice and claim scoping", () => {
    const MAX = APP_CONFIG.constants.TAGS_MAX_ON_URLS;

    function mountChips({ count }: { count: number }): void {
      const urls = Array.from(
        { length: 3 },
        () => '<div class="urlRow" filterable="true"></div>',
      ).join("");
      document.body.innerHTML =
        '<div id="listTags"></div><span id="URLTagFilterAnnouncement"></span>' +
        urls;
      document.body.append(host);
      for (let tagID = 1; tagID <= count; tagID++) {
        $("#listTags").append(buildTagFilterInDeck(1, tagID, `t${tagID}`));
      }
    }

    function selectFirst(count: number): void {
      for (let tagID = 1; tagID <= count; tagID++) {
        toggleTagFilterSelected($(`.tagFilter[data-utub-tag-id="${tagID}"]`));
      }
    }

    beforeEach(() => {
      setup();
      mountChips({ count: MAX + 2 });
      initTagMatchMode();
      vi.mocked(updateURLsAndTagSubheaderWhenTagSelected).mockReset();
    });

    it("returns the filter-result notice when the default echo flips the mode, and announces nothing itself", async () => {
      selectFirst(2);
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagMatchMode: "any" }),
      );
      const result = await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagMatchMode": "any" },
      });
      expect(result).toEqual({
        outcome: "ok",
        notice: "3 URLs shown, matching any selected tags",
      });
      expect($(ANNOUNCEMENT).text()).toBe("");
      expect(announceSettingsStatus).not.toHaveBeenCalled();
    });

    it("adds the trim sentence when the flip trims the selection", async () => {
      setState({ preferences: preferencesWith({ tagMatchMode: "any" }) });
      selectFirst(MAX + 1);
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagMatchMode: "all" }),
      );
      const result = await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagMatchMode": "all" },
      });
      expect(result).toEqual({
        outcome: "ok",
        notice: `3 URLs shown, matching all selected tags. ${APP_CONFIG.strings.TAG_FILTER_TRIM_ANNOUNCEMENT}`,
      });
    });

    it("returns no notice when the resolved mode does not change", async () => {
      selectFirst(2);
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagSort: "newest" }),
      );
      const result = await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagSort": "newest" },
      });
      expect(result).toEqual({ outcome: "ok" });
    });

    it("returns no notice when the override returns the mode to where the save started", async () => {
      selectFirst(2);
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagMatchMode: "any" }),
      );
      vi.mocked(patchMemberSettings).mockResolvedValue(
        overrideOk({ tag_match_mode: "all" }),
      );
      const flipped = await section.save({
        utubID: UTUB_ID,
        patch: {
          "default.tagMatchMode": "any",
          "override.tagMatchMode": "all",
        },
      });
      // Started "all", the default went "any" and the override returned to "all".
      expect(flipped).toEqual({ outcome: "ok" });
    });

    it("keeps the trim sentence when the final mode is back at the start mode", async () => {
      setState({ preferences: preferencesWith({ tagMatchMode: "any" }) });
      selectFirst(MAX + 1);
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagMatchMode: "all" }),
      );
      vi.mocked(patchMemberSettings).mockResolvedValue(
        overrideOk({ tag_match_mode: "any" }),
      );
      const result = await section.save({
        utubID: UTUB_ID,
        patch: {
          "default.tagMatchMode": "all",
          "override.tagMatchMode": "any",
        },
      });
      expect(result).toEqual({
        outcome: "ok",
        notice: APP_CONFIG.strings.TAG_FILTER_TRIM_ANNOUNCEMENT,
      });
    });

    it("measures the start mode at the first claimed write, not before the default send", async () => {
      selectFirst(2);
      // Started "all"; another session flips to "any" while the send is pending,
      // then the (stale) echo carries "all" back: a visible change to announce.
      vi.mocked(patchTagDisplayPreferences).mockImplementation(async () => {
        setState({ preferences: preferencesWith({ tagMatchMode: "any" }) });
        return defaultsOk({ tagSort: "newest", tagMatchMode: "all" });
      });
      const result = await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagSort": "newest" },
      });
      expect(result).toEqual({
        outcome: "ok",
        notice: "3 URLs shown, matching all selected tags",
      });
    });

    it("measures the override-only start mode after the pending call", async () => {
      selectFirst(2);
      vi.mocked(patchMemberSettings).mockImplementation(async () => {
        setState({ preferences: preferencesWith({ tagMatchMode: "any" }) });
        return overrideOk({ tag_match_mode: "all" });
      });
      const result = await section.save({
        utubID: UTUB_ID,
        patch: { "override.tagMatchMode": "all" },
      });
      expect(result).toEqual({
        outcome: "ok",
        notice: "3 URLs shown, matching all selected tags",
      });
    });

    it("takes the later write's sentence when both writes flip away from the start", async () => {
      selectFirst(2);
      setState({ preferences: preferencesWith({ tagMatchMode: "all" }) });
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagMatchMode: "any" }),
      );
      vi.mocked(patchMemberSettings).mockResolvedValue(
        overrideOk({ tag_match_mode: "any" }),
      );
      const result = await section.save({
        utubID: UTUB_ID,
        patch: {
          "default.tagMatchMode": "any",
          "override.tagMatchMode": "any",
        },
      });
      expect(result).toEqual({
        outcome: "ok",
        notice: "3 URLs shown, matching any selected tags",
      });
    });

    it("clears the claim when a write throws, so the next change announces itself", async () => {
      selectFirst(2);
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagMatchMode: "any" }),
      );
      // Reading the payload throws inside the claimed override write.
      const poisoned = {
        get urls(): never {
          throw new Error("payload boom");
        },
      };
      vi.mocked(patchMemberSettings).mockResolvedValue({
        outcome: "ok",
        memberSettings: poisoned as never,
      });
      await expect(
        section.save({
          utubID: UTUB_ID,
          patch: {
            "default.tagMatchMode": "any",
            "override.tagSort": "oldest",
          },
        }),
      ).rejects.toThrow("payload boom");

      setState({ preferences: preferencesWith({ tagMatchMode: "all" }) });
      expect($(ANNOUNCEMENT).text()).toBe(
        "3 URLs shown, matching all selected tags",
      );
    });

    it("does not swallow a mode flip from another session while the override call is pending", async () => {
      selectFirst(2);
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagSort: "newest" }),
      );
      vi.mocked(patchMemberSettings).mockImplementation(async () => {
        setState({ preferences: preferencesWith({ tagMatchMode: "any" }) });
        return overrideOk({ tag_sort: "oldest" });
      });
      const result = await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagSort": "newest", "override.tagSort": "oldest" },
      });
      expect($(ANNOUNCEMENT).text()).toBe(
        "3 URLs shown, matching any selected tags",
      );
      // The mode flip was announced by the handler, so the save claims nothing.
      expect(result).toEqual({ outcome: "ok" });
    });

    it("a refresh-caused mode change between saves leaves no record for the next save", async () => {
      selectFirst(2);
      setState({ preferences: preferencesWith({ tagMatchMode: "any" }) });
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagMatchMode: "any", tagSort: "newest" }),
      );
      const result = await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagSort": "newest" },
      });
      expect(result).toEqual({ outcome: "ok" });
    });

    it("returns the notice on an error when the default echo flipped the mode and the override failed", async () => {
      selectFirst(2);
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagMatchMode: "any" }),
      );
      vi.mocked(patchMemberSettings).mockResolvedValue({ outcome: "error" });
      const result = await section.save({
        utubID: UTUB_ID,
        patch: {
          "default.tagMatchMode": "any",
          "override.tagSort": "oldest",
        },
      });
      expect(result).toEqual({
        outcome: "error",
        notice: "3 URLs shown, matching any selected tags",
      });
    });

    it("returns the notice on a stale result when the default echo flipped the mode", async () => {
      selectFirst(2);
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagMatchMode: "any" }),
      );
      vi.mocked(patchMemberSettings).mockResolvedValue({
        outcome: "stale",
        failed: true,
      });
      const result: SaveResult = await section.save({
        utubID: UTUB_ID,
        patch: {
          "default.tagMatchMode": "any",
          "override.tagSort": "oldest",
        },
      });
      expect(result).toEqual({
        outcome: "stale",
        failed: true,
        notice: "3 URLs shown, matching any selected tags",
      });
    });

    it("returns no notice when the default send itself fails", async () => {
      selectFirst(2);
      vi.mocked(patchTagDisplayPreferences).mockResolvedValue({
        outcome: "failed",
        result: { outcome: "error" },
        timedOut: false,
      });
      const result = await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagMatchMode": "any" },
      });
      expect(result).not.toHaveProperty("notice");
    });

    it("a timeout resync adds no notice and leaves the claim clear for the next save", async () => {
      selectFirst(2);
      vi.mocked(patchTagDisplayPreferences).mockResolvedValueOnce({
        outcome: "failed",
        result: { outcome: "error" },
        timedOut: true,
      });
      // The resync lands a mode change outside any claim: the handler announces it.
      vi.mocked(updateUTubOnFindingStaleData).mockImplementation(async () => {
        setState({ preferences: preferencesWith({ tagMatchMode: "any" }) });
      });
      const failed = await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagMatchMode": "any" },
      });
      expect(failed).not.toHaveProperty("notice");

      vi.mocked(patchTagDisplayPreferences).mockResolvedValue(
        defaultsOk({ tagMatchMode: "any", tagSort: "newest" }),
      );
      const next = await section.save({
        utubID: UTUB_ID,
        patch: { "default.tagSort": "newest" },
      });
      expect(next).toEqual({ outcome: "ok" });
    });
  });
});
