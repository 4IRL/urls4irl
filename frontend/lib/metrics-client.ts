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

export function emit(_event: UIEventName, _dimensions?: EmitDimensions): void {
  /* implementation pending */
}

export function flush(): void {
  /* implementation pending */
}

export function initMetricsClient(): void {
  /* implementation pending */
}

export function resetMetricsClient(): void {
  /* implementation pending */
}
