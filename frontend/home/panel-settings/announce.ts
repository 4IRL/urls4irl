const ANNOUNCEMENT_SELECTOR = "#PanelSettingsAnnouncement";

let _announceTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * Write a message to the polite live region. The region is cleared first and set
 * on the next tick so an identical repeated message is still announced.
 */
export function announceSettingsStatus({ message }: { message: string }): void {
  const region = document.querySelector(ANNOUNCEMENT_SELECTOR);
  if (!region) return;
  if (_announceTimer !== null) clearTimeout(_announceTimer);
  region.textContent = "";
  _announceTimer = setTimeout(() => {
    _announceTimer = null;
    region.textContent = message;
  }, 0);
}
