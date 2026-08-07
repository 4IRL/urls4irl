/**
 * Unit tests for the shared debounce utility (relocated from the admin
 * fragment-swap test suite).
 */

import { makeDebouncer } from "../debounce.js";

describe("makeDebouncer", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("delays execution by the specified delay", () => {
    const fn = vi.fn();
    const debounced = makeDebouncer(fn, 500);

    debounced();

    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(499);
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("resets the timer on repeated calls so fn fires only once after the last call", () => {
    const fn = vi.fn();
    const debounced = makeDebouncer(fn, 500);

    debounced();
    vi.advanceTimersByTime(400);
    debounced();
    vi.advanceTimersByTime(400);
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("fires again on subsequent calls after the first debounce window elapses", () => {
    const fn = vi.fn();
    const debounced = makeDebouncer(fn, 500);

    debounced();
    vi.advanceTimersByTime(500);
    expect(fn).toHaveBeenCalledTimes(1);

    debounced();
    vi.advanceTimersByTime(500);
    expect(fn).toHaveBeenCalledTimes(2);
  });
});
