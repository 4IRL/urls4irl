import type { MatchedField } from "../../types/search.js";

// Recent cross-UTub searches persisted to localStorage so the overlay can
// surface a "recent searches" list on open (empty input). Wall-clock
// timestamps (`Date.now()`) are required here — NOT `performance.now()` —
// because staleness must be computed across page reloads/sessions, and
// `performance.now()` resets to 0 on every navigation.

export interface SearchHistoryEntry {
  query: string;
  fields: MatchedField[];
  ts: number;
}

// App-owned localStorage keys are namespaced `u4i:` (see ARCHITECTURE.md).
const STORAGE_KEY = "u4i:crossSearchHistory";
const MAX_HISTORY = 8;
const MINUTE_MS = 60 * 1000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

function dedupeKey({
  query,
  fields,
}: {
  query: string;
  fields: MatchedField[];
}): string {
  return query + "|" + fields.join(",");
}

// Reads + parses the persisted history. Returns [] on any read/parse error or
// when the stored value is not a structurally valid array of entries.
export function getSearchHistory(): SearchHistoryEntry[] {
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return [];
  }
  if (raw === null) return [];

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return [];
  }
  if (!Array.isArray(parsed)) return [];

  return parsed.filter((entry): entry is SearchHistoryEntry => {
    if (entry === null || typeof entry !== "object") return false;
    const candidate = entry as Record<string, unknown>;
    return (
      typeof candidate.query === "string" &&
      Array.isArray(candidate.fields) &&
      typeof candidate.ts === "number"
    );
  });
}

// Adds (or refreshes) a history entry: an identical query+fields combo has its
// `ts` bumped to now and is moved to the front; the list is capped at
// MAX_HISTORY most-recent-first. Silently no-ops if localStorage is
// unavailable (private mode / quota), matching pane-resizer.ts.
export function pushSearchHistory({
  query,
  fields,
}: {
  query: string;
  fields: MatchedField[];
}): void {
  const key = dedupeKey({ query, fields });
  const existing = getSearchHistory().filter(
    (entry) => dedupeKey({ query: entry.query, fields: entry.fields }) !== key,
  );
  const next: SearchHistoryEntry[] = [
    { query, fields, ts: Date.now() },
    ...existing,
  ].slice(0, MAX_HISTORY);

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // localStorage may be disabled (private mode, quota) — silently ignore.
  }
}

export function clearSearchHistory(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // localStorage may be disabled (private mode, quota) — silently ignore.
  }
}

// Human-readable relative time from a `Date.now()` timestamp. Pure computation;
// the output is user-facing but interpolated, so it is not bridged via
// APP_CONFIG (the string bridge does not support interpolation).
export function formatTimeAgo(ts: number): string {
  const deltaMs = Date.now() - ts;
  if (deltaMs < MINUTE_MS) return "just now";

  if (deltaMs < HOUR_MS) {
    const minutes = Math.floor(deltaMs / MINUTE_MS);
    return minutes === 1 ? "1 minute ago" : `${minutes} minutes ago`;
  }

  if (deltaMs < DAY_MS) {
    const hours = Math.floor(deltaMs / HOUR_MS);
    return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
  }

  const days = Math.floor(deltaMs / DAY_MS);
  return days === 1 ? "1 day ago" : `${days} days ago`;
}
