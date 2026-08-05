// DD-14: proves the real DD-6/DD-16 listener that `settings.ts`'s `ready()` block
// registers actually mutates the global toast DOM — `data-export.test.ts` mocks
// `event-bus.js` entirely and never exercises this listener. Every module
// `settings.ts` imports is mocked EXCEPT `../lib/event-bus.js`, which stays real
// so `emit()` here reaches the listener settings.ts registered.

vi.mock("../lib/security-check.js", () => ({}));

vi.mock("../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

vi.mock("../lib/jquery-plugins.js", () => ({
  registerJQueryPlugins: vi.fn(),
}));

vi.mock("../lib/csrf.js", () => ({
  setupCSRF: vi.fn(),
}));

vi.mock("../lib/cookie-banner.js", () => ({
  initCookieBanner: vi.fn(),
}));

vi.mock("../lib/navbar-shared.js", () => ({
  initNavbarBackdrop: vi.fn(),
  initNavbarRouting: vi.fn(),
}));

vi.mock("../settings/settings-page.js", () => ({
  initSettingsPage: vi.fn(),
}));

vi.mock("../settings/connected-accounts.js", () => ({
  initConnectedAccounts: vi.fn(),
}));

vi.mock("../settings/change-username.js", () => ({
  initChangeUsername: vi.fn(),
}));

vi.mock("../settings/change-password.js", () => ({
  initChangePassword: vi.fn(),
}));

vi.mock("../settings/change-email.js", () => ({
  initChangeEmail: vi.fn(),
}));

vi.mock("../settings/account-removal.js", () => ({
  initAccountRemoval: vi.fn(),
}));

vi.mock("../settings/logout-everywhere.js", () => ({
  initLogoutEverywhere: vi.fn(),
}));

vi.mock("../settings/data-export.js", () => ({
  initDataExport: vi.fn(),
}));

describe("settings entry point — global export-status toast (DD-14)", () => {
  afterEach(() => {
    // Fresh event-bus.ts module instance per test so its module-level `_handlers`
    // map never leaks a registered listener across tests.
    vi.resetModules();
    vi.clearAllMocks();
    document.body.innerHTML = "";
  });

  it("mirrors a status change into the global toast when the panel is hidden (DD-16)", async () => {
    document.body.innerHTML =
      '<div id="SettingsGlobalStatusToast"></div><div id="SettingsPanelPrivacyData" hidden></div>';

    await import("../settings.js");
    // Let the already-ready-document jQuery ready() callback flush so the
    // listener registers.
    await new Promise<void>((resolve) => setTimeout(resolve, 0));

    // Real emit/AppEvents (same module instance settings.ts used, since
    // event-bus.js is unmocked and not yet reset).
    const { emit, AppEvents } = await import("../lib/event-bus.js");
    emit(AppEvents.DATA_EXPORT_STATUS_CHANGED, { message: "Export starting…" });

    expect(
      document.getElementById("SettingsGlobalStatusToast")?.textContent,
    ).toBe("Export starting…");
  });

  it("does NOT write the toast while the Privacy & Data panel is visible (DD-16 gate)", async () => {
    document.body.innerHTML =
      '<div id="SettingsGlobalStatusToast"></div><div id="SettingsPanelPrivacyData"></div>';
    // Panel visible (no `hidden` attribute) → the in-panel region announces it,
    // so the global toast must stay silent to avoid a double announcement.
    document
      .getElementById("SettingsPanelPrivacyData")
      ?.removeAttribute("hidden");

    await import("../settings.js");
    await new Promise<void>((resolve) => setTimeout(resolve, 0));

    const { emit, AppEvents } = await import("../lib/event-bus.js");
    emit(AppEvents.DATA_EXPORT_STATUS_CHANGED, { message: "Export starting…" });

    expect(
      document.getElementById("SettingsGlobalStatusToast")?.textContent,
    ).toBe("");
  });
});

export {};
