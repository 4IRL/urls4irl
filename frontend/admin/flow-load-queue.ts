import { debug } from "../lib/debug.js";

const log = debug("admin-flow-queue");

export const MAX_FLOWS_IN_FLIGHT = 4;

type IdleCause = "settled" | "dropped";

export interface FlowLoadQueue {
  startFanOut({ ids }: { ids: readonly string[] }): void;
  enqueue({ ids }: { ids: readonly string[] }): void;
  abortAll(): void;
  dropId({ id }: { id: string }): void;
  isCurrent({ id, xhr }: { id: string; xhr: JQuery.jqXHR }): boolean;
  isPending({ id }: { id: string }): boolean;
  isIdle(): boolean;
  drain(): void;
}

/**
 * Capped per-id load queue for the admin Flows tab: at most `maxInFlight`
 * requests run at once, the rest wait in order. A new fan-out aborts and
 * discards everything from the previous one, so stale results never land.
 * `enqueue` instead adds ids that are not already pending without aborting
 * anything (per-card Retry, newly discovered flows); it marks the queue busy so
 * `onIdle` fires once when it drains, and is a no-op when nothing is new.
 *
 * `onIdle` is owned by the end of the outermost internal drain and guarded by
 * a latch (`wasIdle`), so it fires once per busy -> idle flip regardless of
 * nested or synchronous settles. Aborts made by `abortAll`/`startFanOut`
 * remove registry entries before calling `abort()`, so their synchronous
 * `always` callbacks are non-current no-ops.
 */
export function createFlowLoadQueue({
  issue,
  isPaused,
  onSettle,
  onIdle,
  maxInFlight = MAX_FLOWS_IN_FLIGHT,
}: {
  issue: ({ id }: { id: string }) => JQuery.jqXHR;
  isPaused: () => boolean;
  onSettle?: ({ id }: { id: string }) => void;
  onIdle: ({ cause }: { cause: IdleCause }) => void;
  maxInFlight?: number;
}): FlowLoadQueue {
  const registry = new Map<string, JQuery.jqXHR>();
  let waiting: string[] = [];
  let wasIdle = true;
  let draining = false;

  function isIdle(): boolean {
    return registry.size === 0 && waiting.length === 0;
  }

  function isCurrent({ id, xhr }: { id: string; xhr: JQuery.jqXHR }): boolean {
    return registry.get(id) === xhr;
  }

  function isPending({ id }: { id: string }): boolean {
    return registry.has(id) || waiting.includes(id);
  }

  function handleSettle({ id, xhr }: { id: string; xhr: JQuery.jqXHR }): void {
    if (!isCurrent({ id, xhr })) return;
    registry.delete(id);
    if (onSettle) {
      try {
        onSettle({ id });
      } catch (error) {
        log("onSettle threw", error);
      }
    }
    drainWithCause({ cause: "settled" });
  }

  function drainWithCause({ cause }: { cause: IdleCause }): void {
    if (draining) return;
    draining = true;
    try {
      while (!isPaused() && registry.size < maxInFlight && waiting.length > 0) {
        const id = waiting.shift() as string;
        let xhr: JQuery.jqXHR;
        try {
          xhr = issue({ id });
        } catch (error) {
          log("issue threw; dropping id", id, error);
          continue;
        }
        registry.set(id, xhr);
        xhr.always(() => handleSettle({ id, xhr }));
      }
    } finally {
      draining = false;
    }
    if (isIdle() && !wasIdle) {
      wasIdle = true;
      onIdle({ cause });
    }
  }

  function abortAll(): void {
    waiting = [];
    const entries = Array.from(registry.entries());
    for (const [id] of entries) registry.delete(id);
    for (const [, xhr] of entries) xhr.abort();
    wasIdle = true;
  }

  function startFanOut({ ids }: { ids: readonly string[] }): void {
    abortAll();
    wasIdle = false;
    for (const id of ids) {
      if (!isPending({ id })) waiting.push(id);
    }
    drainWithCause({ cause: "settled" });
  }

  function enqueue({ ids }: { ids: readonly string[] }): void {
    let added = false;
    for (const id of ids) {
      if (!isPending({ id })) {
        waiting.push(id);
        added = true;
      }
    }
    if (!added) return;
    wasIdle = false;
    drainWithCause({ cause: "settled" });
  }

  function dropId({ id }: { id: string }): void {
    if (!isPending({ id })) return;
    const xhr = registry.get(id);
    registry.delete(id);
    if (xhr) xhr.abort();
    waiting = waiting.filter((waitingId) => waitingId !== id);
    drainWithCause({ cause: "dropped" });
  }

  return {
    startFanOut,
    enqueue,
    abortAll,
    dropId,
    isCurrent,
    isPending,
    isIdle,
    drain: () => drainWithCause({ cause: "settled" }),
  };
}
