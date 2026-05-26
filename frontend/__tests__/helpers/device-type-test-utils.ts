/**
 * Test-only helpers for `frontend/lib/device-type.ts`.
 *
 * Production code never imports from this module. The wrapped reset
 * function clears the module-level device-type cache so individual tests
 * can re-stub `matchMedia` and observe a fresh `getDeviceType()` lookup.
 */

import { __deviceTypeInternals } from "../../lib/device-type.js";

export function resetDeviceTypeCache(): void {
  __deviceTypeInternals.resetCache();
}
