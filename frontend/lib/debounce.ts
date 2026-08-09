/**
 * Shared debounce utility.
 *
 * Relocated out of `frontend/admin/fragment-swap.ts` (where it originated) into
 * `frontend/lib/` so non-admin surfaces — e.g. the settings Display-preferences
 * controller — can share the single implementation instead of reaching across
 * into the admin bundle. The two admin consumers (`audit-log.ts`,
 * `user-search.ts`) import it from here.
 */

/**
 * Returns a debounced wrapper of `fn`.  Repeated calls within `delayMs`
 * milliseconds reset the timer; `fn` fires only after the last call.
 */
export function makeDebouncer(fn: () => void, delayMs: number): () => void {
  let timer: ReturnType<typeof window.setTimeout> | undefined;
  return (): void => {
    window.clearTimeout(timer);
    timer = window.setTimeout(fn, delayMs);
  };
}
