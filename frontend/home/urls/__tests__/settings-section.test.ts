import { setState } from "../../../store/app-store.js";
import {
  EMPTY_UTUB_SETTINGS,
  type ResolvedUtubSettings,
} from "../../../types/settings.js";
import { patchUtubSettings } from "../../panel-settings/client.js";
import {
  _resetRegistryForTests,
  getSections,
} from "../../panel-settings/registry.js";
import type {
  PanelSection,
  SaveResult,
  SectionContext,
  SectionPatch,
} from "../../panel-settings/types.js";
import { getEffectiveDefaultScheme } from "../scheme/scheme-default.js";
import { registerUrlsSettingsSection } from "../settings-section.js";

vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
}));
vi.mock("../../panel-settings/client.js", () => ({
  patchUtubSettings: vi.fn(),
}));

const UTUB_ID = 7;
const SWITCH = "#urlsSettingsHideSwitch";
const TOGGLE = "#urlsSettingsDefaultScheme";

function urlsSettings({
  scheme = "https",
  hide = false,
}: { scheme?: string; hide?: boolean } = {}): ResolvedUtubSettings {
  return {
    ...EMPTY_UTUB_SETTINGS,
    urls: { default_url_scheme: scheme, hide_scheme_selector: hide },
  } as ResolvedUtubSettings;
}

function seed(settings: ResolvedUtubSettings | null): void {
  setState({ activeUTubID: UTUB_ID, settings });
}

function switchEl(): HTMLElement {
  return document.querySelector<HTMLElement>(SWITCH)!;
}

function toggleEl(): HTMLElement {
  return document.querySelector<HTMLElement>(TOGGLE)!;
}

function pick(scheme: string): void {
  toggleEl().click();
  document
    .querySelector<HTMLElement>(`.urlSchemeOption[data-scheme="${scheme}"]`)!
    .click();
}

function mockPatch(
  implementation: (args: {
    utubID: number;
    panel: string;
    patch: SectionPatch;
  }) => Promise<SaveResult>,
): void {
  vi.mocked(patchUtubSettings).mockImplementation(
    implementation as typeof patchUtubSettings,
  );
}

