/**
 * One-shot "swallow the trailing click" flag shared by `swipe.ts` (arms it on a
 * committed swipe) and `actions.ts` (consumes it in the delegated row click
 * handler). Lives in its own module so neither imports the other.
 *
 * A swipe whose click never fires (a snapped-back failed restore, for example)
 * must not swallow a later tap or keyboard activation, so the flag also expires
 * on a short timer and `swipe.ts` clears it on the next pointerdown / keydown.
 */

export const TRAILING_CLICK_SUPPRESSION_MS = 350;

let suppressNextClick = false;
let expiryTimer: ReturnType<typeof setTimeout> | null = null;

export function clearTrashClickSuppression(): void {
  suppressNextClick = false;
  if (expiryTimer !== null) {
    clearTimeout(expiryTimer);
    expiryTimer = null;
  }
}

export function armTrashClickSuppression(): void {
  clearTrashClickSuppression();
  suppressNextClick = true;
  expiryTimer = setTimeout(
    clearTrashClickSuppression,
    TRAILING_CLICK_SUPPRESSION_MS,
  );
}

/** Read-and-reset: true at most once per arming. */
export function consumeTrashClickSuppression(): boolean {
  const suppressed = suppressNextClick;
  clearTrashClickSuppression();
  return suppressed;
}
