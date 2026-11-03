/**
 * Nested rows of a flow-builder step: the filter editor and the drop-off breakdown
 * (with its own filters). Pure rendering from a step and the catalog; it never reads
 * or writes the draft and never imports back into `flow-builder.ts`. The caller owns
 * state changes and re-renders a step's `.flow-builder-extras` after each one.
 */
import type { Schema } from "../types/api-helpers.d.ts";

import { APP_CONFIG } from "../lib/config.js";
import { fillTemplate } from "../lib/string-template.js";

import {
  appendStaleOption,
  makeCell,
  makeElement,
  makeOption,
  makeSelect,
  setDisabled,
} from "./flow-builder-dom.js";
import {
  listBreakdownEventGroups,
  listFilterDims,
  listGroupByDims,
  listNestedMessages,
  storedEventState,
} from "./flow-builder-state.js";
import type {
  DraftAddress,
  DraftBreakdown,
  DraftError,
  DraftFilter,
  DraftStep,
} from "./flow-builder-state.js";

type FlowCatalog = Schema<"FlowCatalogResponseSchema">;
type CatalogDim = Schema<"FlowCatalogDimSchema">;

export const FILTER_DIM_FIELD = "filter_dim";
export const FILTER_VALUE_FIELD = "filter_value";
export const ADD_FILTER_ACTION = "add-filter";
export const REMOVE_FILTER_ACTION = "remove-filter";

export const BREAKDOWN_EVENT_FIELD = "breakdown_event_name";
export const BREAKDOWN_GROUP_BY_FIELD = "breakdown_group_by";
export const BREAKDOWN_FILTER_DIM_FIELD = "breakdown_filter_dim";
export const BREAKDOWN_FILTER_VALUE_FIELD = "breakdown_filter_value";
export const ADD_BREAKDOWN_ACTION = "add-breakdown";
export const REMOVE_BREAKDOWN_ACTION = "remove-breakdown";
export const ADD_BREAKDOWN_FILTER_ACTION = "add-breakdown-filter";
export const REMOVE_BREAKDOWN_FILTER_ACTION = "remove-breakdown-filter";

const STATUS_CODE_KIND = "status_code";
const VALUES_KIND = "values";
const STATUS_CODE_MAX_LENGTH = 3;

interface RowContext {
  uid: string;
  catalog: FlowCatalog | null;
  step: DraftStep;
  position: string;
  /** Every filter and breakdown message of the step, one per address. */
  nested: DraftError[];
}

/** A list of filter rows: the step's own, or the breakdown's. */
interface FilterScope {
  kind: "filter" | "breakdown_filter";
  filters: DraftFilter[];
  dims: CatalogDim[];
  dimField: string;
  valueField: string;
  removeAction: string;
  dimLabel: string;
  valueLabel: string;
  removeLabel: string;
  idTag: string;
  /** Controls are native disabled and read-only; Remove stays usable. */
  frozen: boolean;
}

/** How a stored breakdown's event relates to the catalog. */
export type BreakdownState = "normal" | "unavailable" | "missing";

function filterReasonId({ uid, key }: { uid: string; key: number }): string {
  return `${uid}-${key}-filter-reason`;
}

function breakdownIds({ uid, key }: { uid: string; key: number }): {
  addReason: string;
  addError: string;
  addHint: string;
  filterReason: string;
  filterError: string;
  filterHint: string;
  helper: string;
  eventError: string;
  groupError: string;
  listError: string;
} {
  const base = `${uid}-${key}`;
  return {
    addReason: `${base}-breakdown-reason`,
    addError: `${base}-breakdown-damaged`,
    addHint: `${base}-breakdown-hint`,
    filterReason: `${base}-bd-filter-reason`,
    filterError: `${base}-bd-filter-damaged`,
    filterHint: `${base}-bd-filter-hint`,
    helper: `${base}-bd-helper`,
    eventError: `${base}-bd-event-error`,
    groupError: `${base}-bd-group-error`,
    listError: `${base}-bd-list-error`,
  };
}

/** The `dim_filter` list's own message ids (step level). */
function stepFilterIds({ uid, key }: { uid: string; key: number }): {
  error: string;
  hint: string;
} {
  return {
    error: `${uid}-${key}-filter-damaged`,
    hint: `${uid}-${key}-filter-hint`,
  };
}

function messagesAt({
  ctx,
  match,
}: {
  ctx: RowContext;
  match: (address: DraftAddress) => boolean;
}): DraftError[] {
  return ctx.nested.filter(
    (error) => error.address !== undefined && match(error.address),
  );
}

function texts({ errors }: { errors: readonly DraftError[] }): string[] {
  return errors.map((error) => error.message);
}

/**
 * One filter row's messages. Server messages, blank-row messages and a malformed
 * stored entry live on the row; a stale field or value sits in its own cell.
 */
