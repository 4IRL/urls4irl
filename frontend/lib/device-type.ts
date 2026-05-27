/**
 * Device-type detection for the anonymous metrics pipeline.
 *
 * Returns `DEVICE_TYPE.MOBILE` when the viewport width is at or below the
 * mobile breakpoint (TABLET_WIDTH - 1 px), `DEVICE_TYPE.DESKTOP` otherwise.
 * Detection is lazy: the answer is computed on first call to
 * `getDeviceType()`, then cached for the lifetime of the page. Calling
 * `initDeviceTypeListener()` wires a `change` listener on the underlying
 * `MediaQueryList` so the cached answer updates if the user resizes across
 * the breakpoint.
 *
 * The int wire values come from `APP_CONFIG.constants.DEVICE_TYPE`, which
 * the backend ships from `backend.metrics.events.DeviceType` — a single
 * cross-system source of truth. The frontend never hard-codes 1/2.
 *
 * Aligns with `isMobile()` in `frontend/home/mobile.ts` (which uses
 * `$(window).width() < TABLET_WIDTH`): a window exactly at TABLET_WIDTH
 * is classified as desktop in both places.
 */

import { APP_CONFIG } from "./config.js";
import { TABLET_WIDTH } from "./constants.js";

export type DeviceType =
  (typeof APP_CONFIG.constants.DEVICE_TYPE)[keyof typeof APP_CONFIG.constants.DEVICE_TYPE];

const MOBILE_MEDIA_QUERY = `(max-width: ${TABLET_WIDTH - 1}px)`;

let _cachedDeviceType: DeviceType | null = null;

export function getDeviceType(): DeviceType {
  if (_cachedDeviceType === null) {
    _cachedDeviceType = window.matchMedia(MOBILE_MEDIA_QUERY).matches
      ? APP_CONFIG.constants.DEVICE_TYPE.MOBILE
      : APP_CONFIG.constants.DEVICE_TYPE.DESKTOP;
  }
  return _cachedDeviceType;
}

export function initDeviceTypeListener(): void {
  const mediaQueryList = window.matchMedia(MOBILE_MEDIA_QUERY);
  mediaQueryList.addEventListener("change", (event: MediaQueryListEvent) => {
    _cachedDeviceType = event.matches
      ? APP_CONFIG.constants.DEVICE_TYPE.MOBILE
      : APP_CONFIG.constants.DEVICE_TYPE.DESKTOP;
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
