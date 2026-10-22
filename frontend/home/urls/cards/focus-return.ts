// Applied only while focus is being programmatically moved to a row after a
// delete (WCAG 2.4.3); suppresses the visual focus ring (see urls.css) so this
// native-focus side effect never reads as urlSelected="true" on a row the user
// never selected.
export const FOCUS_RETURN_CLASS = "swipe-focus-return";
const FOCUS_RETURN_NAMESPACE = "blur.swipeFocusReturn";
// setFocusEventListenersOnURLCard (cards.ts) adds this to .goToUrlIcon on
// .urlRow focus and only removes it when the *icon itself* blurs (the real
// keyboard-Tab path). A programmatic focus/blur of the row never blurs the
// icon, so strip it here to avoid leaking it permanently.
const GO_TO_URL_ICON_SELECTOR = ".goToUrlIcon";
const VISIBLE_ON_FOCUS_CLASS = "visible-on-focus";

/**
 * Arm the WCAG 2.4.3 focus-return suppression: add `FOCUS_RETURN_CLASS` so
 * focus moving to the neighbour row after a delete (or back to the row after
 * a failed one) never reads as "selected", and (re)bind a one-shot blur
 * listener that removes it. Must be called every time the class is added,
 * because the one-shot listener self-consumes on the first blur.
 */
export function armFocusReturnSuppression(urlRow: JQuery): void {
  urlRow.addClass(FOCUS_RETURN_CLASS);
  urlRow.off(FOCUS_RETURN_NAMESPACE).one(FOCUS_RETURN_NAMESPACE, () => {
    urlRow.removeClass(FOCUS_RETURN_CLASS);
    urlRow.find(GO_TO_URL_ICON_SELECTOR).removeClass(VISIBLE_ON_FOCUS_CLASS);
  });
}
