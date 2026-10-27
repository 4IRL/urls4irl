import { getState, resetStore, setState } from "../../../store/app-store.js";
import {
  EMPTY_MEMBER_SETTINGS,
  resolveMemberSettings,
  resolveUtubSettings,
  type ResolvedMemberSettings,
} from "../../../types/settings.js";
import { patchMemberSettings } from "../../panel-settings/client.js";
import {
  _resetRegistryForTests,
  getSections,
} from "../../panel-settings/registry.js";
import type {
  PanelSection,
  SectionContext,
  SectionPatch,
} from "../../panel-settings/types.js";
import { registerUrlsPersonalSettingsSection } from "../personal-settings-section.js";
import { syncDeckOrderToServer } from "../view-settings.js";

vi.mock("../../panel-settings/client.js", () => ({
  patchMemberSettings: vi.fn(),
}));
vi.mock("../view-settings.js", () => ({
  syncDeckOrderToServer: vi.fn(),
}));

const UTUB_ID = 7;

function member(
  urls: Partial<ResolvedMemberSettings["urls"]> = {},
): ResolvedMemberSettings {
  return { urls: { ...EMPTY_MEMBER_SETTINGS.urls, ...urls } };
}

function query<Found extends HTMLElement>(selector: string): Found {
  return document.querySelector<Found>(selector)!;
}

function selectEl(id: string): HTMLSelectElement {
  return query<HTMLSelectElement>(`#${id}`);
}

