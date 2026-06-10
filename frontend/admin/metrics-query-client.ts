/**
 * Typed AJAX wrappers for the metrics-query endpoints.
 *
 * Each wrapper builds a typed URL query string against the
 * `/api/metrics/query/*` routes and returns a `JQuery.jqXHR<SuccessResponse<...>>`
 * tied to the corresponding `operations` entry in `frontend/types/api.d.ts`.
 *
 * `ajaxCall()` (see `frontend/lib/ajax.ts`) wraps `$.ajax`, which automatically
 * sends the `X-Requested-With: XMLHttpRequest` header for same-origin GETs. The
 * metrics-query `ajax_required=True` route gate is satisfied by that header, so
 * no manual header injection is needed here.
 */

import type { SuccessResponse } from "../types/api-helpers.d.ts";
import type { DeviceType } from "../types/metrics-dim-values.js";
import type { ResourceName } from "../types/metrics-resources.js";

import { ajaxCall } from "../lib/ajax.js";
import { APP_CONFIG } from "../lib/config.js";

type MetricsCategory = "api" | "ui" | "domain";
type TimeseriesResolution = "hour" | "day";

const DEVICE_TYPE_PARAM = APP_CONFIG.constants.DEVICE_TYPE_DIM_KEY;

const QUERY_TIMEOUT_MS = 5000;
const DEFAULT_TOP_LIMIT = 10;

const TOP_ENDPOINT = "/api/metrics/query/top";
const TIMESERIES_ENDPOINT = "/api/metrics/query/timeseries";
const SUMMARY_ENDPOINT = "/api/metrics/query/summary";

/**
 * Fetch the top-N events for a window, optionally scoped to a single category.
 *
 * Example: `fetchTopEvents({ window: "day", category: "ui", limit: 5 })`
 * issues `GET /api/metrics/query/top?window=day&category=ui&limit=5`.
 */
export function fetchTopEvents({
  window,
  category,
  limit,
  resource,
  deviceType,
}: {
  window: string;
  category: MetricsCategory;
  limit?: number;
  resource?: ResourceName | null;
  deviceType?: DeviceType | null;
}): JQuery.jqXHR<SuccessResponse<"queryTop">> {
  const effectiveLimit = limit ?? DEFAULT_TOP_LIMIT;
  const params = new URLSearchParams({
    window,
    category,
    limit: String(effectiveLimit),
  });
  if (resource !== undefined && resource !== null) {
    params.set("resource", resource);
  }
  if (deviceType !== undefined && deviceType !== null) {
    params.set(DEVICE_TYPE_PARAM, String(deviceType));
  }
  const url = `${TOP_ENDPOINT}?${params.toString()}`;
  return ajaxCall("GET", url, null, QUERY_TIMEOUT_MS) as JQuery.jqXHR<
    SuccessResponse<"queryTop">
  >;
}

/**
 * Fetch the per-bucket timeseries for a single event over a window.
 *
 * Optional `endpoint` + `method` narrow the series to one api_hit
 * (endpoint, method) pair — used by the admin dashboard's API tab to
 * chart per-endpoint timeseries.
 *
 * Example: `fetchTimeseries({ eventName: "utub_opened", window: "week", resolution: "day" })`
 * issues `GET /api/metrics/query/timeseries?event_name=utub_opened&window=week&resolution=day`.
 */
export function fetchTimeseries({
  eventName,
  window,
  resolution,
  endpoint,
  method,
  deviceType,
}: {
  eventName: string;
  window: string;
  resolution?: TimeseriesResolution;
  endpoint?: string;
  method?: string;
  deviceType?: DeviceType | null;
}): JQuery.jqXHR<SuccessResponse<"queryTimeseries">> {
  const params = new URLSearchParams({
    event_name: eventName,
    window,
  });
  if (resolution !== undefined) {
    params.set("resolution", resolution);
  }
  if (endpoint !== undefined) {
    params.set("endpoint", endpoint);
  }
  if (method !== undefined) {
    params.set("method", method);
  }
  if (deviceType !== undefined && deviceType !== null) {
    params.set(DEVICE_TYPE_PARAM, String(deviceType));
  }
  const url = `${TIMESERIES_ENDPOINT}?${params.toString()}`;
  return ajaxCall("GET", url, null, QUERY_TIMEOUT_MS) as JQuery.jqXHR<
    SuccessResponse<"queryTimeseries">
  >;
}

/**
 * Fetch the per-category current/previous totals for a window.
 *
 * Example: `fetchSummary({ window: "day" })`
 * issues `GET /api/metrics/query/summary?window=day`.
 */
export function fetchSummary({
  window,
}: {
  window: string;
}): JQuery.jqXHR<SuccessResponse<"querySummary">> {
  const queryString = new URLSearchParams({ window }).toString();
  const url = `${SUMMARY_ENDPOINT}?${queryString}`;
  return ajaxCall("GET", url, null, QUERY_TIMEOUT_MS) as JQuery.jqXHR<
    SuccessResponse<"querySummary">
  >;
}