function filterMessages({
  ctx,
  scope,
  filter,
}: {
  ctx: RowContext;
  scope: FilterScope;
  filter: DraftFilter;
}): { row: string[]; dim: string[]; value: string[] } {
  const mine = messagesAt({
    ctx,
    match: (address) =>
      (address.kind === "filter" || address.kind === "breakdown_filter") &&
      address.kind === scope.kind &&
      address.filterKey === filter.key,
  });
  const onRow = (error: DraftError): boolean =>
    error.server === true || error.stored === true || filter.raw !== null;
  const partOf = (error: DraftError): string =>
    error.address !== undefined && "part" in error.address
      ? error.address.part
      : "";
  return {
    row: texts({ errors: mine.filter(onRow) }),
    dim: texts({
      errors: mine.filter((error) => !onRow(error) && partOf(error) === "dim"),
    }),
    value: texts({
      errors: mine.filter(
        (error) => !onRow(error) && partOf(error) === "value",
      ),
    }),
  };
}

function filterDims({
  catalog,
  step,
}: {
  catalog: FlowCatalog | null;
  step: DraftStep;
}): CatalogDim[] {
  if (catalog === null) {
    return [];
  }
  return listFilterDims({
    catalog,
    eventName: step.eventName,
    stream: step.stream,
  });
}

function hasStepEvent({ step }: { step: DraftStep }): boolean {
  return step.stream === "api"
    ? step.apiEndpoint !== null
    : step.eventName !== null;
}

/** Shared Step 2 reason set: none, cap, all used (event is checked by the caller). */
function listReason({
  dims,
  filters,
}: {
  dims: CatalogDim[];
  filters: DraftFilter[];
}): string | null {
  const strings = APP_CONFIG.strings;
  const max = APP_CONFIG.constants.METRIC_FLOWS_MAX_FILTERS;
  if (dims.length === 0) {
    return strings.METRICS_FLOW_BUILDER_FILTER_NONE_REASON;
  }
  if (filters.length >= max) {
    return fillTemplate({
      template: strings.METRICS_FLOW_BUILDER_FILTER_LIMIT_REASON,
      values: { max: String(max) },
    });
  }
  const used = new Set(filters.map((filter) => filter.dim));
  if (dims.every((dim) => used.has(dim.key))) {
    return strings.METRICS_FLOW_BUILDER_FILTER_ALL_USED_REASON;
  }
  return null;
}

/** Why Add filter is unavailable (priority: event, none, cap, all used), or null. */
export function filterAddReason({
  catalog,
  step,
}: {
  catalog: FlowCatalog | null;
  step: DraftStep;
}): string | null {
  if (!hasStepEvent({ step })) {
    return APP_CONFIG.strings.METRICS_FLOW_BUILDER_FILTER_NEEDS_EVENT_REASON;
  }
  if (catalog === null) {
    // Still loading: stay disabled (fail closed) without claiming "no fields".
    return "";
  }
  return listReason({
    dims: filterDims({ catalog, step }),
    filters: step.filters,
  });
}

/** Why Add drop-off breakdown is unavailable, or null. "" means catalog loading. */
export function breakdownAddReason({
  catalog,
  step,
}: {
  catalog: FlowCatalog | null;
  step: DraftStep;
}): string | null {
  if (!hasStepEvent({ step })) {
    return APP_CONFIG.strings.METRICS_FLOW_BUILDER_FILTER_NEEDS_EVENT_REASON;
  }
  if (catalog === null) {
    return "";
  }
  if (listBreakdownEventGroups({ catalog }).length === 0) {
    return APP_CONFIG.strings.METRICS_FLOW_BUILDER_BREAKDOWN_UNAVAILABLE;
  }
  return null;
}

/** Classifies the stored breakdown event; only a loaded catalog can judge it. */
export function breakdownState({
  catalog,
  breakdown,
}: {
  catalog: FlowCatalog | null;
  breakdown: DraftBreakdown;
}): BreakdownState {
  const stored = storedEventState({ breakdown, catalog });
  if (stored === null) {
    return "normal";
  }
  return stored === "zero" ? "unavailable" : "missing";
}

function breakdownHelper({ state }: { state: BreakdownState }): string | null {
  if (state === "unavailable") {
    return APP_CONFIG.strings.METRICS_FLOW_BUILDER_BREAKDOWN_UNAVAILABLE;
  }
  if (state === "missing") {
    return APP_CONFIG.strings.METRICS_FLOW_BUILDER_BREAKDOWN_EVENT_MISSING;
  }
  return null;
}

function breakdownFilterDims({
  catalog,
  breakdown,
}: {
  catalog: FlowCatalog | null;
  breakdown: DraftBreakdown;
}): CatalogDim[] {
  if (catalog === null || breakdown.eventName === null) {
    return [];
  }
  return listFilterDims({ catalog, eventName: breakdown.eventName });
}

