import { UI_EVENTS } from "../types/metrics-events.js";
import { initMetricsClient } from "../lib/metrics-client.js";

vi.mock("../lib/security-check.js", () => ({}));

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("./helpers/mock-metrics-client.js"),
);

vi.mock("../lib/metrics-client.js", () => mockMetricsClient());

describe("error module — UI_ERROR_PAGE_REFRESH metric", () => {
  const ORIGINAL_HREF = "http://127.0.0.1:8659/error#some-hash";

  beforeEach(() => {
    document.body.innerHTML = `<button id="refreshBtn">Refresh</button>`;
    Object.defineProperty(window, "location", {
      value: { href: ORIGINAL_HREF },
      writable: true,
      configurable: true,
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.resetModules();
    document.body.innerHTML = "";
  });

  it("emits ui_error_page_refresh on refresh-button click", async () => {
    await import("../error.js");

    const { emit } = await import("../lib/metrics-client.js");
    document.getElementById("refreshBtn")!.click();

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_ERROR_PAGE_REFRESH,
    });
  });

  it("calls initMetricsClient on DOM ready", async () => {
    vi.mocked(initMetricsClient).mockClear();
    vi.resetModules();
    await import("../error.js");

    expect(vi.mocked(initMetricsClient)).toHaveBeenCalled();
  });
});
