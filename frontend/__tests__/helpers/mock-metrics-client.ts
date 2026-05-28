/**
 * Test helper for mocking `frontend/lib/metrics-client.ts` in vitest specs.
 *
 * `mockMetricsClient()` returns a fresh `{ emit, flush, initMetricsClient,
 * resetMetricsClient }` object of `vi.fn()` mocks. It is designed to be used
 * as the factory passed to `vi.mock(path, factory)`. The metrics-client module
 * itself must be mocked at module scope (the path is relative to the test
 * file's location).
 *
 * Vitest hoists `vi.mock` calls above all ESM imports, so a plain
 * `import { mockMetricsClient } from "..."` is unavailable at the time the
 * factory runs. Use `vi.hoisted()` with a dynamic import to make the helper
 * accessible at hoist time.
 *
 * Canonical usage at the top of a `<module>.test.ts`:
 *
 * ```ts
 * const { mockMetricsClient } = await vi.hoisted(
 *   async () => await import("<path>/__tests__/helpers/mock-metrics-client.js"),
 * );
 *
 * vi.mock("<relative-path>/lib/metrics-client.js", () => mockMetricsClient());
 *
 * // Inside the test:
 * const { emit } = await import("<relative-path>/lib/metrics-client.js");
 * expect(emit).toHaveBeenCalledWith("ui_utub_select", { search_active: "false" });
 * ```
 *
 * NEVER include `device_type` in the asserted dimensions — `metrics-client`
 * itself auto-injects it inside `emit()`. Tests of call-site code see only
 * what the caller passes; `device_type` is added downstream.
 */

import type { Mock } from "vitest";

export type { Mock };

export interface MetricsClientMocks {
  emit: Mock;
  flush: Mock;
  initMetricsClient: Mock;
  resetMetricsClient: Mock;
}

export function mockMetricsClient(): MetricsClientMocks {
  return {
    emit: vi.fn(),
    flush: vi.fn().mockResolvedValue(undefined),
    initMetricsClient: vi.fn(),
    resetMetricsClient: vi.fn(),
  };
}
