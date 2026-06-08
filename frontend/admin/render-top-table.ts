/**
 * Render the top-events table head + body. Replaces the entire table content
 * each call with rank + endpoint (name + description) + hits + delta columns.
 *
 * Pure DOM mutation; no fetching, no event binding.
 */

import type { Schema } from "../types/api-helpers.d.ts";

import { APP_CONFIG } from "../lib/config.js";
import { formatDelta } from "../lib/charts/delta.js";

type TopEventRow = Schema<"TopEventRow">;

const TOTAL_COLUMNS = 4;

function clearChildren({ element }: { element: HTMLElement }): void {
  while (element.firstChild !== null) {
    element.removeChild(element.firstChild);
  }
}

function buildHeader({
  nameHeader,
}: {
  nameHeader: string;
}): HTMLTableRowElement {
  const row = document.createElement("tr");
  const headerCells: ReadonlyArray<{ text: string; className: string }> = [
    {
      text: APP_CONFIG.strings.METRICS_TOP_TABLE_HEADER_RANK,
      className: "rank",
    },
    { text: nameHeader, className: "" },
    {
      text: APP_CONFIG.strings.METRICS_TOP_TABLE_HEADER_HITS,
      className: "count",
    },
    {
      text: APP_CONFIG.strings.METRICS_TOP_TABLE_HEADER_DELTA,
      className: "delta",
    },
  ];
  for (const { text, className } of headerCells) {
    const headerCell = document.createElement("th");
    if (className !== "") {
      headerCell.className = className;
    }
    headerCell.textContent = text;
    row.appendChild(headerCell);
  }
  return row;
}

function buildEmptyStateRow({
  message,
}: {
  message: string;
}): HTMLTableRowElement {
  const row = document.createElement("tr");
  row.className = "MetricsTopTableEmptyRow";

  const cell = document.createElement("td");
  cell.colSpan = TOTAL_COLUMNS;
  cell.className = "MetricsEmptyState empty";
  cell.textContent = message;

  row.appendChild(cell);
  return row;
}

function buildEventRow({
  event,
  rank,
  isSelected,
}: {
  event: TopEventRow;
  rank: number;
  isSelected: boolean;
}): HTMLTableRowElement {
  const row = document.createElement("tr");
  row.className = "MetricsTopTableRow";
  row.dataset.eventName = event.event_name;
  row.tabIndex = 0;
  row.setAttribute(
    "aria-label",
    APP_CONFIG.strings.METRICS_TOP_TABLE_ROW_ARIA.replace(
      "{{ name }}",
      event.event_name,
    ),
  );
  if (isSelected) {
    row.setAttribute("aria-current", "true");
  }

  const rankCell = document.createElement("td");
  rankCell.className = "rank";
  rankCell.textContent = String(rank);

  const endpointCell = document.createElement("td");
  endpointCell.className = "endpoint";
  const nameDiv = document.createElement("div");
  nameDiv.className = "name";
  nameDiv.textContent = event.event_name;
  nameDiv.title = event.event_name;
  const descriptionDiv = document.createElement("div");
  descriptionDiv.className = "desc";
  descriptionDiv.textContent = event.description;
  if (event.description !== "") {
    descriptionDiv.title = event.description;
  }
  endpointCell.appendChild(nameDiv);
  endpointCell.appendChild(descriptionDiv);

  const countCell = document.createElement("td");
  countCell.className = "count";
  countCell.textContent = event.total_count.toLocaleString();

  const { text: deltaText, direction } = formatDelta({
    current: event.total_count,
    previous: event.previous_count,
  });
  const deltaCell = document.createElement("td");
  deltaCell.className = `delta ${direction}`;
  deltaCell.textContent = deltaText;

  row.appendChild(rankCell);
  row.appendChild(endpointCell);
  row.appendChild(countCell);
  row.appendChild(deltaCell);
  return row;
}

function matchesQuery({
  event,
  needle,
}: {
  event: TopEventRow;
  needle: string;
}): boolean {
  return (
    event.event_name.toLowerCase().includes(needle) ||
    event.description.toLowerCase().includes(needle)
  );
}

export function renderTopTable({
  tbody,
  events,
  selectedEventName,
  filterQuery,
  nameHeader,
}: {
  tbody: HTMLTableSectionElement;
  events: TopEventRow[];
  selectedEventName?: string | null;
  filterQuery?: string;
  nameHeader?: string;
}): void {
  // Default to the API-tab label so existing callers (and the empty-state
  // bootstrap render) stay backward-compatible without a category context.
  const resolvedHeader =
    nameHeader ?? APP_CONFIG.strings.METRICS_TOP_TABLE_HEADER_ENDPOINT;
  const table = tbody.parentElement as HTMLTableElement | null;
  if (table !== null) {
    const thead = table.tHead ?? table.createTHead();
    clearChildren({ element: thead });
    thead.appendChild(buildHeader({ nameHeader: resolvedHeader }));
  }

  clearChildren({ element: tbody });

  if (events.length === 0) {
    tbody.appendChild(
      buildEmptyStateRow({ message: APP_CONFIG.strings.METRICS_EMPTY_STATE }),
    );
    return;
  }

  const normalizedNeedle =
    filterQuery !== undefined ? filterQuery.trim().toLowerCase() : "";
  const visibleEvents =
    normalizedNeedle === ""
      ? events
      : events.filter((event) =>
          matchesQuery({ event, needle: normalizedNeedle }),
        );

  if (visibleEvents.length === 0) {
    tbody.appendChild(
      buildEmptyStateRow({
        message: APP_CONFIG.strings.METRICS_TOP_EMPTY_NO_MATCHES,
      }),
    );
    return;
  }

  visibleEvents.forEach((event, index) => {
    tbody.appendChild(
      buildEventRow({
        event,
        rank: index + 1,
        isSelected: event.event_name === selectedEventName,
      }),
    );
  });
}
