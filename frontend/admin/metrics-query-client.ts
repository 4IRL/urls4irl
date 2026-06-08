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
import type { ResourceName } from "../types/metrics-resources.js";

import { ajaxCall } from "../lib/ajax.js";

type MetricsCategory = "api" | "ui" | "domain";
type TimeseriesResolution = "hour" | "day";

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
}: {
  window: string;
  category: MetricsCategory;
  limit?: number;
  resource?: ResourceName | null;
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
}: {
  eventName: string;
  window: string;
  resolution?: TimeseriesResolution;
  endpoint?: string;
  method?: string;
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