/** Why Add breakdown filter is unavailable (Step 2 order), or null. */
export function breakdownFilterAddReason({
  catalog,
  breakdown,
}: {
  catalog: FlowCatalog | null;
  breakdown: DraftBreakdown;
}): string | null {
  const helper = breakdownHelper({
    state: breakdownState({ catalog, breakdown }),
  });
  if (helper !== null) {
    return helper;
  }
  if (breakdown.eventName === null) {
    return APP_CONFIG.strings.METRICS_FLOW_BUILDER_FILTER_NEEDS_EVENT_REASON;
  }
  if (catalog === null) {
    return "";
  }
  return listReason({
    dims: breakdownFilterDims({ catalog, breakdown }),
    filters: breakdown.filters,
  });
}

function filterIds({
  uid,
  key,
  filter,
  scope,
}: {
  uid: string;
  key: number;
  filter: DraftFilter;
  scope: FilterScope;
}): { dimError: string; valueError: string; rowError: string; hint: string } {
  const base = `${uid}-${key}-${scope.idTag}${filter.key}`;
  return {
    dimError: `${base}-dim-error`,
    valueError: `${base}-value-error`,
    rowError: `${base}-row-error`,
    hint: `${base}-hint`,
  };
}

function renderDimCell({
  ctx,
  scope,
  filter,
  index,
  stale,
}: {
  ctx: RowContext;
  scope: FilterScope;
  filter: DraftFilter;
  index: number;
  stale: boolean;
}): HTMLElement {
  const strings = APP_CONFIG.strings;
  const select = makeSelect({
    field: scope.dimField,
    key: ctx.step.key,
    label: fillTemplate({
      template: scope.dimLabel,
      values: { step: ctx.position, n: String(index + 1) },
    }),
  });
  select.setAttribute("data-filter-key", String(filter.key));
  const ids = filterIds({ uid: ctx.uid, key: ctx.step.key, filter, scope });
  if (scope.frozen) {
    // Read-only: the stored field stays visible as the only option.
    select.disabled = true;
    select.append(
      makeOption({
        value: "",
        text:
          filter.raw ??
          filter.dim ??
          strings.METRICS_FLOW_BUILDER_FILTER_DIM_PLACEHOLDER,
        selected: true,
      }),
    );
    if (filter.raw !== null) {
      select.setAttribute("aria-invalid", "true");
    }
    return makeCell({
      control: select,
      field: `${scope.dimField}_${filter.key}`,
      messages: [],
      errorId: ids.dimError,
    });
  }
  const isRaw = filter.raw !== null;
  select.append(
    makeOption({
      value: "",
      text: isRaw
        ? (filter.raw ?? "")
        : strings.METRICS_FLOW_BUILDER_FILTER_DIM_PLACEHOLDER,
      selected: filter.dim === null,
    }),
  );
  if (isRaw) {
    select.setAttribute("aria-invalid", "true");
  }
  if (stale && filter.dim !== null) {
    appendStaleOption({ select, value: filter.dim });
  }
  const usedElsewhere = new Set(
    scope.filters
      .filter((other) => other.key !== filter.key)
      .flatMap((other) => (other.dim === null ? [] : [other.dim])),
  );
  for (const dim of scope.dims) {
    if (usedElsewhere.has(dim.key)) {
      continue;
    }
    select.append(
      makeOption({
        value: dim.key,
        text: dim.key,
        selected: dim.key === filter.dim,
      }),
    );
  }
  return makeCell({
    control: select,
    field: `${scope.dimField}_${filter.key}`,
    messages: filterMessages({ ctx, scope, filter }).dim,
    errorId: ids.dimError,
  });
}

function disabledValueSelect({
  ctx,
  scope,
  filter,
  index,
  text,
}: {
  ctx: RowContext;
  scope: FilterScope;
  filter: DraftFilter;
  index: number;
  text: string;
}): HTMLSelectElement {
  const select = makeSelect({
    field: scope.valueField,
    key: ctx.step.key,
    label: fillTemplate({
      template: scope.valueLabel,
      values: { step: ctx.position, n: String(index + 1) },
    }),
  });
  select.setAttribute("data-filter-key", String(filter.key));
  select.disabled = true;
  select.append(makeOption({ value: "", text, selected: true }));
  return select;
}

