import { mockMetricsClient } from "./mock-metrics-client.js";

import { UI_EVENTS } from "../../lib/metrics-events.js";
describe("mockMetricsClient", () => {
  it("returns four distinct Mock fns", () => {
    const mocks = mockMetricsClient();

    expect(vi.isMockFunction(mocks.emit)).toBe(true);
    expect(vi.isMockFunction(mocks.flush)).toBe(true);
    expect(vi.isMockFunction(mocks.initMetricsClient)).toBe(true);
    expect(vi.isMockFunction(mocks.resetMetricsClient)).toBe(true);

    const fns = [
      mocks.emit,
      mocks.flush,
      mocks.initMetricsClient,
      mocks.resetMetricsClient,
    ];
    const uniqueFns = new Set(fns);
    expect(uniqueFns.size).toBe(fns.length);
  });

  it("returns a fresh set of mocks on each invocation", () => {
    const firstInvocation = mockMetricsClient();
    const secondInvocation = mockMetricsClient();

    expect(firstInvocation.emit).not.toBe(secondInvocation.emit);
    expect(firstInvocation.flush).not.toBe(secondInvocation.flush);
    expect(firstInvocation.initMetricsClient).not.toBe(
      secondInvocation.initMetricsClient,
    );
    expect(firstInvocation.resetMetricsClient).not.toBe(
      secondInvocation.resetMetricsClient,
    );

    firstInvocation.emit({
      event: UI_EVENTS.UI_UTUB_SELECT,
      search_active: "false",
    });
    expect(firstInvocation.emit).toHaveBeenCalledTimes(1);
    expect(secondInvocation.emit).not.toHaveBeenCalled();
  });

  it("flush resolves to undefined to match metrics-client signature", async () => {
    const mocks = mockMetricsClient();
    await expect(mocks.flush()).resolves.toBeUndefined();
  });
});
