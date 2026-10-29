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

function mockFinePointer({
  fine,
  wide = true,
}: {
  fine: boolean;
  wide?: boolean;
}): void {
  window.matchMedia = vi.fn((query: string) => ({
    matches:
      (fine && query === "(any-pointer: fine)") ||
      (wide && query === "(min-width: 992px)"),
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

  describe("view options by viewport", () => {
    const VIEW = "urlsSettingsViewSelect";

    function optionValues(): string[] {
      return Array.from(selectEl(VIEW).options).map((option) => option.value);
    }

    function setDefaultView(
      defaultView: "list" | "cards" | "title_line",
    ): void {
      setState({ preferences: { ...getState().preferences, defaultView } });
    }

    it("lists all four options in order on a wide viewport", () => {
      setup();
      expect(optionValues()).toEqual([
        "",
        "list",
        "title_line",
        "url_line",
        "cards",
      ]);
      expect(selectEl(VIEW).options[4].textContent).toBe("Cards");
    });

    it("omits cards on a narrow viewport", () => {
      mockFinePointer({ fine: true, wide: false });
      setup();
      expect(optionValues()).toEqual(["", "list", "title_line", "url_line"]);
    });

    it("omits cards when matchMedia is missing (fail closed)", () => {
      (window as { matchMedia?: unknown }).matchMedia = undefined;
      setup();
      expect(optionValues()).not.toContain("cards");
    });

    it("shows a cards override as one selected extra option on a narrow viewport", () => {
      mockFinePointer({ fine: true, wide: false });
      setDefaultView("title_line");
      setup({ slice: member({ view_mode: "cards" }) });
      expect(selectEl(VIEW).value).toBe("cards");
      expect(optionValues().filter((value) => value === "cards")).toHaveLength(
        1,
      );
      expect(selectEl(VIEW).selectedOptions[0].textContent).toBe(
        "Cards (List on small screens)",
      );
      expect(selectEl(VIEW).options[0].textContent).toBe("Default: Title line");
    });

    it("clears a cards override through Default on a narrow viewport", () => {
      mockFinePointer({ fine: true, wide: false });
      setup({ slice: member({ view_mode: "cards" }) });
      choose({ id: VIEW, value: "" });
      expect(submit).toHaveBeenCalledWith({ patch: { view_mode: null } });
    });

    it("labels a cards account default with a single prefix on a narrow viewport", () => {
      mockFinePointer({ fine: true, wide: false });
      setDefaultView("cards");
      setup();
      expect(selectEl(VIEW).options[0].textContent).toBe(
        "Default: Cards (List on small screens)",
      );
      expect(optionValues()).not.toContain("cards");
    });

    it("selects the extra option when both default and override are cards", () => {
      mockFinePointer({ fine: true, wide: false });
      setDefaultView("cards");
      setup({ slice: member({ view_mode: "cards" }) });
      expect(selectEl(VIEW).options[0].textContent).toBe(
        "Default: Cards (List on small screens)",
      );
      expect(selectEl(VIEW).selectedOptions[0].textContent).toBe(
        "Cards (List on small screens)",
      );
    });

    it("keeps the true default label on a wide viewport", () => {
      setDefaultView("cards");
      setup();
      expect(selectEl(VIEW).options[0].textContent).toBe("Default: Cards");
    });
  });

  describe("density control follows the effective view", () => {
    const DENSITY = "urlsSettingsDensitySelect";
    const HINT_TEXT = "Density applies to List view and the selected URL";

    function hintEl(): HTMLElement {
      return query("#urlsSettingsDensityHint");
    }

    function densityDisabled(): boolean {
      return selectEl(DENSITY).getAttribute("aria-disabled") === "true";
    }

    it.each(["title_line", "url_line", "cards"] as const)(
      "is aria-disabled with a visible hint for %s on a wide viewport",
      (viewMode) => {
        setup({ slice: member({ view_mode: viewMode }) });
        expect(densityDisabled()).toBe(true);
        expect(selectEl(DENSITY).hasAttribute("disabled")).toBe(false);
        expect(hintEl().hidden).toBe(false);
        expect(hintEl().textContent).toBe(HINT_TEXT);
      },
    );

    it("is enabled for list with the hint hidden", () => {
      setup({ slice: member({ view_mode: "list" }) });
      expect(densityDisabled()).toBe(false);
      expect(hintEl().hidden).toBe(true);
    });

    it("is enabled when Default resolves to list", () => {
      setup();
      expect(densityDisabled()).toBe(false);
    });

    it("is disabled when Default resolves to a line mode", () => {
      setState({
        preferences: { ...getState().preferences, defaultView: "url_line" },
      });
      setup();
      expect(densityDisabled()).toBe(true);
    });

    it("is enabled for a cards setting on a narrow viewport (renders as list)", () => {
      mockFinePointer({ fine: true, wide: false });
      setup({ slice: member({ view_mode: "cards" }) });
      expect(densityDisabled()).toBe(false);
      expect(hintEl().hidden).toBe(true);
    });

    it("describes the select by the desc and, while shown, the hint", () => {
      setup({ slice: member({ view_mode: "title_line" }) });
      const descId = query(`#${DENSITY}`)
        .closest(".panelSettingsRow")!
        .querySelector(".panelSettingsRowDesc")!.id;
      expect(
        selectEl(DENSITY).getAttribute("aria-describedby")?.split(" "),
      ).toEqual([descId, "urlsSettingsDensityHint"]);

      setup({ slice: member({ view_mode: "list" }) });
      expect(selectEl(DENSITY).getAttribute("aria-describedby")).toBe(descId);
    });

    it("toggles immediately from the view select change and keeps the value", () => {
      setup({ slice: member({ density: "compact" }) });
      expect(densityDisabled()).toBe(false);

      choose({ id: "urlsSettingsViewSelect", value: "title_line" });
      expect(densityDisabled()).toBe(true);
      expect(hintEl().hidden).toBe(false);
      expect(selectEl(DENSITY).value).toBe("compact");

      choose({ id: "urlsSettingsViewSelect", value: "list" });
      expect(densityDisabled()).toBe(false);
      expect(hintEl().hidden).toBe(true);
      expect(selectEl(DENSITY).value).toBe("compact");
      expect(
        submit.mock.calls.filter(([arg]) => "density" in arg.patch),
      ).toHaveLength(0);
    });

    it("re-resolves Default to the account default on a view change", () => {
      setState({
        preferences: { ...getState().preferences, defaultView: "title_line" },
      });
      setup({ slice: member({ view_mode: "list" }) });
      expect(densityDisabled()).toBe(false);
      choose({ id: "urlsSettingsViewSelect", value: "" });
      expect(densityDisabled()).toBe(true);
    });

    it("ignores a density change while view-disabled and reverts it", () => {
      setup({ slice: member({ view_mode: "url_line" }) });
      choose({ id: DENSITY, value: "compact" });
      expect(submit).not.toHaveBeenCalled();
      expect(selectEl(DENSITY).value).toBe("");
    });

    it("keeps density disabled when inert even if the view is list", () => {
      setup({ canWrite: false });
      expect(densityDisabled()).toBe(true);
      expect(hintEl().hidden).toBe(true);
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
