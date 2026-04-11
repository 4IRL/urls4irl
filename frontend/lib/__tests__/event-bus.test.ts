import type {
  AppEventMap,
  StaleDataDetectedPayload,
  UtubSelectedPayload,
} from "../event-bus.js";
import { on, emit, AppEvents } from "../event-bus.js";

describe("event-bus", () => {
  // Reset internal handler map between tests by removing each registered handler
  let cleanups: (() => void)[] = [];

  afterEach(() => {
    cleanups.forEach((fn) => fn());
    cleanups = [];
  });

  function track<K extends keyof AppEventMap>(
    event: K,
    handler: (payload: AppEventMap[K]) => void,
  ): () => void {
    const unsub = on(event, handler);
    cleanups.push(unsub);
    return unsub;
  }

  it("emit with no listeners does not throw", () => {
    // @ts-expect-error intentional out-of-contract call to verify runtime no-throw guarantee
    expect(() => emit("unknown:event", { data: 1 })).not.toThrow();
  });

  it("emit with unknown AppEvents name does not throw", () => {
    // @ts-expect-error intentional out-of-contract call to verify runtime no-throw guarantee
    expect(() => emit("no-such-event")).not.toThrow();
  });

  it("on + emit calls handler with the correct payload", () => {
    const handler = vi.fn<(payload: AppEventMap["utub:selected"]) => void>();
    track(AppEvents.UTUB_SELECTED, handler);
    emit(AppEvents.UTUB_SELECTED, { utubID: 42 } as UtubSelectedPayload);
    expect(handler).toHaveBeenCalledOnce();
    expect(handler).toHaveBeenCalledWith({ utubID: 42 });
  });

  it("multiple handlers for the same event all fire", () => {
    const h1 = vi.fn<(payload: AppEventMap["tag:deleted"]) => void>();
    const h2 = vi.fn<(payload: AppEventMap["tag:deleted"]) => void>();
    track(AppEvents.TAG_DELETED, h1);
    track(AppEvents.TAG_DELETED, h2);
    emit(AppEvents.TAG_DELETED, { utubTagID: 7 });
    expect(h1).toHaveBeenCalledOnce();
    expect(h2).toHaveBeenCalledOnce();
  });

  it("off stops handler from firing", () => {
    const handler = vi.fn<(payload: AppEventMap["utub:deleted"]) => void>();
    const removeHandler = track(AppEvents.UTUB_DELETED, handler);
    emit(AppEvents.UTUB_DELETED, { utubID: 1 });
    expect(handler).toHaveBeenCalledTimes(1);
    removeHandler();
    emit(AppEvents.UTUB_DELETED, { utubID: 1 });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("returned unsubscribe function stops handler from firing", () => {
    const handler =
      vi.fn<(payload: AppEventMap["tag:filter-changed"]) => void>();
    const unsubscribe = on(AppEvents.TAG_FILTER_CHANGED, handler);
    emit(AppEvents.TAG_FILTER_CHANGED, { selectedTagIDs: [1] });
    expect(handler).toHaveBeenCalledTimes(1);
    unsubscribe();
    emit(AppEvents.TAG_FILTER_CHANGED, { selectedTagIDs: [2] });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("STALE_DATA_DETECTED handler receives correct payload", () => {
    const handler =
      vi.fn<(payload: AppEventMap["stale-data:detected"]) => void>();
    track(AppEvents.STALE_DATA_DETECTED, handler);
    const payload: StaleDataDetectedPayload = {
      utubID: 99,
      urls: [{ id: 1 }],
      tags: [{ id: 2 }],
      members: [{ id: 3 }],
    };
    emit(AppEvents.STALE_DATA_DETECTED, payload);
    expect(handler).toHaveBeenCalledOnce();
    expect(handler).toHaveBeenCalledWith(payload);
  });

  it("handlers for different events do not interfere", () => {
    const h1 = vi.fn<(payload: AppEventMap["utub:selected"]) => void>();
    const h2 = vi.fn<(payload: AppEventMap["utub:deleted"]) => void>();
    track(AppEvents.UTUB_SELECTED, h1);
    track(AppEvents.UTUB_DELETED, h2);
    emit(AppEvents.UTUB_SELECTED, {} as UtubSelectedPayload);
    expect(h1).toHaveBeenCalledOnce();
    expect(h2).not.toHaveBeenCalled();
  });
});