function renderValueCell({
  ctx,
  scope,
  filter,
  index,
  dim,
  dimStale,
}: {
  ctx: RowContext;
  scope: FilterScope;
  filter: DraftFilter;
  index: number;
  dim: CatalogDim | null;
  dimStale: boolean;
}): HTMLElement {
  const strings = APP_CONFIG.strings;
  const ids = filterIds({ uid: ctx.uid, key: ctx.step.key, filter, scope });
  const field = `${scope.valueField}_${filter.key}`;
  const label = fillTemplate({
    template: scope.valueLabel,
    values: { step: ctx.position, n: String(index + 1) },
  });
  const inertCell = (text: string): HTMLElement =>
    makeCell({
      control: disabledValueSelect({ ctx, scope, filter, index, text }),
      field,
      messages: [],
      errorId: ids.valueError,
    });
  const needsDim = strings.METRICS_FLOW_BUILDER_FILTER_VALUE_NEEDS_DIM;
  if (scope.frozen) {
    return inertCell(filter.value ?? needsDim);
  }
  if (filter.dim === null) {
    return inertCell(needsDim);
  }
  if (dim === null || dimStale) {
    return inertCell(filter.value ?? needsDim);
  }
  const attrs = {
    "data-field": scope.valueField,
    "data-filter-key": String(filter.key),
    "data-step-key": String(ctx.step.key),
    "aria-label": label,
  };
  if (dim.filter_kind === STATUS_CODE_KIND) {
    const input = makeElement({
      tag: "input",
      className: "flow-builder-input",
      attrs: {
        ...attrs,
        type: "text",
        autocomplete: "off",
        inputmode: "numeric",
        maxlength: String(STATUS_CODE_MAX_LENGTH),
        placeholder: strings.METRICS_FLOW_BUILDER_FILTER_STATUS_PLACEHOLDER,
        "aria-describedby": ids.hint,
      },
    });
    input.value = filter.value ?? "";
    const cell = makeCell({
      control: input,
      field,
      messages: [],
      errorId: ids.valueError,
      describedBy: [ids.hint],
    });
    cell.append(
      makeElement({
        tag: "p",
        className: "flow-builder-hint",
        text: strings.METRICS_FLOW_BUILDER_FILTER_STATUS_HINT,
        attrs: { id: ids.hint },
      }),
    );
    return cell;
  }
  if (dim.filter_kind !== VALUES_KIND) {
    // Fail closed: an unknown kind gets no free text box.
    return inertCell(filter.value ?? needsDim);
  }
  const select = makeSelect({
    field: scope.valueField,
    key: ctx.step.key,
    label,
  });
  select.setAttribute("data-filter-key", String(filter.key));
  select.append(
    makeOption({
      value: "",
      text: strings.METRICS_FLOW_BUILDER_FILTER_VALUE_PLACEHOLDER,
      selected: filter.value === null,
    }),
  );
  const valueStale =
    filter.value !== null && !dim.values.includes(filter.value);
  if (valueStale && filter.value !== null) {
    appendStaleOption({ select, value: filter.value });
  }
  for (const value of dim.values) {
    select.append(
      makeOption({ value, text: value, selected: value === filter.value }),
    );
  }
  return makeCell({
    control: select,
    field,
    messages: filterMessages({ ctx, scope, filter }).value,
    errorId: ids.valueError,
  });
}

function renderFilterRow({
  ctx,
  scope,
  filter,
  index,
}: {
  ctx: RowContext;
  scope: FilterScope;
  filter: DraftFilter;
  index: number;
}): HTMLElement {
  // Without a loaded catalog nothing can be judged stale.
  const dim = scope.dims.find((item) => item.key === filter.dim) ?? null;
  const dimStale =
    ctx.catalog !== null &&
    !scope.frozen &&
    filter.dim !== null &&
    filter.raw === null &&
    dim === null;
  const row = makeElement({
    tag: "div",
    className: "flow-builder-filter",
    attrs: { "data-filter-key": String(filter.key) },
  });
  const remove = makeElement({
    tag: "button",
    className: "flow-builder-icon-btn",
    attrs: {
      type: "button",
      "data-action": scope.removeAction,
      "data-filter-key": String(filter.key),
      "aria-label": fillTemplate({
        template: scope.removeLabel,
        values: { step: ctx.position, n: String(index + 1) },
      }),
    },
  });
  const dimCell = renderDimCell({ ctx, scope, filter, index, stale: dimStale });
  const valueCell = renderValueCell({
    ctx,
    scope,
    filter,
    index,
    dim,
    dimStale,
  });
  row.append(dimCell, valueCell, remove);
  const rowMessages = filterMessages({ ctx, scope, filter }).row;
  if (rowMessages.length > 0) {
    const rowErrorId = filterIds({
      uid: ctx.uid,
      key: ctx.step.key,
      filter,
      scope,
    }).rowError;
    row.append(
      makeElement({
        tag: "p",
        className: "flow-builder-error",
        text: rowMessages.join(" "),
        attrs: { id: rowErrorId },
      }),
    );
    for (const cell of [dimCell, valueCell]) {
      const control = cell.querySelector("[data-field]");
      control?.setAttribute("aria-invalid", "true");
      const describedBy = control?.getAttribute("aria-describedby");
      control?.setAttribute(
        "aria-describedby",
        describedBy === null || describedBy === undefined
          ? rowErrorId
          : `${describedBy} ${rowErrorId}`,
      );
    }
  }
  return row;
}

