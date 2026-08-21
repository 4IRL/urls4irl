import {
  isAnyBulkPickerOpen,
  onPickerOpenChange,
  resetPickerGuardForTest,
  setPickerOpen,
} from "../picker-guard.js";

// Exercises the DD-5 subscriber addition (onPickerOpenChange) in isolation,
// independent of bulk-bar.ts. The module owns process-wide singletons, so each
// case starts from a clean state via resetPickerGuardForTest() — otherwise
// listeners registered by one it() and open ids left by another leak across.
describe("picker-guard onPickerOpenChange subscriber", () => {
  beforeEach(() => {
    resetPickerGuardForTest();
  });

  it("registers a callback that fires with true when the first picker opens", () => {
    const callback = vi.fn();
    onPickerOpenChange(callback);

    setPickerOpen("bulk-tag", true);

    expect(callback).toHaveBeenCalledTimes(1);
    expect(callback).toHaveBeenLastCalledWith(true);
    expect(isAnyBulkPickerOpen()).toBe(true);
  });

  it("keeps notifying with true (never a stale false) while a second picker opens", () => {
    const callback = vi.fn();
    onPickerOpenChange(callback);

    setPickerOpen("bulk-tag", true);
    setPickerOpen("bulk-copy", true);

    // "any picker" semantics: both notifications carry true, never false.
    expect(callback).toHaveBeenCalledTimes(2);
    expect(callback.mock.calls.every(([open]) => open === true)).toBe(true);
    expect(isAnyBulkPickerOpen()).toBe(true);
  });

  it("notifies with false only when the LAST open picker closes", () => {
    const callback = vi.fn();
    onPickerOpenChange(callback);

    setPickerOpen("bulk-tag", true);
    setPickerOpen("bulk-copy", true);
    // One of two closes: another picker is still open, so still true.
    setPickerOpen("bulk-tag", false);
    expect(callback).toHaveBeenLastCalledWith(true);
    expect(isAnyBulkPickerOpen()).toBe(true);

    // The last picker closes → the open set empties → notify false.
    setPickerOpen("bulk-copy", false);
    expect(callback).toHaveBeenLastCalledWith(false);
    expect(isAnyBulkPickerOpen()).toBe(false);
  });

  it("fires every registered callback on a state change", () => {
    const first = vi.fn();
    const second = vi.fn();
    onPickerOpenChange(first);
    onPickerOpenChange(second);

    setPickerOpen("bulk-tag", true);

    expect(first).toHaveBeenCalledTimes(1);
    expect(first).toHaveBeenLastCalledWith(true);
    expect(second).toHaveBeenCalledTimes(1);
    expect(second).toHaveBeenLastCalledWith(true);
  });

  it("resetPickerGuardForTest() clears both listeners and open ids", () => {
    const stale = vi.fn();
    onPickerOpenChange(stale);
    setPickerOpen("bulk-tag", true);

    resetPickerGuardForTest();

    // Open ids cleared → no picker considered open.
    expect(isAnyBulkPickerOpen()).toBe(false);

    // Listeners cleared → the previously-registered callback no longer fires.
    stale.mockClear();
    setPickerOpen("bulk-copy", true);
    expect(stale).not.toHaveBeenCalled();
  });
});
