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
    previous_count: 0,
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

  it("renders the thead with rank + endpoint + hits + delta headers", () => {
    renderTopTable({ tbody, events: [buildEvent()] });

    const headerCells = table.tHead?.querySelectorAll("th") ?? [];
    expect(headerCells.length).toBe(4);
    expect(headerCells[0].textContent).toBe("#");
    expect(headerCells[1].textContent).toBe("Endpoint");
    expect(headerCells[2].textContent).toBe("Hits");
    expect(headerCells[3].textContent).toBe("Δ vs prev");
  });

  it("renders one row per event with rank, name+description, hits, and delta cells", () => {
    const events = [
      buildEvent({
        event_name: "utub_opened",
        total_count: 100,
        previous_count: 80,
      }),
      buildEvent({
        event_name: "ui_url_copy",
        description: "User copied a URL",
        category: "ui",
        total_count: 25,
        previous_count: 50,
      }),
    ];
    renderTopTable({ tbody, events });

    expect(tbody.children.length).toBe(events.length);
    const firstRow = tbody.children[0];
    expect(firstRow.children.length).toBe(4);
    expect(firstRow.children[0].textContent).toBe("1");
    expect(firstRow.children[1].querySelector(".name")?.textContent).toBe(
      "utub_opened",
    );
    expect(firstRow.children[1].querySelector(".desc")?.textContent).toBe(
      "User opened a UTub",
    );
    expect(firstRow.children[2].textContent).toBe((100).toLocaleString());
    expect(firstRow.children[3].textContent).toBe("▲ 25.0%");
    expect(firstRow.children[3].classList.contains("up")).toBe(true);

    const secondRow = tbody.children[1];
    expect(secondRow.children[0].textContent).toBe("2");
    expect(secondRow.children[3].textContent).toBe("▼ 50.0%");
    expect(secondRow.children[3].classList.contains("down")).toBe(true);
  });

  it("renders the unavailable placeholder for events with zero previous_count", () => {
    renderTopTable({
      tbody,
      events: [buildEvent({ total_count: 42, previous_count: 0 })],
    });

    const deltaCell = tbody.children[0].children[3];
    expect(deltaCell.textContent).toBe(
      APP_CONFIG.strings.METRICS_SUMMARY_DELTA_UNAVAILABLE,
    );
    expect(deltaCell.classList.contains("none")).toBe(true);
  });

  it("renders a flat delta with ' — ' and the flat class when current equals previous", () => {
    renderTopTable({
      tbody,
      events: [buildEvent({ total_count: 50, previous_count: 50 })],
    });
    const deltaCell = tbody.children[0].children[3];
    expect(deltaCell.textContent).toBe("— 0.0%");
    expect(deltaCell.classList.contains("flat")).toBe(true);
  });

  it("formats large total_count values with thousands separators", () => {
    renderTopTable({
      tbody,
      events: [buildEvent({ total_count: 1234567 })],
    });
    const totalCountCell = tbody.children[0].children[2];
    expect(totalCountCell.textContent).toBe((1234567).toLocaleString());
  });

  it("clears existing rows before rendering and re-numbers ranks", () => {
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
    expect(tbody.children[0].children[0].textContent).toBe("1");
    expect(
      tbody.children[0].children[1].querySelector(".name")?.textContent,
    ).toBe("second");
    expect(tbody.children[1].children[0].textContent).toBe("2");
    expect(
      tbody.children[1].children[1].querySelector(".name")?.textContent,
    ).toBe("third");
  });

  it("renders a single empty-state row spanning all four columns when events array is empty", () => {
    renderTopTable({ tbody, events: [] });
    expect(tbody.children.length).toBe(1);
    const emptyRow = tbody.children[0] as HTMLTableRowElement;
    expect(emptyRow.classList.contains("MetricsTopTableEmptyRow")).toBe(true);
    const emptyCell = emptyRow.querySelector(".MetricsEmptyState");
    expect(emptyCell?.textContent).toBe(APP_CONFIG.strings.METRICS_EMPTY_STATE);
    expect((emptyCell as HTMLTableCellElement | null)?.colSpan).toBe(4);
  });
});