function renderFilterGroup({
  ctx,
  scope,
  ariaLabel,
}: {
  ctx: RowContext;
  scope: FilterScope;
  ariaLabel: string;
}): HTMLElement {
  const group = makeElement({
    tag: "div",
    className: "flow-builder-filters",
    attrs: { role: "group", "aria-label": ariaLabel },
  });
  group.append(
    makeElement({
      tag: "p",
      className: "flow-builder-group-title",
      text: APP_CONFIG.strings.METRICS_FLOW_BUILDER_FILTERS_HEADING,
      attrs: { "aria-hidden": "true" },
    }),
    ...scope.filters.map((filter, index) =>
      renderFilterRow({ ctx, scope, filter, index }),
    ),
  );
  return group;
}

/** A button whose visible text comes first, with the hidden step suffix after it. */
function makeSuffixedButton({
  action,
  text,
  position,
}: {
  action: string;
  text: string;
  position: string;
}): HTMLButtonElement {
  const button = makeElement({
    tag: "button",
    className: "flow-builder-btn",
    attrs: { type: "button", "data-action": action },
    text,
  });
  button.append(
    makeElement({
      tag: "span",
      className: "visually-hidden",
      text: fillTemplate({
        template: APP_CONFIG.strings.METRICS_FLOW_BUILDER_FOR_STEP_SUFFIX,
        values: { step: position },
      }),
    }),
  );
  return button;
}

/** A message that belongs to an Add control (a list-level or damaged one). */
interface AddNotice {
  errorId: string;
  hintId: string;
  messages: string[];
  /** Names the other way out; shown only when Add is disabled, never for a server message. */
  hint: string | null;
}

/**
 * Disables `button` for `reason`, appends the adjacent reason text when one exists,
 * then the notice (message, then recourse hint) linked from the button.
 */
function applyReason({
  button,
  container,
  reason,
  reasonId,
  notice = null,
}: {
  button: HTMLButtonElement;
  container: HTMLElement;
  reason: string | null;
  reasonId: string;
  notice?: AddNotice | null;
}): void {
  setDisabled({ element: button, disabled: reason !== null, reasonId });
  const describedBy: string[] = [];
  if (reason === "") {
    // Disabled with nothing to say yet (catalog loading): no dangling describedby.
    button.removeAttribute("aria-describedby");
  } else if (reason !== null) {
    container.append(
      makeElement({
        tag: "p",
        className: "flow-builder-reason",
        text: reason,
        attrs: { id: reasonId },
      }),
    );
    describedBy.push(reasonId);
  }
  if (notice === null || notice.messages.length === 0) {
    return;
  }
  container.append(
    makeElement({
      tag: "p",
      className: "flow-builder-error",
      text: notice.messages.join(" "),
      attrs: { id: notice.errorId },
    }),
  );
  describedBy.push(notice.errorId);
  if (reason !== null && notice.hint !== null) {
    container.append(
      makeElement({
        tag: "p",
        className: "flow-builder-hint",
        text: notice.hint,
        attrs: { id: notice.hintId },
      }),
    );
    describedBy.push(notice.hintId);
  }
  button.setAttribute("aria-describedby", describedBy.join(" "));
}

/** The notice for a list-level spot, or null when it has nothing to show. */
function noticeAt({
  ctx,
  match,
  errorId,
  hintId,
  hint,
  damaged,
}: {
  ctx: RowContext;
  match: (address: DraftAddress) => boolean;
  errorId: string;
  hintId: string;
  hint: string;
  /** A damaged stored value owns this spot: the hint shows even beside a server message. */
  damaged: boolean;
}): AddNotice | null {
  const errors = messagesAt({ ctx, match });
  if (errors.length === 0) {
    return null;
  }
  return {
    errorId,
    hintId,
    messages: texts({ errors }),
    hint: damaged ? hint : null,
  };
}

function renderAddRow({ ctx }: { ctx: RowContext }): HTMLElement {
  const strings = APP_CONFIG.strings;
  const addRow = makeElement({ tag: "div", className: "flow-builder-add-row" });
  const filterButton = makeSuffixedButton({
    action: ADD_FILTER_ACTION,
    position: ctx.position,
    text: fillTemplate({
      template: strings.METRICS_FLOW_BUILDER_ADD_FILTER,
      values: {
        count: String(ctx.step.filters.length),
        max: String(APP_CONFIG.constants.METRIC_FLOWS_MAX_FILTERS),
      },
    }),
  });
  addRow.append(filterButton);
  const filterIds = stepFilterIds({ uid: ctx.uid, key: ctx.step.key });
  applyReason({
    button: filterButton,
    container: addRow,
    reason: filterAddReason({ catalog: ctx.catalog, step: ctx.step }),
    reasonId: filterReasonId({ uid: ctx.uid, key: ctx.step.key }),
    notice: noticeAt({
      ctx,
      match: (address) => address.kind === "filters",
      errorId: filterIds.error,
      hintId: filterIds.hint,
      hint: strings.METRICS_FLOW_BUILDER_DAMAGED_RECOURSE_STEP,
      damaged: ctx.step.damaged !== null && "dim_filter" in ctx.step.damaged,
    }),
  });
  if (ctx.step.breakdown === null) {
    // The button is replaced by the block while a breakdown exists: 1 per step.
    const breakdownButton = makeSuffixedButton({
      action: ADD_BREAKDOWN_ACTION,
      position: ctx.position,
      text: strings.METRICS_FLOW_BUILDER_ADD_BREAKDOWN,
    });
    addRow.append(breakdownButton);
    const ids = breakdownIds({ uid: ctx.uid, key: ctx.step.key });
    applyReason({
      button: breakdownButton,
      container: addRow,
      reason: breakdownAddReason({ catalog: ctx.catalog, step: ctx.step }),
      reasonId: ids.addReason,
      notice: noticeAt({
        ctx,
        match: (address) =>
          address.kind === "breakdown" && address.part === "add",
        errorId: ids.addError,
        hintId: ids.addHint,
        hint: strings.METRICS_FLOW_BUILDER_DAMAGED_RECOURSE_STEP,
        damaged:
          ctx.step.damaged !== null && "drop_breakdown" in ctx.step.damaged,
      }),
    });
  }
  return addRow;
}

