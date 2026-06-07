import type { Schema } from "../../types/api-helpers.d.ts";

import { APP_CONFIG } from "../../lib/config.js";
import { renderTopTable } from "../render-top-table.js";

type TopEventRow = Schema<"TopEventRow">;

function buildEvent(overrides: Partial<TopEventRow> = {}): TopEventRow {
  return {
    event_name: "utub_opened",
    category: "domain",
    description: "User opened a UTub",
    total_count: 42,
    ...overrides,
  };
}

describe("renderTopTable", () => {
  let table: HTMLTableElement;
  let tbody: HTMLTableSectionElement;

  beforeEach(() => {
    table = document.createElement("table");
    tbody = document.createElement("tbody");
    table.appendChild(tbody);
    document.body.appendChild(table);
  });

  afterEach(() => {
    table.remove();
  });

  it("appends one row per event with event_name, description, and total_count", () => {
    const events = [
      buildEvent({ event_name: "utub_opened", total_count: 100 }),
      buildEvent({
        event_name: "ui_url_copy",
        description: "User copied a URL",
        category: "ui",
        total_count: 25,
      }),
    ];
    renderTopTable({ tbody, events });

    expect(tbody.children.length).toBe(events.length);
    const firstRow = tbody.children[0];
    expect(firstRow.children.length).toBe(3);
    expect(firstRow.children[0].textContent).toBe("utub_opened");
    expect(firstRow.children[1].textContent).toBe("User opened a UTub");
    expect(firstRow.children[2].textContent).toBe((100).toLocaleString());
  });

  it("formats large total_count values with thousands separators", () => {
    renderTopTable({
      tbody,
      events: [buildEvent({ total_count: 1234567 })],
    });
    const totalCountCell = tbody.querySelector(".MetricsTopTableTotalCount");
    expect(totalCountCell?.textContent).toBe((1234567).toLocaleString());
  });

  it("clears existing rows before rendering", () => {
    renderTopTable({
      tbody,
      events: [buildEvent({ event_name: "first" })],
    });
    renderTopTable({
      tbody,
      events: [
        buildEvent({ event_name: "second" }),
        buildEvent({ event_name: "third" }),
      ],
    });

    expect(tbody.children.length).toBe(2);
    expect(tbody.children[0].children[0].textContent).toBe("second");
    expect(tbody.children[1].children[0].textContent).toBe("third");
  });

  it("renders a single empty-state row when events array is empty", () => {
    renderTopTable({ tbody, events: [] });
    expect(tbody.children.length).toBe(1);
    const emptyRow = tbody.children[0] as HTMLTableRowElement;
    expect(emptyRow.classList.contains("MetricsTopTableEmptyRow")).toBe(true);
    const emptyCell = emptyRow.querySelector(".MetricsEmptyState");
    expect(emptyCell?.textContent).toBe(APP_CONFIG.strings.METRICS_EMPTY_STATE);
    expect((emptyCell as HTMLTableCellElement | null)?.colSpan).toBe(3);
  });
});
