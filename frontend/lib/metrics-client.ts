/* eslint-disable @typescript-eslint/no-unused-vars -- scaffolding; identifiers consumed by emit/flush/init logic in follow-up commits */
import type { Schema } from "../types/api-helpers.d.ts";

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
  _buffer.push({ event_name: event, dimensions: dimensions ?? null });
  if (_buffer.length >= BATCH_THRESHOLD) {
    void flush();
  }
}

export async function flush(): Promise<void> {
  if (_inFlightBatchId === null || _inFlightEvents === null) {
    if (_buffer.length === 0) return;
    if (_inFlightBatchId !== null || _retryTimerId !== null) return;
    _inFlightEvents = _buffer.splice(0, MAX_BATCH_SIZE);
    _inFlightBatchId = crypto.randomUUID();
  }

  const payload: MetricsIngestRequest = {
    events: _inFlightEvents,
    batch_id: _inFlightBatchId,
    csrf_token: null,
  };

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
    if (response.ok || response.status === 200) {
      _clearInFlight();
    }
    /* error branches land in Step 8 */
  } catch {
    /* error branches land in Step 8 */
  }
}

export function initMetricsClient(): void {
  if (_intervalId !== null) return;
  _intervalId = setInterval(() => {
    void flush();
  }, FLUSH_INTERVAL_MS);
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
  _onVisibilityChange = null;
  _onPageHide = null;
  _csrfDeadForLifetime = false;
}
