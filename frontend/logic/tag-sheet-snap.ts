/**
 * Pure snap-decision logic for the mobile tag-filter bottom-sheet swipe gesture.
 * Direction-agnostic and DOM-free so the threshold math is unit-testable with
 * plain values. DOM/gesture binding lives in home/tags/sheet.ts.
 */

export const SNAP_DISTANCE_FRACTION = 0.35;
export const FLING_VELOCITY_PX_PER_MS = 0.5;

/**
 * Clamp `value` to the range [min, max].
 * @example clamp({ value: 450, min: 0, max: 400 }) === 400
 * @example clamp({ value: -10, min: 0, max: 400 }) === 0
 */
export function clamp({
  value,
  min,
  max,
}: {
  value: number;
  min: number;
  max: number;
}): number {
  return Math.min(Math.max(value, min), max);
}

/**
 * Decide whether a released swipe commits the gesture (open or close).
 *
 * `draggedFraction` = fraction of the sheet height moved toward the committed
 * state (0..1). `velocity` = speed in px/ms in the commit direction (positive =
 * toward commit, negative = finger reversed away from commit). A gesture commits
 * if it has either dragged far enough OR is flinging fast enough toward commit.
 *
 * @example shouldCommitSheetGesture({ draggedFraction: 0.4, velocity: 0 }) === true
 * @example shouldCommitSheetGesture({ draggedFraction: 0.1, velocity: 0.6 }) === true
 * @example shouldCommitSheetGesture({ draggedFraction: 0.1, velocity: 0.1 }) === false
 * @example shouldCommitSheetGesture({ draggedFraction: 0.1, velocity: -1 }) === false
 */
export function shouldCommitSheetGesture({
  draggedFraction,
  velocity,
}: {
  draggedFraction: number;
  velocity: number;
}): boolean {
  return (
    draggedFraction >= SNAP_DISTANCE_FRACTION ||
    velocity >= FLING_VELOCITY_PX_PER_MS
  );
}
