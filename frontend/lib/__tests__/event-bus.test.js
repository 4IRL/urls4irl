import { on, off, emit, AppEvents } from "../event-bus.js";

describe("event-bus", () => {
  // Reset internal handler map between tests by removing each registered handler
  let cleanups = [];

  afterEach(() => {
    cleanups.forEach((fn) => fn());
    cleanups = [];
  });

  function track(event, handler) {
    const off = on(event, handler);
    cleanups.push(off);
    return off;
  }

  it("emit with no listeners does not throw", () => {
    expect(() => emit("unknown:event", { data: 1 })).not.toThrow();
  });

  it("emit with unknown AppEvents name does not throw", () => {
    expect(() => emit("no-such-event")).not.toThrow();
  });

  it("on + emit calls handler with the correct payload", () => {
    const handler = vi.fn();
    track(AppEvents.UTUB_SELECTED, handler);
    emit(AppEvents.UTUB_SELECTED, { utubID: 42 });
    expect(handler).toHaveBeenCalledOnce();
    expect(handler).toHaveBeenCalledWith({ utubID: 42 });
  });

  it("multiple handlers for the same event all fire", () => {
    const h1 = vi.fn();
    const h2 = vi.fn();
    track(AppEvents.TAG_DELETED, h1);
    track(AppEvents.TAG_DELETED, h2);
    emit(AppEvents.TAG_DELETED, { utubTagID: 7 });
    expect(h1).toHaveBeenCalledOnce();
    expect(h2).toHaveBeenCalledOnce();
  });

  it("off stops handler from firing", () => {
    const handler = vi.fn();
    const removeHandler = track(AppEvents.UTUB_DELETED, handler);
    emit(AppEvents.UTUB_DELETED, { utubID: 1 });
    expect(handler).toHaveBeenCalledTimes(1);
    removeHandler();
    emit(AppEvents.UTUB_DELETED, { utubID: 1 });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("returned unsubscribe function stops handler from firing", () => {
    const handler = vi.fn();
    const unsubscribe = on(AppEvents.TAG_FILTER_CHANGED, handler);
    emit(AppEvents.TAG_FILTER_CHANGED, { selectedTagIDs: [1] });
    expect(handler).toHaveBeenCalledTimes(1);
    unsubscribe();
    emit(AppEvents.TAG_FILTER_CHANGED, { selectedTagIDs: [2] });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("handlers for different events do not interfere", () => {
    const h1 = vi.fn();
    const h2 = vi.fn();
    track(AppEvents.UTUB_SELECTED, h1);
    track(AppEvents.UTUB_DELETED, h2);
    emit(AppEvents.UTUB_SELECTED, {});
    expect(h1).toHaveBeenCalledOnce();
    expect(h2).not.toHaveBeenCalled();
  });
});
