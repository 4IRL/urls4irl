// Leaf module (no imports, so it adds no cycle): true only while a background
// refresh-on-focus is applying its STALE_DATA_DETECTED diff, so deck listeners
// can skip user-attention side effects (e.g. the swipe nudge) for cards that
// other members added.
let backgroundRefreshActive = false;

export function setBackgroundRefreshActive({
  active,
}: {
  active: boolean;
}): void {
  backgroundRefreshActive = active;
}

export function isBackgroundRefreshActive(): boolean {
  return backgroundRefreshActive;
}
