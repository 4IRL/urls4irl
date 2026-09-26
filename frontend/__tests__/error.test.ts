vi.mock("../lib/security-check.js", () => ({}));

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("./helpers/mock-metrics-client.js"),
);

vi.mock("../lib/metrics-client.js", () => mockMetricsClient());

describe("error entry point", () => {
  const ORIGINAL_HREF = "http://127.0.0.1:8659/error#some-hash";

  beforeEach(() => {
    document.body.innerHTML = `<button id="refreshBtn">Refresh</button>`;
    Object.defineProperty(window, "location", {
      value: { href: ORIGINAL_HREF },
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    vi.resetModules();
    vi.unstubAllGlobals();
    document.body.innerHTML = "";
  });

  it("sets location.href to hash-stripped value on refreshBtn click", async () => {
    await import("../error.js");

    document.getElementById("refreshBtn")!.click();

    expect(window.location.href).toBe("http://127.0.0.1:8659/error");
  });

  it("does not error when refreshBtn is absent", async () => {
    document.body.innerHTML = "";

    await expect(import("../error.js")).resolves.not.toThrow();
  });

  it("binds the refresh button on a standalone error page with no jQuery loaded", async () => {
    // The error page ships no jQuery; a fresh load must not depend on it.
    vi.stubGlobal("jQuery", undefined);
    vi.stubGlobal("$", undefined);

    await import("../error.js");
    document.getElementById("refreshBtn")!.click();

    expect(window.location.href).toBe("http://127.0.0.1:8659/error");
  });

  it("waits for DOMContentLoaded before binding while the document is still loading", async () => {
    const readyStateSpy = vi
      .spyOn(document, "readyState", "get")
      .mockReturnValue("loading");

    await import("../error.js");
    document.getElementById("refreshBtn")!.click();
    expect(window.location.href).toBe(ORIGINAL_HREF);

    readyStateSpy.mockRestore();
    document.dispatchEvent(new Event("DOMContentLoaded"));
    document.getElementById("refreshBtn")!.click();

    expect(window.location.href).toBe("http://127.0.0.1:8659/error");
  });
});

export {};
