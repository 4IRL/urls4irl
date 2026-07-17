import type { Schema } from "../types/api-helpers.d.ts";
import type { UIEventDimensions } from "../types/metrics-dimensions.d.ts";
import type { UIEventName } from "../types/metrics-events.js";

import { UI_EVENTS } from "../types/metrics-events.js";
import { APP_CONFIG } from "./config.js";
import { debug } from "./debug.js";
import { getDeviceType, initDeviceTypeListener } from "./device-type.js";
import { clearOpenForm, getOpenForm } from "./modal-tracking.js";

const log = debug("metrics");

type MetricsIngestEvent = Schema<"MetricsIngestEvent">;
type MetricsIngestRequest = Schema<"MetricsIngestRequest">;

// Re-export `UIEventName` from the codegen module so `emit()` callers continue
// to import it from `metrics-client.js`. The const object in
// `metrics-events.ts` is now the single source of truth for both the wire
// strings and the type.
export type { UIEventDimensions, UIEventName };
export type EmitDimensions = Record<string, string | number | boolean>;

// The caller's view of an event's dimensions: the Pydantic shape minus
// `device_type` (which `emit()` auto-injects from `getDeviceType()`).
export type CallerDimensions<EventT extends UIEventName> = Omit<
  UIEventDimensions[EventT],
  "device_type"
>;

// The single args-object accepted by `emit()`. `event` is the discriminator;
// the rest of the keys are the flat caller-supplied dimensions for that event.
export type EmitArgs<EventT extends UIEventName> = {
  event: EventT;
} & CallerDimensions<EventT>;

const METRICS_INGEST_URL = "/api/metrics" as const;
const METRICS_INGEST_BEACON_URL =
  `${METRICS_INGEST_URL}?transport=beacon` as const;
const DEDUPE_COOLDOWN_MS = 1000;
const FLUSH_INTERVAL_MS = 60000;
const BATCH_THRESHOLD = 50;
const MAX_BATCH_SIZE = 100;
const RETRY_MAX_ATTEMPTS = 3;
const RETRY_BASE_BACKOFF_MS = 1000;

const _allowedDimensionKeys = new Set<string>(
  APP_CONFIG.constants.DIMENSION_KEYS,
);

let _buffer: MetricsIngestEvent[] = [];
let _dedupe: Map<string, number> = new Map();
let _inFlightBatchId: string | null = null;
let _inFlightEvents: MetricsIngestEvent[] | null = null;
let _postInFlight: boolean = false;
let _retryAttempts: number = 0;
let _retryTimerId: ReturnType<typeof setTimeout> | null = null;
let _intervalId: ReturnType<typeof setInterval> | null = null;
let _onVisibilityChange: (() => void) | null = null;
let _onPageHide: (() => void) | null = null;

function _clearInFlight(): void {
  _inFlightBatchId = null;
  _inFlightEvents = null;
  _retryAttempts = 0;
  _postInFlight = false;
  if (_retryTimerId !== null) {
    clearTimeout(_retryTimerId);
    _retryTimerId = null;
  }
}

function _scheduleRetry(): void {
  _retryAttempts += 1;
  if (_retryAttempts >= RETRY_MAX_ATTEMPTS) {
    log("retry cap exhausted — dropping batch permanently", {
      batchId: _inFlightBatchId,
      eventsLost: _inFlightEvents?.length,
      attempts: _retryAttempts,
    });
    _clearInFlight();
    return;
  }
  const backoffMs = RETRY_BASE_BACKOFF_MS * 2 ** (_retryAttempts - 1);
  log("retry scheduled", {
    attempt: _retryAttempts,
    backoffMs,
    batchId: _inFlightBatchId,
  });
  _retryTimerId = setTimeout(() => {
    _retryTimerId = null;
    void flush();
  }, backoffMs);
}

function filterDimensions(dimensions: EmitDimensions): EmitDimensions {
  const filtered: EmitDimensions = {};
  for (const key of Object.keys(dimensions)) {
    if (_allowedDimensionKeys.has(key)) {
      filtered[key] = dimensions[key];
    }
  }
  return filtered;
}