function renderBreakdownEventCell({
  ctx,
  breakdown,
  state,
}: {
  ctx: RowContext;
  breakdown: DraftBreakdown;
  state: BreakdownState;
}): HTMLElement {
  const strings = APP_CONFIG.strings;
  const ids = breakdownIds({ uid: ctx.uid, key: ctx.step.key });
  const select = makeSelect({
    field: BREAKDOWN_EVENT_FIELD,
    key: ctx.step.key,
    label: fillTemplate({
      template: strings.METRICS_FLOW_BUILDER_BREAKDOWN_EVENT_LABEL,
      values: { step: ctx.position },
    }),
  });
  select.append(
    makeOption({
      value: "",
      text: strings.METRICS_FLOW_BUILDER_BREAKDOWN_EVENT_PLACEHOLDER,
      selected: breakdown.eventName === null,
    }),
  );
  if (breakdown.eventName !== null) {
    if (ctx.catalog === null) {
      // Catalog still loading: keep the stored value visible, judge nothing yet.
      select.append(
        makeOption({
          value: breakdown.eventName,
          text: breakdown.eventName,
          selected: true,
        }),
      );
    } else if (state === "missing") {
      appendStaleOption({ select, value: breakdown.eventName });
    } else if (state === "unavailable") {
      // Exists but has no groupable dim: a plain selected option, not "(no longer exists)".
      select.append(
        makeOption({
          value: breakdown.eventName,
          text: breakdown.eventName,
          selected: true,
        }),
      );
      select.setAttribute("aria-invalid", "true");
    }
  }
  const catalog = ctx.catalog;
  if (catalog !== null) {
    for (const group of listBreakdownEventGroups({ catalog })) {
      const optgroup = makeElement({
        tag: "optgroup",
        attrs: { label: group.category },
      });
      for (const event of group.events) {
        optgroup.append(
          makeOption({
            value: event.event_name,
            text: event.event_name,
            selected: event.event_name === breakdown.eventName,
          }),
        );
      }
      select.append(optgroup);
    }
  }
  const helper = breakdownHelper({ state });
  // The helper already says a missing or ungroupable event; no second copy.
  const messages = texts({
    errors: messagesAt({
      ctx,
      match: (address) =>
        address.kind === "breakdown" && address.part === "event",
    }),
  }).filter((text) => text !== helper);
  const cell = makeCell({
    control: select,
    field: BREAKDOWN_EVENT_FIELD,
    messages,
    errorId: ids.eventError,
    describedBy: helper === null ? [] : [ids.helper],
  });
  if (messages.length === 0 && helper !== null) {
    select.setAttribute("aria-describedby", ids.helper);
  }
  return cell;
}

