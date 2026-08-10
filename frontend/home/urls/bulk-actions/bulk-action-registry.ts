import type { UtubUrlItem } from "../../../types/url.js";

/**
 * The context a bulk action is gated and activated against. Carries the current
 * selection plus the full URL list so a future action (e.g. bulk-delete) can
 * inspect per-URL capabilities (every selected `url.canDelete`) rather than the
 * ids alone.
 */
export interface BulkActionContext {
  selectedURLCardIDs: number[];
  urls: UtubUrlItem[];
}

/**
 * A capability-aware bulk action. Phase 1 registers ZERO of these — the
 * interface plus register/query pair is the documented extension seam that
 * Phase 2 (bulk-tag) and Phase 3 (bulk-copy) plug into.
 */
export interface BulkAction {
  id: string;
  label: string;
  /**
   * Optional leading icon markup. The bar injects this as raw HTML
   * (`.prepend(iconHtml)`), so it MUST be a trusted static literal (e.g. a
   * hard-coded Bootstrap-icon `<i>` / inline SVG) — never build it by
   * interpolating user-controlled content (URL title, tag name, UTub name),
   * which would be an HTML-injection sink in the bulk bar.
   */
  iconHtml?: string;
  isAvailable(context: BulkActionContext): boolean;
  onActivate(context: BulkActionContext): void;
}

// Module-scoped registry. Deliberately empty in Phase 1; later phases append to
// it at their own module-init time.
const registeredBulkActions: BulkAction[] = [];

/** Register a bulk action into the shared registry. */
export function registerBulkAction(action: BulkAction): void {
  registeredBulkActions.push(action);
}

/**
 * The subset of registered actions whose `isAvailable(context)` is true for the
 * current selection/URL context — what the bar renders into #bulkActionButtons.
 */
export function getAvailableBulkActions(
  context: BulkActionContext,
): BulkAction[] {
  return registeredBulkActions.filter((action) => action.isAvailable(context));
}

/**
 * Clear every registered action. Test-only support so a suite that registers a
 * fake action does not leak it into sibling tests; production code never calls
 * this (registration is append-only across the app's lifetime).
 */
export function resetBulkActionRegistryForTest(): void {
  registeredBulkActions.length = 0;
}
