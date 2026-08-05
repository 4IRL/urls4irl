import { emit as emitAppEvent } from "../../lib/event-bus.js";
import { emit as recordUIEvent } from "../../lib/metrics-client.js";
import { showNewPageOnAJAXHTMLResponse } from "../../lib/page-utils.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { initDataExport, _resetDataExportForTests } from "../data-export.js";
import {
  clearControllerInFlight,
  registerControllerInFlight,
} from "../removal-shared.js";

vi.mock("../../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

vi.mock("../../lib/metrics-client.js", () => ({
  emit: vi.fn(),
}));

vi.mock("../../lib/event-bus.js", () => ({
  emit: vi.fn(),
  AppEvents: { DATA_EXPORT_STATUS_CHANGED: "data-export:status-changed" },
}));

vi.mock("../../lib/page-utils.js", () => ({
  showNewPageOnAJAXHTMLResponse: vi.fn(),
}));

const $ = window.jQuery;

const EXPORT_URL = "/users/1/data-export";
const STATUS_CHANGED_EVENT = "data-export:status-changed";

// Panel fixture: the always-present #SettingsPanelPrivacyData container the init
// guard keys off, holding the plain in-page export button + its status region.
function privacyDataHtml(): string {
  return `
    <section id="SettingsPanelPrivacyData">
    <button id="SettingsExportDataBtn" data-export-url="${EXPORT_URL}"></button>
    <div id="SettingsExportStatus" class="alert d-none"></div>
    </section>
  `;
}

interface FetchLike {
  ok: boolean;
  status: number;
  headers: { get: (name: string) => string | null };
  json?: () => Promise<unknown>;
  text?: () => Promise<string>;
}

function okResponse(exportData: unknown): FetchLike {
  return {
    ok: true,
    status: 200,
    headers: { get: () => "application/json" },
    json: async () => ({ export: exportData }),
  };
}

function notOkResponse(status: number): FetchLike {
  return {
    ok: false,
    status,
    headers: { get: () => "application/json" },
    text: async () => "",
  };
}

function html429Response(): FetchLike {
  return {
    ok: false,
    status: 429,
    headers: { get: () => "text/html" },
    text: async () => "<html>rate limited</html>",
  };
}

// One macrotask tick drains the microtask queue, letting the async handler's
// already-resolved fetch/json awaits settle before assertions run.
function flush(): Promise<void> {
  return new Promise<void>((resolve) => setTimeout(resolve, 0));
}

describe("data-export", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.URL.createObjectURL = vi.fn(() => "blob:mock");
    global.URL.revokeObjectURL = vi.fn();
    _resetDataExportForTests();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    _resetDataExportForTests();
    // Release any cross-controller registration a DD-21 test set, so the
    // module-level registry never leaks between tests.
    clearControllerInFlight("accountDelete");
  });

  it("is a no-op when the Privacy & Data panel is absent", () => {
    document.body.innerHTML = "<div id='Unrelated'></div>";
    global.fetch = vi.fn();
    initDataExport();
    $("body").trigger("click");
    expect(vi.mocked(global.fetch)).not.toHaveBeenCalled();
  });

  it("happy path: downloads the export blob and announces started", async () => {
    document.body.innerHTML = privacyDataHtml();
    global.fetch = vi.fn().mockResolvedValue(okResponse({ utubs: [] }));
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => {});
    initDataExport();

    $("#SettingsExportDataBtn").trigger("click");
    await flush();

    expect(global.URL.createObjectURL).toHaveBeenCalledTimes(1);
    expect(clickSpy).toHaveBeenCalledTimes(1);
    const status = $("#SettingsExportStatus");
    expect(status.hasClass("alert-success")).toBe(true);
    expect(status.text()).toBe("Your download is starting.");
    expect(vi.mocked(emitAppEvent)).toHaveBeenCalledWith(STATUS_CHANGED_EVENT, {
      message: "Your download is starting.",
    });
    // In-flight markers released on completion (DD-20).
    expect($("#SettingsExportDataBtn").attr("aria-disabled")).toBeUndefined();
  });

  it("sad path: a non-ok response shows the error banner and clears aria-disabled", async () => {
    document.body.innerHTML = privacyDataHtml();
    global.fetch = vi.fn().mockResolvedValue(notOkResponse(500));
    initDataExport();

    $("#SettingsExportDataBtn").trigger("click");
    await flush();

    const status = $("#SettingsExportStatus");
    expect(status.hasClass("alert-danger")).toBe(true);
    expect(status.text()).toBe("Couldn't export your data. Please try again.");
    expect(vi.mocked(emitAppEvent)).toHaveBeenCalledWith(STATUS_CHANGED_EVENT, {
      message: "Couldn't export your data. Please try again.",
    });
    expect($("#SettingsExportDataBtn").attr("aria-disabled")).toBeUndefined();
  });

  it("429 text/html: replaces the page and emits the rate-limit metric (DD-5)", async () => {
    document.body.innerHTML = privacyDataHtml();
    global.fetch = vi.fn().mockResolvedValue(html429Response());
    initDataExport();

    $("#SettingsExportDataBtn").trigger("click");
    await flush();

    expect(vi.mocked(showNewPageOnAJAXHTMLResponse)).toHaveBeenCalledWith(
      "<html>rate limited</html>",
    );
    expect(vi.mocked(recordUIEvent)).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_RATE_LIMIT_HIT,
    });
  });

  it("network reject: the rejected fetch is caught and shows the error banner (DD-7)", async () => {
    document.body.innerHTML = privacyDataHtml();
    global.fetch = vi.fn().mockRejectedValue(new Error("network down"));
    initDataExport();

    $("#SettingsExportDataBtn").trigger("click");
    await flush();

    const status = $("#SettingsExportStatus");
    expect(status.hasClass("alert-danger")).toBe(true);
    expect(status.text()).toBe("Couldn't export your data. Please try again.");
    expect($("#SettingsExportDataBtn").attr("aria-disabled")).toBeUndefined();
  });

  it("cross-panel guard: no-ops and shows the blocked notice when account-delete is in flight (DD-21)", async () => {
    document.body.innerHTML = privacyDataHtml();
    global.fetch = vi.fn();
    // Account-delete is mid-request; the symmetric DD-21 guard must block export.
    registerControllerInFlight("accountDelete");
    initDataExport();

    $("#SettingsExportDataBtn").trigger("click");
    await flush();

    expect(vi.mocked(global.fetch)).not.toHaveBeenCalled();
    const status = $("#SettingsExportStatus");
    expect(status.hasClass("alert-danger")).toBe(true);
    expect(status.text()).toBe(
      "Finish or cancel the account deletion in progress before exporting.",
    );
  });

  it("emits UI_DATA_EXPORT_TRIGGERED at click-time regardless of outcome (DD-19)", async () => {
    document.body.innerHTML = privacyDataHtml();
    // Pending (never-resolving) fetch: the trigger metric must fire immediately,
    // before the request settles.
    global.fetch = vi.fn().mockReturnValue(new Promise(() => {}));
    initDataExport();

    $("#SettingsExportDataBtn").trigger("click");
    await flush();

    expect(vi.mocked(recordUIEvent)).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_DATA_EXPORT_TRIGGERED,
    });
    // Still in flight: aria markers set, not yet cleared.
    expect($("#SettingsExportDataBtn").attr("aria-disabled")).toBe("true");
    expect($("#SettingsExportDataBtn").attr("aria-busy")).toBe("true");
  });
});
