import {
  emit,
  flush,
  initMetricsClient,
  resetMetricsClient,
} from "../metrics-client.js";

describe("metrics-client", () => {
  it("exports emit, flush, initMetricsClient, resetMetricsClient", () => {
    expect(typeof emit).toBe("function");
    expect(typeof flush).toBe("function");
    expect(typeof initMetricsClient).toBe("function");
    expect(typeof resetMetricsClient).toBe("function");
  });

  it("rejects non-UI EventName values at compile time", () => {
    // @ts-expect-error utub_created is a domain-category EventName, not a UI event name
    emit("utub_created", undefined);
  });
});
