import {
  createFlowLoadQueue,
  MAX_FLOWS_IN_FLIGHT,
} from "../flow-load-queue.js";

const { logSpy } = vi.hoisted(() => ({ logSpy: vi.fn() }));

vi.mock("../../lib/debug.js", () => ({
  debug: () => logSpy,
}));

interface FakeXhr {
  xhr: JQuery.jqXHR;
  settle: () => void;
  abort: ReturnType<typeof vi.fn>;
  isSettled: () => boolean;
}

// Mirrors a real jqXHR: abort() synchronously fires fail then always.
function makeFakeXhr({
  settleOnAttach = false,
}: { settleOnAttach?: boolean } = {}): FakeXhr {
  const alwaysCallbacks: Array<() => void> = [];
  let settled = false;
  const fire = (): void => {
    if (settled) return;
    settled = true;
    for (const callback of alwaysCallbacks) callback();
  };
  const abort = vi.fn(fire);
  const chainable = {
    done: vi.fn().mockReturnThis(),
    fail: vi.fn().mockReturnThis(),
    always: vi.fn().mockImplementation((callback: () => void) => {
      alwaysCallbacks.push(callback);
      if (settleOnAttach || settled) callback();
      return chainable;
    }),
    abort,
  };
  return {
    xhr: chainable as unknown as JQuery.jqXHR,
    settle: fire,
    abort,
    isSettled: () => settled,
  };
}

const IDS = [
  "custom_1",
  "custom_2",
  "custom_3",
  "custom_4",
  "custom_5",
  "custom_6",
];

