// Persists the desktop user's chosen Member/Tag deck collapse layout so the
// choice survives UTub switches, reloads and Back/Forward instead of being
// force-expanded on every UTub selection. Only the Member and Tag decks are
// persisted — never the UTubs deck, whose collapse composes with the no-UTub
// auto-lock into an all-inert left panel.
//
// localStorage (not sessionStorage) because the layout is a standing
// preference: it must outlive the tab that set it, the same way
// `u4i:crossSearchHistory` and `u4i:onboardingSeen` do.
//
// Modeled on `onboarding/nudge-storage.ts`: a dependency-free leaf module that
// imports nothing from `frontend/home/**`, with every access try/catch-wrapped
// and a safe default so private-mode / quota / blocked-storage failures degrade
// silently rather than throwing.

// App-owned localStorage keys are namespaced `u4i:` (see ARCHITECTURE.md).
const STORAGE_KEY = "u4i:deckLayout";

/** The two decks whose collapsed state is persisted. */
export const PERSISTABLE_DECK = {
  MEMBERS: "members",
  TAGS: "tags",
} as const;

type PersistableDeck = (typeof PERSISTABLE_DECK)[keyof typeof PERSISTABLE_DECK];

/** The persisted layout: one collapsed flag per persistable deck. */
export interface DeckLayout {
  membersMinimized: boolean;
  tagsMinimized: boolean;
}

// Both decks expanded — the layout a first-time user sees, and the value every
// read/parse/validation failure falls back to.
const DEFAULT_DECK_LAYOUT: DeckLayout = {
  membersMinimized: false,
  tagsMinimized: false,
};

// Coerces one persisted field to a boolean, defaulting a missing or non-boolean
// value to `false` (expanded) so a corrupt value can never leave a deck stuck
// shut with no obvious way back.
function readMinimizedField(
  source: Record<string, unknown>,
  key: keyof DeckLayout,
): boolean {
  const value = source[key];
  return typeof value === "boolean" ? value : false;
}

/**
 * Reads the persisted deck layout. Returns `DEFAULT_DECK_LAYOUT` (both decks
 * expanded) on any read/parse error, when the stored value is not a
 * structurally valid object, and — per field — when the stored field is not a
 * boolean.
 */
export function getDeckLayout(): DeckLayout {
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return { ...DEFAULT_DECK_LAYOUT };
  }
  if (raw === null) return { ...DEFAULT_DECK_LAYOUT };

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return { ...DEFAULT_DECK_LAYOUT };
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return { ...DEFAULT_DECK_LAYOUT };
  }

  const candidate = parsed as Record<string, unknown>;
  return {
    membersMinimized: readMinimizedField(candidate, "membersMinimized"),
    tagsMinimized: readMinimizedField(candidate, "tagsMinimized"),
  };
}

/**
 * Persists one deck's collapsed state (read-merge-write), preserving the other
 * deck's saved state. Silently no-ops if localStorage is unavailable (private
 * mode / quota), matching `nudge-storage.ts`.
 *
 * @param deck - which persistable deck the preference is for
 *   (`PERSISTABLE_DECK.MEMBERS` or `PERSISTABLE_DECK.TAGS`).
 * @param minimized - `true` when the user collapsed the deck, `false` when they
 *   expanded it.
 */
export function setDeckMinimizedPreference({
  deck,
  minimized,
}: {
  deck: PersistableDeck;
  minimized: boolean;
}): void {
  const layout = getDeckLayout();
  if (deck === PERSISTABLE_DECK.MEMBERS) {
    layout.membersMinimized = minimized;
  } else {
    layout.tagsMinimized = minimized;
  }

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(layout));
  } catch {
    // localStorage may be disabled (private mode, quota) — silently ignore.
  }
}

/**
 * Test-only helper: clears the persisted layout so a test never leaks deck
 * state into the next test (mirrors `nudge-storage.ts`'s
 * `_resetOnboardingStorageForTests`). Silently no-ops if localStorage is
 * unavailable.
 */
export function _resetDeckLayoutStorageForTests(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // localStorage may be disabled (private mode, quota) — silently ignore.
  }
}
