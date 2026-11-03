import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  PREVIEW_DEBOUNCE_MS,
  PREVIEW_MIN_INTERVAL_MS,
  createFlowPreview,
  type FlowPreviewState,
} from "../flow-preview.js";

interface Deferred {
  xhr: JQuery.jqXHR;
  abort: ReturnType<typeof vi.fn>;
  resolve: (response?: unknown) => void;
  /** Delivers a response even after abort (one already in the network stack). */
  forceResolve: (response?: unknown) => void;
  forceReject: (args?: { status?: number }) => void;
  reject: (args?: {
    status?: number;
    readyState?: number;
    statusText?: string;
    responseJSON?: unknown;
  }) => void;
}

function makeDeferred(): Deferred {
  const doneCallbacks: Array<(response: unknown) => void> = [];
  const failCallbacks: Array<(xhr: unknown) => void> = [];
  let settled = false;
  const fake = {
    status: 0,
    readyState: 1,
    statusText: "",
    responseJSON: undefined as unknown,
    done: (callback: (response: unknown) => void) => {
      doneCallbacks.push(callback);
      return fake;
    },
    fail: (callback: (xhr: unknown) => void) => {
      failCallbacks.push(callback);
      return fake;
    },
    abort: vi.fn(() => {
      if (settled) return;
      settled = true;
      fake.readyState = 0;
      fake.statusText = "abort";
      failCallbacks.forEach((callback) => callback(fake));
    }),
  };
  return {
    xhr: fake as unknown as JQuery.jqXHR,
    abort: fake.abort,
    resolve: (response = { steps: [] }) => {
      if (settled) return;
      settled = true;
      fake.status = 200;
      fake.readyState = 4;
      doneCallbacks.forEach((callback) => callback(response));
    },
    forceResolve: (response = { steps: [] }) => {
      fake.status = 200;
      fake.readyState = 4;
      doneCallbacks.forEach((callback) => callback(response));
    },
    forceReject: ({ status = 500 } = {}) => {
      fake.status = status;
      fake.readyState = 4;
      fake.statusText = "error";
      failCallbacks.forEach((callback) => callback(fake));
    },
    reject: ({
      status = 500,
      readyState = 4,
      statusText = "error",
      responseJSON = undefined,
    } = {}) => {
      if (settled) return;
      settled = true;
      fake.status = status;
      fake.readyState = readyState;
      fake.statusText = statusText;
      fake.responseJSON = responseJSON;
      failCallbacks.forEach((callback) => callback(fake));
    },
  };
}

const SUBMITTED = [{ key: 1, filterKeys: [], breakdownFilterKeys: [] }];

function req(name: string) {
  return {
    body: { display_name: "Preview", steps: [name] } as never,
    window: "7d",
    submitted: SUBMITTED,
  };
}

function resp(tag: string) {
  return { steps: [], tag } as never;
}