function renderBreakdownGroupCell({
  ctx,
  breakdown,
  state,
}: {
  ctx: RowContext;
  breakdown: DraftBreakdown;
  state: BreakdownState;
}): HTMLElement {
  const strings = APP_CONFIG.strings;
  const ids = breakdownIds({ uid: ctx.uid, key: ctx.step.key });
  const select = makeSelect({
    field: BREAKDOWN_GROUP_BY_FIELD,
    key: ctx.step.key,
    label: fillTemplate({
      template: strings.METRICS_FLOW_BUILDER_BREAKDOWN_GROUP_BY_LABEL,
      values: { step: ctx.position },
    }),
  });
  const placeholder =
    strings.METRICS_FLOW_BUILDER_BREAKDOWN_GROUP_BY_PLACEHOLDER;
  if (state !== "normal" || breakdown.eventName === null) {
    // Read-only: shows the stored value (or the placeholder) until an event is chosen.
    select.disabled = true;
    select.append(
      makeOption({
        value: "",
        text: breakdown.groupBy ?? placeholder,
        selected: true,
      }),
    );
    if (state !== "normal") {
      select.setAttribute("aria-describedby", ids.helper);
    }
    return makeCell({
      control: select,
      field: BREAKDOWN_GROUP_BY_FIELD,
      messages: [],
      errorId: ids.groupError,
    });
  }
  select.append(
    makeOption({
      value: "",
      text: placeholder,
      selected: breakdown.groupBy === null,
    }),
  );
  const dims =
    ctx.catalog === null
      ? []
      : listGroupByDims({
          catalog: ctx.catalog,
          eventName: breakdown.eventName,
        });
  if (ctx.catalog === null && breakdown.groupBy !== null) {
    select.append(
      makeOption({
        value: breakdown.groupBy,
        text: breakdown.groupBy,
        selected: true,
      }),
    );
  }
  const messages = texts({
    errors: messagesAt({
      ctx,
      match: (address) =>
        address.kind === "breakdown" && address.part === "group_by",
    }),
  });
  const stale =
    ctx.catalog !== null &&
    breakdown.groupBy !== null &&
    !dims.some((dim) => dim.key === breakdown.groupBy);
  if (stale && breakdown.groupBy !== null) {
    appendStaleOption({ select, value: breakdown.groupBy });
  }
  for (const dim of dims) {
    select.append(
      makeOption({
        value: dim.key,
        text: dim.key,
        selected: dim.key === breakdown.groupBy,
      }),
    );
  }
  return makeCell({
    control: select,
    field: BREAKDOWN_GROUP_BY_FIELD,
    messages,
    errorId: ids.groupError,
  });
}

function renderBreakdown({
  ctx,
  breakdown,
}: {
  ctx: RowContext;
  breakdown: DraftBreakdown;
}): HTMLElement {
  const strings = APP_CONFIG.strings;
  const ids = breakdownIds({ uid: ctx.uid, key: ctx.step.key });
  const state = breakdownState({ catalog: ctx.catalog, breakdown });
  const frozen = state !== "normal";
  const block = makeElement({
    tag: "div",
    className: "flow-builder-breakdown",
    attrs: {
      role: "group",
      "aria-label":
        strings.METRICS_FLOW_BUILDER_BREAKDOWN_HEADING +
        fillTemplate({
          template: strings.METRICS_FLOW_BUILDER_FOR_STEP_SUFFIX,
          values: { step: ctx.position },
        }),
    },
  });
  const head = makeElement({
    tag: "div",
    className: "flow-builder-breakdown-head",
  });
  const removeButton = makeSuffixedButton({
    action: REMOVE_BREAKDOWN_ACTION,
    position: ctx.position,
    text: strings.METRICS_FLOW_BUILDER_REMOVE_BREAKDOWN,
  });
  head.append(
    makeElement({
      tag: "p",
      className: "flow-builder-group-title",
      text: strings.METRICS_FLOW_BUILDER_BREAKDOWN_HEADING,
      attrs: { "aria-hidden": "true" },
    }),
    removeButton,
  );
  const grid = makeElement({
    tag: "div",
    className: "flow-builder-breakdown-grid",
  });
  grid.append(
    renderBreakdownEventCell({ ctx, breakdown, state }),
    renderBreakdownGroupCell({ ctx, breakdown, state }),
  );
  block.append(head, grid);
  const listMessages = texts({
    errors: messagesAt({
      ctx,
      match: (address) =>
        address.kind === "breakdown" && address.part === "list",
    }),
  });
  if (listMessages.length > 0) {
    block.append(
      makeElement({
        tag: "p",
        className: "flow-builder-error",
        text: listMessages.join(" "),
        attrs: { id: ids.listError },
      }),
    );
  }
  const helper = breakdownHelper({ state });
  if (helper !== null) {
    block.append(
      makeElement({
        tag: "p",
        className: "flow-builder-hint",
        text: helper,
        attrs: { id: ids.helper },
      }),
    );
  }
  const scope: FilterScope = {
    kind: "breakdown_filter",
    filters: breakdown.filters,
    dims: breakdownFilterDims({ catalog: ctx.catalog, breakdown }),
    dimField: BREAKDOWN_FILTER_DIM_FIELD,
    valueField: BREAKDOWN_FILTER_VALUE_FIELD,
    removeAction: REMOVE_BREAKDOWN_FILTER_ACTION,
    dimLabel: strings.METRICS_FLOW_BUILDER_BREAKDOWN_FILTER_DIM_LABEL,
    valueLabel: strings.METRICS_FLOW_BUILDER_BREAKDOWN_FILTER_VALUE_LABEL,
    removeLabel: strings.METRICS_FLOW_BUILDER_BREAKDOWN_FILTER_REMOVE_LABEL,
    idTag: "bf",
    frozen,
  };
  if (breakdown.filters.length > 0) {
    block.append(
      renderFilterGroup({
        ctx,
        scope,
        ariaLabel: fillTemplate({
          template: strings.METRICS_FLOW_BUILDER_BREAKDOWN_FILTERS_LABEL,
          values: { step: ctx.position },
        }),
      }),
    );
  }
  const addRow = makeElement({ tag: "div", className: "flow-builder-add-row" });
  const addButton = makeSuffixedButton({
    action: ADD_BREAKDOWN_FILTER_ACTION,
    position: ctx.position,
    text: fillTemplate({
      template: strings.METRICS_FLOW_BUILDER_ADD_BREAKDOWN_FILTER,
      values: {
        count: String(breakdown.filters.length),
        max: String(APP_CONFIG.constants.METRIC_FLOWS_MAX_FILTERS),
      },
    }),
  });
  addRow.append(addButton);
  const notice = noticeAt({
    ctx,
    match: (address) => address.kind === "breakdown_filters",
    errorId: ids.filterError,
    hintId: ids.filterHint,
    hint: strings.METRICS_FLOW_BUILDER_DAMAGED_RECOURSE_BREAKDOWN,
    damaged: breakdown.damaged !== null,
  });
  if (helper !== null) {
    // The helper already says why: point Add at it, no duplicate paragraph.
    setDisabled({ element: addButton, disabled: true, reasonId: ids.helper });
    if (notice !== null) {
      applyReason({
        button: addButton,
        container: addRow,
        reason: "",
        reasonId: ids.helper,
        notice,
      });
      const described = addButton.getAttribute("aria-describedby");
      addButton.setAttribute(
        "aria-describedby",
        [ids.helper, ...(described?.split(" ") ?? [])].join(" "),
      );
    }
  } else {
    applyReason({
      button: addButton,
      container: addRow,
      reason: breakdownFilterAddReason({ catalog: ctx.catalog, breakdown }),
      reasonId: ids.filterReason,
      notice,
    });
  }
  block.append(addRow);
  return block;
}