function pruneDedupeMap(now: number): void {
  for (const [key, timestamp] of _dedupe) {
    if (now - timestamp >= DEDUPE_COOLDOWN_MS) {
      _dedupe.delete(key);
    }
  }
}

// `crypto.randomUUID()` requires a secure context (HTTPS or localhost). In
// non-secure HTTP origins (e.g. dev stacks served from a hostname like
// `http://web:8080`), `crypto.randomUUID` is `undefined` and calling it
// throws a TypeError that aborts the in-flight flush, so the buffered
// events are never POSTed. The shape only needs to be unique-per-page-load
// enough for the ingest route's `reserve_batch` dedupe key — full RFC 4122
// compliance is not required. Fall back to a `getRandomValues`-based v4
// shape when the native helper is missing.
function generateBatchId(): string {
  if (typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (byteValue) =>
    byteValue.toString(16).padStart(2, "0"),
  ).join("");
  return (
    hex.slice(0, 8) +
    "-" +
    hex.slice(8, 12) +
    "-" +
    hex.slice(12, 16) +
    "-" +
    hex.slice(16, 20) +
    "-" +
    hex.slice(20, 32)
  );
}

// `emit()` takes a single args object: `{ event, ...dimensions }`. For events
// whose `CallerDimensions` is `{}` (i.e. only `device_type` in the Pydantic
// model), the intersection adds nothing and the caller passes just
// `{ event: UI_EVENTS.UI_X }`. For events with caller-supplied dims, the keys
// are required flat on the args object — a typo on any dim key fails `tsc`.
export function emit<EventT extends UIEventName>(args: EmitArgs<EventT>): void {
  const { event, ...dimensions } = args;
  // performance.now() is monotonic high-resolution time relative to page navigation start;
  // it cannot be persisted across page loads and is safe from NTP/clock jumps.
  const now = performance.now();
  // Auto-inject device_type as the FIRST step so it (a) survives the allow-list
  // filter, (b) participates in the dedupe-key bucket (mobile vs desktop emits
  // for the same event/dims are distinct), and (c) is impossible for callers
  // to forget. Caller-supplied dimensions win via spread order.
  const dimensionsWithDevice: EmitDimensions = {
    device_type: getDeviceType(),
    ...(dimensions as EmitDimensions),
  };
  pruneDedupeMap(now);
  const dedupeKey = `${event}|${JSON.stringify(dimensionsWithDevice)}`;
  const lastEmittedAt = _dedupe.get(dedupeKey);
  if (lastEmittedAt !== undefined && now - lastEmittedAt < DEDUPE_COOLDOWN_MS) {
    log("dedupe drop", { event, msSinceLastEmit: now - lastEmittedAt });
    return;
  }
  _dedupe.set(dedupeKey, now);
  _buffer.push({
    event_name: event,
    dimensions: filterDimensions(dimensionsWithDevice),
  });
  if (_buffer.length >= BATCH_THRESHOLD) {
    log("batch threshold crossed — flushing", { bufferSize: _buffer.length });
    void flush();
  }
}

export async function flush(): Promise<void> {
  if (_postInFlight) {
    log("flush skipped — POST already in flight", {
      batchId: _inFlightBatchId,
    });
    return;
  }
  if (_retryTimerId !== null) {
    log("flush skipped — retry pending", { attempts: _retryAttempts });
    return;
  }
  if (_inFlightBatchId === null || _inFlightEvents === null) {
    if (_buffer.length === 0) return;
    _inFlightEvents = _buffer.splice(0, MAX_BATCH_SIZE);
    _inFlightBatchId = generateBatchId();
  }

  const payload: MetricsIngestRequest = {
    events: _inFlightEvents,
    batch_id: _inFlightBatchId,
  };

  _postInFlight = true;
  try {
    const response = await fetch(METRICS_INGEST_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
      credentials: "same-origin",
    });
    _postInFlight = false;
    if (response.ok) {
      _clearInFlight();
      return;
    }
    if (response.status === 400) {
      log("400 from /api/metrics — dropping malformed batch", {
        batchId: _inFlightBatchId,
        events: _inFlightEvents?.length,
      });
      _clearInFlight();
      return;
    }
    if (response.status === 429 || response.status >= 500) {
      log("retryable error from /api/metrics", {
        status: response.status,
        batchId: _inFlightBatchId,
      });
      _scheduleRetry();
      return;
    }
    log("unexpected status from /api/metrics — dropping batch", {
      status: response.status,
      batchId: _inFlightBatchId,
    });
    _clearInFlight();
  } catch (err) {
    _postInFlight = false;
    log("fetch threw — scheduling retry", {
      batchId: _inFlightBatchId,
      error: String(err),
    });
    _scheduleRetry();
  }
}

