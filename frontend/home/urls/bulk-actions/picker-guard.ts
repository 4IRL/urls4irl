/**
 * Shared open-picker registry for the bulk sub-pickers (bulk-tag, bulk-copy).
 *
 * This module is a deliberate LEAF: it imports NEITHER picker module. The two
 * picker modules depend on `picker-guard.ts` (they call `setPickerOpen(...)` /
 * `registerPickerClose(...)` from their own init/open/close paths); nothing here
 * ever reaches back into them by import — the only handle it holds is each
 * picker's own close callback, registered at init time. That inversion is what
 * keeps the dependency graph one-directional (picker modules → picker-guard,
 * never the reverse) and free of circular imports, while still giving the bar /
 * selection / mode-exit code a single predicate (`isAnyBulkPickerOpen`) and a
 * single teardown (`closeAllPickers`) that cover BOTH pickers.
 */

export type PickerId = "bulk-tag" | "bulk-copy";

const openPickerIds = new Set<PickerId>();
const closeCallbacks = new Map<PickerId, () => void>();
// Subscribers notified whenever the aggregate open/closed state changes. Both
// pickers feed the SAME notification (via isAnyBulkPickerOpen()), mirroring the
// module's single-predicate-covers-BOTH-pickers contract (see file header).
const openChangeListeners = new Set<(open: boolean) => void>();

/** Register a picker's close callback. Called once, from its own init function. */
export function registerPickerClose(id: PickerId, onClose: () => void): void {
  closeCallbacks.set(id, onClose);
}

/**
 * Subscribe to aggregate picker open/closed changes. The callback fires on every
 * setPickerOpen() with the fresh isAnyBulkPickerOpen() value — so bulk-bar.ts can
 * sync the range strip's inert state from a single place for BOTH pickers.
 */
export function onPickerOpenChange(callback: (open: boolean) => void): void {
  openChangeListeners.add(callback);
}

/** Mark a picker open/closed. Called by the picker module itself on open/close. */
export function setPickerOpen(id: PickerId, open: boolean): void {
  if (open) {
    openPickerIds.add(id);
  } else {
    openPickerIds.delete(id);
  }
  const anyOpen = isAnyBulkPickerOpen();
  openChangeListeners.forEach((callback) => callback(anyOpen));
}

/** Whether any bulk sub-picker (tag or copy) is currently open. */
export function isAnyBulkPickerOpen(): boolean {
  return openPickerIds.size > 0;
}

/** Close every currently-open picker via its registered close callback. */
export function closeAllPickers(): void {
  [...openPickerIds].forEach((id) => closeCallbacks.get(id)?.());
}

/**
 * Test-only: reset BOTH module-level singletons this module owns — the open-id
 * set and the open-change listener set — so a suite can start each case from a
 * clean picker-guard state (this module's state is process-wide and otherwise
 * leaks across tests). Not called by app code.
 */
export function resetPickerGuardForTest(): void {
  openPickerIds.clear();
  openChangeListeners.clear();
}
