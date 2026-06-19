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
// Window during which a prefix-extension of the most-recent entry is treated as
// the same in-progress typing session and collapses into one entry rather than
// appending. Generous enough to span a typing burst with reading pauses, but far
// shorter than the gap between genuinely separate search sessions.
const HISTORY_COLLAPSE_WINDOW_MS = 5 * MINUTE_MS;

// True when one query is a prefix of the other (case-insensitive), i.e. they
// belong to the same forward-typing or backspacing chain (e.g. "reh" -> "rehre"
// or "rehre" -> "reh").
function isPrefixChain(left: string, right: string): boolean {
  const a = left.toLowerCase();
  const b = right.toLowerCase();
  return a.startsWith(b) || b.startsWith(a);
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

// Adds (or refreshes) a history entry. The list is most-recent-first and capped
// at MAX_HISTORY. Entries are identified by their query text alone — the search
// fields (url/title/tag) are NOT part of the identity, so re-searching the same
// query with a different field selection refreshes the single existing entry
// (bumping its `ts` to now, moving it to the front, and recording the latest
// fields) rather than adding a near-duplicate row. Crucially, an in-progress
// typing chain collapses into a single entry: because the search fetch (and thus
// this push) fires on every debounced keystroke, typing "rehrehreh" would
// otherwise leave eight partial entries — so when the most-recent entry was
// added within HISTORY_COLLAPSE_WINDOW_MS and one query is a prefix of the other,
// it is replaced rather than appended. Silently no-ops if localStorage is
// unavailable (private mode / quota), matching pane-resizer.ts.
export function pushSearchHistory({
  query,
  fields,
}: {
  query: string;
  fields: MatchedField[];
}): void {
  const now = Date.now();
  const history = getSearchHistory();
  const mostRecent = history[0];

  const collapsesIntoMostRecent =
    mostRecent !== undefined &&
    now - mostRecent.ts < HISTORY_COLLAPSE_WINDOW_MS &&
    isPrefixChain(mostRecent.query, query);

  // When collapsing the active typing chain, drop the prior (prefix) entry so
  // the chain leaves only its final query; otherwise keep all prior entries.
  const remainder = collapsesIntoMostRecent ? history.slice(1) : history;

  const deduped = remainder.filter((entry) => entry.query !== query);
  const next: SearchHistoryEntry[] = [
    { query, fields, ts: now },
    ...deduped,
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

// Removes the history entry for the given query (identity is the query text
// alone, matching pushSearchHistory) and writes the remainder back. Silently
// no-ops if localStorage is unavailable (private mode / quota).
export function removeSearchHistoryEntry({ query }: { query: string }): void {
  const remainder = getSearchHistory().filter((entry) => entry.query !== query);

  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(remainder));
  } catch {
    // localStorage may be disabled (private mode, quota) — silently ignore.
  }
}
