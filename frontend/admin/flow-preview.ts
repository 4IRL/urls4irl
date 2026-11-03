/**
 * Timing and request state machine for the flow builder's live preview.
 *
 * The builder feeds client-valid drafts to `update()`. A send goes out 300 ms after the
 * last edit and never more often than every 2.5 s; an edit that arrives too soon is
 * held (latest wins) and sent later. Older requests are aborted and their late answers
 * ignored, and each outcome reaches `onState` once.
 */
import type { Schema, SuccessResponse } from "../types/api-helpers.d.ts";

import type { captureSubmitted } from "./flow-builder-state.js";
import {
  BAD_REQUEST_STATUS,
  RATE_LIMITED_STATUS,
} from "./metrics-flow-codes.js";

export const PREVIEW_DEBOUNCE_MS = 300;
export const PREVIEW_MIN_INTERVAL_MS = 2500;

type FlowResponseSchema = Schema<"FlowResponseSchema">;
type Submitted = ReturnType<typeof captureSubmitted>;

export type FlowPreviewState =
  | { kind: "placeholder" }
  | { kind: "updating"; previous: FlowResponseSchema | null }
  | { kind: "result"; response: FlowResponseSchema }
  | { kind: "failed" }
  | { kind: "rate-limited" }
  | {
      kind: "field-errors";
      errors: Record<string, string[]>;
      submitted: Submitted;
    };

interface PreviewRequest {
  body: Schema<"LenientFlowDefinition">;
  window: string;
  submitted: Submitted;
}

interface PendingRequest extends PreviewRequest {
  key: string;
}

interface InFlight {
  key: string;
  xhr: JQuery.jqXHR<SuccessResponse<"previewMetricFlow">>;
  submitted: Submitted;
}

interface Settled {
  key: string;
  response: FlowResponseSchema;
}

interface ErrorBody {
  errors?: Record<string, string[]> | null;
}

export function createFlowPreview({
  send,
  onState,
}: {
  send: (args: {
    body: Schema<"LenientFlowDefinition">;
    window: string;
  }) => JQuery.jqXHR<SuccessResponse<"previewMetricFlow">>;
  onState: (state: FlowPreviewState) => void;
}): {
  update: (request: PreviewRequest) => void;
  invalidate: () => void;
  cancel: () => void;
} {
  let debounceTimer: number | null = null;
  let deferTimer: number | null = null;
  let pending: PendingRequest | null = null;
  let inFlight: InFlight | null = null;
  let settled: Settled | null = null;
  let lastSendStart: number | null = null;
  let lastEmitted: FlowPreviewState | null = null;

  function emit(state: FlowPreviewState): void {
    lastEmitted = state;
    onState(state);
  }

  function clearTimers(): void {
    if (debounceTimer !== null) {
      window.clearTimeout(debounceTimer);
      debounceTimer = null;
    }
    if (deferTimer !== null) {
      window.clearTimeout(deferTimer);
      deferTimer = null;
    }
  }

  /** Drops the in-flight request first so its abort callbacks are ignored. */
  function abortInFlight(): void {
    const old = inFlight;
    inFlight = null;
    old?.xhr.abort();
  }

  function sendPending(): void {
    deferTimer = null;
    const request = pending;
    if (request === null) {
      return;
    }
    pending = null;
    abortInFlight();
    lastSendStart = Date.now();
    const xhr = send({ body: request.body, window: request.window });
    inFlight = { key: request.key, xhr, submitted: request.submitted };
    xhr
      .done((response) => handleDone({ xhr, response }))
      .fail((failed) => handleFail({ xhr, failed }));
  }

  function onDebounce(): void {
    debounceTimer = null;
    if (pending === null) {
      return;
    }
    const wait =
      lastSendStart === null
        ? 0
        : PREVIEW_MIN_INTERVAL_MS - (Date.now() - lastSendStart);
    if (wait <= 0) {
      sendPending();
      return;
    }
    deferTimer = window.setTimeout(sendPending, wait);
  }

  function handleDone({
    xhr,
    response,
  }: {
    xhr: InFlight["xhr"];
    response: FlowResponseSchema;
  }): void {
    if (inFlight === null || inFlight.xhr !== xhr) {
      return;
    }
    settled = { key: inFlight.key, response };
    inFlight = null;
    // A newer draft is already queued: hold the response, keep the card dimmed.
    if (pending === null) {
      emit({ kind: "result", response });
    }
  }

  function handleFail({
    xhr,
    failed,
  }: {
    xhr: InFlight["xhr"];
    failed: JQuery.jqXHR;
  }): void {
    if (inFlight === null || inFlight.xhr !== xhr) {
      return;
    }
    if (failed.readyState === 0 && failed.statusText === "abort") {
      // Aborted from outside the controller: nothing is in flight any more.
      inFlight = null;
      return;
    }
    const { submitted } = inFlight;
    inFlight = null;
    if (pending !== null) {
      return;
    }
    settled = null;
    const body: ErrorBody = failed.responseJSON ?? {};
    const errors = body.errors ?? {};
    if (failed.status === RATE_LIMITED_STATUS) {
      emit({ kind: "rate-limited" });
    } else if (
      failed.status === BAD_REQUEST_STATUS &&
      Object.keys(errors).length > 0
    ) {
      emit({ kind: "field-errors", errors, submitted });
    } else {
      emit({ kind: "failed" });
    }
  }

  function update({
    body,
    window: windowKey,
    submitted,
  }: PreviewRequest): void {
    const key = JSON.stringify({ body, window: windowKey });
    const matchesSettled = settled !== null && settled.key === key;
    const matchesInFlight = inFlight !== null && inFlight.key === key;
    if (matchesSettled || matchesInFlight) {
      clearTimers();
      pending = null;
      if (settled !== null && matchesSettled) {
        abortInFlight();
        const { response } = settled;
        if (
          lastEmitted?.kind !== "result" ||
          lastEmitted.response !== response
        ) {
          emit({ kind: "result", response });
        }
      }
      return;
    }
    pending = { body, window: windowKey, submitted, key };
    if (lastEmitted?.kind !== "updating") {
      emit({ kind: "updating", previous: settled?.response ?? null });
    }
    clearTimers();
    debounceTimer = window.setTimeout(onDebounce, PREVIEW_DEBOUNCE_MS);
  }

  function invalidate(): void {
    clearTimers();
    pending = null;
    abortInFlight();
    settled = null;
    if (lastEmitted?.kind !== "placeholder") {
      emit({ kind: "placeholder" });
    }
  }

  function cancel(): void {
    clearTimers();
    pending = null;
    abortInFlight();
    settled = null;
    lastEmitted = null;
  }

  return { update, invalidate, cancel };
}
