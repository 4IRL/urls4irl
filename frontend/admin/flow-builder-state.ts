/**
 * Pure draft state for the custom-flow builder: no DOM, no network.
 *
 * A draft is built from a saved flow entry (or blank), edited through functions
 * that each return a new draft, validated against the shared limits, turned into a
 * request body, and mapped back from server error paths. Fields the form cannot
 * show (`dim_filter`, `drop_breakdown`, unknown keys) ride along on each step's
 * `original` so a save never loses them.
 */
import type { Schema } from "../types/api-helpers.d.ts";

import { APP_CONFIG } from "../lib/config.js";
import { fillTemplate } from "../lib/string-template.js";

type FlowEntry = Schema<"MetricFlowEntrySchema">;
type FlowCatalog = Schema<"FlowCatalogResponseSchema">;
type CatalogEvent = Schema<"FlowCatalogEventSchema">;
type CatalogDim = Schema<"FlowCatalogDimSchema">;
type CatalogEndpoint = Schema<"FlowCatalogApiEndpointSchema">;

export type StepStream = "ui" | "api" | "domain";
export type StepField = "label" | "event_name" | "api_endpoint" | "api_method";
export type DraftErrorField =
  | StepField
  | "display_name"
  | "steps"
  | "form"
  | "nested";

/**
 * Where a filter or breakdown message lives. Problems carry the focus target
 * (`breakdown` + `group_by`/`list` resolve to `event`, or `add` when no block exists).
 */
export type DraftAddress =
  | { kind: "filters" }
  | { kind: "filter"; filterKey: number; part: "dim" | "value" }
  | { kind: "breakdown"; part: "event" | "group_by" | "list" | "add" }
  | { kind: "breakdown_filters" }
  | { kind: "breakdown_filter"; filterKey: number; part: "dim" | "value" };

export interface DraftError {
  field: DraftErrorField;
  /** Step the error belongs to; null for name, step-count and form-level errors. */
  stepKey: number | null;
  message: string;
  /** Set for `nested` errors (filters and breakdown). */
  address?: DraftAddress;
  /** `nested` only: kept in `clientErrors` until edited (a blank row), not derived on read. */
  stored?: boolean;
  /** `nested` only: came from the server (`serverErrors`). */
  server?: boolean;
  /**
   * `nested` only: a second message on a control that already has a summary entry
   * (redirected onto the breakdown event select). Shown in its paragraph, not listed.
   */
  extra?: boolean;
}

export interface DraftFilter {
  key: number;
  dim: string | null;
  value: string | null;
  /** A malformed stored entry, serialized unchanged until the row is edited. */
  raw: string | null;
  serverErrors: string[];
  clientErrors: string[];
}

export interface DraftBreakdown {
  eventName: string | null;
  groupBy: string | null;
  filters: DraftFilter[];
  /** The raw non-list (or non-string-entry) stored breakdown `dim_filter`. */
  damaged: { dim_filter: unknown } | null;
  /** Unknown stored keys, serialized back unchanged. */
  extra: Record<string, unknown>;
  serverErrors: { event_name: string[]; group_by: string[] };
  clientErrors: { event_name: string[]; group_by: string[] };
}

export interface DraftListErrors {
  serverErrors: string[];
  clientErrors: string[];
}

export interface DraftListErrorMap {
  dim_filter: DraftListErrors;
  drop_breakdown: DraftListErrors;
  drop_breakdown_filters: DraftListErrors;
}

/** The raw non-list / non-object stored values; test with `in`, never truthiness. */
export interface DraftStepDamaged {
  dim_filter?: unknown;
  drop_breakdown?: unknown;
}

export interface DraftStep {
  key: number;
  /** Unknown step keys only; filters and breakdown live in their own fields. */
  original: Record<string, unknown>;
  stream: StepStream;
  label: string;
  eventName: string | null;
  apiEndpoint: string | null;
  apiMethod: string | null;
  filters: DraftFilter[];
  breakdown: DraftBreakdown | null;
  damaged: DraftStepDamaged | null;
  listErrors: DraftListErrorMap;
  errors: Record<string, string[]>;
}

export interface FlowDraft {
  flowId: string | null;
  displayName: string;
  steps: DraftStep[];
  serverErrors: DraftError[];
}

export const STREAMS: readonly StepStream[] = ["ui", "api", "domain"];
const BLANK_STEP_COUNT = 2;
const STEP_PATH = /^steps\.(\d+)\.(.+)$/;

// Module-wide so a key is never reused: server errors resolve against keys captured
// at Save, and a removed step's key must not later name a different step.
let nextStepKey = 1;

