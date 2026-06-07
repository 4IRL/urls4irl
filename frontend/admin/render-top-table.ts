/**
 * Render the top-events table body. Clears the supplied `<tbody>` and appends
 * one `<tr>` per event row, or a single empty-state row when no events are
 * available for the active window/category.
 *
 * Pure DOM mutation; no fetching, no event binding.
 */

import type { Schema } from "../types/api-helpers.d.ts";

import { APP_CONFIG } from "../lib/config.js";

type TopEventRow = Schema<"TopEventRow">;

const EMPTY_STATE_COLUMN_SPAN = 3;

function clearChildren({ element }: { element: HTMLElement }): void {
  while (element.firstChild !== null) {
    element.removeChild(element.firstChild);
  }
}

function buildEmptyStateRow(): HTMLTableRowElement {
  const row = document.createElement("tr");
  row.className = "MetricsTopTableEmptyRow";

  const cell = document.createElement("td");
  cell.colSpan = EMPTY_STATE_COLUMN_SPAN;
  cell.className = "MetricsEmptyState";
  cell.textContent = APP_CONFIG.strings.METRICS_EMPTY_STATE;

  row.appendChild(cell);
  return row;
}

function buildEventRow({ event }: { event: TopEventRow }): HTMLTableRowElement {
  const row = document.createElement("tr");
  row.className = "MetricsTopTableRow";

  const eventNameCell = document.createElement("td");
  eventNameCell.className = "MetricsTopTableEventName";
  eventNameCell.textContent = event.event_name;

  const descriptionCell = document.createElement("td");
  descriptionCell.className = "MetricsTopTableDescription";
  descriptionCell.textContent = event.description;

  const totalCountCell = document.createElement("td");
  totalCountCell.className = "MetricsTopTableTotalCount";
  totalCountCell.textContent = event.total_count.toLocaleString();

  row.appendChild(eventNameCell);
  row.appendChild(descriptionCell);
  row.appendChild(totalCountCell);
  return row;
}

export function renderTopTable({
  tbody,
  events,
}: {
  tbody: HTMLTableSectionElement;
  events: TopEventRow[];
}): void {
  clearChildren({ element: tbody });

  if (events.length === 0) {
    tbody.appendChild(buildEmptyStateRow());
    return;
  }

  for (const event of events) {
    tbody.appendChild(buildEventRow({ event }));
  }
}