describe("createFlowLoadQueue", () => {
  let issued: string[];
  let xhrs: Map<string, FakeXhr[]>;
  let paused: boolean;
  let idleCalls: string[];
  let calls: string[];
  let settleSync: boolean;

  function latest(id: string): FakeXhr {
    const list = xhrs.get(id) as FakeXhr[];
    return list[list.length - 1];
  }

  function build({
    issueImpl,
    maxInFlight,
  }: {
    issueImpl?: ({ id }: { id: string }) => JQuery.jqXHR;
    maxInFlight?: number;
  } = {}) {
    return createFlowLoadQueue({
      maxInFlight,
      issue:
        issueImpl ??
        (({ id }) => {
          issued.push(id);
          calls.push(`issue:${id}`);
          const fake = makeFakeXhr({ settleOnAttach: settleSync });
          xhrs.set(id, [...(xhrs.get(id) ?? []), fake]);
          return fake.xhr;
        }),
      isPaused: () => paused,
      onSettle: ({ id }) => calls.push(`settle:${id}`),
      onIdle: ({ cause }) => idleCalls.push(cause),
    });
  }

  beforeEach(() => {
    issued = [];
    xhrs = new Map();
    paused = false;
    idleCalls = [];
    calls = [];
    settleSync = false;
    logSpy.mockClear();
  });

  it("issues at most 4 at once and a settle starts the next", () => {
    const queue = build();
    queue.startFanOut({ ids: IDS });
    expect(MAX_FLOWS_IN_FLIGHT).toBe(4);
    expect(issued).toEqual(IDS.slice(0, 4));
    latest("custom_1").settle();
    expect(issued).toEqual(IDS.slice(0, 5));
    latest("custom_2").settle();
    expect(issued).toEqual(IDS);
  });

  it("one id settling late does not affect the others", () => {
    const queue = build();
    queue.startFanOut({ ids: IDS.slice(0, 3) });
    latest("custom_2").settle();
    expect(queue.isPending({ id: "custom_1" })).toBe(true);
    expect(queue.isPending({ id: "custom_3" })).toBe(true);
    expect(queue.isPending({ id: "custom_2" })).toBe(false);
    expect(idleCalls).toEqual([]);
  });

  it("startFanOut aborts in-flight and never issues old waiting ids", () => {
    const queue = build();
    queue.startFanOut({ ids: IDS });
    const first = latest("custom_1");
    queue.startFanOut({ ids: ["custom_6"] });
    expect(first.abort).toHaveBeenCalledTimes(1);
    expect(issued.slice(4)).toEqual(["custom_6"]);
    expect(issued).not.toContain("custom_5");
    expect(idleCalls).toEqual([]);
    expect(calls.filter((call) => call.startsWith("settle:"))).toEqual([]);
  });

  it("enqueue while 4 are in flight does not abort them; new id starts on a free slot", () => {
    const queue = build();
    queue.startFanOut({ ids: IDS.slice(0, 4) });
    const inFlight = IDS.slice(0, 4).map((id) => latest(id));
    queue.enqueue({ ids: ["custom_5"] });
    for (const fake of inFlight) expect(fake.abort).not.toHaveBeenCalled();
    expect(issued).toEqual(IDS.slice(0, 4));
    latest("custom_1").settle();
    expect(issued).toEqual(IDS.slice(0, 5));
  });

  it("enqueue of an in-flight or waiting id is a no-op", () => {
    const queue = build();
    queue.startFanOut({ ids: IDS });
    queue.enqueue({ ids: ["custom_1", "custom_6"] });
    expect(issued).toEqual(IDS.slice(0, 4));
    latest("custom_1").settle();
    latest("custom_2").settle();
    expect(issued.filter((id) => id === "custom_6")).toHaveLength(1);
    expect(issued.filter((id) => id === "custom_1")).toHaveLength(1);
  });

  it("enqueue on an idle queue issues the id and fires onIdle once on drain", () => {
    const queue = build();
    queue.enqueue({ ids: ["custom_1"] });
    expect(issued).toEqual(["custom_1"]);
    expect(idleCalls).toEqual([]);
    latest("custom_1").settle();
    expect(idleCalls).toEqual(["settled"]);
  });

  it("enqueue of an empty list fires nothing", () => {
    const queue = build();
    queue.enqueue({ ids: [] });
    expect(issued).toEqual([]);
    expect(idleCalls).toEqual([]);
  });

  it("enqueue while paused holds ids; a later startFanOut replaces them", () => {
    const queue = build();
    paused = true;
    queue.enqueue({ ids: ["custom_1"] });
    expect(queue.isPending({ id: "custom_1" })).toBe(true);
    expect(issued).toEqual([]);
    paused = false;
    queue.startFanOut({ ids: ["custom_2"] });
    expect(issued).toEqual(["custom_2"]);
    expect(queue.isPending({ id: "custom_1" })).toBe(false);
  });

  it("isCurrent is false for an aborted xhr", () => {
    const queue = build();
    queue.startFanOut({ ids: ["custom_1"] });
    const old = latest("custom_1");
    expect(queue.isCurrent({ id: "custom_1", xhr: old.xhr })).toBe(true);
    queue.abortAll();
    expect(queue.isCurrent({ id: "custom_1", xhr: old.xhr })).toBe(false);
  });

  it("fires onIdle once with cause settled, not early, not from abortAll", () => {
    const queue = build();
    queue.startFanOut({ ids: IDS });
    for (const id of IDS.slice(0, 4)) latest(id).settle();
    expect(idleCalls).toEqual([]);
    latest("custom_5").settle();
    expect(idleCalls).toEqual([]);
    latest("custom_6").settle();
    expect(idleCalls).toEqual(["settled"]);

    queue.startFanOut({ ids: IDS });
    queue.abortAll();
    expect(idleCalls).toEqual(["settled"]);
  });

  it("a stale settle is a no-op, even when the id was re-issued", () => {
    const queue = build();
    queue.startFanOut({ ids: ["custom_1"] });
    const oldFake = latest("custom_1");
    // Capture the old xhr's always callback to fire it after abort.
    const alwaysMock = (
      oldFake.xhr.always as unknown as ReturnType<typeof vi.fn>
    ).mock.calls[0][0] as () => void;
    queue.startFanOut({ ids: ["custom_1"] });
    const newFake = latest("custom_1");
    expect(newFake).not.toBe(oldFake);
    alwaysMock();
    expect(queue.isCurrent({ id: "custom_1", xhr: newFake.xhr })).toBe(true);
    expect(queue.isPending({ id: "custom_1" })).toBe(true);
    expect(idleCalls).toEqual([]);
    expect(calls.filter((call) => call.startsWith("settle:"))).toEqual([]);
    newFake.settle();
    expect(idleCalls).toEqual(["settled"]);
  });

  it("a stale settle after abortAll is a no-op and a later drain stays silent", () => {
    const queue = build();
    queue.startFanOut({ ids: ["custom_1"] });
    const oldFake = latest("custom_1");
    const alwaysMock = (
      oldFake.xhr.always as unknown as ReturnType<typeof vi.fn>
    ).mock.calls[0][0] as () => void;
    queue.abortAll();
    alwaysMock();
    expect(calls.filter((call) => call.startsWith("settle:"))).toEqual([]);
    expect(idleCalls).toEqual([]);
    queue.drain();
    expect(idleCalls).toEqual([]);
    expect(queue.isIdle()).toBe(true);
  });

  it("issues a duplicate id within one fan-out once", () => {
    const queue = build();
    queue.startFanOut({ ids: ["custom_1", "custom_1", "custom_2"] });
    expect(issued).toEqual(["custom_1", "custom_2"]);
  });

  it("an empty fan-out fires onIdle once, also when already idle", () => {
    const queue = build();
    queue.startFanOut({ ids: [] });
    expect(idleCalls).toEqual(["settled"]);
    queue.startFanOut({ ids: [] });
    expect(idleCalls).toEqual(["settled", "settled"]);
    expect(issued).toEqual([]);
  });

  it("mixed sync and async settles stay within the cap and fire onIdle once, last", () => {
    const ids = [...IDS, "custom_7", "custom_8"];
    const syncIds = new Set(["custom_1", "custom_2", "custom_5"]);
    let inFlight = 0;
    let maxSeen = 0;
    const queue = build({
      issueImpl: ({ id }) => {
        issued.push(id);
        inFlight += 1;
        maxSeen = Math.max(maxSeen, inFlight);
        const fake = makeFakeXhr({ settleOnAttach: syncIds.has(id) });
        xhrs.set(id, [fake]);
        fake.xhr.always(() => {
          inFlight -= 1;
        });
        return fake.xhr;
      },
    });
    queue.startFanOut({ ids });
    expect(idleCalls).toEqual([]);
    for (const id of ids) {
      if (xhrs.has(id) && !latest(id).isSettled()) latest(id).settle();
      expect(idleCalls).toEqual(id === "custom_8" ? ["settled"] : []);
    }
    expect(issued).toEqual(ids);
    expect(new Set(issued).size).toBe(ids.length);
    expect(maxSeen).toBeLessThanOrEqual(MAX_FLOWS_IN_FLIGHT);
    expect(queue.isIdle()).toBe(true);
  });

  it("dropId aborts the in-flight xhr and removes waiting ids", () => {
    const queue = build();
    queue.startFanOut({ ids: IDS });
    const first = latest("custom_1");
    queue.dropId({ id: "custom_1" });
    expect(first.abort).toHaveBeenCalledTimes(1);
    expect(queue.isPending({ id: "custom_1" })).toBe(false);
    queue.dropId({ id: "custom_6" });
    expect(queue.isPending({ id: "custom_6" })).toBe(false);
    latest("custom_5").settle();
    expect(issued).not.toContain("custom_6");
    expect(calls).not.toContain("settle:custom_1");
  });

  it("dropId of an in-flight id drains the next waiting id without onIdle", () => {
    const queue = build();
    queue.startFanOut({ ids: IDS.slice(0, 5) });
    queue.dropId({ id: "custom_1" });
    expect(issued).toEqual(IDS.slice(0, 5));
    expect(idleCalls).toEqual([]);
  });

  it("dropId of the last in-flight id fires onIdle once with cause dropped", () => {
    const queue = build();
    queue.startFanOut({ ids: ["custom_1"] });
    queue.dropId({ id: "custom_1" });
    expect(idleCalls).toEqual(["dropped"]);
  });

  it("dropId of a waiting-only id that empties the queue fires dropped", () => {
    paused = true;
    const queue = build();
    queue.startFanOut({ ids: ["custom_1"] });
    expect(queue.isPending({ id: "custom_1" })).toBe(true);
    queue.dropId({ id: "custom_1" });
    expect(idleCalls).toEqual(["dropped"]);
  });

  it("dropId of an absent id is a no-op", () => {
    const queue = build();
    queue.dropId({ id: "custom_1" });
    expect(idleCalls).toEqual([]);
    queue.startFanOut({ ids: ["custom_2"] });
    queue.dropId({ id: "custom_1" });
    expect(idleCalls).toEqual([]);
    expect(queue.isPending({ id: "custom_2" })).toBe(true);
  });

  it("isPending tracks in-flight, waiting, settle, drop and abort", () => {
    const queue = build();
    queue.startFanOut({ ids: IDS });
    expect(queue.isPending({ id: "custom_1" })).toBe(true);
    expect(queue.isPending({ id: "custom_6" })).toBe(true);
    latest("custom_1").settle();
    expect(queue.isPending({ id: "custom_1" })).toBe(false);
    queue.dropId({ id: "custom_2" });
    expect(queue.isPending({ id: "custom_2" })).toBe(false);
    queue.abortAll();
    expect(queue.isPending({ id: "custom_3" })).toBe(false);
    expect(queue.isPending({ id: "custom_6" })).toBe(false);
    queue.startFanOut({ ids: IDS });
    queue.startFanOut({ ids: [] });
    expect(queue.isPending({ id: "custom_1" })).toBe(false);
  });

  it("holds ids while paused, replaces them on a new fan-out, drains on unpause", () => {
    paused = true;
    const queue = build();
    queue.startFanOut({ ids: ["custom_1", "custom_2"] });
    expect(issued).toEqual([]);
    queue.startFanOut({ ids: ["custom_3"] });
    expect(queue.isPending({ id: "custom_1" })).toBe(false);
    paused = false;
    queue.drain();
    expect(issued).toEqual(["custom_3"]);
  });

  it("stays silent while paused with ids held and drains once unpaused", () => {
    const queue = build();
    queue.startFanOut({ ids: IDS.slice(0, 5) });
    paused = true;
    latest("custom_1").settle();
    queue.drain();
    expect(issued).toEqual(IDS.slice(0, 4));
    expect(idleCalls).toEqual([]);
    expect(queue.isPending({ id: "custom_5" })).toBe(true);
    for (const id of IDS.slice(1, 4)) latest(id).settle();
    queue.drain();
    expect(idleCalls).toEqual([]);
    expect(queue.isPending({ id: "custom_5" })).toBe(true);
    paused = false;
    queue.drain();
    expect(issued).toEqual(IDS.slice(0, 5));
    latest("custom_5").settle();
    expect(idleCalls).toEqual(["settled"]);
  });

  it("honors a maxInFlight override", () => {
    const queue = build({ maxInFlight: 2 });
    queue.startFanOut({ ids: IDS });
    expect(issued).toEqual(IDS.slice(0, 2));
    latest("custom_1").settle();
    expect(issued).toEqual(IDS.slice(0, 3));
  });

  it("onSettle fires once per current settle, before the next issue", () => {
    let pendingInside: boolean | null = null;
    const observed = createFlowLoadQueue({
      issue: ({ id }) => {
        calls.push(`issue:${id}`);
        const fake = makeFakeXhr();
        xhrs.set(id, [fake]);
        return fake.xhr;
      },
      isPaused: () => false,
      onSettle: ({ id }) => {
        calls.push(`settle:${id}`);
        pendingInside = observed.isPending({ id });
      },
      onIdle: ({ cause }) => idleCalls.push(cause),
    });
    observed.startFanOut({ ids: IDS.slice(0, 5) });
    latest("custom_1").settle();
    expect(pendingInside).toBe(false);
    expect(calls.indexOf("settle:custom_1")).toBeLessThan(
      calls.indexOf("issue:custom_5"),
    );
    expect(calls.filter((call) => call === "settle:custom_1")).toHaveLength(1);
    observed.dropId({ id: "custom_2" });
    observed.startFanOut({ ids: ["custom_1"] });
    observed.abortAll();
    // dropId, startFanOut and abortAll aborts never reach onSettle.
    expect(calls.filter((call) => call.startsWith("settle:"))).toEqual([
      "settle:custom_1",
    ]);
    expect(observed.isIdle()).toBe(true);
  });

  it("a throwing onSettle is logged and the drain still runs", () => {
    const error = new Error("settle boom");
    const queue = createFlowLoadQueue({
      issue: ({ id }) => {
        issued.push(id);
        const fake = makeFakeXhr();
        xhrs.set(id, [fake]);
        return fake.xhr;
      },
      isPaused: () => false,
      onSettle: () => {
        throw error;
      },
      onIdle: ({ cause }) => idleCalls.push(cause),
    });
    queue.startFanOut({ ids: IDS.slice(0, 5) });
    expect(() => latest("custom_1").settle()).not.toThrow();
    expect(logSpy).toHaveBeenCalledWith("onSettle threw", error);
    expect(issued).toEqual(IDS.slice(0, 5));
    for (const id of IDS.slice(1, 5)) latest(id).settle();
    expect(idleCalls).toEqual(["settled"]);
  });

  it("abortAll then drain fires no onIdle, a later fan-out still does", () => {
    const queue = build();
    queue.startFanOut({ ids: ["custom_1"] });
    queue.abortAll();
    queue.drain();
    expect(idleCalls).toEqual([]);
    queue.startFanOut({ ids: ["custom_2"] });
    latest("custom_2").settle();
    expect(idleCalls).toEqual(["settled"]);
  });

  it("survives a throwing issue and still reports idle", () => {
    const thrown: string[] = [];
    const queue = build({
      issueImpl: ({ id }) => {
        if (id === "custom_2") {
          thrown.push(id);
          throw new Error("boom");
        }
        issued.push(id);
        const fake = makeFakeXhr();
        xhrs.set(id, [fake]);
        return fake.xhr;
      },
    });
    queue.startFanOut({ ids: IDS.slice(0, 3) });
    expect(issued).toEqual(["custom_1", "custom_3"]);
    expect(queue.isPending({ id: "custom_2" })).toBe(false);
    expect(logSpy).toHaveBeenCalledWith(
      "issue threw; dropping id",
      "custom_2",
      expect.objectContaining({ message: "boom" }),
    );
    expect(calls).not.toContain("settle:custom_2");
    latest("custom_1").settle();
    latest("custom_3").settle();
    expect(idleCalls).toEqual(["settled"]);
    // Not wedged: a later fan-out works.
    queue.startFanOut({ ids: ["custom_4"] });
    expect(issued).toContain("custom_4");
  });

  it("fires onIdle once when every issue throws", () => {
    const queue = build({
      issueImpl: () => {
        throw new Error("boom");
      },
    });
    queue.startFanOut({ ids: IDS });
    expect(idleCalls).toEqual(["settled"]);
    queue.drain();
    expect(idleCalls).toEqual(["settled"]);
  });

  it("dropId drain where the last waiting id throws fires dropped once", () => {
    let throwNow = false;
    const queue = build({
      issueImpl: ({ id }) => {
        if (throwNow) throw new Error("boom");
        issued.push(id);
        const fake = makeFakeXhr();
        xhrs.set(id, [fake]);
        return fake.xhr;
      },
    });
    paused = true;
    queue.startFanOut({ ids: ["custom_4", "custom_5"] });
    // Both wait while paused; unpausing makes custom_5's throw happen
    // inside dropId's drain.
    paused = false;
    throwNow = true;
    queue.dropId({ id: "custom_4" });
    expect(idleCalls).toEqual(["dropped"]);
    expect(calls.filter((call) => call.startsWith("settle:"))).toEqual([]);
  });
});
