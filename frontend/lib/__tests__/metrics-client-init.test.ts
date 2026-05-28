import { resetDeviceTypeCache } from "../../__tests__/helpers/device-type-test-utils.js";
import { initMetricsClient, resetMetricsClient } from "../metrics-client.js";

// Entry-point wiring contract for `initMetricsClient()` — it must be
// (a) a function on the module export, and (b) idempotent under double-init
// so the two entry points (`main.ts` and `splash.ts`) cannot accidentally
// double-register the 60s flush interval if either bundle imports it twice
// or DOM-ready fires more than once.
// The in-depth interval / listener lifecycle coverage lives in
// `metrics-client.test.ts`; this file is a narrow init-shape guard.

beforeEach(() => {
  vi.stubGlobal(
    "matchMedia",
    vi.fn().mockReturnValue({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }),
  );
  resetDeviceTypeCache();
  resetMetricsClient();
});

afterEach(() => {
  resetMetricsClient();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  resetDeviceTypeCache();
});

describe("metrics-client-init entry-point contract", () => {
  it("initMetricsClient is a function on the module export", () => {
    expect(typeof initMetricsClient).toBe("function");
  });

  it("calling initMetricsClient twice does not register two intervals", () => {
    vi.useFakeTimers();
    const setIntervalSpy = vi.spyOn(globalThis, "setInterval");

    initMetricsClient();
    initMetricsClient();

    expect(setIntervalSpy).toHaveBeenCalledTimes(1);
  });
});
