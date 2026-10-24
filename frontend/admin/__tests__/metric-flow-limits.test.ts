import { describe, expect, it } from "vitest";

import flowLimitKeys from "../../../backend/metrics/flow_limit_keys.json";
import { APP_CONFIG } from "../../lib/config.js";

const PREFIX = "METRIC_FLOWS_";

describe("metric-flow limits bridge", () => {
  it("APP_CONFIG.constants METRIC_FLOWS_* entries equal the shared limits JSON", () => {
    const bridged = Object.fromEntries(
      Object.entries(APP_CONFIG.constants).filter(([key]) =>
        key.startsWith(PREFIX),
      ),
    );

    expect(bridged).toEqual(flowLimitKeys);
  });

  it("exposes MAX_STEPS as 8", () => {
    expect(APP_CONFIG.constants.METRIC_FLOWS_MAX_STEPS).toBe(8);
  });
});
