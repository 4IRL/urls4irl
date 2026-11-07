import { syncUTubPinDivider } from "../pin-divider.js";

const $ = window.jQuery;

type Row = { id: number; pinned: boolean; hidden?: boolean };

function seed(rows: Row[], { withDivider = false } = {}): void {
  const html = rows
    .map(
      (row) =>
        `<span class="UTubSelector${row.hidden ? " hidden" : ""}" utubid="${row.id}">${
          row.pinned ? '<svg class="UTubPinIcon"></svg>' : ""
        }<svg class="memberRole"></svg></span>`,
    )
    .join("");
  const divider = withDivider
    ? '<div id="UTubPinDivider" class="UTubPinDivider hidden" aria-hidden="true"></div>'
    : "";
  document.body.innerHTML = `<div id="listUTubs">${divider}${html}</div>`;
}

function childIDs(): string[] {
  return $("#listUTubs")
    .children()
    .map((_, element) => element.id || `row${$(element).attr("utubid")}`)
    .get();
}

function divider(): JQuery<HTMLElement> {
  return $("#listUTubs > #UTubPinDivider");
}

describe("syncUTubPinDivider", () => {
  it("creates one hidden divider for an empty deck", () => {
    document.body.innerHTML = '<div id="listUTubs"></div>';
    syncUTubPinDivider();
    expect(divider().length).toBe(1);
    expect(divider().hasClass("hidden")).toBe(true);
  });

  it("is aria-hidden with no role", () => {
    seed([{ id: 1, pinned: true }]);
    syncUTubPinDivider();
    expect(divider().attr("aria-hidden")).toBe("true");
    expect(divider().attr("role")).toBeUndefined();
  });

  it("stays hidden with no pins and sits before the first row", () => {
    seed([
      { id: 1, pinned: false },
      { id: 2, pinned: false },
    ]);
    syncUTubPinDivider();
    expect(divider().hasClass("hidden")).toBe(true);
    expect(childIDs()).toEqual(["UTubPinDivider", "row1", "row2"]);
  });

  it("stays hidden when every row is pinned and sits last", () => {
    seed([
      { id: 1, pinned: true },
      { id: 2, pinned: true },
    ]);
    syncUTubPinDivider();
    expect(divider().hasClass("hidden")).toBe(true);
    expect(childIDs()).toEqual(["row1", "row2", "UTubPinDivider"]);
  });

  it("shows between the groups when both have visible rows", () => {
    seed([
      { id: 1, pinned: true },
      { id: 2, pinned: false },
      { id: 3, pinned: false },
    ]);
    syncUTubPinDivider();
    expect(divider().hasClass("hidden")).toBe(false);
    expect(childIDs()).toEqual(["row1", "UTubPinDivider", "row2", "row3"]);
  });

  it("hides when a filter hides every pinned row", () => {
    seed([
      { id: 1, pinned: true, hidden: true },
      { id: 2, pinned: false },
    ]);
    syncUTubPinDivider();
    expect(divider().hasClass("hidden")).toBe(true);
  });

  it("hides when a filter hides every unpinned row", () => {
    seed([
      { id: 1, pinned: true },
      { id: 2, pinned: false, hidden: true },
    ]);
    syncUTubPinDivider();
    expect(divider().hasClass("hidden")).toBe(true);
  });

  it("hides after the last pinned row is removed", () => {
    seed([
      { id: 1, pinned: true },
      { id: 2, pinned: false },
    ]);
    syncUTubPinDivider();
    expect(divider().hasClass("hidden")).toBe(false);

    $('.UTubSelector[utubid="1"]').remove();
    syncUTubPinDivider();
    expect(divider().hasClass("hidden")).toBe(true);
    expect(childIDs()).toEqual(["UTubPinDivider", "row2"]);
  });

  it("repositions an existing divider and removes duplicates", () => {
    seed(
      [
        { id: 1, pinned: true },
        { id: 2, pinned: true },
        { id: 3, pinned: false },
      ],
      { withDivider: true },
    );
    $("#listUTubs").append(
      '<div id="UTubPinDivider" class="UTubPinDivider" aria-hidden="true"></div>',
    );
    syncUTubPinDivider();
    expect(divider().length).toBe(1);
    expect(childIDs()).toEqual(["row1", "row2", "UTubPinDivider", "row3"]);
    expect(divider().hasClass("hidden")).toBe(false);
  });

  it("does nothing without a deck", () => {
    document.body.innerHTML = "";
    expect(() => syncUTubPinDivider()).not.toThrow();
  });
});
