import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";

import type { MatchedField } from "../../types/search.js";

// Inline per-search field-select + ordering controls. The user picks which of
// url/title/tag to search and in what priority order; the selection is
// serialized by the caller into the comma-joined ordered `?fields=` param. The
// default (all checked, url>title>tag) is detectable so the caller can omit
// `&fields=` entirely. Inline-only — there is no persisted Settings default.

const DEFAULT_FIELD_ORDER: MatchedField[] = ["url", "title", "tag"];

// Current display order (mutated by reorder clicks).
let _fieldOrder: MatchedField[] = [...DEFAULT_FIELD_ORDER];
// Per-field include state (mutated by checkbox toggles).
let _included: Record<MatchedField, boolean> = {
  url: true,
  title: true,
  tag: true,
};
let _onChange: ((fields: MatchedField[]) => void) | null = null;

function fieldDisplayName(field: MatchedField): string {
  switch (field) {
    case "url":
      return APP_CONFIG.strings.CROSS_SEARCH_FIELD_URL;
    case "title":
      return APP_CONFIG.strings.CROSS_SEARCH_FIELD_TITLE;
    case "tag":
      return APP_CONFIG.strings.CROSS_SEARCH_FIELD_TAG;
  }
}

// Returns the checked fields in current display order.
export function getSelectedFields(): MatchedField[] {
  return _fieldOrder.filter((field) => _included[field]);
}

function notifyChange(): void {
  if (_onChange !== null) {
    _onChange(getSelectedFields());
  }
}

function swapFields({
  field,
  delta,
}: {
  field: MatchedField;
  delta: number;
}): void {
  const index = _fieldOrder.indexOf(field);
  const target = index + delta;
  if (target < 0 || target >= _fieldOrder.length) return;
  const swapped = _fieldOrder[target];
  _fieldOrder[target] = field;
  _fieldOrder[index] = swapped;
  render();
  notifyChange();
}

function buildRow(field: MatchedField, position: number): JQuery<HTMLElement> {
  const displayName = fieldDisplayName(field);
  const isFirst = position === 0;
  const isLast = position === _fieldOrder.length - 1;

  const row = $(document.createElement("div"))
    .addClass("crossSearchFieldRow")
    .attr("data-field", field);

  const include = $(document.createElement("input"))
    .addClass("crossSearchFieldInclude")
    .attr("type", "checkbox")
    .attr("aria-label", "Include " + field + " in search");
  include.prop("checked", _included[field]);
  include.on("change", () => {
    _included[field] = include.prop("checked") as boolean;
    notifyChange();
  });
  include.appendTo(row);

  $(document.createElement("label"))
    .addClass("crossSearchFieldLabel")
    .text(displayName)
    .appendTo(row);

  const upButton = $(document.createElement("button"))
    .addClass("crossSearchFieldUp")
    .attr("type", "button")
    .attr("aria-label", "Move " + displayName + " up")
    .text("▲");
  if (isFirst) {
    upButton.attr("aria-disabled", "true").prop("disabled", true);
  }
  upButton.on("click", () => swapFields({ field, delta: -1 }));
  upButton.appendTo(row);

  const downButton = $(document.createElement("button"))
    .addClass("crossSearchFieldDown")
    .attr("type", "button")
    .attr("aria-label", "Move " + displayName + " down")
    .text("▼");
  if (isLast) {
    downButton.attr("aria-disabled", "true").prop("disabled", true);
  }
  downButton.on("click", () => swapFields({ field, delta: 1 }));
  downButton.appendTo(row);

  return row;
}

function render(): void {
  const container = $("#crossUtubSearchFieldControls");
  container.empty();
  _fieldOrder.forEach((field, position) => {
    buildRow(field, position).appendTo(container);
  });
}

export function initFieldControls({
  onChange,
}: {
  onChange: (fields: MatchedField[]) => void;
}): void {
  _onChange = onChange;
  _fieldOrder = [...DEFAULT_FIELD_ORDER];
  _included = { url: true, title: true, tag: true };
  render();
}

// Programmatically resets the controls to match the given fields array:
// fields present become checked and ordered first (left-to-right); absent
// fields become unchecked and retain relative order after the present ones.
// Fires onChange after the update so the search re-triggers.
export function setFieldControls({ fields }: { fields: MatchedField[] }): void {
  const present = fields.filter((field) => DEFAULT_FIELD_ORDER.includes(field));
  const absent = DEFAULT_FIELD_ORDER.filter(
    (field) => !present.includes(field),
  );
  _fieldOrder = [...present, ...absent];
  _included = { url: false, title: false, tag: false };
  present.forEach((field) => {
    _included[field] = true;
  });
  render();
  notifyChange();
}
