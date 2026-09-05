// Per-tip "seen once" persistence for the onboarding nudge system. A single
// namespaced key holds a JSON object mapping each seen tip id to `true`, so a
// first-time nudge is shown at most once across sessions. Persisted to
// localStorage (survives across sessions), modeled on `search-history.ts`:
// every access is try/catch-wrapped with safe defaults so private-mode / quota
// failures degrade silently rather than throwing.

// App-owned localStorage keys are namespaced `u4i:` (see ARCHITECTURE.md).
const STORAGE_KEY = "u4i:onboardingSeen";

// Reads the persisted seen-tips object, returning {} on any read/parse error or
// when the stored value is not a structurally valid object.
function readSeenTips(): Record<string, true> {
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return {};
  }
  if (raw === null) return {};

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return {};
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return {};
  }
  return parsed as Record<string, true>;
}

/**
 * True when the given tip has already been marked seen. Returns `false` on any
 * storage/parse failure so a first-time nudge still shows rather than being
 * silently suppressed by a corrupt value.
 *
 * @param tipId - the tip's stable identifier (Step 4/6 pass a `TipId` union
 *   value, which is assignable to `string`).
 */
export function hasSeenTip(tipId: string): boolean {
  return readSeenTips()[tipId] === true;
}

/**
 * Marks the given tip seen (read-merge-write), preserving any previously-seen
 * tips. Silently no-ops if localStorage is unavailable (private mode / quota),
 * matching `search-history.ts`.
 *
 * @param tipId - the tip's stable identifier.
 */
export function markTipSeen(tipId: string): void {
  const seenTips = readSeenTips();
  seenTips[tipId] = true;

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(seenTips));
  } catch {
    // localStorage may be disabled (private mode, quota) — silently ignore.
  }
}

/**
 * Clears the "seen" flag for a single tip (read-merge-write), preserving every
 * other tip's flag. Used by the "re-arm" logic in `nudges.ts`: when a tip's deck
 * regains content (the user left the empty state), its seen flag is cleared so
 * the tip becomes eligible again if the user later re-empties that deck. Reading
 * a missing/malformed value yields `{}` (via `readSeenTips`), so clearing a
 * never-seen tip is a safe no-op. Silently no-ops if localStorage is unavailable
 * (private mode / quota), matching the other accessors in this module.
 *
 * @param tipId - the tip's stable identifier.
 */
export function clearTipSeen(tipId: string): void {
  const seenTips = readSeenTips();
  delete seenTips[tipId];

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(seenTips));
  } catch {
    // localStorage may be disabled (private mode, quota) — silently ignore.
  }
}

/**
 * Clears the persisted seen-tips object so every onboarding nudge becomes
 * eligible to re-show. This is the dev-reset entry point behind the
 * `?resetNudges` URL hook (see `nudges.ts`), letting a nudge sequence be
 * replayed on a device with no DevTools console (e.g. mobile). Silently no-ops
 * if localStorage is unavailable (private mode / quota), matching the other
 * accessors in this module.
 */
export function clearAllSeenTips(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // localStorage may be disabled (private mode, quota) — silently ignore.
  }
}

/**
 * Test-only helper: clears the persisted seen-tips object so a test never leaks
 * seen state into the next test (mirrors `swipe.ts`'s
 * `_resetURLSwipeGestureForTests`). Delegates to `clearAllSeenTips` so there is
 * a single `removeItem` site.
 */
export function _resetOnboardingStorageForTests(): void {
  clearAllSeenTips();
}
