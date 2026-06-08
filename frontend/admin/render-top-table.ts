/**
 * Render the top-events table head + body. Replaces the entire table content
 * each call with rank + endpoint (name + description) + hits + delta columns.
 *
 * Pure DOM mutation; no fetching, no event binding.
 */

import type { Schema } from "../types/api-helpers.d.ts";

import { APP_CONFIG } from "../lib/config.js";

type TopEventRow = Schema<"TopEventRow">;

const TOTAL_COLUMNS = 4;

type DeltaDirection = "up" | "down" | "flat" | "none";

function clearChildren({ element }: { element: HTMLElement }): void {
  while (element.firstChild !== null) {
    element.removeChild(element.firstChild);
  }
}

function formatDelta({
  current,
  previous,
}: {
  current: number;
  previous: number;
}): { text: string; direction: DeltaDirection } {
  if (previous === 0) {
    return {
      text: APP_CONFIG.strings.METRICS_SUMMARY_DELTA_UNAVAILABLE,
      direction: "none",
    };
  }
  const deltaFraction = (current - previous) / previous;
  const absolutePercent = `${Math.abs(deltaFraction * 100).toFixed(1)}%`;
  if (deltaFraction > 0) {
    return { text: `▲ ${absolutePercent}`, direction: "up" };
  }
  if (deltaFraction < 0) {
    return { text: `▼ ${absolutePercent}`, direction: "down" };
  }
  return { text: `— ${absolutePercent}`, direction: "flat" };
}

function buildHeader(): HTMLTableRowElement {
  const row = document.createElement("tr");
  for (const { key, className } of [
    { key: "METRICS_TOP_TABLE_HEADER_RANK", className: "rank" },
    { key: "METRICS_TOP_TABLE_HEADER_ENDPOINT", className: "" },
    { key: "METRICS_TOP_TABLE_HEADER_HITS", className: "count" },
    { key: "METRICS_TOP_TABLE_HEADER_DELTA", className: "delta" },
  ] as const) {
    const headerCell = document.createElement("th");
    if (className !== "") {
      headerCell.className = className;
    }
    headerCell.textContent = APP_CONFIG.strings[key];
    row.appendChild(headerCell);
  }
  return row;
}

function buildEmptyStateRow(): HTMLTableRowElement {
  const row = document.createElement("tr");
  row.className = "MetricsTopTableEmptyRow";

  const cell = document.createElement("td");
  cell.colSpan = TOTAL_COLUMNS;
  cell.className = "MetricsEmptyState empty";
  cell.textContent = APP_CONFIG.strings.METRICS_EMPTY_STATE;

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
  const descriptionDiv = document.createElement("div");
  descriptionDiv.className = "desc";
  descriptionDiv.textContent = event.description;
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

export function renderTopTable({
  tbody,
  events,
  selectedEventName,
}: {
  tbody: HTMLTableSectionElement;
  events: TopEventRow[];
  selectedEventName?: string | null;
}): void {
  const table = tbody.parentElement as HTMLTableElement | null;
  if (table !== null) {
    const thead = table.tHead ?? table.createTHead();
    clearChildren({ element: thead });
    thead.appendChild(buildHeader());
  }

  clearChildren({ element: tbody });

  if (events.length === 0) {
    tbody.appendChild(buildEmptyStateRow());
    return;
  }

  events.forEach((event, index) => {
    tbody.appendChild(
      buildEventRow({
        event,
        rank: index + 1,
        isSelected: event.event_name === selectedEventName,
      }),
    );
  });
}