function choose({ id, value }: { id: string; value: string }): void {
  const select = selectEl(id);
  select.value = value;
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

const SWITCHES = {
  copy: "#urlsPersonalHideCopySwitch",
  shortLink: "#urlsPersonalHideShortLinkSwitch",
  date: "#urlsPersonalHideDateSwitch",
  swipe: "#urlsPersonalDisableSwipeSwitch",
};

function mockFinePointer({ fine }: { fine: boolean }): void {
  window.matchMedia = vi.fn((query: string) => ({
    matches: fine && query === "(any-pointer: fine)",
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia;
}

describe("registerUrlsPersonalSettingsSection", () => {
  const originalMatchMedia = window.matchMedia;
  let host: HTMLElement;
  let section: PanelSection;
  let unregister: () => void;
  let submit: ReturnType<typeof vi.fn>;

  function renderSection({
    canWrite = true,
  }: { canWrite?: boolean } = {}): void {
    host.innerHTML = "";
    const ctx: SectionContext = {
      settings: null,
      canWrite,
      submit: submit as SectionContext["submit"],
    };
    section.render({ container: host, ctx });
  }

  function setup({
    slice = member(),
    canWrite = true,
  }: {
    slice?: ResolvedMemberSettings | null;
    canWrite?: boolean;
  } = {}): void {
    setState({ activeUTubID: UTUB_ID, memberSettings: slice });
    renderSection({ canWrite });
  }

  beforeEach(() => {
    _resetRegistryForTests();
    resetStore();
    document.body.innerHTML = "";
    host = document.createElement("div");
    document.body.append(host);
    submit = vi.fn();
    vi.mocked(patchMemberSettings).mockReset();
    vi.mocked(syncDeckOrderToServer).mockReset();
    mockFinePointer({ fine: true });
    unregister = registerUrlsPersonalSettingsSection();
    section = getSections("urls")[0];
  });

  afterEach(() => {
    unregister();
    window.matchMedia = originalMatchMedia;
    resetStore();
    document.body.innerHTML = "";
  });

  it("registers a per-utub user section on the urls panel", () => {
    expect(section).toMatchObject({
      id: "urls-personal",
      panel: "urls",
      scope: "user",
      userKind: "per-utub",
      title: "Your view of this UTub",
    });
    expect(section.rerenderOn).toHaveLength(3);
  });

  it("is idempotent with its unregister", () => {
    unregister();
    unregister();
    expect(getSections("urls")).toHaveLength(0);
  });

  describe("render", () => {
    it("renders sort, layout and density selects then four switches in order", () => {
      setup();
      const order = Array.from(
        host.querySelectorAll("select, button[role='switch']"),
      ).map((control) => control.id);
      expect(order).toEqual([
        "urlsSettingsSortSelect",
        "urlsSettingsViewSelect",
        "urlsSettingsDensitySelect",
        "urlsPersonalHideCopySwitch",
        "urlsPersonalHideShortLinkSwitch",
        "urlsPersonalHideDateSwitch",
        "urlsPersonalDisableSwipeSwitch",
      ]);
    });

    it("renders a description only for select rows that have one", () => {
      setup();
      for (const id of ["urlsSettingsSortSelect", "urlsSettingsViewSelect"]) {
        const row = selectEl(id).closest(".panelSettingsRow");
        expect(row?.querySelector(".panelSettingsRowDesc")).toBeNull();
        expect(selectEl(id).hasAttribute("aria-describedby")).toBe(false);
      }
      const densitySelect = selectEl("urlsSettingsDensitySelect");
      const densityDescId = densitySelect.getAttribute("aria-describedby");
      expect(densityDescId).not.toBeNull();
      expect(host.querySelector(`#${densityDescId}`)?.className).toBe(
        "panelSettingsRowDesc",
      );
    });

    it("labels the default option with the current preference", () => {
      setup();
      const first = selectEl("urlsSettingsSortSelect").options[0];
      expect(first.value).toBe("");
      setState({
        preferences: { ...getState().preferences, defaultSort: "title_az" },
      });
      renderSection();
      expect(selectEl("urlsSettingsSortSelect").options[0].textContent).toBe(
        "Default: Title A–Z",
      );
    });

    it("selects the stored override and marks it overridden", () => {
      setup({ slice: member({ sort: "oldest", view_mode: "cards" }) });
      expect(selectEl("urlsSettingsSortSelect").value).toBe("oldest");
      expect(selectEl("urlsSettingsSortSelect").classList).toContain(
        "overridden",
      );
      expect(selectEl("urlsSettingsViewSelect").value).toBe("cards");
      expect(selectEl("urlsSettingsDensitySelect").value).toBe("");
      expect(selectEl("urlsSettingsDensitySelect").classList).not.toContain(
        "overridden",
      );
    });

    it("reflects stored switch values", () => {
      setup({ slice: member({ hide_copy_button: true }) });
      expect(query(SWITCHES.copy).getAttribute("aria-checked")).toBe("true");
      expect(query(SWITCHES.date).getAttribute("aria-checked")).toBe("false");
    });

    it("omits the density row without a fine pointer", () => {
      mockFinePointer({ fine: false });
      setup();
      expect(host.querySelector("#urlsSettingsDensitySelect")).toBeNull();
      expect(host.querySelector("#urlsSettingsSortSelect")).not.toBeNull();
    });

    it("shows the density row when matchMedia is unavailable", () => {
      (window as { matchMedia?: unknown }).matchMedia = undefined;
      setup();
      expect(host.querySelector("#urlsSettingsDensitySelect")).not.toBeNull();
    });

    it("renders every control aria-disabled while the slice is absent", () => {
      setup({ slice: null });
      for (const control of host.querySelectorAll("select, button")) {
        expect(control.getAttribute("aria-disabled")).toBe("true");
      }
    });
  });

  describe("interaction", () => {
    it("submits a select change once", () => {
      setup();
      choose({ id: "urlsSettingsSortSelect", value: "title_az" });
      expect(submit).toHaveBeenCalledTimes(1);
      expect(submit).toHaveBeenCalledWith({ patch: { sort: "title_az" } });
    });

    it("maps the default option to null", () => {
      setup({ slice: member({ view_mode: "cards" }) });
      choose({ id: "urlsSettingsViewSelect", value: "" });
      expect(submit).toHaveBeenCalledWith({ patch: { view_mode: null } });
      expect(selectEl("urlsSettingsViewSelect").classList).not.toContain(
        "overridden",
      );
    });

    it("submits a density change", () => {
      setup();
      choose({ id: "urlsSettingsDensitySelect", value: "compact" });
      expect(submit).toHaveBeenCalledWith({ patch: { density: "compact" } });
    });

    it("toggles a switch optimistically and submits the new value", () => {
      setup();
      query(SWITCHES.date).click();
      expect(query(SWITCHES.date).getAttribute("aria-checked")).toBe("true");
      expect(submit).toHaveBeenCalledWith({
        patch: { hide_date_added: true },
      });
    });

    it("submits each switch under its own key", () => {
      setup();
      query(SWITCHES.copy).click();
      query(SWITCHES.shortLink).click();
      query(SWITCHES.swipe).click();
      expect(submit.mock.calls.map(([arg]) => arg.patch)).toEqual([
        { hide_copy_button: true },
        { hide_short_link_button: true },
        { disable_swipe_delete: true },
      ]);
    });

    it("is a no-op while the slice is absent, and a select reverts", () => {
      setup({ slice: null });
      query(SWITCHES.copy).click();
      choose({ id: "urlsSettingsSortSelect", value: "oldest" });
      expect(submit).not.toHaveBeenCalled();
      expect(query(SWITCHES.copy).getAttribute("aria-checked")).toBe("false");
      expect(selectEl("urlsSettingsSortSelect").value).toBe("");
    });

    it("ignores changes when the context cannot write", () => {
      setup({ canWrite: false });
      query(SWITCHES.date).click();
      choose({ id: "urlsSettingsSortSelect", value: "oldest" });
      expect(submit).not.toHaveBeenCalled();
      expect(query(SWITCHES.date).getAttribute("aria-disabled")).toBe("true");
      expect(
        selectEl("urlsSettingsSortSelect").getAttribute("aria-disabled"),
      ).toBe("true");
      expect(selectEl("urlsSettingsSortSelect").value).toBe("");
    });

    it("is writable for a plain member in a locked UTub", () => {
      setState({ isCurrentUserOwner: false, isCurrentUTubLocked: true });
      setup();

      expect(query(SWITCHES.date).getAttribute("aria-disabled")).toBeNull();
      expect(
        selectEl("urlsSettingsSortSelect").getAttribute("aria-disabled"),
      ).toBeNull();
      query(SWITCHES.date).click();
      choose({ id: "urlsSettingsSortSelect", value: "oldest" });
      expect(submit.mock.calls.map(([arg]) => arg.patch)).toEqual([
        { hide_date_added: true },
        { sort: "oldest" },
      ]);
    });

    it("rolls a failed optimistic change back when the shell re-renders from the stored slice", () => {
      setup();
      query(SWITCHES.date).click();
      choose({ id: "urlsSettingsSortSelect", value: "oldest" });
      expect(query(SWITCHES.date).getAttribute("aria-checked")).toBe("true");

      // The shell's rollback re-render: the store never took the failed values.
      renderSection();

      expect(query(SWITCHES.date).getAttribute("aria-checked")).toBe("false");
      expect(selectEl("urlsSettingsSortSelect").value).toBe("");
    });
  });

  describe("short links off", () => {
    it("re-enables the short-link switch and drops the hint when the policy turns back on", () => {
      setState({ activeUTubID: UTUB_ID, memberSettings: member() });
      setState({
        settings: resolveUtubSettings({
          urls: { allow_short_links: false },
        } as never),
      });
      renderSection();
      expect(query(SWITCHES.shortLink).getAttribute("aria-disabled")).toBe(
        "true",
      );

      setState({
        settings: resolveUtubSettings({
          urls: { allow_short_links: true },
        } as never),
      });
      renderSection();

      const toggle = query(SWITCHES.shortLink);
      expect(toggle.getAttribute("aria-disabled")).toBeNull();
      expect(
        document.querySelector("#urlsPersonalHideShortLinkHint"),
      ).toBeNull();
      expect(toggle.getAttribute("aria-describedby") ?? "").not.toContain(
        "Hint",
      );
      toggle.click();
      expect(submit).toHaveBeenCalledWith({
        patch: { hide_short_link_button: true },
      });
    });

    function seedShortLinksOff(): void {
      setState({
        settings: resolveUtubSettings({
          urls: { allow_short_links: false },
        } as never),
      });
    }

    it("disables the short-link switch, keeps its stored value and shows the hint", () => {
      setState({
        activeUTubID: UTUB_ID,
        memberSettings: member({ hide_short_link_button: true }),
      });
      seedShortLinksOff();
      renderSection();

      const toggle = query(SWITCHES.shortLink);
      expect(toggle.getAttribute("aria-disabled")).toBe("true");
      expect(toggle.getAttribute("aria-checked")).toBe("true");
      const hint = query("#urlsPersonalHideShortLinkHint");
      expect(hint.textContent).toBe(
        "Short links are turned off for everyone in this UTub.",
      );
      expect(toggle.getAttribute("aria-describedby")).toContain(hint.id);
      toggle.click();
      expect(submit).not.toHaveBeenCalled();
    });

    it("leaves the other switches usable", () => {
      setState({ activeUTubID: UTUB_ID, memberSettings: member() });
      seedShortLinksOff();
      renderSection();
      expect(query(SWITCHES.copy).getAttribute("aria-disabled")).toBeNull();
    });
  });

  describe("save", () => {
    it("rejects a missing UTub id", async () => {
      await expect(
        section.save({ utubID: null, patch: { sort: "oldest" } }),
      ).resolves.toEqual({ outcome: "error" });
      expect(patchMemberSettings).not.toHaveBeenCalled();
    });

    it("patches the urls panel and writes the response with a version bump", async () => {
      setState({ activeUTubID: UTUB_ID, memberSettingsVersion: 2 });
      vi.mocked(patchMemberSettings).mockResolvedValue({
        outcome: "ok",
        memberSettings: { urls: { sort: "oldest", hide_date_added: true } },
      } as never);

      const result = await section.save({
        utubID: UTUB_ID,
        patch: { sort: "oldest", hide_date_added: true },
      });

      expect(patchMemberSettings).toHaveBeenCalledWith({
        utubID: UTUB_ID,
        panel: "urls",
        patch: { sort: "oldest", hide_date_added: true },
      });
      expect(getState().memberSettingsVersion).toBe(3);
      expect(getState().memberSettings).toEqual(
        resolveMemberSettings({
          urls: { sort: "oldest", hide_date_added: true },
        } as never),
      );
      expect(result).toEqual({
        outcome: "ok",
        notice: "Date added hidden. Sort set to Date added (oldest)",
      });
    });

    it("names the default in the notice when an override is cleared", async () => {
      setState({ activeUTubID: UTUB_ID });
      vi.mocked(patchMemberSettings).mockResolvedValue({
        outcome: "ok",
        memberSettings: { urls: {} },
      } as never);

      const result = await section.save({
        utubID: UTUB_ID,
        patch: { view_mode: null, density: null } as SectionPatch,
      });

      expect(result).toEqual({
        outcome: "ok",
        notice: "Layout uses your default. Density uses your default",
      });
    });

    it("triggers exactly one deck order sync for a sort save, including a reset to default", async () => {
      setState({ activeUTubID: UTUB_ID });
      vi.mocked(patchMemberSettings).mockResolvedValue({
        outcome: "ok",
        memberSettings: { urls: { sort: "oldest" } },
      } as never);

      await section.save({ utubID: UTUB_ID, patch: { sort: "oldest" } });
      expect(syncDeckOrderToServer).toHaveBeenCalledTimes(1);

      await section.save({
        utubID: UTUB_ID,
        patch: { sort: null } as SectionPatch,
      });
      expect(syncDeckOrderToServer).toHaveBeenCalledTimes(2);
    });

    it("triggers no deck order sync for a non-sort save", async () => {
      setState({ activeUTubID: UTUB_ID });
      vi.mocked(patchMemberSettings).mockResolvedValue({
        outcome: "ok",
        memberSettings: { urls: { hide_copy_button: true } },
      } as never);

      await section.save({
        utubID: UTUB_ID,
        patch: { hide_copy_button: true },
      });
      expect(syncDeckOrderToServer).not.toHaveBeenCalled();
    });

    it("triggers no deck order sync when the save fails or resolves after a UTub switch", async () => {
      setState({ activeUTubID: UTUB_ID });
      vi.mocked(patchMemberSettings).mockResolvedValue({
        outcome: "error",
      } as never);
      await section.save({ utubID: UTUB_ID, patch: { sort: "oldest" } });

      vi.mocked(patchMemberSettings).mockImplementation(async () => {
        setState({ activeUTubID: 99 });
        return {
          outcome: "ok",
          memberSettings: { urls: { sort: "oldest" } },
        } as never;
      });
      await section.save({ utubID: UTUB_ID, patch: { sort: "oldest" } });

      expect(syncDeckOrderToServer).not.toHaveBeenCalled();
    });

    it("maps invalid to error", async () => {
      setState({ activeUTubID: UTUB_ID });
      vi.mocked(patchMemberSettings).mockResolvedValue({
        outcome: "invalid",
      } as never);
      await expect(
        section.save({ utubID: UTUB_ID, patch: { sort: "oldest" } }),
      ).resolves.toEqual({ outcome: "error" });
    });

    it("passes other non-ok outcomes through without touching the store", async () => {
      setState({ activeUTubID: UTUB_ID, memberSettings: member() });
      vi.mocked(patchMemberSettings).mockResolvedValue({
        outcome: "forbidden",
      } as never);
      const before = getState().memberSettings;

      await expect(
        section.save({ utubID: UTUB_ID, patch: { sort: "oldest" } }),
      ).resolves.toEqual({ outcome: "forbidden" });
      expect(getState().memberSettings).toBe(before);
      expect(getState().memberSettingsVersion).toBe(0);
    });

    it("drops an ok result that resolves after a UTub switch", async () => {
      setState({ activeUTubID: UTUB_ID });
      vi.mocked(patchMemberSettings).mockImplementation(async () => {
        setState({ activeUTubID: 99 });
        return {
          outcome: "ok",
          memberSettings: { urls: { sort: "oldest" } },
        } as never;
      });

      const result = await section.save({
        utubID: UTUB_ID,
        patch: { sort: "oldest" },
      });

      expect(result.outcome).toBe("stale");
      expect(getState().memberSettings).toBeNull();
      expect(getState().memberSettingsVersion).toBe(0);
    });
  });
});
