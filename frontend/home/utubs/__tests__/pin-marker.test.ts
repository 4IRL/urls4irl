import { $ } from "../../../lib/globals.js";
import {
  makeUTubPinIcon,
  rowHasPinMarker,
  setRowPinMarker,
} from "../pin-marker.js";
import markerSource from "../pin-marker.ts?raw";
import templateSource from "../../../../backend/templates/components/home/UTubDeck/UTubCard.html?raw";

function makeRow({ withRole }: { withRole: boolean }): JQuery<HTMLElement> {
  const row = $(document.createElement("div"));
  row.append($(document.createElement("span")).addClass("UTubName"));
  if (withRole) {
    row.append($(document.createElement("span")).addClass("memberRole"));
  }
  return row;
}

const PATH_D = /UTubPinIcon"[^>]*>[^<]*<path d="([^"]+)"/;

function pinPathD({ source }: { source: string }): string {
  const match = PATH_D.exec(source);
  if (match === null) throw new Error("no <path d=...> found");
  return match[1];
}

describe("pin-marker", () => {
  it("uses the same pin SVG path as UTubCard.html", () => {
    expect(pinPathD({ source: markerSource })).toBe(
      pinPathD({ source: templateSource }),
    );
  });

  it("builds a bare aria-hidden icon", () => {
    const icon = makeUTubPinIcon();

    expect(icon.hasClass("UTubPinIcon")).toBe(true);
    expect(icon.attr("aria-hidden")).toBe("true");
  });

  it("inserts the marker before .memberRole", () => {
    const row = makeRow({ withRole: true });

    setRowPinMarker({ row, isPinned: true });

    const classes = row
      .children()
      .toArray()
      .map((child) => child.getAttribute("class") ?? "");
    expect(classes.findIndex((name) => name.includes("UTubPinIcon"))).toBe(
      classes.findIndex((name) => name.includes("memberRole")) - 2,
    );
    expect(row.children(".UTubPinnedLabel")).toHaveLength(1);
  });

  it("appends the marker when the row has no .memberRole child", () => {
    const row = makeRow({ withRole: false });

    setRowPinMarker({ row, isPinned: true });

    expect(rowHasPinMarker(row)).toBe(true);
    expect(row.children().last().hasClass("UTubPinnedLabel")).toBe(true);
  });

  it("keeps exactly one marker when pinned again after removal", () => {
    const row = makeRow({ withRole: true });

    setRowPinMarker({ row, isPinned: true });
    setRowPinMarker({ row, isPinned: false });
    setRowPinMarker({ row, isPinned: true });
    setRowPinMarker({ row, isPinned: true });

    expect(row.children(".UTubPinIcon")).toHaveLength(1);
    expect(row.children(".UTubPinnedLabel")).toHaveLength(1);
  });

  it("removes the marker on unpin", () => {
    const row = makeRow({ withRole: false });
    setRowPinMarker({ row, isPinned: true });

    setRowPinMarker({ row, isPinned: false });

    expect(rowHasPinMarker(row)).toBe(false);
    expect(row.children(".UTubPinnedLabel")).toHaveLength(0);
  });
});
