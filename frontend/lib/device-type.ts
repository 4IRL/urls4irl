/**
 * Device-type detection for the anonymous metrics pipeline.
 *
 * Returns `"mobile"` when the viewport width is at or below the mobile
 * breakpoint (TABLET_WIDTH - 1 px), `"desktop"` otherwise. Detection is
 * lazy: the answer is computed on first call to `getDeviceType()`, then
 * cached for the lifetime of the page. Calling `initDeviceTypeListener()`
 * wires a `change` listener on the underlying `MediaQueryList` so the
 * cached answer updates if the user resizes across the breakpoint.
 *
 * Aligns with `isMobile()` in `frontend/home/mobile.ts` (which uses
 * `$(window).width() < TABLET_WIDTH`): a window exactly at TABLET_WIDTH
 * is classified as desktop in both places.
 */

import { TABLET_WIDTH } from "./constants.js";

export type DeviceType = "mobile" | "desktop";

const MOBILE_MEDIA_QUERY = `(max-width: ${TABLET_WIDTH - 1}px)`;

let _cachedDeviceType: DeviceType | null = null;

export function getDeviceType(): DeviceType {
  if (_cachedDeviceType === null) {
    _cachedDeviceType = window.matchMedia(MOBILE_MEDIA_QUERY).matches
      ? "mobile"
      : "desktop";
  }
  return _cachedDeviceType;
}

export function initDeviceTypeListener(): void {
  const mediaQueryList = window.matchMedia(MOBILE_MEDIA_QUERY);
  mediaQueryList.addEventListener("change", (event: MediaQueryListEvent) => {
    _cachedDeviceType = event.matches ? "mobile" : "desktop";
  });
}

/**
 * Internal hook for tree-shakable test access to the module-level cache.
 * Production code MUST NOT import this — it exists only so the test-utility
 * `frontend/__tests__/helpers/device-type-test-utils.ts` can reset cached
 * state between tests. Vite tree-shakes this in production builds because
 * no application module imports it.
 */
export const __deviceTypeInternals = Object.freeze({
  resetCache(): void {
    _cachedDeviceType = null;
  },
});
