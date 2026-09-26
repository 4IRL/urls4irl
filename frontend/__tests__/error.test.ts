import { getRefreshDestination } from "../error.js";
import { APP_CONFIG } from "../lib/config.js";

vi.mock("../lib/security-check.js", () => ({}));

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("./helpers/mock-metrics-client.js"),
);

vi.mock("../lib/metrics-client.js", () => mockMetricsClient());

describe("error entry point", () => {
  const ORIGINAL_HREF = "http://127.0.0.1:8659/error#some-hash";

  beforeEach(() => {
    // The top-level import below already evaluated error.js once; reset so each
    // test's dynamic import re-runs its init against the fresh DOM.
    vi.resetModules();
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

  it("sends a non-reload-safe page to a same-origin referrer on click", async () => {
    document.body.innerHTML = `<button id="refreshBtn" data-reload-safe="false">Refresh</button>`;
    Object.defineProperty(window, "location", {
      value: {
        href: "http://127.0.0.1:8659/login",
        origin: "http://127.0.0.1:8659",
      },
      writable: true,
      configurable: true,
    });
    const referrerSpy = vi
      .spyOn(document, "referrer", "get")
      .mockReturnValue("http://127.0.0.1:8659/");

    await import("../error.js");
    document.getElementById("refreshBtn")!.click();

    expect(window.location.href).toBe("http://127.0.0.1:8659/");
    referrerSpy.mockRestore();
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

describe("getRefreshDestination", () => {
  const ORIGIN = "http://127.0.0.1:8659";

  it("reloads the hash-stripped current URL when the page came from a GET", () => {
    expect(
      getRefreshDestination({
        isReloadSafe: true,
        currentHref: `${ORIGIN}/home?UTubID=3#frag`,
        referrer: `${ORIGIN}/`,
        origin: ORIGIN,
      }),
    ).toBe(`${ORIGIN}/home?UTubID=3`);
  });

  it("returns the referrer after a POST when the referrer is same-origin", () => {
    expect(
      getRefreshDestination({
        isReloadSafe: false,
        currentHref: `${ORIGIN}/login`,
        referrer: `${ORIGIN}/?next=abc`,
        origin: ORIGIN,
      }),
    ).toBe(`${ORIGIN}/?next=abc`);
  });

  it("falls back to the home route after a POST with a cross-origin referrer", () => {
    expect(
      getRefreshDestination({
        isReloadSafe: false,
        currentHref: `${ORIGIN}/login`,
        referrer: "https://evil.example.com/phish",
        origin: ORIGIN,
      }),
    ).toBe(APP_CONFIG.routes.home);
  });

  it("falls back to the home route after a POST with no referrer", () => {
    expect(
      getRefreshDestination({
        isReloadSafe: false,
        currentHref: `${ORIGIN}/login`,
        referrer: "",
        origin: ORIGIN,
      }),
    ).toBe(APP_CONFIG.routes.home);
  });

  it("falls back to the home route after a POST with a malformed referrer", () => {
    expect(
      getRefreshDestination({
        isReloadSafe: false,
        currentHref: `${ORIGIN}/login`,
        referrer: "not a url",
        origin: ORIGIN,
      }),
    ).toBe(APP_CONFIG.routes.home);
  });
});