function allocateStepKey(): number {
  const key = nextStepKey;
  nextStepKey += 1;
  return key;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

export function isStream(value: unknown): value is StepStream {
  return STREAMS.some((stream) => stream === value);
}

let nextFilterKey = 1;

function emptyListErrors(): DraftListErrors {
  return { serverErrors: [], clientErrors: [] };
}

function emptyListErrorMap(): DraftListErrorMap {
  return {
    dim_filter: emptyListErrors(),
    drop_breakdown: emptyListErrors(),
    drop_breakdown_filters: emptyListErrors(),
  };
}

function createFilter({
  dim = null,
  value = null,
  raw = null,
}: {
  dim?: string | null;
  value?: string | null;
  raw?: string | null;
}): DraftFilter {
  const key = nextFilterKey;
  nextFilterKey += 1;
  return { key, dim, value, raw, serverErrors: [], clientErrors: [] };
}

/** Splits on the FIRST colon; no colon, an empty dim or an empty value stays raw. */
function filterFromEntry({ entry }: { entry: string }): DraftFilter {
  const colon = entry.indexOf(":");
  if (colon <= 0 || colon === entry.length - 1) {
    return createFilter({ dim: entry, value: null, raw: entry });
  }
  return createFilter({
    dim: entry.slice(0, colon),
    value: entry.slice(colon + 1),
  });
}

function filterToEntry({ filter }: { filter: DraftFilter }): string {
  return filter.raw ?? `${filter.dim ?? ""}:${filter.value ?? ""}`;
}

type HydratedFilters =
  | { filters: DraftFilter[]; damaged: false }
  | { filters: DraftFilter[]; damaged: true; rawValue: unknown };

/** A missing or null list is empty; a non-list or a list with a non-string is damaged. */
function filtersFromRaw({ value }: { value: unknown }): HydratedFilters {
  if (value === null || value === undefined) {
    return { filters: [], damaged: false };
  }
  if (
    !Array.isArray(value) ||
    !value.every((entry) => typeof entry === "string")
  ) {
    return { filters: [], damaged: true, rawValue: value };
  }
  return {
    filters: value.map((entry: string) => filterFromEntry({ entry })),
    damaged: false,
  };
}

function breakdownFromRaw({
  raw,
}: {
  raw: Record<string, unknown>;
}): DraftBreakdown {
  const { event_name, group_by, dim_filter, ...rest } = raw;
  const hydrated = filtersFromRaw({ value: dim_filter });
  const eventName = stringOrNull(event_name);
  const groupBy = stringOrNull(group_by);
  // A stored value the draft cannot hold (non-string, null, blank) stays in `extra`
  // so it saves back unchanged until that field is edited.
  const extra: Record<string, unknown> = { ...rest };
  if (eventName === null && "event_name" in raw) {
    extra.event_name = event_name;
  }
  if (groupBy === null && "group_by" in raw) {
    extra.group_by = group_by;
  }
  return {
    eventName,
    groupBy,
    filters: hydrated.filters,
    damaged: hydrated.damaged ? { dim_filter: hydrated.rawValue } : null,
    extra,
    serverErrors: { event_name: [], group_by: [] },
    clientErrors: { event_name: [], group_by: [] },
  };
}

function createBlankBreakdown(): DraftBreakdown {
  return {
    eventName: null,
    groupBy: null,
    filters: [],
    damaged: null,
    extra: {},
    serverErrors: { event_name: [], group_by: [] },
    clientErrors: { event_name: [], group_by: [] },
  };
}

function createBlankStep(): DraftStep {
  return {
    key: allocateStepKey(),
    original: {},
    stream: "ui",
    label: "",
    eventName: null,
    apiEndpoint: null,
    apiMethod: null,
    filters: [],
    breakdown: null,
    damaged: null,
    listErrors: emptyListErrorMap(),
    errors: {},
  };
}

function stepFromRaw({ raw }: { raw: unknown }): DraftStep {
  if (!isRecord(raw)) {
    return createBlankStep();
  }
  const { dim_filter, drop_breakdown, ...unknownKeys } = raw;
  const damaged: DraftStepDamaged = {};
  const hydrated = filtersFromRaw({ value: dim_filter });
  if (hydrated.damaged) {
    damaged.dim_filter = hydrated.rawValue;
  }
  let breakdown: DraftBreakdown | null = null;
  if (isRecord(drop_breakdown)) {
    breakdown = breakdownFromRaw({ raw: drop_breakdown });
  } else if (drop_breakdown !== null && drop_breakdown !== undefined) {
    damaged.drop_breakdown = drop_breakdown;
  }
  return {
    key: allocateStepKey(),
    original: unknownKeys,
    stream: isStream(raw.stream) ? raw.stream : "ui",
    label: typeof raw.label === "string" ? raw.label : "",
    eventName: stringOrNull(raw.event_name),
    apiEndpoint: stringOrNull(raw.api_endpoint),
    apiMethod: stringOrNull(raw.api_method),
    filters: hydrated.filters,
    breakdown,
    damaged: Object.keys(damaged).length > 0 ? damaged : null,
    listErrors: emptyListErrorMap(),
    errors: {},
  };
}

export function createBlankDraft(): FlowDraft {
  return {
    flowId: null,
    displayName: "",
    steps: Array.from({ length: BLANK_STEP_COUNT }, createBlankStep),
    serverErrors: [],
  };
}

/**
 * Builds a draft from a list entry, tolerating a raw stored definition.
 * Example: `draftFromEntry({ entry })` with `entry.errors` = `{"steps.1.label": [...]}`
 * attaches that message to the second step.
 */
export function draftFromEntry({ entry }: { entry: FlowEntry }): FlowDraft {
  const rawSteps = isRecord(entry.definition) ? entry.definition.steps : null;
  const steps = Array.isArray(rawSteps)
    ? rawSteps.map((raw) => stepFromRaw({ raw }))
    : Array.from({ length: BLANK_STEP_COUNT }, createBlankStep);
  const draft: FlowDraft = {
    flowId: entry.id,
    displayName: entry.display_name,
    steps,
    serverErrors: [],
  };
  return applyServerErrors({
    draft,
    errors: entry.errors ?? {},
    submitted: captureSubmitted({ draft }),
  });
}

// ---------------------------------------------------------------------------
// Request body, dirty tracking
// ---------------------------------------------------------------------------

function stepToRequest({
  step,
}: {
  step: DraftStep;
}): Schema<"LenientFlowStep"> {
  const isApi = step.stream === "api";
  return {
    ...step.original,
    stream: step.stream,
    label: step.label.trim(),
    event_name: isApi ? null : step.eventName,
    api_endpoint: isApi ? step.apiEndpoint : null,
    api_method: isApi ? step.apiMethod : null,
    dim_filter: serializeFilters({
      filters: step.filters,
      damaged: step.damaged,
    }) as Schema<"LenientFlowStep">["dim_filter"],
    drop_breakdown: serializeBreakdown({
      step,
    }) as Schema<"LenientFlowStep">["drop_breakdown"],
  };
}

/** Empty gives null; a damaged raw value is sent unchanged. */
function serializeFilters({
  filters,
  damaged,
}: {
  filters: DraftFilter[];
  damaged: { dim_filter?: unknown } | null;
}): unknown {
  if (damaged !== null && "dim_filter" in damaged) {
    return damaged.dim_filter;
  }
  return filters.length === 0
    ? null
    : filters.map((filter) => filterToEntry({ filter }));
}

function serializeBreakdown({ step }: { step: DraftStep }): unknown {
  if (step.damaged !== null && "drop_breakdown" in step.damaged) {
    return step.damaged.drop_breakdown;
  }
  const breakdown = step.breakdown;
  if (breakdown === null) {
    return null;
  }
  const body: Record<string, unknown> = {
    ...breakdown.extra,
    dim_filter: serializeFilters({
      filters: breakdown.filters,
      damaged: breakdown.damaged,
    }),
  };
  if (breakdown.eventName !== null) {
    body.event_name = breakdown.eventName;
  }
  if (breakdown.groupBy !== null) {
    body.group_by = breakdown.groupBy;
  }
  return body;
}

/**
 * The body for create or update. Only edited fields are overwritten, so hidden
 * filters, breakdowns and unknown keys travel with their step.
 */
export function toRequestBody({
  draft,
}: {
  draft: FlowDraft;
}): Schema<"LenientFlowDefinition"> {
  return {
    display_name: draft.displayName.trim(),
    steps: draft.steps.map((step) => stepToRequest({ step })),
  };
}

function canonicalize(value: unknown): unknown {
  if (typeof value === "string") {
    return value.trim();
  }
  if (Array.isArray(value)) {
    return value.map(canonicalize);
  }
  if (isRecord(value)) {
    const result: Record<string, unknown> = {};
    for (const key of Object.keys(value).sort()) {
      const entry = value[key];
      if (entry !== null && entry !== undefined) {
        result[key] = canonicalize(entry);
      }
    }
    return result;
  }
  return value;
}

/**
 * Stable string form of what a save would send: keys sorted, strings trimmed,
 * `null` and missing treated alike. `key`, `errors`, `serverErrors` and
 * message lists never enter it.
 */
export function normalizeDraft({ draft }: { draft: FlowDraft }): string {
  return JSON.stringify(canonicalize(toRequestBody({ draft })));
}

export function isDraftDirty({
  draft,
  snapshot,
}: {
  draft: FlowDraft;
  snapshot: string;
}): boolean {
  return normalizeDraft({ draft }) !== snapshot;
}

// ---------------------------------------------------------------------------
// Edits
// ---------------------------------------------------------------------------

function mapStep({
  draft,
  key,
  update,
}: {
  draft: FlowDraft;
  key: number;
  update: (step: DraftStep) => DraftStep;
}): FlowDraft {
  if (!draft.steps.some((step) => step.key === key)) {
    return draft;
  }
  return {
    ...draft,
    steps: draft.steps.map((step) => (step.key === key ? update(step) : step)),
  };
}

/** True while the step carries a filter, a breakdown or a damaged stored value. */
export function hasNestedContent({ step }: { step: DraftStep }): boolean {
  return (
    step.filters.length > 0 || step.breakdown !== null || step.damaged !== null
  );
}

/** Drops filters, breakdown, any damaged value and their list messages. */
function resetNested({ step }: { step: DraftStep }): DraftStep {
  if (!hasNestedContent({ step })) {
    return step;
  }
  return {
    ...step,
    filters: [],
    breakdown: null,
    damaged: null,
    listErrors: emptyListErrorMap(),
  };
}

// ---------------------------------------------------------------------------
// Filter and breakdown edits
// ---------------------------------------------------------------------------

function withoutDamagedKey({
  damaged,
  field,
}: {
  damaged: DraftStepDamaged | null;
  field: keyof DraftStepDamaged;
}): DraftStepDamaged | null {
  if (damaged === null || !(field in damaged)) {
    return damaged;
  }
  const rest: DraftStepDamaged = { ...damaged };
  delete rest[field];
  return Object.keys(rest).length > 0 ? rest : null;
}

function withoutKey({
  record,
  field,
}: {
  record: Record<string, unknown>;
  field: string;
}): Record<string, unknown> {
  const rest = { ...record };
  delete rest[field];
  return rest;
}

function mapFilter({
  filters,
  filterKey,
  update,
}: {
  filters: DraftFilter[];
  filterKey: number;
  update: (filter: DraftFilter) => DraftFilter;
}): DraftFilter[] {
  return filters.map((filter) =>
    filter.key === filterKey ? update(filter) : filter,
  );
}

function editedDim({
  filter,
  dim,
}: {
  filter: DraftFilter;
  dim: string | null;
}): DraftFilter {
  return {
    ...filter,
    dim: dim === "" ? null : dim,
    value: null,
    raw: null,
    serverErrors: [],
    clientErrors: [],
  };
}

function editedValue({
  filter,
  value,
}: {
  filter: DraftFilter;
  value: string | null;
}): DraftFilter {
  return {
    ...filter,
    value: value === "" ? null : value,
    raw: null,
    serverErrors: [],
    clientErrors: [],
  };
}

export function addFilter({
  draft,
  key,
}: {
  draft: FlowDraft;
  key: number;
}): FlowDraft {
  return mapStep({
    draft,
    key,
    update: (step) => ({
      ...step,
      filters: [...step.filters, createFilter({})],
      damaged: withoutDamagedKey({
        damaged: step.damaged,
        field: "dim_filter",
      }),
      listErrors: { ...step.listErrors, dim_filter: emptyListErrors() },
    }),
  });
}

export function removeFilter({
  draft,
  key,
  filterKey,
}: {
  draft: FlowDraft;
  key: number;
  filterKey: number;
}): FlowDraft {
  return mapStep({
    draft,
    key,
    update: (step) => ({
      ...step,
      filters: step.filters.filter((filter) => filter.key !== filterKey),
      listErrors: { ...step.listErrors, dim_filter: emptyListErrors() },
    }),
  });
}

export function setFilterDim({
  draft,
  key,
  filterKey,
  dim,
}: {
  draft: FlowDraft;
  key: number;
  filterKey: number;
  dim: string | null;
}): FlowDraft {
  return mapStep({
    draft,
    key,
    update: (step) => ({
      ...step,
      filters: mapFilter({
        filters: step.filters,
        filterKey,
        update: (filter) => editedDim({ filter, dim }),
      }),
      listErrors: { ...step.listErrors, dim_filter: emptyListErrors() },
    }),
  });
}

export function setFilterValue({
  draft,
  key,
  filterKey,
  value,
}: {
  draft: FlowDraft;
  key: number;
  filterKey: number;
  value: string | null;
}): FlowDraft {
  return mapStep({
    draft,
    key,
    update: (step) => ({
      ...step,
      filters: mapFilter({
        filters: step.filters,
        filterKey,
        update: (filter) => editedValue({ filter, value }),
      }),
      listErrors: { ...step.listErrors, dim_filter: emptyListErrors() },
    }),
  });
}

/** Adds a blank breakdown; a no-op when one is already present. */
export function addBreakdown({
  draft,
  key,
}: {
  draft: FlowDraft;
  key: number;
}): FlowDraft {
  return mapStep({
    draft,
    key,
    update: (step) =>
      step.breakdown !== null
        ? step
        : {
            ...step,
            breakdown: createBlankBreakdown(),
            damaged: withoutDamagedKey({
              damaged: step.damaged,
              field: "drop_breakdown",
            }),
            listErrors: {
              ...step.listErrors,
              drop_breakdown: emptyListErrors(),
              drop_breakdown_filters: emptyListErrors(),
            },
          },
  });
}

/** Drops the whole breakdown (its `extra` and `damaged` included) and any damaged value. */
export function removeBreakdown({
  draft,
  key,
}: {
  draft: FlowDraft;
  key: number;
}): FlowDraft {
  return mapStep({
    draft,
    key,
    update: (step) => ({
      ...step,
      breakdown: null,
      damaged: withoutDamagedKey({
        damaged: step.damaged,
        field: "drop_breakdown",
      }),
      listErrors: {
        ...step.listErrors,
        drop_breakdown: emptyListErrors(),
        drop_breakdown_filters: emptyListErrors(),
      },
    }),
  });
}

function mapBreakdown({
  draft,
  key,
  update,
  clearList,
}: {
  draft: FlowDraft;
  key: number;
  update: (breakdown: DraftBreakdown) => DraftBreakdown;
  clearList: readonly (keyof DraftListErrorMap)[];
}): FlowDraft {
  return mapStep({
    draft,
    key,
    update: (step) => {
      if (step.breakdown === null) {
        return step;
      }
      const listErrors = { ...step.listErrors };
      for (const list of clearList) {
        listErrors[list] = emptyListErrors();
      }
      return { ...step, breakdown: update(step.breakdown), listErrors };
    },
  });
}

/** An edited event is a new breakdown: group_by, filters, `damaged` and `extra` reset. */
export function setBreakdownEvent({
  draft,
  key,
  eventName,
}: {
  draft: FlowDraft;
  key: number;
  eventName: string | null;
}): FlowDraft {
  const next = eventName === "" ? null : eventName;
  return mapBreakdown({
    draft,
    key,
    clearList: ["drop_breakdown", "drop_breakdown_filters"],
    update: (breakdown) =>
      breakdown.eventName === next
        ? breakdown
        : { ...createBlankBreakdown(), eventName: next },
  });
}

export function setBreakdownGroupBy({
  draft,
  key,
  groupBy,
}: {
  draft: FlowDraft;
  key: number;
  groupBy: string | null;
}): FlowDraft {
  return mapBreakdown({
    draft,
    key,
    clearList: ["drop_breakdown"],
    update: (breakdown) => ({
      ...breakdown,
      extra: withoutKey({ record: breakdown.extra, field: "group_by" }),
      groupBy: groupBy === "" ? null : groupBy,
      serverErrors: { ...breakdown.serverErrors, group_by: [] },
      // The only stored event message is "choose an event and group by".
      clientErrors: { event_name: [], group_by: [] },
    }),
  });
}

export function addBreakdownFilter({
  draft,
  key,
}: {
  draft: FlowDraft;
  key: number;
}): FlowDraft {
  return mapBreakdown({
    draft,
    key,
    clearList: ["drop_breakdown_filters"],
    update: (breakdown) => ({
      ...breakdown,
      filters: [...breakdown.filters, createFilter({})],
      damaged: null,
    }),
  });
}

export function removeBreakdownFilter({
  draft,
  key,
  filterKey,
}: {
  draft: FlowDraft;
  key: number;
  filterKey: number;
}): FlowDraft {
  return mapBreakdown({
    draft,
    key,
    clearList: ["drop_breakdown_filters"],
    update: (breakdown) => ({
      ...breakdown,
      filters: breakdown.filters.filter((filter) => filter.key !== filterKey),
    }),
  });
}

export function setBreakdownFilterDim({
  draft,
  key,
  filterKey,
  dim,
}: {
  draft: FlowDraft;
  key: number;
  filterKey: number;
  dim: string | null;
}): FlowDraft {
  return mapBreakdown({
    draft,
    key,
    clearList: ["drop_breakdown_filters"],
    update: (breakdown) => ({
      ...breakdown,
      filters: mapFilter({
        filters: breakdown.filters,
        filterKey,
        update: (filter) => editedDim({ filter, dim }),
      }),
    }),
  });
}

export function setBreakdownFilterValue({
  draft,
  key,
  filterKey,
  value,
}: {
  draft: FlowDraft;
  key: number;
  filterKey: number;
  value: string | null;
}): FlowDraft {
  return mapBreakdown({
    draft,
    key,
    clearList: ["drop_breakdown_filters"],
    update: (breakdown) => ({
      ...breakdown,
      filters: mapFilter({
        filters: breakdown.filters,
        filterKey,
        update: (filter) => editedValue({ filter, value }),
      }),
    }),
  });
}

export function setDisplayName({
  draft,
  value,
}: {
  draft: FlowDraft;
  value: string;
}): FlowDraft {
  return { ...draft, displayName: value };
}

export function setStepLabel({
  draft,
  key,
  value,
}: {
  draft: FlowDraft;
  key: number;
  value: string;
}): FlowDraft {
  return mapStep({
    draft,
    key,
    update: (step) => ({ ...step, label: value }),
  });
}

/** A stream change resets event, endpoint and method and clears filters and breakdown. */
export function setStepStream({
  draft,
  key,
  stream,
}: {
  draft: FlowDraft;
  key: number;
  stream: StepStream;
}): FlowDraft {
  return mapStep({
    draft,
    key,
    update: (step) =>
      step.stream === stream
        ? step
        : resetNested({
            step: {
              ...step,
              stream,
              eventName: null,
              apiEndpoint: null,
              apiMethod: null,
            },
          }),
  });
}

export function setStepEvent({
  draft,
  key,
  eventName,
}: {
  draft: FlowDraft;
  key: number;
  eventName: string | null;
}): FlowDraft {
  const next = eventName === "" ? null : eventName;
  return mapStep({
    draft,
    key,
    update: (step) =>
      step.stream === "api" || step.eventName === next
        ? step
        : resetNested({ step: { ...step, eventName: next } }),
  });
}

/**
 * Changing the endpoint is the API step's "event": filters and breakdown clear. The
 * method clears unless the catalog allows exactly one, which is then selected.
 */
export function setStepEndpoint({
  draft,
  key,
  apiEndpoint,
  catalog,
}: {
  draft: FlowDraft;
  key: number;
  apiEndpoint: string | null;
  catalog: FlowCatalog | null;
}): FlowDraft {
  const next = apiEndpoint === "" ? null : apiEndpoint;
  return mapStep({
    draft,
    key,
    update: (step) => {
      if (step.stream !== "api" || step.apiEndpoint === next) {
        return step;
      }
      const methods =
        catalog === null || next === null
          ? []
          : listMethods({ catalog, endpoint: next });
      return resetNested({
        step: {
          ...step,
          apiEndpoint: next,
          apiMethod: methods.length === 1 ? methods[0] : null,
        },
      });
    },
  });
}

/** A method change keeps filters and breakdown. */
export function setStepMethod({
  draft,
  key,
  apiMethod,
}: {
  draft: FlowDraft;
  key: number;
  apiMethod: string | null;
}): FlowDraft {
  return mapStep({
    draft,
    key,
    update: (step) => ({
      ...step,
      apiMethod: apiMethod === "" ? null : apiMethod,
    }),
  });
}

export function addStep({ draft }: { draft: FlowDraft }): FlowDraft {
  return { ...draft, steps: [...draft.steps, createBlankStep()] };
}

export function removeStep({
  draft,
  key,
}: {
  draft: FlowDraft;
  key: number;
}): FlowDraft {
  return { ...draft, steps: draft.steps.filter((step) => step.key !== key) };
}

export function moveStep({
  draft,
  key,
  direction,
}: {
  draft: FlowDraft;
  key: number;
  direction: "up" | "down";
}): FlowDraft {
  const from = draft.steps.findIndex((step) => step.key === key);
  const to = direction === "up" ? from - 1 : from + 1;
  if (from === -1 || to < 0 || to >= draft.steps.length) {
    return draft;
  }
  const steps = [...draft.steps];
  [steps[from], steps[to]] = [steps[to], steps[from]];
  return { ...draft, steps };
}

// ---------------------------------------------------------------------------
// Validation
// ---------------------------------------------------------------------------

function lengthMessage({
  template,
  min,
  max,
}: {
  template: string;
  min: number;
  max: number;
}): string {
  return fillTemplate({
    template,
    values: { min: String(min), max: String(max) },
  });
}

/**
 * Mirrors only the shared limits plus completeness and staleness of filters and
 * breakdown; semantics, control characters, uniqueness and the custom-flow cap stay
 * server-side. `catalog` is null while the catalog loads or failed: staleness is then
 * not judged (server errors still block).
 */
export function validateDraft({
  draft,
  catalog,
}: {
  draft: FlowDraft;
  catalog: FlowCatalog | null;
}): DraftError[] {
  const constants = APP_CONFIG.constants;
  const strings = APP_CONFIG.strings;
  const errors: DraftError[] = [];

  const nameLength = draft.displayName.trim().length;
  if (
    nameLength < constants.METRIC_FLOWS_NAME_MIN_LENGTH ||
    nameLength > constants.METRIC_FLOWS_NAME_MAX_LENGTH
  ) {
    errors.push({
      field: "display_name",
      stepKey: null,
      message: lengthMessage({
        template: strings.METRICS_FLOW_BUILDER_ERR_NAME_LENGTH,
        min: constants.METRIC_FLOWS_NAME_MIN_LENGTH,
        max: constants.METRIC_FLOWS_NAME_MAX_LENGTH,
      }),
    });
  }

  const count = draft.steps.length;
  if (count < constants.METRIC_FLOWS_MIN_STEPS) {
    errors.push({
      field: "steps",
      stepKey: null,
      message: fillTemplate({
        template: strings.METRICS_FLOW_BUILDER_HINT_MIN_STEPS,
        values: { min: String(constants.METRIC_FLOWS_MIN_STEPS) },
      }),
    });
  } else if (count > constants.METRIC_FLOWS_MAX_STEPS) {
    errors.push({
      field: "steps",
      stepKey: null,
      message: fillTemplate({
        template: strings.METRICS_FLOW_BUILDER_HINT_MAX_STEPS,
        values: { max: String(constants.METRIC_FLOWS_MAX_STEPS) },
      }),
    });
  }

  for (const step of draft.steps) {
    const labelLength = step.label.trim().length;
    if (
      labelLength < constants.METRIC_FLOWS_LABEL_MIN_LENGTH ||
      labelLength > constants.METRIC_FLOWS_LABEL_MAX_LENGTH
    ) {
      errors.push({
        field: "label",
        stepKey: step.key,
        message: lengthMessage({
          template: strings.METRICS_FLOW_BUILDER_ERR_LABEL_LENGTH,
          min: constants.METRIC_FLOWS_LABEL_MIN_LENGTH,
          max: constants.METRIC_FLOWS_LABEL_MAX_LENGTH,
        }),
      });
    }
    if (step.stream === "api") {
      if (!step.apiEndpoint) {
        errors.push({
          field: "api_endpoint",
          stepKey: step.key,
          message: strings.METRICS_FLOW_BUILDER_ERR_ENDPOINT_REQUIRED,
        });
      }
      if (!step.apiMethod) {
        errors.push({
          field: "api_method",
          stepKey: step.key,
          message: strings.METRICS_FLOW_BUILDER_ERR_METHOD_REQUIRED,
        });
      }
    } else if (!step.eventName) {
      errors.push({
        field: "event_name",
        stepKey: step.key,
        message: strings.METRICS_FLOW_BUILDER_ERR_EVENT_REQUIRED,
      });
    }
    for (const issue of deriveNestedIssues({ step, catalog })) {
      errors.push({
        field: "nested",
        stepKey: step.key,
        message: issue.message,
        address: issue.address,
        stored: issue.stored,
      });
    }
  }
  return errors;
}

/**
 * Puts client validation results where server errors live (name and step-count
 * errors in `serverErrors`, step errors on their step), replacing earlier errors.
 * Filter and breakdown rows are different: only the `clientErrors` lists are
 * replaced, every `serverErrors` list is kept, and a client message is skipped
 * where a server message already exists. Only blank-row messages are stored;
 * stale, damaged and unavailable messages are derived on read, so an edit retires
 * them without bookkeeping.
 */
export function applyValidationErrors({
  draft,
  errors,
}: {
  draft: FlowDraft;
  errors: readonly DraftError[];
}): FlowDraft {
  return {
    ...draft,
    serverErrors: errors.filter((error) => error.stepKey === null),
    steps: draft.steps.map((step) => {
      const forStep: Record<string, string[]> = {};
      const stored: DraftError[] = [];
      for (const error of errors) {
        if (error.stepKey !== step.key) {
          continue;
        }
        if (error.field !== "nested") {
          forStep[error.field] = [
            ...(forStep[error.field] ?? []),
            error.message,
          ];
        } else if (error.stored === true) {
          stored.push(error);
        }
      }
      return storeClientErrors({
        step: { ...step, errors: forStep },
        issues: stored,
      });
    }),
  };
}

/** Replaces a step's stored client messages with `issues`, never over a server message. */
function storeClientErrors({
  step,
  issues,
}: {
  step: DraftStep;
  issues: readonly DraftError[];
}): DraftStep {
  const cleared = (filters: DraftFilter[]): DraftFilter[] =>
    filters.map((filter) => ({ ...filter, clientErrors: [] }));
  let filters = cleared(step.filters);
  let breakdown: DraftBreakdown | null =
    step.breakdown === null
      ? null
      : {
          ...step.breakdown,
          filters: cleared(step.breakdown.filters),
          clientErrors: { event_name: [], group_by: [] },
        };
  const withMessage = ({
    list,
    filterKey,
    message,
  }: {
    list: DraftFilter[];
    filterKey: number;
    message: string;
  }): DraftFilter[] =>
    list.map((filter) =>
      filter.key === filterKey && filter.serverErrors.length === 0
        ? { ...filter, clientErrors: [message] }
        : filter,
    );
  for (const issue of issues) {
    const address = issue.address;
    if (address === undefined) {
      continue;
    }
    if (address.kind === "filter") {
      filters = withMessage({
        list: filters,
        filterKey: address.filterKey,
        message: issue.message,
      });
    } else if (address.kind === "breakdown_filter" && breakdown !== null) {
      breakdown = {
        ...breakdown,
        filters: withMessage({
          list: breakdown.filters,
          filterKey: address.filterKey,
          message: issue.message,
        }),
      };
    } else if (
      address.kind === "breakdown" &&
      (address.part === "event" || address.part === "group_by") &&
      breakdown !== null
    ) {
      const part = address.part === "event" ? "event_name" : "group_by";
      if (breakdown.serverErrors[part].length === 0) {
        breakdown = {
          ...breakdown,
          clientErrors: { ...breakdown.clientErrors, [part]: [issue.message] },
        };
      }
    }
  }
  const listErrors: DraftListErrorMap = {
    dim_filter: { ...step.listErrors.dim_filter, clientErrors: [] },
    drop_breakdown: { ...step.listErrors.drop_breakdown, clientErrors: [] },
    drop_breakdown_filters: {
      ...step.listErrors.drop_breakdown_filters,
      clientErrors: [],
    },
  };
  return { ...step, filters, breakdown, listErrors };
}

/** Drops draft-level errors (`display_name`, `steps` or `form`) of one field. */
export function clearDraftError({
  draft,
  field,
}: {
  draft: FlowDraft;
  field: DraftErrorField;
}): FlowDraft {
  if (!draft.serverErrors.some((error) => error.field === field)) {
    return draft;
  }
  return {
    ...draft,
    serverErrors: draft.serverErrors.filter((error) => error.field !== field),
  };
}

/** Replaces any form-level errors with these messages. */
export function setFormErrors({
  draft,
  messages,
}: {
  draft: FlowDraft;
  messages: readonly string[];
}): FlowDraft {
  return {
    ...draft,
    serverErrors: [
      ...draft.serverErrors.filter((error) => error.field !== "form"),
      ...messages.map((message) => ({
        field: "form" as const,
        stepKey: null,
        message,
      })),
    ],
  };
}

export interface DraftProblem extends DraftError {
  /** 1-based position of the step, null for name, step-count and form errors. */
  stepNumber: number | null;
}

const PROBLEM_FIELD_ORDER: readonly StepField[] = [
  "label",
  "event_name",
  "api_endpoint",
  "api_method",
];

/**
 * Every field-level problem in reading order: name, step count, then each step's
 * fields, then its filters and breakdown. Form-level errors are excluded; they
 * render once in their own region. `catalog` is null until the catalog loads.
 */
export function listProblems({
  draft,
  catalog,
}: {
  draft: FlowDraft;
  catalog: FlowCatalog | null;
}): DraftProblem[] {
  const problems: DraftProblem[] = [];
  for (const field of ["display_name", "steps"] as const) {
    for (const error of draft.serverErrors) {
      if (error.field === field) {
        problems.push({ ...error, stepNumber: null });
      }
    }
  }
  draft.steps.forEach((step, index) => {
    for (const field of PROBLEM_FIELD_ORDER) {
      for (const message of step.errors[field] ?? []) {
        problems.push({
          field,
          stepKey: step.key,
          message,
          stepNumber: index + 1,
        });
      }
    }
    for (const error of listNestedMessages({ step, catalog })) {
      if (error.extra !== true) {
        problems.push({ ...error, stepNumber: index + 1 });
      }
    }
  });
  return problems;
}

export function listFormErrors({ draft }: { draft: FlowDraft }): string[] {
  return draft.serverErrors
    .filter((error) => error.field === "form")
    .map((error) => error.message);
}

// ---------------------------------------------------------------------------
// Server errors
// ---------------------------------------------------------------------------

/** What one step looked like in the body that was sent, by key and position. */
export interface SubmittedStep {
  key: number;
  /** Keys of the step's `dim_filter` entries, in sent order. */
  filterKeys: number[];
  /** Keys of the breakdown's `dim_filter` entries, in sent order. */
  breakdownFilterKeys: number[];
}

/** Captures the per-step shape `toRequestBody` is about to send. */
export function captureSubmitted({
  draft,
}: {
  draft: FlowDraft;
}): SubmittedStep[] {
  return draft.steps.map((step) => ({
    key: step.key,
    filterKeys:
      step.damaged !== null && "dim_filter" in step.damaged
        ? []
        : step.filters.map((filter) => filter.key),
    breakdownFilterKeys:
      step.damaged !== null && "drop_breakdown" in step.damaged
        ? []
        : (step.breakdown?.filters.map((filter) => filter.key) ?? []),
  }));
}

const SERVER_STEP_FIELDS = [
  "label",
  "event_name",
  "api_endpoint",
  "api_method",
] as const;

function isServerStepField(
  value: string,
): value is (typeof SERVER_STEP_FIELDS)[number] {
  return SERVER_STEP_FIELDS.some((field) => field === value);
}

const ENTRY_SUFFIX = /^(dim_filter|drop_breakdown\.dim_filter)\.(\d+)$/;

/** Server error suffixes that address a whole nested list, by list key. */
const LIST_SUFFIX_KEYS: Partial<Record<string, keyof DraftListErrorMap>> = {
  dim_filter: "dim_filter",
  drop_breakdown: "drop_breakdown",
  "drop_breakdown.dim_filter": "drop_breakdown_filters",
};

/** An empty, immutable-by-convention message bag for one step's nested server messages. */
function clearServerNested({ step }: { step: DraftStep }): DraftStep {
  const cleared = (filters: DraftFilter[]): DraftFilter[] =>
    filters.map((filter) => ({ ...filter, serverErrors: [] }));
  const list = (lists: DraftListErrors): DraftListErrors => ({
    ...lists,
    serverErrors: [],
  });
  return {
    ...step,
    errors: {},
    filters: cleared(step.filters),
    breakdown:
      step.breakdown === null
        ? null
        : {
            ...step.breakdown,
            filters: cleared(step.breakdown.filters),
            serverErrors: { event_name: [], group_by: [] },
          },
    listErrors: {
      dim_filter: list(step.listErrors.dim_filter),
      drop_breakdown: list(step.listErrors.drop_breakdown),
      drop_breakdown_filters: list(step.listErrors.drop_breakdown_filters),
    },
  };
}

/** Where one dotted server error path lands, decided against the current draft. */
export type ResolvedServerPath =
  | {
      kind: "step_field";
      stepKey: number;
      field: (typeof SERVER_STEP_FIELDS)[number];
    }
  | {
      kind: "nested";
      stepKey: number;
      list: "dim_filter" | "drop_breakdown" | "drop_breakdown.dim_filter";
      /** The sent filter's key; null for the breakdown's own event/group_by. */
      entryKey: number | null;
      /** `entry` is a filter row; `event_name`/`group_by` are breakdown parts. */
      field: "entry" | "event_name" | "group_by";
    }
  | { kind: "list"; stepKey: number; list: keyof DraftListErrorMap }
  | { kind: "flow_field"; field: "display_name" | "steps" }
  | { kind: "form" };

/**
 * Resolves one server path through `submitted` (the body that was sent) to the
 * current `draft`. A target row, filter or breakdown that is gone, an unknown
 * path and `__root__`/`window` all resolve to `form`. Pure; writes nothing.
 */
export function resolveServerPath({
  path,
  submitted,
  draft,
}: {
  path: string;
  submitted: readonly SubmittedStep[];
  draft: FlowDraft;
}): ResolvedServerPath {
  if (path === "display_name" || path === "steps") {
    return { kind: "flow_field", field: path };
  }
  const match = STEP_PATH.exec(path);
  if (match === null) {
    return { kind: "form" };
  }
  const sent: SubmittedStep | undefined = submitted[Number(match[1])];
  const step = draft.steps.find((item) => item.key === sent?.key);
  if (sent === undefined || step === undefined) {
    return { kind: "form" };
  }
  const suffix = match[2];
  const stepKey = sent.key;
  if (isServerStepField(suffix)) {
    return { kind: "step_field", stepKey, field: suffix };
  }
  const list = LIST_SUFFIX_KEYS[suffix];
  if (list !== undefined) {
    return { kind: "list", stepKey, list };
  }
  if (
    suffix === "drop_breakdown.event_name" ||
    suffix === "drop_breakdown.group_by"
  ) {
    if (step.breakdown === null) {
      return { kind: "form" };
    }
    return {
      kind: "nested",
      stepKey,
      list: "drop_breakdown",
      entryKey: null,
      field: suffix === "drop_breakdown.group_by" ? "group_by" : "event_name",
    };
  }
  const entry = ENTRY_SUFFIX.exec(suffix);
  if (entry === null) {
    return { kind: "form" };
  }
  const inBreakdown = entry[1] !== "dim_filter";
  const sentKeys = inBreakdown ? sent.breakdownFilterKeys : sent.filterKeys;
  const entryKey: number | undefined = sentKeys[Number(entry[2])];
  const filters = inBreakdown ? step.breakdown?.filters : step.filters;
  if (
    entryKey === undefined ||
    !filters?.some((filter) => filter.key === entryKey)
  ) {
    return { kind: "form" };
  }
  return {
    kind: "nested",
    stepKey,
    list: inBreakdown ? "drop_breakdown.dim_filter" : "dim_filter",
    entryKey,
    field: "entry",
  };
}

/**
 * Maps dotted, 0-based server paths onto the current draft. `steps.N` resolves
 * through `submitted[N].key` (the order of the body that was sent) and then by key,
 * so errors stay with their step after a reorder. `dim_filter.M` and
 * `drop_breakdown.dim_filter.M` resolve through the captured filter keys the same
 * way. Anything whose target is gone since the submit (a removed step, filter or
 * breakdown) surfaces at form level; nothing is dropped. Replaces earlier server
 * errors and leaves client messages alone.
 */
export function applyServerErrors({
  draft,
  errors,
  submitted,
}: {
  draft: FlowDraft;
  errors: Record<string, string[]>;
  submitted: readonly SubmittedStep[];
}): FlowDraft {
  const serverErrors: DraftError[] = [];
  let steps = draft.steps.map((step) => clearServerNested({ step }));

  const addFormError = ({ path, message }: { path: string; message: string }) =>
    serverErrors.push({
      field: "form",
      stepKey: null,
      message: path === "__root__" ? message : `${path}: ${message}`,
    });

  const updateStep = ({
    key,
    update,
  }: {
    key: number;
    update: (step: DraftStep) => DraftStep | null;
  }): boolean => {
    const target = steps.find((step) => step.key === key);
    if (target === undefined) {
      return false;
    }
    const next = update(target);
    if (next === null) {
      return false;
    }
    steps = steps.map((step) => (step.key === key ? next : step));
    return true;
  };

  const withFilterMessage = ({
    filters,
    filterKey,
    message,
  }: {
    filters: DraftFilter[];
    filterKey: number | undefined;
    message: string;
  }): DraftFilter[] | null => {
    if (!filters.some((filter) => filter.key === filterKey)) {
      return null;
    }
    return filters.map((filter) =>
      filter.key === filterKey
        ? { ...filter, serverErrors: [...filter.serverErrors, message] }
        : filter,
    );
  };

  const withListMessage = ({
    step,
    list,
    message,
  }: {
    step: DraftStep;
    list: keyof DraftListErrorMap;
    message: string;
  }): DraftStep => ({
    ...step,
    listErrors: {
      ...step.listErrors,
      [list]: {
        ...step.listErrors[list],
        serverErrors: [...step.listErrors[list].serverErrors, message],
      },
    },
  });

  const applyResolved = ({
    resolved,
    message,
  }: {
    resolved: Exclude<ResolvedServerPath, { kind: "form" | "flow_field" }>;
    message: string;
  }): boolean =>
    updateStep({
      key: resolved.stepKey,
      update: (step) => {
        switch (resolved.kind) {
          case "step_field":
            return {
              ...step,
              errors: {
                ...step.errors,
                [resolved.field]: [
                  ...(step.errors[resolved.field] ?? []),
                  message,
                ],
              },
            };
          case "list":
            return withListMessage({ step, list: resolved.list, message });
          case "nested": {
            if (resolved.list === "drop_breakdown") {
              if (step.breakdown === null || resolved.field === "entry") {
                return null;
              }
              const part = resolved.field;
              return {
                ...step,
                breakdown: {
                  ...step.breakdown,
                  serverErrors: {
                    ...step.breakdown.serverErrors,
                    [part]: [...step.breakdown.serverErrors[part], message],
                  },
                },
              };
            }
            if (resolved.list === "drop_breakdown.dim_filter") {
              if (step.breakdown === null) {
                return null;
              }
              const filters = withFilterMessage({
                filters: step.breakdown.filters,
                filterKey: resolved.entryKey ?? undefined,
                message,
              });
              return filters === null
                ? null
                : { ...step, breakdown: { ...step.breakdown, filters } };
            }
            const filters = withFilterMessage({
              filters: step.filters,
              filterKey: resolved.entryKey ?? undefined,
              message,
            });
            return filters === null ? null : { ...step, filters };
          }
          default:
            return null;
        }
      },
    });

  for (const [path, messages] of Object.entries(errors)) {
    const resolved = resolveServerPath({ path, submitted, draft });
    for (const message of messages) {
      if (resolved.kind === "flow_field") {
        serverErrors.push({ field: resolved.field, stepKey: null, message });
      } else if (
        resolved.kind === "form" ||
        !applyResolved({ resolved, message })
      ) {
        addFormError({ path, message });
      }
    }
  }

  return { ...draft, serverErrors, steps };
}

// ---------------------------------------------------------------------------
// Filter and breakdown messages
// ---------------------------------------------------------------------------

interface NestedIssue {
  address: DraftAddress;
  message: string;
  /** Kept in `clientErrors` until edited rather than derived on every read. */
  stored: boolean;
}

function addressKey({ address }: { address: DraftAddress }): string {
  switch (address.kind) {
    case "filters":
    case "breakdown_filters":
      return address.kind;
    case "filter":
    case "breakdown_filter":
      return `${address.kind}:${address.filterKey}`;
    case "breakdown":
      return address.part === "list" || address.part === "add"
        ? `breakdown:${address.part}`
        : "breakdown:field";
  }
}

/** The event a step's filters are judged against; null when none is chosen. */
function filterEventName({ step }: { step: DraftStep }): string | null {
  return step.stream === "api" ? API_EVENT_NAME : step.eventName;
}

function filterIssues({
  filters,
  eventName,
  catalog,
  kind,
}: {
  filters: DraftFilter[];
  eventName: string | null;
  catalog: FlowCatalog | null;
  kind: "filter" | "breakdown_filter";
}): NestedIssue[] {
  const strings = APP_CONFIG.strings;
  const event =
    catalog === null ? null : findCatalogEvent({ catalog, eventName });
  const issues: NestedIssue[] = [];
  for (const filter of filters) {
    const dimAddress: DraftAddress = {
      kind,
      filterKey: filter.key,
      part: "dim",
    };
    if (filter.raw !== null) {
      issues.push({
        address: dimAddress,
        message: strings.METRICS_FLOW_BUILDER_FILTER_INCOMPLETE,
        stored: false,
      });
      continue;
    }
    if (filter.dim === null || filter.value === null) {
      issues.push({
        address: dimAddress,
        message: strings.METRICS_FLOW_BUILDER_FILTER_INCOMPLETE,
        stored: true,
      });
      continue;
    }
    if (event === null) {
      continue;
    }
    const dim = listFilterDimsOf({ event }).find(
      (item) => item.key === filter.dim,
    );
    if (dim === undefined) {
      issues.push({
        address: dimAddress,
        message: fillTemplate({
          template: strings.METRICS_FLOW_BUILDER_FILTER_STALE_DIM,
          values: { dim: filter.dim },
        }),
        stored: false,
      });
    } else if (
      dim.filter_kind === "values" &&
      !dim.values.includes(filter.value)
    ) {
      issues.push({
        address: { kind, filterKey: filter.key, part: "value" },
        message: strings.METRICS_FLOW_BUILDER_FILTER_STALE_VALUE,
        stored: false,
      });
    }
  }
  return issues;
}

function listFilterDimsOf({ event }: { event: CatalogEvent }): CatalogDim[] {
  return event.dims.filter((dim) => dim.filter_kind !== "group_by_only");
}

/**
 * Everything wrong with a step's filters and breakdown that does not come from the
 * server: blank rows (stored on Save), and damaged stored values and stale catalog
 * references (derived, so an edit that fixes them retires them). `catalog` null
 * skips the catalog judgements.
 */
function deriveNestedIssues({
  step,
  catalog,
}: {
  step: DraftStep;
  catalog: FlowCatalog | null;
}): NestedIssue[] {
  const strings = APP_CONFIG.strings;
  const issues: NestedIssue[] = [];
  const judged = judgedCatalog({ step, catalog });
  const damaged = step.damaged;
  if (damaged !== null && "dim_filter" in damaged) {
    issues.push({
      address: { kind: "filters" },
      message: strings.METRICS_FLOW_BUILDER_DAMAGED_FILTERS,
      stored: false,
    });
  }
  if (damaged !== null && "drop_breakdown" in damaged) {
    issues.push({
      address: { kind: "breakdown", part: "add" },
      message: strings.METRICS_FLOW_BUILDER_DAMAGED_BREAKDOWN,
      stored: false,
    });
  }
  issues.push(
    ...filterIssues({
      filters: step.filters,
      eventName: filterEventName({ step }),
      catalog: judged,
      kind: "filter",
    }),
  );
  const breakdown = step.breakdown;
  if (breakdown === null) {
    return issues;
  }
  if (breakdown.damaged !== null) {
    issues.push({
      address: { kind: "breakdown_filters" },
      message: strings.METRICS_FLOW_BUILDER_DAMAGED_BREAKDOWN_FILTERS,
      stored: false,
    });
  }
  const breakdownEvent =
    judged === null
      ? null
      : findCatalogEvent({ catalog: judged, eventName: breakdown.eventName });
  if (breakdown.eventName === null) {
    issues.push({
      address: { kind: "breakdown", part: "event" },
      message: strings.METRICS_FLOW_BUILDER_BREAKDOWN_INCOMPLETE,
      stored: true,
    });
  } else if (judged !== null && breakdownEvent === null) {
    issues.push({
      address: { kind: "breakdown", part: "event" },
      message: strings.METRICS_FLOW_BUILDER_BREAKDOWN_EVENT_MISSING,
      stored: false,
    });
  } else if (
    breakdownEvent !== null &&
    !breakdownEvent.dims.some((dim) => dim.groupable)
  ) {
    issues.push({
      address: { kind: "breakdown", part: "event" },
      message: strings.METRICS_FLOW_BUILDER_BREAKDOWN_UNAVAILABLE,
      stored: false,
    });
  } else if (breakdown.groupBy === null) {
    issues.push({
      address: { kind: "breakdown", part: "group_by" },
      message: strings.METRICS_FLOW_BUILDER_BREAKDOWN_INCOMPLETE,
      stored: true,
    });
  } else if (
    breakdownEvent !== null &&
    !breakdownEvent.dims.some(
      (dim) => dim.groupable && dim.key === breakdown.groupBy,
    )
  ) {
    issues.push({
      address: { kind: "breakdown", part: "group_by" },
      message: fillTemplate({
        template: strings.METRICS_FLOW_BUILDER_BREAKDOWN_GROUP_BY_STALE,
        values: { group_by: breakdown.groupBy },
      }),
      stored: false,
    });
  }
  // Read-only rows (missing or ungroupable event) are judged only for completeness.
  const frozen = storedEventState({ breakdown, catalog }) !== null;
  issues.push(
    ...filterIssues({
      filters: breakdown.filters,
      eventName: breakdown.eventName,
      catalog: frozen ? null : judged,
      kind: "breakdown_filter",
    }),
  );
  return issues;
}

/** The catalog to judge a step's nested rows against; null when the step event is stale or unset. */
function judgedCatalog({
  step,
  catalog,
}: {
  step: DraftStep;
  catalog: FlowCatalog | null;
}): FlowCatalog | null {
  if (catalog === null) {
    return null;
  }
  if (step.stream === "api") {
    const endpoint = step.apiEndpoint;
    return endpoint === null ||
      endpoint === "" ||
      isStaleEndpoint({ catalog, apiEndpoint: endpoint })
      ? null
      : catalog;
  }
  return step.eventName === null ||
    step.eventName === "" ||
    isStaleEvent({
      catalog,
      stream: step.stream,
      eventName: step.eventName,
    })
    ? null
    : catalog;
}

export type StoredEventState = "zero" | "missing" | null;

/** A stored breakdown event that is ungroupable ("zero") or gone ("missing"); needs a catalog. */
export function storedEventState({
  breakdown,
  catalog,
}: {
  breakdown: DraftBreakdown;
  catalog: FlowCatalog | null;
}): StoredEventState {
  if (catalog === null || breakdown.eventName === null) {
    return null;
  }
  const event = findCatalogEvent({ catalog, eventName: breakdown.eventName });
  if (event === null) {
    return "missing";
  }
  return event.dims.some((dim) => dim.groupable) ? null : "zero";
}

/**
 * The message for each filter or breakdown spot of a step, one per address, in
 * reading order. A server message wins over a client one at the same spot, and a
 * server `group_by` message on a stored zero-groupable breakdown moves to the event
 * select (nothing to choose from there).
 */
export function listNestedMessages({
  step,
  catalog,
}: {
  step: DraftStep;
  catalog: FlowCatalog | null;
}): DraftError[] {
  const breakdown = step.breakdown;
  const state =
    breakdown === null ? null : storedEventState({ breakdown, catalog });
  const zero = state === "zero";
  const frozen = state !== null;
  const eventAddress: DraftAddress = { kind: "breakdown", part: "event" };
  interface NestedEntry {
    error: DraftError;
    address: DraftAddress;
    redirected: boolean;
  }
  const entries: NestedEntry[] = [];
  const taken = new Set<string>();
  const push = ({
    address,
    message,
    stored,
    server,
    redirect = false,
  }: {
    address: DraftAddress;
    message: string;
    stored?: boolean;
    server?: boolean;
    redirect?: boolean;
  }) => {
    if (
      redirect &&
      entries.some(
        (entry) => entry.redirected && entry.error.message === message,
      )
    ) {
      return;
    }
    if (stored === true || server === true) {
      taken.add(addressKey({ address }));
    }
    const target = redirect ? eventAddress : address;
    entries.push({
      error: {
        field: "nested",
        stepKey: step.key,
        message,
        address: target,
        stored,
        server,
      },
      address: target,
      redirected: redirect,
    });
  };

  const lists = step.listErrors;
  for (const message of lists.dim_filter.serverErrors) {
    push({ address: { kind: "filters" }, message, server: true });
  }
  for (const filter of step.filters) {
    const address: DraftAddress = {
      kind: "filter",
      filterKey: filter.key,
      part: "dim",
    };
    for (const message of filter.serverErrors) {
      push({ address, message, server: true });
    }
    for (const message of filter.clientErrors) {
      push({ address, message, stored: true });
    }
  }
  for (const message of lists.drop_breakdown.serverErrors) {
    push({
      address: {
        kind: "breakdown",
        part: breakdown === null ? "add" : "list",
      },
      message,
      server: true,
    });
  }
  if (breakdown !== null) {
    for (const message of breakdown.serverErrors.event_name) {
      push({ address: eventAddress, message, server: true });
    }
    // A stored zero-groupable event leaves nothing to choose in group_by or the
    // breakdown filters, so their server messages land on the event select.
    for (const message of breakdown.serverErrors.group_by) {
      push({
        address: { kind: "breakdown", part: "group_by" },
        message,
        server: true,
        redirect: zero,
      });
    }
    for (const message of breakdown.clientErrors.event_name) {
      push({ address: eventAddress, message, stored: true });
    }
    for (const message of breakdown.clientErrors.group_by) {
      push({
        address: { kind: "breakdown", part: "group_by" },
        message,
        stored: true,
        redirect: frozen,
      });
    }
    for (const message of lists.drop_breakdown_filters.serverErrors) {
      push({
        address: { kind: "breakdown_filters" },
        message,
        server: true,
        redirect: zero,
      });
    }
    for (const filter of breakdown.filters) {
      const address: DraftAddress = {
        kind: "breakdown_filter",
        filterKey: filter.key,
        part: "dim",
      };
      for (const message of filter.serverErrors) {
        push({ address, message, server: true, redirect: zero });
      }
      for (const message of filter.clientErrors) {
        push({ address, message, stored: true, redirect: frozen });
      }
    }
  }
  if (
    entries.some((entry) => entry.redirected && entry.error.server === true)
  ) {
    // A redirected server message replaces the derived event message.
    taken.add(addressKey({ address: eventAddress }));
  }

  for (const issue of deriveNestedIssues({ step, catalog })) {
    if (issue.stored || taken.has(addressKey({ address: issue.address }))) {
      continue;
    }
    push({
      ...issue,
      redirect: frozen && issue.address.kind === "breakdown_filter",
    });
  }

  const position = ({ address }: NestedEntry): number => {
    const rows =
      address.kind === "filter"
        ? step.filters
        : address.kind === "breakdown_filter"
          ? (breakdown?.filters ?? [])
          : [];
    const row =
      "filterKey" in address
        ? rows.findIndex((filter) => filter.key === address.filterKey)
        : 0;
    return nestedSection({ address }) * 1000 + Math.max(row, 0);
  };
  const rank = (entry: NestedEntry): number =>
    position(entry) * 2 + (entry.redirected ? 1 : 0);
  const sorted = [...entries].sort((left, right) => rank(left) - rank(right));
  // Redirected messages share the event select with at most one summary entry.
  let listed = sorted.some(
    (entry) =>
      !entry.redirected &&
      addressKey({ address: entry.address }) ===
        addressKey({ address: eventAddress }) &&
      nestedSection({ address: entry.address }) === 3,
  );
  return sorted.map(({ error, redirected }) => {
    if (!redirected) {
      return error;
    }
    const extra = listed;
    listed = true;
    return extra ? { ...error, extra: true } : error;
  });
}

/** Reading-order bucket of an address (the `listProblems` order per step). */
function nestedSection({ address }: { address: DraftAddress }): number {
  switch (address.kind) {
    case "filters":
      return 0;
    case "filter":
      return 1;
    case "breakdown":
      if (address.part === "list" || address.part === "add") {
        return 2;
      }
      return address.part === "event" ? 3 : 4;
    case "breakdown_filters":
      return 5;
    case "breakdown_filter":
      return 6;
  }
}

// ---------------------------------------------------------------------------
// Catalog helpers
// ---------------------------------------------------------------------------

const API_EVENT_NAME = "api_hit";

/** Searches every group (any category, `step_allowed` or not); null when absent. */
export function findCatalogEvent({
  catalog,
  eventName,
}: {
  catalog: FlowCatalog;
  eventName: string | null;
}): CatalogEvent | null {
  if (eventName === null) {
    return null;
  }
  for (const group of catalog.event_groups) {
    const found = group.events.find((event) => event.event_name === eventName);
    if (found !== undefined) {
      return found;
    }
  }
  return null;
}

function dimsFor({
  catalog,
  eventName,
  stream,
}: {
  catalog: FlowCatalog;
  eventName: string | null;
  stream?: StepStream;
}): CatalogDim[] {
  const resolved = stream === "api" ? API_EVENT_NAME : eventName;
  return findCatalogEvent({ catalog, eventName: resolved })?.dims ?? [];
}

/** Dims a filter may use: everything but `group_by_only`. API steps use `api_hit`. */
export function listFilterDims({
  catalog,
  eventName,
  stream,
}: {
  catalog: FlowCatalog;
  eventName: string | null;
  stream?: StepStream;
}): CatalogDim[] {
  const resolved = stream === "api" ? API_EVENT_NAME : eventName;
  const event = findCatalogEvent({ catalog, eventName: resolved });
  return event === null ? [] : listFilterDimsOf({ event });
}

/** Groupable dims only. API steps use `api_hit`. */
export function listGroupByDims({
  catalog,
  eventName,
  stream,
}: {
  catalog: FlowCatalog;
  eventName: string | null;
  stream?: StepStream;
}): CatalogDim[] {
  return dimsFor({ catalog, eventName, stream }).filter((dim) => dim.groupable);
}

export interface BreakdownEventGroup {
  category: CatalogEvent["category"];
  events: CatalogEvent[];
}

/** Events with at least one groupable dim, by category, `step_allowed: false` included. */
export function listBreakdownEventGroups({
  catalog,
}: {
  catalog: FlowCatalog;
}): BreakdownEventGroup[] {
  return catalog.event_groups
    .map((group) => ({
      category: group.category,
      events: group.events.filter((event) =>
        event.dims.some((dim) => dim.groupable),
      ),
    }))
    .filter((group) => group.events.length > 0);
}

/** Events a step of this stream may pick: `step_allowed` and in the stream's category. */
export function listEventOptions({
  catalog,
  stream,
}: {
  catalog: FlowCatalog;
  stream: StepStream;
}): CatalogEvent[] {
  return catalog.event_groups
    .filter((group) => group.category === stream)
    .flatMap((group) => group.events)
    .filter((event) => event.step_allowed && event.category === stream);
}

export interface EndpointGroup {
  blueprint: string;
  endpoints: CatalogEndpoint[];
}

/** Endpoints grouped by blueprint, in catalog order. */
export function listEndpointGroups({
  catalog,
}: {
  catalog: FlowCatalog;
}): EndpointGroup[] {
  const groups = new Map<string, EndpointGroup>();
  for (const endpoint of catalog.api_endpoints) {
    const group = groups.get(endpoint.blueprint) ?? {
      blueprint: endpoint.blueprint,
      endpoints: [],
    };
    group.endpoints.push(endpoint);
    groups.set(endpoint.blueprint, group);
  }
  return [...groups.values()];
}

export function listMethods({
  catalog,
  endpoint,
}: {
  catalog: FlowCatalog;
  endpoint: string;
}): string[] {
  const found = catalog.api_endpoints.find(
    (item) => item.endpoint === endpoint,
  );
  return found ? [...found.methods] : [];
}

/** True for a stored event that is not a current option for the stream. */
export function isStaleEvent({
  catalog,
  stream,
  eventName,
}: {
  catalog: FlowCatalog;
  stream: StepStream;
  eventName: string | null;
}): boolean {
  if (stream === "api" || eventName === null || eventName === "") {
    return false;
  }
  return !listEventOptions({ catalog, stream }).some(
    (event) => event.event_name === eventName,
  );
}

export function isStaleEndpoint({
  catalog,
  apiEndpoint,
}: {
  catalog: FlowCatalog;
  apiEndpoint: string | null;
}): boolean {
  if (apiEndpoint === null || apiEndpoint === "") {
    return false;
  }
  return !catalog.api_endpoints.some((item) => item.endpoint === apiEndpoint);
}

/** A method is stale when absent from its endpoint's methods, or the endpoint is gone. */
export function isStaleMethod({
  catalog,
  apiEndpoint,
  apiMethod,
}: {
  catalog: FlowCatalog;
  apiEndpoint: string | null;
  apiMethod: string | null;
}): boolean {
  if (apiMethod === null || apiMethod === "") {
    return false;
  }
  if (apiEndpoint === null) {
    return true;
  }
  return !listMethods({ catalog, endpoint: apiEndpoint }).includes(apiMethod);
}