function flushBeacon(): void {
  if (_buffer.length === 0) return;
  if (_inFlightBatchId !== null) {
    log("beacon skipped — flush already in flight", {
      batchId: _inFlightBatchId,
    });
    return;
  }
  const beaconEvents = _buffer.splice(0, MAX_BATCH_SIZE);
  const beaconBatchId = generateBatchId();
  const payload: MetricsIngestRequest = {
    events: beaconEvents,
    batch_id: beaconBatchId,
  };
  const serialized = JSON.stringify(payload);
  try {
    const blob = new Blob([serialized], { type: "application/json" });
    const beaconEnqueued =
      typeof navigator.sendBeacon === "function"
        ? navigator.sendBeacon(METRICS_INGEST_BEACON_URL, blob)
        : false;
    if (!beaconEnqueued) {
      log("sendBeacon rejected — falling back to keepalive fetch", {
        batchId: beaconBatchId,
        events: beaconEvents.length,
      });
      void fetch(METRICS_INGEST_BEACON_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: serialized,
        credentials: "same-origin",
        keepalive: true,
      });
    }
  } catch (err) {
    log("beacon path threw on unload", { error: String(err) });
    /* telemetry must never break page unload */
  }
}

export function initMetricsClient(): void {
  if (_intervalId !== null) {
    log("initMetricsClient skipped — already initialized");
    return;
  }
  initDeviceTypeListener();
  _intervalId = setInterval(() => {
    void flush();
  }, FLUSH_INTERVAL_MS);
  log("metrics client initialized — flush interval started", {
    intervalMs: FLUSH_INTERVAL_MS,
  });
  _onVisibilityChange = () => {
    if (document.visibilityState === "hidden") {
      log("visibility hidden — triggering beacon flush", {
        bufferedEvents: _buffer.length,
      });
      flushBeacon();
    }
  };
  _onPageHide = () => {
    // A form left open at navigation time is an abandoned form. Emit a
    // navigation cancel for it (into the buffer) before the beacon flush so
    // the funnel's "unknown" residual shrinks. Auth forms (login/register)
    // carry their own event with a `form` dim; all other forms use the
    // generic UI_FORM_CANCEL.
    const openFormId = getOpenForm();
    if (openFormId === "login" || openFormId === "register") {
      emit({
        event: UI_EVENTS.UI_AUTH_CANCEL,
        form: openFormId,
        trigger: "navigation" as const,
      });
    } else if (openFormId !== null) {
      emit({
        event: UI_EVENTS.UI_FORM_CANCEL,
        form: openFormId,
        trigger: "navigation" as const,
      });
    }
    flushBeacon();
  };
  document.addEventListener("visibilitychange", _onVisibilityChange);
  window.addEventListener("pagehide", _onPageHide);
}

export function resetMetricsClient(): void {
  log("resetMetricsClient called", {
    bufferedEvents: _buffer.length,
    intervalActive: _intervalId !== null,
  });
  clearOpenForm();
  _buffer.length = 0;
  _dedupe.clear();
  _clearInFlight();
  if (_intervalId !== null) {
    clearInterval(_intervalId);
    _intervalId = null;
  }
  if (_onVisibilityChange !== null) {
    document.removeEventListener("visibilitychange", _onVisibilityChange);
    _onVisibilityChange = null;
  }
  if (_onPageHide !== null) {
    window.removeEventListener("pagehide", _onPageHide);
    _onPageHide = null;
  }
}
