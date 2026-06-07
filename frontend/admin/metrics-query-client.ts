/**
 * Typed AJAX wrappers for the Phase 10 metrics-query endpoints.
 *
 * Each wrapper builds a typed URL query string against the
 * `/api/metrics/query/*` routes and returns a `JQuery.jqXHR<SuccessResponse<...>>`
 * tied to the corresponding `operations` entry in `frontend/types/api.d.ts`.
 *
 * `ajaxCall()` (see `frontend/lib/ajax.ts`) wraps `$.ajax`, which automatically
 * sends the `X-Requested-With: XMLHttpRequest` header for same-origin GETs. The
 * Phase 10 `ajax_required=True` route gate is satisfied by that header, so no
 * manual header injection is needed here.
 */

import type { SuccessResponse } from "../types/api-helpers.d.ts";

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
}: {
  window: string;
  category: MetricsCategory;
  limit?: number;
}): JQuery.jqXHR<SuccessResponse<"queryTop">> {
  const effectiveLimit = limit ?? DEFAULT_TOP_LIMIT;
  const queryString = new URLSearchParams({
    window,
    category,
    limit: String(effectiveLimit),
  }).toString();
  const url = `${TOP_ENDPOINT}?${queryString}`;
  return ajaxCall("GET", url, null, QUERY_TIMEOUT_MS) as JQuery.jqXHR<
    SuccessResponse<"queryTop">
  >;
}

/**
 * Fetch the per-bucket timeseries for a single event over a window.
 *
 * Example: `fetchTimeseries({ eventName: "utub_opened", window: "week", resolution: "day" })`
 * issues `GET /api/metrics/query/timeseries?event_name=utub_opened&window=week&resolution=day`.
 */
export function fetchTimeseries({
  eventName,
  window,
  resolution,
}: {
  eventName: string;
  window: string;
  resolution?: TimeseriesResolution;
}): JQuery.jqXHR<SuccessResponse<"queryTimeseries">> {
  const params = new URLSearchParams({
    event_name: eventName,
    window,
  });
  if (resolution !== undefined) {
    params.set("resolution", resolution);
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
