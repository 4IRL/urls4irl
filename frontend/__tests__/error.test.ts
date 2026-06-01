vi.mock("../lib/security-check.js", () => ({}));

vi.mock("../lib/globals.js", () => ({
  $: window.jQuery,
  jQuery: window.jQuery,
  bootstrap: window.bootstrap,
}));

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
    document.body.innerHTML = "";
  });

  it("sets location.href to hash-stripped value on refreshBtn click", async () => {
    await import("../error.js");
    await new Promise<void>((resolve) => setTimeout(resolve, 0));

    document.getElementById("refreshBtn")!.click();

    expect(window.location.href).toBe("http://127.0.0.1:8659/error");
  });

  it("does not error when refreshBtn is absent", async () => {
    document.body.innerHTML = "";

    await expect(import("../error.js")).resolves.not.toThrow();
  });
});

export {};
