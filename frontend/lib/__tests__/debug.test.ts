import { APP_CONFIG } from "../config.js";
import { debug, PUBLIC_NAMESPACES } from "../debug.js";

// Mock the config bridge so `APP_CONFIG.debugEnabled` is a mutable, test-controlled
// value. The real APP_CONFIG is frozen (see config.test.ts), which would make the
// per-test overrides below throw. The mock is a plain mutable object shared by
// reference with debug.ts, so mutating `debugEnabled` here is visible to the helper.
vi.mock("../config.js", () => ({
  APP_CONFIG: { debugEnabled: true },
}));

function setDebugEnabled(value: boolean): void {
  (APP_CONFIG as { debugEnabled: boolean }).debugEnabled = value;
}

describe("debug", () => {
  beforeEach(() => {
    vi.spyOn(console, "log").mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    setDebugEnabled(true);
  });

  it("returns a no-op when localStorage.debug is unset", () => {
    setDebugEnabled(true);
    debug("metrics")("foo");
    expect(console.log).not.toHaveBeenCalled();
  });

  it("returns a no-op when localStorage.debug is empty string", () => {
    setDebugEnabled(true);
    localStorage.setItem("debug", "");
    debug("metrics")("foo");
    expect(console.log).not.toHaveBeenCalled();
  });

  it("logs with [namespace] prefix when namespace exactly matches the allow-list", () => {
    setDebugEnabled(true);
    localStorage.setItem("debug", "metrics");
    debug("metrics")("foo", { count: 3 });
    expect(console.log).toHaveBeenCalledTimes(1);
    expect(console.log).toHaveBeenCalledWith("[metrics]", "foo", { count: 3 });
  });

  it("logs only namespaces present in a comma-separated allow-list", () => {
    setDebugEnabled(true);
    localStorage.setItem("debug", "metrics,store");
    debug("metrics")("a");
    debug("store")("b");
    debug("ajax")("c");
    expect(console.log).toHaveBeenCalledTimes(2);
    expect(console.log).toHaveBeenCalledWith("[metrics]", "a");
    expect(console.log).toHaveBeenCalledWith("[store]", "b");
  });

  it("tolerates whitespace around commas", () => {
    setDebugEnabled(true);
    localStorage.setItem("debug", "metrics, ajax");
    debug("metrics")("a");
    debug("ajax")("b");
    expect(console.log).toHaveBeenCalledTimes(2);
    expect(console.log).toHaveBeenCalledWith("[metrics]", "a");
    expect(console.log).toHaveBeenCalledWith("[ajax]", "b");
  });

  it("logs every namespace when allow-list is *", () => {
    setDebugEnabled(true);
    localStorage.setItem("debug", "*");
    debug("metrics")("a");
    debug("anything")("b");
    expect(console.log).toHaveBeenCalledTimes(2);
    expect(console.log).toHaveBeenCalledWith("[metrics]", "a");
    expect(console.log).toHaveBeenCalledWith("[anything]", "b");
  });

  it("supports colon-hierarchical wildcards", () => {
    setDebugEnabled(true);
    localStorage.setItem("debug", "metrics:*");
    debug("metrics:flush")("a");
    debug("metrics:retry")("b");
    debug("ajax")("c");
    expect(console.log).toHaveBeenCalledTimes(2);
    expect(console.log).toHaveBeenCalledWith("[metrics:flush]", "a");
    expect(console.log).toHaveBeenCalledWith("[metrics:retry]", "b");
  });

  it("supports negation with leading -", () => {
    setDebugEnabled(true);
    localStorage.setItem("debug", "*,-noise");
    debug("metrics")("a");
    debug("noise")("b");
    expect(console.log).toHaveBeenCalledTimes(1);
    expect(console.log).toHaveBeenCalledWith("[metrics]", "a");
  });

  it("supports multiple negations", () => {
    setDebugEnabled(true);
    localStorage.setItem("debug", "*,-noise,-verbose");
    debug("metrics")("a");
    debug("noise")("b");
    debug("verbose")("c");
    expect(console.log).toHaveBeenCalledTimes(1);
    expect(console.log).toHaveBeenCalledWith("[metrics]", "a");
  });

  it("exclude wins over a specific (non-wildcard) include", () => {
    setDebugEnabled(true);
    localStorage.setItem("debug", "metrics,-metrics");
    debug("metrics")("foo");
    expect(console.log).not.toHaveBeenCalled();
  });

  it("returns a no-op when localStorage.getItem throws", () => {
    setDebugEnabled(true);
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("storage disabled");
    });
    expect(() => debug("splash:login")("foo")).not.toThrow();
    expect(console.log).not.toHaveBeenCalled();
  });

  it("public namespace emits for anonymous user when namespace is enabled", () => {
    setDebugEnabled(false);
    localStorage.setItem("debug", "splash:login");
    debug("splash:login")("foo");
    expect(console.log).toHaveBeenCalledTimes(1);
    expect(console.log).toHaveBeenCalledWith("[splash:login]", "foo");
  });

  it("public namespace returns no-op when namespace is NOT in allow-list", () => {
    setDebugEnabled(false);
    localStorage.setItem("debug", "");
    debug("splash")("foo");
    expect(console.log).not.toHaveBeenCalled();
  });

  it("admin-only namespace returns no-op for anonymous user even when in allow-list", () => {
    setDebugEnabled(false);
    localStorage.setItem("debug", "metrics");
    debug("metrics")("foo");
    expect(console.log).not.toHaveBeenCalled();
  });

  it("admin-only namespace emits when admin user enables it", () => {
    setDebugEnabled(true);
    localStorage.setItem("debug", "metrics");
    debug("metrics")("foo");
    expect(console.log).toHaveBeenCalledTimes(1);
    expect(console.log).toHaveBeenCalledWith("[metrics]", "foo");
  });

  it("PUBLIC_NAMESPACES contains exactly the 5 splash namespaces", () => {
    expect(PUBLIC_NAMESPACES.has("splash")).toBe(true);
    expect(PUBLIC_NAMESPACES.has("splash:login")).toBe(true);
    expect(PUBLIC_NAMESPACES.has("splash:register")).toBe(true);
    expect(PUBLIC_NAMESPACES.has("splash:password")).toBe(true);
    expect(PUBLIC_NAMESPACES.has("splash:email")).toBe(true);
    expect(PUBLIC_NAMESPACES.size).toBe(5);
    // Privacy invariant: only splash namespaces may be public, since public
    // namespaces reach every anonymous prod user regardless of debugEnabled.
    expect(
      [...PUBLIC_NAMESPACES].every(
        (namespace) =>
          namespace === "splash" || namespace.startsWith("splash:"),
      ),
    ).toBe(true);
  });
});
