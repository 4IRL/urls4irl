const ANNOUNCEMENT_SELECTOR = "#PanelSettingsAnnouncement";

let _announceTimer: ReturnType<typeof setTimeout> | null = null;
// Text of the message whose timer is still pending (null once it was written).
let _pendingMessage: string | null = null;

/**
 * Write a message to the polite live region. The region is cleared first and set
 * on the next tick so an identical repeated message is still announced.
 *
 * `append: true` joins the new message onto a still-pending one ("A" + "B"
 * reads "A. B", a trailing period on the pending text is trimmed). With nothing
 * pending it behaves exactly like a plain call.
 */
export function announceSettingsStatus({
  message,
  append,
}: {
  message: string;
  append?: boolean;
}): void {
  const region = document.querySelector(ANNOUNCEMENT_SELECTOR);
  if (!region) return;
  let text = message;
  if (append === true && _pendingMessage !== null) {
    text = `${_pendingMessage.replace(/\.$/, "")}. ${message}`;
  }
  if (_announceTimer !== null) clearTimeout(_announceTimer);
  region.textContent = "";
  _pendingMessage = text;
  _announceTimer = setTimeout(() => {
    _announceTimer = null;
    _pendingMessage = null;
    region.textContent = text;
  }, 0);
}
