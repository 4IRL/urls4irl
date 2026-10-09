// Shared "nothing to confirm" look for the green ✓ buttons of the mobile edit
// panels (URL card and UTub header). Leaf module: the single place that owns the
// aria-disabled + `unchanged` class convention, which the coarse-pointer CSS keys
// on. Uses aria-disabled (never native `disabled`) so focus is kept, matching the
// in-flight guard convention.

export const UNCHANGED_CLASS = "unchanged";

/**
 * Marks `button` as unchanged (disabled look + aria-disabled) or, when the field
 * is dirty, lifts only the state this module set. An aria-disabled applied by an
 * in-flight guard (no `unchanged` class) is left alone.
 */
export function setConfirmButtonUnchanged({
  button,
  isUnchanged,
}: {
  button: JQuery;
  isUnchanged: boolean;
}): void {
  if (isUnchanged) {
    button.addClass(UNCHANGED_CLASS).attr("aria-disabled", "true");
    return;
  }
  button
    .filter(`.${UNCHANGED_CLASS}`)
    .removeClass(UNCHANGED_CLASS)
    .removeAttr("aria-disabled");
}

/** Removes the unchanged state entirely (panel close). */
export function clearConfirmButtonState(button: JQuery): void {
  button.removeClass(UNCHANGED_CLASS).removeAttr("aria-disabled");
}

/** True while the button is aria-disabled (unchanged or in flight). */
export function isConfirmButtonDisabled(button: JQuery): boolean {
  return button.attr("aria-disabled") === "true";
}
