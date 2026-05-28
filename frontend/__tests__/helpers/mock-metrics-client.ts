/**
 * Test helper for asserting calls into `frontend/lib/metrics-client.ts`.
 *
 * `mockMetricsClient()` returns a fresh `{ emit, flush, initMetricsClient,
 * resetMetricsClient }` object of `vi.fn()` mocks. The metrics-client module
 * itself must be mocked at module scope with `vi.mock(...)` — the helper does
 * not call `vi.mock` because the path is relative to the module under test.
 *
 * Canonical usage at the top of a `<module>.test.ts`:
 *
 * ```ts
 * vi.mock("<relative-path>/lib/metrics-client.js", () => ({
 *   emit: vi.fn(),
 *   flush: vi.fn().mockResolvedValue(undefined),
 *   initMetricsClient: vi.fn(),
 *   resetMetricsClient: vi.fn(),
 * }));
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
    flush: vi.fn(),
    initMetricsClient: vi.fn(),
    resetMetricsClient: vi.fn(),
  };
}
