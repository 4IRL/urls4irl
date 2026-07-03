/**
 * Pure snap-decision logic for the mobile URL-row swipe-to-delete gesture.
 * Direction-agnostic (distance-or-velocity threshold) and DOM-free so the
 * commit math is unit-testable with plain values. DOM/gesture binding lives
 * in home/urls/cards/swipe.ts.
 */

// These thresholds and clamp() intentionally mirror frontend/logic/tag-sheet-snap.ts.
// The two gestures (URL-row swipe-to-delete vs. tag-filter bottom-sheet) are tuned
// independently, so the duplication is deliberate rather than accidental drift.
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
 * Decide whether a released swipe commits the gesture (reveal → open the
 * delete-confirmation modal).
 *
 * `draggedFraction` = fraction of the reveal panel's width dragged toward the
 * committed state (0..1). `velocity` = speed in px/ms in the commit direction
 * (positive = toward commit, negative = finger reversed away from commit). A
 * gesture commits if it has either dragged far enough OR is flinging fast
 * enough toward commit.
 *
 * @example shouldCommitSwipeGesture({ draggedFraction: 0.4, velocity: 0 }) === true
 * @example shouldCommitSwipeGesture({ draggedFraction: 0.1, velocity: 0.6 }) === true
 * @example shouldCommitSwipeGesture({ draggedFraction: 0.1, velocity: 0.1 }) === false
 * @example shouldCommitSwipeGesture({ draggedFraction: 0.1, velocity: -1 }) === false
 */
export function shouldCommitSwipeGesture({
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
