import type { Schema } from "../types/api-helpers.d.ts";

import { APP_CONFIG } from "./config.js";

type MetricsIngestEvent = Schema<"MetricsIngestEvent">;
type MetricsIngestRequest = Schema<"MetricsIngestRequest">;

export type UIEventName = MetricsIngestEvent["event_name"];
export type EmitDimensions = Record<string, string | number | boolean>;

const METRICS_INGEST_URL = "/api/metrics" as const;
const DEDUPE_COOLDOWN_MS = 1000;
const FLUSH_INTERVAL_MS = 60000;
const BATCH_THRESHOLD = 50;
const MAX_BATCH_SIZE = 100;
const RETRY_MAX_ATTEMPTS = 3;
const RETRY_BASE_BACKOFF_MS = 1000;

let _buffer: MetricsIngestEvent[] = [];
let _dedupe: Map<string, number> = new Map();
let _inFlightBatchId: string | null = null;
let _inFlightEvents: MetricsIngestEvent[] | null = null;
let _postInFlight: boolean = false;
let _retryAttempts: number = 0;
let _retryTimerId: ReturnType<typeof setTimeout> | null = null;
let _intervalId: ReturnType<typeof setInterval> | null = null;
let _csrfDeadForLifetime: boolean = false;
let _onVisibilityChange: (() => void) | null = null;
let _onPageHide: (() => void) | null = null;

function getCsrfToken(): string | null {
  return (
    document.querySelector<HTMLMetaElement>("meta[name=csrf-token]")?.content ??
    null
  );
}

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
    const droppedCount = _inFlightEvents?.length ?? 0;
    _clearInFlight();
    console.warn("metrics: retry cap exhausted, dropping batch", {
      events: droppedCount,
    });
    return;
  }
  const backoffMs = RETRY_BASE_BACKOFF_MS * 2 ** (_retryAttempts - 1);
  _retryTimerId = setTimeout(() => {
    _retryTimerId = null;
    void flush();
  }, backoffMs);
}

function filterDimensions(
  dimensions: EmitDimensions | undefined,
): EmitDimensions | null {
  if (dimensions === undefined) return null;
  const allowed = new Set<string>(APP_CONFIG.constants.DIMENSION_KEYS);
  const filtered: EmitDimensions = {};
  for (const key of Object.keys(dimensions)) {
    if (allowed.has(key)) {
      filtered[key] = dimensions[key];
    }
  }
  return Object.keys(filtered).length === 0 ? null : filtered;
}

function pruneDedupeMap(now: number): void {
  for (const [key, timestamp] of _dedupe) {
    if (now - timestamp >= DEDUPE_COOLDOWN_MS) {
      _dedupe.delete(key);
    }
  }
}

export function emit(event: UIEventName, dimensions?: EmitDimensions): void {
  const now = Date.now();
  pruneDedupeMap(now);
  const dedupeKey = `${event}|${JSON.stringify(dimensions ?? null)}`;
  const lastEmittedAt = _dedupe.get(dedupeKey);
  if (lastEmittedAt !== undefined && now - lastEmittedAt < DEDUPE_COOLDOWN_MS) {
    return;
  }
  _dedupe.set(dedupeKey, now);
  _buffer.push({ event_name: event, dimensions: filterDimensions(dimensions) });
  if (_buffer.length >= BATCH_THRESHOLD) {
    void flush();
  }
}

export async function flush(): Promise<void> {
  if (_postInFlight) return;
  if (_inFlightBatchId === null || _inFlightEvents === null) {
    if (_buffer.length === 0) return;
    if (_retryTimerId !== null) return;
    if (_csrfDeadForLifetime) return;
    _inFlightEvents = _buffer.splice(0, MAX_BATCH_SIZE);
    _inFlightBatchId = crypto.randomUUID();
  }

  const payload: MetricsIngestRequest = {
    events: _inFlightEvents,
    batch_id: _inFlightBatchId,
    csrf_token: null,
  };

  _postInFlight = true;
  try {
    const response = await fetch(METRICS_INGEST_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCsrfToken() ?? "",
      },
      body: JSON.stringify(payload),
      credentials: "same-origin",
      keepalive: false,
    });
    _postInFlight = false;
    if (response.ok || response.status === 200) {
      _clearInFlight();
      return;
    }
    if (response.status === 400) {
      console.warn("metrics: 400 — dropping batch");
      _clearInFlight();
      return;
    }
    if (response.status === 403) {
      _csrfDeadForLifetime = true;
      console.warn("metrics: 403 — dropping batch, CSRF dead for lifetime");
      _clearInFlight();
      return;
    }
    if (response.status === 429 || response.status >= 500) {
      _scheduleRetry();
      return;
    }
    _clearInFlight();
  } catch {
    _postInFlight = false;
    _scheduleRetry();
  }
}

function flushBeacon(): void {
  if (_csrfDeadForLifetime) return;
  if (_buffer.length === 0) return;
  if (_inFlightBatchId !== null) return;
  const beaconEvents = _buffer.splice(0, MAX_BATCH_SIZE);
  const beaconBatchId = crypto.randomUUID();
  const payload: MetricsIngestRequest = {
    events: beaconEvents,
    batch_id: beaconBatchId,
    csrf_token: getCsrfToken(),
  };
  const serialized = JSON.stringify(payload);
  try {
    const blob = new Blob([serialized], { type: "application/json" });
    const beaconEnqueued =
      typeof navigator.sendBeacon === "function"
        ? navigator.sendBeacon(METRICS_INGEST_URL, blob)
        : false;
    if (!beaconEnqueued) {
      void fetch(METRICS_INGEST_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: serialized,
        credentials: "same-origin",
        keepalive: true,
      });
    }
  } catch {
    /* telemetry must never break page unload */
  }
}

export function initMetricsClient(): void {
  if (_intervalId !== null) return;
  _intervalId = setInterval(() => {
    void flush();
  }, FLUSH_INTERVAL_MS);
  _onVisibilityChange = () => {
    if (document.visibilityState === "hidden") {
      flushBeacon();
    }
  };
  _onPageHide = () => {
    flushBeacon();
  };
  document.addEventListener("visibilitychange", _onVisibilityChange);
  window.addEventListener("pagehide", _onPageHide);
}

export function resetMetricsClient(): void {
  _buffer.length = 0;
  _dedupe.clear();
  _clearInFlight();
  if (_retryTimerId !== null) {
    clearTimeout(_retryTimerId);
    _retryTimerId = null;
  }
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
  _csrfDeadForLifetime = false;
}
