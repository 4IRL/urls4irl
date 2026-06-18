import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MatchedField } from "../../../types/search.js";

const $ = window.jQuery;

const FIELD_CONTROLS_HTML = `<div id="crossUtubSearchFieldControls"></div>`;

const DEFAULT_FIELDS: MatchedField[] = ["url", "title", "tag"];

function rowFor(field: MatchedField): JQuery<HTMLElement> {
  return $(`#crossUtubSearchFieldControls [data-field="${field}"]`);
}

function clickUp(field: MatchedField): void {
  rowFor(field).find(".crossSearchFieldUp").trigger("click");
}

function clickDown(field: MatchedField): void {
  rowFor(field).find(".crossSearchFieldDown").trigger("click");
}

function toggleInclude(field: MatchedField): void {
  // Mirror browser behavior: the checked state flips before `change` fires.
  const checkbox = rowFor(field).find(".crossSearchFieldInclude");
  checkbox.prop("checked", !checkbox.prop("checked")).trigger("change");
}

describe("field-controls", () => {
  beforeEach(() => {
    document.body.innerHTML = FIELD_CONTROLS_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("(a) default state yields the default ordered fields and the caller omits &fields=", async () => {
    const { initFieldControls, getSelectedFields } = await import(
      "../field-controls.js"
    );
    const onChange = vi.fn();
    initFieldControls({ onChange });

    expect(getSelectedFields()).toEqual(DEFAULT_FIELDS);
  });

  it("(b) deselecting tag yields the remaining checked fields in order", async () => {
    const { initFieldControls, getSelectedFields } = await import(
      "../field-controls.js"
    );
    const onChange = vi.fn();
    initFieldControls({ onChange });

    toggleInclude("tag");

    expect(getSelectedFields()).toEqual(["url", "title"]);
    expect(onChange).toHaveBeenLastCalledWith(["url", "title"]);
  });

  it("(c) reordering to title-first yields ['title','url','tag']", async () => {
    const { initFieldControls, getSelectedFields } = await import(
      "../field-controls.js"
    );
    const onChange = vi.fn();
    initFieldControls({ onChange });

    clickUp("title");

    expect(getSelectedFields()).toEqual(["title", "url", "tag"]);
    expect(onChange).toHaveBeenLastCalledWith(["title", "url", "tag"]);
  });

  it("(d) a change re-triggers the (debounced) search via onChange", async () => {
    const { initFieldControls } = await import("../field-controls.js");
    const onChange = vi.fn();
    initFieldControls({ onChange });

    clickDown("url");

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenLastCalledWith(["title", "url", "tag"]);
  });

  it("(e) up/down buttons carry aria-labels and boundary buttons are disabled", async () => {
    const { initFieldControls } = await import("../field-controls.js");
    const onChange = vi.fn();
    initFieldControls({ onChange });

    // aria-labels reference the field display name.
    expect(rowFor("url").find(".crossSearchFieldUp").attr("aria-label")).toBe(
      "Move URL up",
    );
    expect(
      rowFor("title").find(".crossSearchFieldDown").attr("aria-label"),
    ).toBe("Move Title down");

    // Default order url>title>tag: url-row up disabled, tag-row down disabled.
    const urlUp = rowFor("url").find(".crossSearchFieldUp");
    const tagDown = rowFor("tag").find(".crossSearchFieldDown");
    expect(urlUp.attr("aria-disabled")).toBe("true");
    expect(urlUp.prop("disabled")).toBe(true);
    expect(tagDown.attr("aria-disabled")).toBe("true");
    expect(tagDown.prop("disabled")).toBe(true);

    // After reordering to title>url>tag, title-row up disabled, tag-row down disabled.
    clickUp("title");
    const titleUp = rowFor("title").find(".crossSearchFieldUp");
    const tagDownAfter = rowFor("tag").find(".crossSearchFieldDown");
    expect(titleUp.attr("aria-disabled")).toBe("true");
    expect(titleUp.prop("disabled")).toBe(true);
    expect(tagDownAfter.attr("aria-disabled")).toBe("true");
    expect(tagDownAfter.prop("disabled")).toBe(true);
    // The previously-disabled url-up is now enabled.
    expect(rowFor("url").find(".crossSearchFieldUp").prop("disabled")).toBe(
      false,
    );
  });
});
