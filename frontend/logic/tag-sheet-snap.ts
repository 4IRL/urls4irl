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

export type ExpandableSheetOutcome = "dismiss" | "default" | "expanded";

/**
 * Resolve where a released drag leaves a two-detent (default / expanded) sheet
 * that can also be dismissed downward. `delta` = finger travel since the press
 * (positive = down); `velocity` = last-sample speed in px/ms (positive = down).
 *
 * - From default: up past the threshold expands; down past it dismisses.
 * - From expanded: down only dismisses once the finger is well past the default
 *   detent; a shorter downward drag (or a fling that has not crossed it) returns
 *   to default; everything else stays expanded.
 * Fails closed to "default" when the heights are unusable.
 *
 * @example resolveExpandableSheetRelease({ expanded: false, delta: -200, velocity: 0, defaultHeight: 400, expandedHeight: 700 }) === "expanded"
 * @example resolveExpandableSheetRelease({ expanded: true, delta: 150, velocity: 0, defaultHeight: 400, expandedHeight: 700 }) === "default"
 * @example resolveExpandableSheetRelease({ expanded: true, delta: 600, velocity: 0, defaultHeight: 400, expandedHeight: 700 }) === "dismiss"
 */
export function resolveExpandableSheetRelease({
  expanded,
  delta,
  velocity,
  defaultHeight,
  expandedHeight,
}: {
  expanded: boolean;
  delta: number;
  velocity: number;
  defaultHeight: number;
  expandedHeight: number;
}): ExpandableSheetOutcome {
  if (defaultHeight <= 0) return "default";
  const range = Math.max(expandedHeight - defaultHeight, 0);

  if (!expanded) {
    if (delta < 0) {
      if (range <= 0) return "default";
      const commitsExpand = shouldCommitSheetGesture({
        draggedFraction: clamp({ value: -delta / range, min: 0, max: 1 }),
        velocity: -velocity,
      });
      return commitsExpand ? "expanded" : "default";
    }
    const commitsDismiss = shouldCommitSheetGesture({
      draggedFraction: clamp({ value: delta / defaultHeight, min: 0, max: 1 }),
      velocity,
    });
    return commitsDismiss ? "dismiss" : "default";
  }

  const pastDefault = delta - range;
  if (
    pastDefault > 0 &&
    shouldCommitSheetGesture({
      draggedFraction: clamp({
        value: pastDefault / defaultHeight,
        min: 0,
        max: 1,
      }),
      velocity,
    })
  ) {
    return "dismiss";
  }
  if (delta <= 0 || range <= 0) return range <= 0 ? "default" : "expanded";
  const commitsCollapse = shouldCommitSheetGesture({
    draggedFraction: clamp({ value: delta / range, min: 0, max: 1 }),
    velocity,
  });
  return commitsCollapse ? "default" : "expanded";
}
