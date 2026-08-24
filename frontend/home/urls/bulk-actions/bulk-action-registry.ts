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
  /**
   * Optional extra CSS class(es) added to the rendered `.barBtn` — e.g. the
   * destructive "danger" variant for bulk-delete. A trusted static literal set by
   * the action itself; never user-controlled.
   */
  className?: string;
  isAvailable(context: BulkActionContext): boolean;
  /**
   * Optional ENABLED gate, distinct from `isAvailable` (which decides whether the
   * button renders at all). When present and it returns false, the bar renders
   * the button DISABLED — visible but inert (aria-disabled, no-op click, greyed)
   * with `disabledReason` surfaced — instead of hiding it. This lets bulk-delete
   * stay visible as a discoverable affordance while the current selection holds
   * no URL the user may delete, enabling only once a deletable URL is selected.
   * Absent → the action is always enabled whenever it is available.
   */
  isEnabled?(context: BulkActionContext): boolean;
  /**
   * Human-readable reason the action is disabled, shown as the button's tooltip
   * (`title`) and accessible name (`aria-label`) while `isEnabled` returns false.
   * A trusted static string (rendered via jQuery `.attr()`, never `.html()`);
   * ignored when `isEnabled` is absent or returns true.
   */
  disabledReason?: string;
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