describe("createFlowPreview", () => {
  let sends: Array<{ body: unknown; window: string; deferred: Deferred }>;
  let states: FlowPreviewState[];
  let preview: ReturnType<typeof createFlowPreview>;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(100000);
    sends = [];
    states = [];
    preview = createFlowPreview({
      send: ({ body, window }) => {
        const deferred = makeDeferred();
        sends.push({ body, window, deferred });
        return deferred.xhr as never;
      },
      onState: (state) => states.push(state),
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  const kinds = () => states.map((state) => state.kind);

  async function settleResult(name: string) {
    preview.update(req(name));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    sends[sends.length - 1].deferred.resolve(resp(name));
  }

  it("collapses three updates inside the debounce into one send", async () => {
    preview.update(req("a"));
    await vi.advanceTimersByTimeAsync(100);
    preview.update(req("b"));
    await vi.advanceTimersByTimeAsync(100);
    preview.update(req("c"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    expect(sends).toHaveLength(1);
    expect(sends[0].body).toEqual(req("c").body);
  });

  it("defers a too-soon send and sends the newest body", async () => {
    preview.update(req("a"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    expect(sends).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(700);
    preview.update(req("b"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    preview.update(req("c"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    expect(sends).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
    expect(sends).toHaveLength(2);
    expect(sends[1].body).toEqual(req("c").body);
    expect(sends[0].deferred.abort).toHaveBeenCalled();
  });

  it("emits updating once and no settled state until the response", async () => {
    preview.update(req("a"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    preview.update(req("b"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    expect(kinds()).toEqual(["updating"]);
    sends[0].deferred.resolve(resp("x"));
    expect(kinds()).toEqual(["updating"]);
  });

  it("ignores a late response from a superseded xhr", async () => {
    preview.update(req("a"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    preview.update(req("b"));
    await vi.advanceTimersByTimeAsync(
      PREVIEW_MIN_INTERVAL_MS + PREVIEW_DEBOUNCE_MS,
    );
    expect(sends).toHaveLength(2);
    sends[1].deferred.resolve(resp("b"));
    sends[0].deferred.forceResolve(resp("a"));
    sends[0].deferred.forceReject();
    const last = states[states.length - 1];
    expect(last).toEqual({ kind: "result", response: resp("b") });
    expect(kinds()).toEqual(["updating", "result"]);
  });

  it("ignores a late response that arrives after the newer send started", async () => {
    preview.update(req("a"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    preview.update(req("b"));
    await vi.advanceTimersByTimeAsync(
      PREVIEW_MIN_INTERVAL_MS + PREVIEW_DEBOUNCE_MS,
    );
    sends[0].deferred.forceResolve(resp("a"));
    expect(kinds()).toEqual(["updating"]);
  });

  it("pins the debounce and interval boundaries", async () => {
    preview.update(req("a"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS - 1);
    expect(sends).toHaveLength(0);
    await vi.advanceTimersByTimeAsync(1);
    expect(sends).toHaveLength(1);
    preview.update(req("b"));
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS - 1);
    expect(sends).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(sends).toHaveLength(2);
  });

  it("a Retry waits out the interval and shows updating with previous null", async () => {
    preview.update(req("a"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    sends[0].deferred.reject({ status: 500 });
    preview.update(req("a"));
    expect(states[states.length - 1]).toEqual({
      kind: "updating",
      previous: null,
    });
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    expect(sends).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
    expect(sends).toHaveLength(2);
  });

  it("classifies a timeout and a 400 without errors as failed", async () => {
    preview.update(req("a"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    sends[0].deferred.reject({
      status: 0,
      readyState: 0,
      statusText: "timeout",
    });
    expect(states[states.length - 1]).toEqual({ kind: "failed" });
    preview.update(req("a"));
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
    sends[1].deferred.reject({ status: 400, responseJSON: {} });
    expect(states[states.length - 1]).toEqual({ kind: "failed" });
  });

  it.each([
    ["rate-limited", { status: 429 }],
    ["field-errors", { status: 400, responseJSON: { errors: { a: ["b"] } } }],
    ["failed", { status: 500 }],
  ])(
    "a revert after %s sends again and never re-emits the old result",
    async (_n, args) => {
      await settleResult("x");
      await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
      preview.update(req("y"));
      await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
      sends[1].deferred.reject(args);
      states.length = 0;
      preview.update(req("x"));
      await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
      expect(sends).toHaveLength(3);
      expect(kinds()).toEqual(["updating"]);
    },
  );

  it.each([
    ["500", { status: 500 }],
    ["400", { status: 400, responseJSON: { errors: { a: ["b"] } } }],
  ])("discards a held-window late %s with no emission", async (_n, args) => {
    preview.update(req("x"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    preview.update(req("y"));
    sends[0].deferred.reject(args);
    expect(kinds()).toEqual(["updating"]);
  });

  it("invalidate during deferral and during flight clears the dedupe key", async () => {
    preview.update(req("a"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    preview.invalidate();
    expect(sends[0].deferred.abort).toHaveBeenCalled();
    preview.update(req("a"));
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
    expect(sends).toHaveLength(2);
    preview.update(req("b"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    expect(sends).toHaveLength(2);
    preview.invalidate();
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS * 2);
    expect(sends).toHaveLength(2);
    expect(states[states.length - 1]).toEqual({ kind: "placeholder" });
  });

  it.each([
    ["rate-limited", { status: 429 }, { kind: "rate-limited" }],
    [
      "field-errors",
      { status: 400, responseJSON: { errors: { "steps.0.x": ["bad"] } } },
      {
        kind: "field-errors",
        errors: { "steps.0.x": ["bad"] },
        submitted: SUBMITTED,
      },
    ],
    ["500", { status: 500 }, { kind: "failed" }],
    [
      "network error",
      { status: 0, readyState: 0, statusText: "error" },
      { kind: "failed" },
    ],
  ])(
    "classifies %s and a repeat update sends again",
    async (_n, args, state) => {
      preview.update(req("a"));
      await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
      sends[0].deferred.reject(args);
      expect(states[states.length - 1]).toEqual(state);
      preview.update(req("a"));
      await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
      expect(sends).toHaveLength(2);
    },
  );

  it("emits nothing for a real abort", async () => {
    preview.update(req("a"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    sends[0].deferred.reject({
      status: 0,
      readyState: 0,
      statusText: "abort",
    });
    expect(kinds()).toEqual(["updating"]);
  });

  it("invalidate aborts, clears timers and emits placeholder", async () => {
    preview.update(req("a"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    preview.update(req("b"));
    preview.invalidate();
    expect(sends[0].deferred.abort).toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS * 2);
    expect(sends).toHaveLength(1);
    expect(kinds()).toEqual(["updating", "placeholder"]);
  });

  it("cancel clears everything with zero emissions", async () => {
    preview.update(req("a"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    preview.update(req("b"));
    const before = states.length;
    preview.cancel();
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS * 2);
    expect(sends).toHaveLength(1);
    expect(sends[0].deferred.abort).toHaveBeenCalled();
    expect(states).toHaveLength(before);
  });

  it("dedupes on body and window but a changed window sends", async () => {
    await settleResult("a");
    preview.update(req("a"));
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
    expect(sends).toHaveLength(1);
    preview.update({ ...req("a"), window: "30d" });
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
    expect(sends).toHaveLength(2);
  });

  it("revert inside the debounce re-emits the settled result", async () => {
    await settleResult("x");
    preview.update(req("y"));
    await vi.advanceTimersByTimeAsync(100);
    preview.update(req("x"));
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
    expect(sends).toHaveLength(1);
    expect(kinds()).toEqual(["updating", "result", "updating", "result"]);
  });

  it("revert to the in-flight key clears the deferral and sends nothing", async () => {
    preview.update(req("x"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    preview.update(req("y"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    preview.update(req("x"));
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS * 2);
    expect(sends).toHaveLength(1);
    expect(kinds()).toEqual(["updating"]);
  });

  it("previous is null after failure, 429, 400 and invalidate", async () => {
    const cases: Array<() => void> = [
      () => sends[sends.length - 1].deferred.reject({ status: 500 }),
      () => sends[sends.length - 1].deferred.reject({ status: 429 }),
      () =>
        sends[sends.length - 1].deferred.reject({
          status: 400,
          responseJSON: { errors: { a: ["b"] } },
        }),
      () => preview.invalidate(),
    ];
    for (const settle of cases) {
      states.length = 0;
      await settleResult("x");
      await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
      preview.update(req("y"));
      await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
      settle();
      await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
      preview.update(req("z"));
      expect(states[states.length - 1]).toEqual({
        kind: "updating",
        previous: null,
      });
      preview.cancel();
    }
  });

  it("holds a late success silently and re-emits it on revert", async () => {
    preview.update(req("x"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    preview.update(req("y"));
    sends[0].deferred.resolve(resp("x"));
    expect(kinds()).toEqual(["updating"]);
    preview.update(req("x"));
    expect(states[states.length - 1]).toEqual({
      kind: "result",
      response: resp("x"),
    });
    expect(sends).toHaveLength(1);
  });

  it("a held response is replaced by the newer result", async () => {
    preview.update(req("x"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    preview.update(req("y"));
    sends[0].deferred.resolve(resp("x"));
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
    expect(sends).toHaveLength(2);
    sends[1].deferred.resolve(resp("y"));
    expect(states[states.length - 1]).toEqual({
      kind: "result",
      response: resp("y"),
    });
  });

  it("discards a late failure while a newer draft is queued", async () => {
    preview.update(req("x"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    preview.update(req("y"));
    sends[0].deferred.reject({ status: 429 });
    expect(kinds()).toEqual(["updating"]);
    preview.update(req("x"));
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
    expect(sends).toHaveLength(2);
    expect(sends[1].body).toEqual(req("x").body);
  });

  it("revert to a settled key aborts the different in-flight key", async () => {
    await settleResult("x");
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
    preview.update(req("y"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    expect(sends).toHaveLength(2);
    preview.update(req("x"));
    expect(sends[1].deferred.abort).toHaveBeenCalled();
    sends[1].deferred.resolve(resp("y"));
    expect(states[states.length - 1]).toEqual({
      kind: "result",
      response: resp("x"),
    });
    expect(sends).toHaveLength(2);
  });

  it("a revert after a failure sends again and never re-emits the old result", async () => {
    await settleResult("x");
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
    preview.update(req("y"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    sends[1].deferred.reject({ status: 500 });
    states.length = 0;
    preview.update(req("x"));
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
    expect(sends).toHaveLength(3);
    expect(kinds()).toEqual(["updating"]);
  });

  it("sends the same draft again after cancel, through the interval gate", async () => {
    await settleResult("x");
    preview.cancel();
    preview.update(req("x"));
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    expect(sends).toHaveLength(1);
    await vi.advanceTimersByTimeAsync(PREVIEW_MIN_INTERVAL_MS);
    expect(sends).toHaveLength(2);
  });

  it("field-errors carries the submitted snapshot that was sent", async () => {
    const first = [{ key: 7, filterKeys: [], breakdownFilterKeys: [] }];
    preview.update({ ...req("a"), submitted: first });
    await vi.advanceTimersByTimeAsync(PREVIEW_DEBOUNCE_MS);
    preview.update({ ...req("a"), submitted: SUBMITTED });
    sends[0].deferred.reject({
      status: 400,
      responseJSON: { errors: { a: ["b"] } },
    });
    // Same key as in flight: the failure is reported with the sent snapshot.
    expect(states[states.length - 1]).toMatchObject({
      kind: "field-errors",
      submitted: first,
    });
  });
});
