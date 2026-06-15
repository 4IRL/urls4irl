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
import type { FlowId } from "../types/metrics-flows.js";
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
const GROUPED_TIMESERIES_ENDPOINT = "/api/metrics/query/grouped-timeseries";
const SUMMARY_ENDPOINT = "/api/metrics/query/summary";
const FLOW_ENDPOINT = "/api/metrics/query/flow";
const GAUGES_TIMESERIES_ENDPOINT = "/api/metrics/query/gauges/timeseries";

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
 * Fetch a grouped timeseries — one row per `(bucket × dim-tuple)`. Used by
 * the Pipeline Health card to produce a stacked-bar series grouped by
 * `batch_size_bucket × transport × device_type`. The request schema accepts
 * `group_by` as a repeated query parameter (Pydantic list-of-strings via
 * Flask's `request.args.getlist`); `URLSearchParams.append` emits one
 * `group_by=<field>` pair per entry.
 *
 * Example:
 *   fetchGroupedTimeseries({
 *     eventName: "api_metrics_ingest_batch",
 *     groupBy: ["batch_size_bucket", "transport", "device_type"],
 *     window: "day",
 *   })
 * issues `GET /api/metrics/query/grouped-timeseries`
 * with `?event_name=api_metrics_ingest_batch&group_by=batch_size_bucket&group_by=transport&group_by=device_type&window=day`.
 *
 * `device_type` is NOT supplied as a query parameter — the dim is injected
 * by the metrics middleware from the request's User-Agent header. Including
 * the dim as a `group_by` field selects on it server-side without needing
 * the client to know its value.
 */
export function fetchGroupedTimeseries({
  eventName,
  groupBy,
  window,
  resolution,
}: {
  eventName: string;
  groupBy: readonly string[];
  window: string;
  resolution?: TimeseriesResolution;
}): JQuery.jqXHR<SuccessResponse<"queryGroupedTimeseries">> {
  const params = new URLSearchParams({
    event_name: eventName,
    window,
  });
  for (const groupByField of groupBy) {
    params.append("group_by", groupByField);
  }
  if (resolution !== undefined) {
    params.set("resolution", resolution);
  }
  const url = `${GROUPED_TIMESERIES_ENDPOINT}?${params.toString()}`;
  return ajaxCall("GET", url, null, QUERY_TIMEOUT_MS) as JQuery.jqXHR<
    SuccessResponse<"queryGroupedTimeseries">
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

/**
 * Fetch one assembled conversion funnel for a window. The server loops over the
 * flow's `FlowStep` list and fans out per-step `grouped_count_scalar` /
 * `grouped_count_by` calls, so the
 * client only needs the flow id + window.
 *
 * Example: `fetchFlow({ flowId: "add_url_to_utub", window: "day" })`
 * issues `GET /api/metrics/query/flow?flow_id=add_url_to_utub&window=day`.
 */
export function fetchFlow({
  flowId,
  window,
}: {
  flowId: FlowId;
  window: string;
}): JQuery.jqXHR<SuccessResponse<"queryFlow">> {
  const queryString = new URLSearchParams({
    flow_id: flowId,
    window,
  }).toString();
  const url = `${FLOW_ENDPOINT}?${queryString}`;
  return ajaxCall("GET", url, null, QUERY_TIMEOUT_MS) as JQuery.jqXHR<
    SuccessResponse<"queryFlow">
  >;
}

/**
 * Fetch every gauge's windowed series in ONE batched request — the response
 * carries one entry per gauge, each folding in its own `kind`/`description`
 * metadata, so all gauge data the dashboard needs comes from this single
 * endpoint. There is NO `name` query param: the endpoint is batched and
 * returns all gauges.
 *
 * `window` is typed `string` (not `MetricsWindow`) to avoid a circular import —
 * `MetricsWindow` lives in `metrics-dashboard.ts`, which already imports from
 * this module; the call site passes `_currentWindow` (a `MetricsWindow`, which
 * is assignable to `string`), mirroring `fetchTimeseries`.
 *
 * Example: `fetchGaugesTimeseries({ window: "day" })`
 * issues `GET /api/metrics/query/gauges/timeseries?window=day`.
 */
export function fetchGaugesTimeseries({
  window,
  start,
  end,
}: {
  window?: string;
  start?: string;
  end?: string;
}): JQuery.jqXHR<SuccessResponse<"queryGaugesTimeseries">> {
  const params = new URLSearchParams();
  if (window !== undefined) {
    params.set("window", window);
  }
  if (start !== undefined) {
    params.set("start", start);
  }
  if (end !== undefined) {
    params.set("end", end);
  }
  const url = `${GAUGES_TIMESERIES_ENDPOINT}?${params.toString()}`;
  return ajaxCall("GET", url, null, QUERY_TIMEOUT_MS) as JQuery.jqXHR<
    SuccessResponse<"queryGaugesTimeseries">
  >;
}