describe("registerUrlsSettingsSection", () => {
  let host: HTMLElement;
  let section: PanelSection;
  let unregister: () => void;
  let submit: ReturnType<typeof vi.fn>;
  let cleanup: void | (() => void);
  let seedSettings: ResolvedUtubSettings | null;

  function renderSection({
    canWrite = true,
  }: { canWrite?: boolean } = {}): void {
    const ctx: SectionContext = {
      settings: seedSettings,
      canWrite,
      submit: submit as SectionContext["submit"],
    };
    cleanup = section.render({ container: host, ctx });
  }

  function setup({
    settings,
    canWrite,
  }: {
    settings: ResolvedUtubSettings | null;
    canWrite?: boolean;
  }): void {
    seedSettings = settings;
    seed(settings);
    renderSection({ canWrite });
  }

  beforeEach(() => {
    _resetRegistryForTests();
    document.body.innerHTML = "";
    host = document.createElement("div");
    document.body.append(host);
    submit = vi.fn();
    vi.mocked(patchUtubSettings).mockReset();
    unregister = registerUrlsSettingsSection();
    section = getSections("urls")[0];
    cleanup = undefined;
  });

  afterEach(() => {
    if (typeof cleanup === "function") cleanup();
    unregister();
    setState({ settings: null, activeUTubID: null });
    document.body.innerHTML = "";
  });

  it("registers the New URLs section on the urls panel with utub scope", () => {
    expect(section).toMatchObject({
      id: "urls-defaults",
      panel: "urls",
      scope: "utub",
      title: "New URLs",
    });
  });

  it("is idempotent with its unregister", () => {
    expect(getSections("urls")).toHaveLength(1);
    unregister();
    unregister();
    expect(getSections("urls")).toHaveLength(0);
    unregister = registerUrlsSettingsSection();
    expect(getSections("urls")).toHaveLength(1);
  });

  describe("render", () => {
    it("shows the stored values", () => {
      setup({ settings: urlsSettings({ scheme: "https", hide: true }) });

      expect(toggleEl().textContent).toContain("https");
      expect(switchEl().getAttribute("aria-checked")).toBe("true");
      expect(switchEl().hasAttribute("aria-disabled")).toBe(false);
      expect(switchEl().getAttribute("role")).toBe("switch");
    });

    it("shows the defaults when the slice is null", () => {
      setup({ settings: null });

      expect(toggleEl().textContent).toContain("https");
      expect(switchEl().getAttribute("aria-checked")).toBe("false");
    });

    it("renders a slice default outside URL_SCHEMES as given, while the effective default falls back", () => {
      setup({ settings: urlsSettings({ scheme: "gopher" }) });

      expect(toggleEl().textContent).toContain("gopher");
      expect(getEffectiveDefaultScheme()).toBe("https");
    });

    it("names the controls and links their descriptions", () => {
      setup({ settings: urlsSettings() });

      const schemeDescId = toggleEl().getAttribute("aria-describedby")!;
      expect(document.getElementById(schemeDescId)!.textContent).toBe(
        "New URLs start with this scheme.",
      );
      expect(toggleEl().getAttribute("aria-labelledby")).toContain(
        "urlsSettingsDefaultSchemeLabel",
      );
      const hideDescId = switchEl().getAttribute("aria-describedby")!;
      expect(hideDescId.split(" ")).toHaveLength(1);
      expect(document.getElementById(hideDescId)!.textContent).toBe(
        "Members see the scheme as a note under the URL field.",
      );
      expect(switchEl().getAttribute("aria-labelledby")).toBe(
        "urlsSettingsHideLabel",
      );
    });

    it("destroys the picker on cleanup", () => {
      setup({ settings: urlsSettings() });
      const toggle = toggleEl();
      toggle.click();
      expect(toggle.getAttribute("aria-expanded")).toBe("true");

      (cleanup as () => void)();
      cleanup = undefined;

      expect(document.querySelector(TOGGLE)).toBeNull();
      expect(document.querySelector(".urlSchemeListbox")).toBeNull();
    });
  });

  describe("picker", () => {
    it("submits the picked default scheme", () => {
      setup({ settings: urlsSettings() });

      pick("http");

      expect(submit).toHaveBeenCalledWith({
        patch: { default_url_scheme: "http" },
      });
      expect(toggleEl().textContent).toContain("http");
    });

    it("leaves focus on the toggle after a pick and announces nothing outside the closed listbox", () => {
      setup({ settings: urlsSettings() });

      pick("http");

      expect(document.activeElement).toBe(toggleEl());
      // Every picker live region sits inside the (now closed) hidden listbox, so
      // only the shell's own live region announces the save.
      const liveRegions = Array.from(host.querySelectorAll("[aria-live]"));
      expect(liveRegions.length).toBeGreaterThan(0);
      expect(
        liveRegions.every((region) =>
          region.closest(".urlSchemeListbox")?.classList.contains("hidden"),
        ),
      ).toBe(true);
    });

    it("closes only the list on Escape and lets the second Escape bubble", () => {
      setup({ settings: urlsSettings() });
      const bubbled = vi.fn();
      document.addEventListener("keydown", bubbled);
      toggleEl().click();

      toggleEl().dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
      expect(toggleEl().getAttribute("aria-expanded")).toBe("false");
      expect(bubbled).not.toHaveBeenCalled();

      toggleEl().dispatchEvent(
        new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
      );
      expect(bubbled).toHaveBeenCalledTimes(1);
      document.removeEventListener("keydown", bubbled);
    });
  });

  describe("switch", () => {
    it("toggles and submits the hide flag", () => {
      setup({ settings: urlsSettings() });

      switchEl().click();
      expect(switchEl().getAttribute("aria-checked")).toBe("true");
      expect(submit).toHaveBeenLastCalledWith({
        patch: { hide_scheme_selector: true },
      });

      switchEl().click();
      expect(switchEl().getAttribute("aria-checked")).toBe("false");
      expect(submit).toHaveBeenLastCalledWith({
        patch: { hide_scheme_selector: false },
      });
    });

    it("is disabled with a linked hint for a non-https value and the toggle is a no-op", () => {
      setup({ settings: urlsSettings({ scheme: "ssh" }) });

      expect(switchEl().getAttribute("aria-disabled")).toBe("true");
      expect(switchEl().getAttribute("aria-checked")).toBe("false");
      const hint = document.getElementById("urlsSettingsHideHint")!;
      expect(hint.hidden).toBe(false);
      expect(hint.textContent).toBe(
        "Only available when the default is https.",
      );
      expect(switchEl().getAttribute("aria-describedby")).toBe(
        "urlsSettingsHideDesc urlsSettingsHideHint",
      );

      switchEl().click();

      expect(submit).not.toHaveBeenCalled();
      expect(switchEl().getAttribute("aria-checked")).toBe("false");
    });

    it("turns off and disables when a non-https default is chosen while on, without sending a hide key", () => {
      setup({ settings: urlsSettings({ hide: true }) });

      pick("ssh");

      expect(switchEl().getAttribute("aria-checked")).toBe("false");
      expect(switchEl().getAttribute("aria-disabled")).toBe("true");
      expect(submit).toHaveBeenCalledWith({
        patch: { default_url_scheme: "ssh" },
      });
      expect(
        submit.mock.calls.every(
          ([arg]) => !("hide_scheme_selector" in arg.patch),
        ),
      ).toBe(true);
    });

    it("restores the last hide intent when the picker returns to https (coalesced sequence)", () => {
      setup({ settings: urlsSettings() });
      switchEl().click();
      expect(switchEl().getAttribute("aria-checked")).toBe("true");

      pick("ssh");
      expect(switchEl().getAttribute("aria-checked")).toBe("false");
      pick("https");

      expect(switchEl().getAttribute("aria-checked")).toBe("true");
      expect(switchEl().hasAttribute("aria-disabled")).toBe(false);
      expect(document.getElementById("urlsSettingsHideHint")!.hidden).toBe(
        true,
      );
      expect(switchEl().getAttribute("aria-describedby")).toBe(
        "urlsSettingsHideDesc",
      );
    });

    it("restores the server's auto-reset result after an ok non-https save", async () => {
      setup({ settings: urlsSettings({ hide: true }) });
      mockPatch(async () => {
        const settings = urlsSettings({ scheme: "ssh", hide: false });
        setState({ settings });
        return { outcome: "ok", settings };
      });

      pick("ssh");
      await section.save({
        utubID: UTUB_ID,
        patch: { default_url_scheme: "ssh" },
      });
      pick("https");

      expect(switchEl().getAttribute("aria-checked")).toBe("false");
      expect(switchEl().hasAttribute("aria-disabled")).toBe(false);
    });
  });

  describe("read-only", () => {
    it("disables both controls but keeps them focusable", () => {
      setup({ settings: urlsSettings({ hide: true }), canWrite: false });

      expect(toggleEl().getAttribute("aria-disabled")).toBe("true");
      expect(switchEl().getAttribute("aria-disabled")).toBe("true");
      expect(switchEl().getAttribute("aria-checked")).toBe("true");
      expect(switchEl().hasAttribute("disabled")).toBe(false);
      expect(toggleEl().hasAttribute("disabled")).toBe(false);

      toggleEl().click();
      expect(toggleEl().getAttribute("aria-expanded")).toBe("false");
      switchEl().click();
      expect(submit).not.toHaveBeenCalled();
      switchEl().focus();
      expect(document.activeElement).toBe(switchEl());
    });
  });

  describe("save", () => {
    it("sanitizes a coalesced hide-on plus non-https patch before patching", async () => {
      seed(urlsSettings());
      mockPatch(async () => ({ outcome: "ok", settings: urlsSettings() }));

      await section.save({
        utubID: UTUB_ID,
        patch: { hide_scheme_selector: true, default_url_scheme: "ssh" },
      });

      expect(patchUtubSettings).toHaveBeenCalledWith({
        utubID: UTUB_ID,
        panel: "urls",
        patch: { default_url_scheme: "ssh" },
      });
    });

    it("keeps hide=true when the default is https", async () => {
      seed(urlsSettings());
      mockPatch(async () => ({ outcome: "ok", settings: urlsSettings() }));

      await section.save({
        utubID: UTUB_ID,
        patch: { hide_scheme_selector: true, default_url_scheme: "https" },
      });

      expect(patchUtubSettings).toHaveBeenCalledWith({
        utubID: UTUB_ID,
        panel: "urls",
        patch: { hide_scheme_selector: true, default_url_scheme: "https" },
      });
    });

    it("keeps hide=false next to a non-https default", async () => {
      seed(urlsSettings());
      mockPatch(async () => ({ outcome: "ok", settings: urlsSettings() }));

      await section.save({
        utubID: UTUB_ID,
        patch: { hide_scheme_selector: false, default_url_scheme: "ssh" },
      });

      expect(patchUtubSettings).toHaveBeenCalledWith({
        utubID: UTUB_ID,
        panel: "urls",
        patch: { hide_scheme_selector: false, default_url_scheme: "ssh" },
      });
    });

    it("returns the auto-reset notice only on a true to false flip with no hide key", async () => {
      seed(urlsSettings({ hide: true }));
      mockPatch(async () => {
        const settings = urlsSettings({ scheme: "ssh", hide: false });
        setState({ settings });
        return { outcome: "ok", settings };
      });

      const result = await section.save({
        utubID: UTUB_ID,
        patch: { default_url_scheme: "ssh" },
      });

      expect(result).toMatchObject({
        outcome: "ok",
        notice:
          "Scheme selector shown again because the default is no longer https.",
      });
    });

    it("still returns the notice when the switch is optimistically off (baseline read before the await)", async () => {
      setup({ settings: urlsSettings({ hide: true }) });
      pick("ssh");
      expect(switchEl().getAttribute("aria-checked")).toBe("false");
      // Matches client.ts: the response is written to the slice before resolve.
      mockPatch(async () => {
        const settings = urlsSettings({ scheme: "ssh", hide: false });
        setState({ settings });
        return { outcome: "ok", settings };
      });

      const result = await section.save({
        utubID: UTUB_ID,
        patch: { hide_scheme_selector: true, default_url_scheme: "ssh" },
      });

      expect(result).toMatchObject({
        outcome: "ok",
        notice:
          "Scheme selector shown again because the default is no longer https.",
      });
    });

    it.each([
      ["the stored hide was already false", false, "ssh", false],
      ["the default stays https", true, "https", true],
    ])(
      "returns no notice when %s",
      async (_label, storedHide, scheme, hide) => {
        seed(urlsSettings({ hide: storedHide }));
        mockPatch(async () => {
          const settings = urlsSettings({ scheme, hide });
          setState({ settings });
          return { outcome: "ok", settings };
        });

        const result = await section.save({
          utubID: UTUB_ID,
          patch: { default_url_scheme: scheme },
        });

        expect(result).toEqual({
          outcome: "ok",
          settings: expect.anything(),
        });
        expect((result as { notice?: string }).notice).toBeUndefined();
      },
    );

    it("flips the switch in place while focus is inside the section", async () => {
      setup({ settings: urlsSettings({ hide: true }) });
      let resolveSave!: (result: SaveResult) => void;
      mockPatch(
        () =>
          new Promise<SaveResult>((resolve) => {
            resolveSave = resolve;
          }),
      );
      pick("ssh");
      const saving = section.save({
        utubID: UTUB_ID,
        patch: { default_url_scheme: "ssh" },
      });
      // Back on https before the save lands: the switch shows the hide intent.
      pick("https");
      switchEl().focus();
      expect(switchEl().getAttribute("aria-checked")).toBe("true");

      const settings = urlsSettings({ scheme: "ssh", hide: false });
      setState({ settings });
      resolveSave({ outcome: "ok", settings });
      await saving;

      expect(document.activeElement).toBe(switchEl());
      expect(switchEl().getAttribute("aria-checked")).toBe("false");
      expect(switchEl().hasAttribute("aria-disabled")).toBe(false);
    });

    it("makes no DOM write and does not throw when it resolves after unmount", async () => {
      setup({ settings: urlsSettings({ hide: true }) });
      let resolveSave!: (result: SaveResult) => void;
      mockPatch(
        () =>
          new Promise<SaveResult>((resolve) => {
            resolveSave = resolve;
          }),
      );
      const saving = section.save({
        utubID: UTUB_ID,
        patch: { default_url_scheme: "ssh" },
      });
      (cleanup as () => void)();
      cleanup = undefined;
      const before = document.body.innerHTML;

      resolveSave({
        outcome: "ok",
        settings: urlsSettings({ scheme: "ssh", hide: false }),
      });

      await expect(saving).resolves.toMatchObject({ outcome: "ok" });
      expect(document.body.innerHTML).toBe(before);
    });

    it("makes no DOM write when it resolves for another UTub", async () => {
      setup({ settings: urlsSettings({ hide: true }) });
      const before = document.body.innerHTML;
      mockPatch(async () => ({
        outcome: "ok",
        settings: urlsSettings({ scheme: "ssh", hide: false }),
      }));

      await expect(
        section.save({ utubID: 99, patch: { default_url_scheme: "ssh" } }),
      ).resolves.toMatchObject({ outcome: "ok" });

      expect(document.body.innerHTML).toBe(before);
    });

    it("maps an invalid outcome to error so the shell resyncs", async () => {
      seed(urlsSettings());
      mockPatch(async () => ({ outcome: "invalid" }));

      await expect(
        section.save({ utubID: UTUB_ID, patch: { default_url_scheme: "ssh" } }),
      ).resolves.toEqual({ outcome: "error" });
    });

    it.each<SaveResult>([
      { outcome: "locked" },
      { outcome: "forbidden" },
      { outcome: "gone" },
      { outcome: "error", resync: false },
      { outcome: "stale", failed: true },
    ])("passes %j through unchanged", async (outcome) => {
      seed(urlsSettings());
      mockPatch(async () => outcome);

      await expect(
        section.save({
          utubID: UTUB_ID,
          patch: { hide_scheme_selector: true },
        }),
      ).resolves.toEqual(outcome);
    });

    it("errors without patching when there is no UTub", async () => {
      await expect(
        section.save({ utubID: null, patch: { hide_scheme_selector: true } }),
      ).resolves.toEqual({ outcome: "error" });
      expect(patchUtubSettings).not.toHaveBeenCalled();
    });
  });
});
