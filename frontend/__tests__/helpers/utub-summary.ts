import type { UtubSummaryItem } from "../../types/utub.js";

/**
 * Build a complete UTub summary list item for tests. Every field has a default so
 * a fixture only names what it asserts on.
 */
export function makeUtubSummaryItem(
  overrides: Partial<UtubSummaryItem> = {},
): UtubSummaryItem {
  return {
    id: 1,
    name: "UTub",
    memberRole: "creator",
    isLocked: false,
    urlCount: 0,
    memberCount: 1,
    createdAt: "2026-01-01T00:00:00.000Z",
    lastUpdated: "2026-01-01T00:00:00.000Z",
    lastOpenedAt: null,
    ...overrides,
  };
}