/** The step's `.flow-builder-extras`: filters, the Add row and the breakdown block. */
export function renderExtras({
  uid,
  catalog,
  step,
  position,
}: {
  uid: string;
  catalog: FlowCatalog | null;
  step: DraftStep;
  position: string;
}): HTMLElement {
  const ctx: RowContext = {
    uid,
    catalog,
    step,
    position,
    nested: listNestedMessages({ step, catalog }),
  };
  const strings = APP_CONFIG.strings;
  const extras = makeElement({ tag: "div", className: "flow-builder-extras" });
  if (step.filters.length > 0) {
    extras.append(
      renderFilterGroup({
        ctx,
        ariaLabel:
          strings.METRICS_FLOW_BUILDER_FILTERS_HEADING +
          fillTemplate({
            template: strings.METRICS_FLOW_BUILDER_FOR_STEP_SUFFIX,
            values: { step: position },
          }),
        scope: {
          kind: "filter",
          filters: step.filters,
          dims: filterDims({ catalog, step }),
          dimField: FILTER_DIM_FIELD,
          valueField: FILTER_VALUE_FIELD,
          removeAction: REMOVE_FILTER_ACTION,
          dimLabel: strings.METRICS_FLOW_BUILDER_FILTER_DIM_LABEL,
          valueLabel: strings.METRICS_FLOW_BUILDER_FILTER_VALUE_LABEL,
          removeLabel: strings.METRICS_FLOW_BUILDER_FILTER_REMOVE_LABEL,
          idTag: "f",
          frozen: false,
        },
      }),
    );
  }
  extras.append(renderAddRow({ ctx }));
  if (step.breakdown !== null) {
    extras.append(renderBreakdown({ ctx, breakdown: step.breakdown }));
  }
  return extras;
}

/** The control of one filter row (step or breakdown) inside a step's `<li>`. */
export function findFilterControl({
  row,
  filterKey,
  field,
}: {
  row: HTMLElement;
  filterKey: number;
  field: string;
}): HTMLElement | null {
  return row.querySelector<HTMLElement>(
    `[data-field="${field}"][data-filter-key="${filterKey}"]`,
  );
}

/** A breakdown-level control (event or group_by select) inside a step's `<li>`. */
export function findBreakdownControl({
  row,
  field,
}: {
  row: HTMLElement;
  field: string;
}): HTMLElement | null {
  return row.querySelector<HTMLElement>(`[data-field="${field}"]`);
}

/** A nested action button (`add-filter`, `add-breakdown`, ...) inside a step's `<li>`. */
export function findExtrasButton({
  row,
  action,
}: {
  row: HTMLElement;
  action: string;
}): HTMLButtonElement | null {
  return row.querySelector<HTMLButtonElement>(`[data-action="${action}"]`);
}

/** The Remove button of one filter row, for a given remove action. */
export function findFilterRemoveButton({
  row,
  action,
  filterKey,
}: {
  row: HTMLElement;
  action: string;
  filterKey: number;
}): HTMLButtonElement | null {
  return row.querySelector<HTMLButtonElement>(
    `[data-action="${action}"][data-filter-key="${filterKey}"]`,
  );
}
