// Module-level busy signals for the panel settings shell: the open flag is set
// by the popover and the pending-save count is mirrored by the save queue.

let _isOpen = false;
let _pendingSaveCount = 0;

/** True while the popover is open. */
export function isPanelSettingsOpen(): boolean {
  return _isOpen;
}

/** True while the popover is open or any section save is queued, debouncing or in flight. */
export function isPanelSettingsBusy(): boolean {
  return _isOpen || _pendingSaveCount > 0;
}

export function setPanelSettingsOpen({ open }: { open: boolean }): void {
  _isOpen = open;
}

export function setPanelSettingsPendingSaveCount({
  count,
}: {
  count: number;
}): void {
  _pendingSaveCount = Math.max(0, count);
}
