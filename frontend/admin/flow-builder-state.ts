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
type CatalogEndpoint = Schema<"FlowCatalogApiEndpointSchema">;

export type StepStream = "ui" | "api" | "domain";
export type StepField =
  | "label"
  | "event_name"
  | "api_endpoint"
  | "api_method"
  | "hidden";
export type DraftErrorField = StepField | "display_name" | "steps" | "form";

export interface DraftError {
  field: DraftErrorField;
  /** Step the error belongs to; null for name, step-count and form-level errors. */
  stepKey: number | null;
  message: string;
}

export interface DraftStep {
  key: number;
  original: Record<string, unknown>;
  stream: StepStream;
  label: string;
  eventName: string | null;
  apiEndpoint: string | null;
  apiMethod: string | null;
  hiddenCleared: boolean;
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
const HIDDEN_KEYS = ["dim_filter", "drop_breakdown"] as const;
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

function createBlankStep(): DraftStep {
  return {
    key: allocateStepKey(),
    original: {},
    stream: "ui",
    label: "",
    eventName: null,
    apiEndpoint: null,
    apiMethod: null,
    hiddenCleared: false,
    errors: {},
  };
}

function stepFromRaw({ raw }: { raw: unknown }): DraftStep {
  if (!isRecord(raw)) {
    return createBlankStep();
  }
  return {
    key: allocateStepKey(),
    original: { ...raw },
    stream: isStream(raw.stream) ? raw.stream : "ui",
    label: typeof raw.label === "string" ? raw.label : "",
    eventName: stringOrNull(raw.event_name),
    apiEndpoint: stringOrNull(raw.api_endpoint),
    apiMethod: stringOrNull(raw.api_method),
    hiddenCleared: false,
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
    submittedKeys: steps.map((step) => step.key),
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
    dim_filter: (step.original.dim_filter ??
      null) as Schema<"LenientFlowStep">["dim_filter"],
    drop_breakdown: (step.original.drop_breakdown ??
      null) as Schema<"LenientFlowStep">["drop_breakdown"],
  };
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
 * `hiddenCleared` never enter it.
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

/** Drops `dim_filter` and `drop_breakdown`, flagging the step only when something went. */
function clearHidden({ step }: { step: DraftStep }): DraftStep {
  const hadHidden = HIDDEN_KEYS.some((field) => {
    const value = step.original[field];
    return (
      value !== null &&
      value !== undefined &&
      !(Array.isArray(value) && value.length === 0)
    );
  });
  if (!hadHidden) {
    return step;
  }
  return {
    ...step,
    original: {
      ...step.original,
      ...Object.fromEntries(HIDDEN_KEYS.map((field) => [field, null])),
    },
    hiddenCleared: true,
  };
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

/** A stream change resets event, endpoint and method and clears hidden fields. */
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
        : clearHidden({
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
        : clearHidden({ step: { ...step, eventName: next } }),
  });
}

/**
 * Changing the endpoint is the API step's "event": hidden fields clear. The
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
      return clearHidden({
        step: {
          ...step,
          apiEndpoint: next,
          apiMethod: methods.length === 1 ? methods[0] : null,
        },
      });
    },
  });
}

/** A method change keeps hidden fields. */
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
 * Mirrors only the shared limits; semantics, control characters, uniqueness and the
 * custom-flow cap stay server-side.
 */
export function validateDraft({ draft }: { draft: FlowDraft }): DraftError[] {
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
  }
  return errors;
}

/**
 * Puts client validation results where server errors live (name and step-count
 * errors in `serverErrors`, step errors on their step), replacing earlier errors.
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
      // A rejected filter/breakdown stays until an edit removes it.
      const forStep: Record<string, string[]> =
        step.errors.hidden && !step.hiddenCleared
          ? { hidden: step.errors.hidden }
          : {};
      for (const error of errors) {
        if (error.stepKey === step.key) {
          forStep[error.field] = [
            ...(forStep[error.field] ?? []),
            error.message,
          ];
        }
      }
      return { ...step, errors: forStep };
    }),
  };
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
  "hidden",
];

/**
 * Every field-level problem in reading order: name, step count, then each step's
 * fields. Form-level errors are excluded; they render once in their own region.
 */
export function listProblems({ draft }: { draft: FlowDraft }): DraftProblem[] {
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
  });
  return problems;
}

export function listFormErrors({ draft }: { draft: FlowDraft }): string[] {
  return draft.serverErrors
    .filter((error) => error.field === "form")
    .map((error) => error.message);
}

function isPresent(value: unknown): boolean {
  return (
    value !== null &&
    value !== undefined &&
    !(Array.isArray(value) && value.length === 0)
  );
}

/** What a step still carries in `dim_filter` and `drop_breakdown`. */
export function summarizeHidden({ step }: { step: DraftStep }): {
  filterCount: number;
  hasBreakdown: boolean;
} {
  const filters = step.original.dim_filter;
  return {
    filterCount: Array.isArray(filters)
      ? filters.length
      : isPresent(filters)
        ? 1
        : 0,
    hasBreakdown: isPresent(step.original.drop_breakdown),
  };
}

// ---------------------------------------------------------------------------
// Server errors
// ---------------------------------------------------------------------------

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

function stepFieldForSuffix({ suffix }: { suffix: string }): StepField | null {
  if (isServerStepField(suffix)) {
    return suffix;
  }
  if (
    HIDDEN_KEYS.some((key) => suffix === key || suffix.startsWith(`${key}.`))
  ) {
    return "hidden";
  }
  return null;
}

/**
 * Maps dotted, 0-based server paths onto the current draft. `steps.N` resolves
 * through `submittedKeys[N]` (the key order of the body that was sent) and then by
 * key, so errors stay with their step after a reorder; a step removed since the
 * submit surfaces at form level. Nothing is dropped. Replaces earlier errors.
 */
export function applyServerErrors({
  draft,
  errors,
  submittedKeys,
}: {
  draft: FlowDraft;
  errors: Record<string, string[]>;
  submittedKeys: readonly number[];
}): FlowDraft {
  const serverErrors: DraftError[] = [];
  const stepErrors = new Map<number, Record<string, string[]>>();

  const addFormError = ({ path, message }: { path: string; message: string }) =>
    serverErrors.push({
      field: "form",
      stepKey: null,
      message: path === "__root__" ? message : `${path}: ${message}`,
    });

  for (const [path, messages] of Object.entries(errors)) {
    const match = STEP_PATH.exec(path);
    for (const message of messages) {
      if (path === "display_name") {
        serverErrors.push({ field: "display_name", stepKey: null, message });
      } else if (path === "steps") {
        serverErrors.push({ field: "steps", stepKey: null, message });
      } else if (match === null) {
        addFormError({ path, message });
      } else {
        const key: number | undefined = submittedKeys[Number(match[1])];
        const field = stepFieldForSuffix({ suffix: match[2] });
        if (
          key === undefined ||
          field === null ||
          !draft.steps.some((step) => step.key === key)
        ) {
          addFormError({ path, message });
        } else {
          const forStep = stepErrors.get(key) ?? {};
          forStep[field] = [...(forStep[field] ?? []), message];
          stepErrors.set(key, forStep);
        }
      }
    }
  }

  return {
    ...draft,
    serverErrors,
    steps: draft.steps.map((step) => ({
      ...step,
      errors: stepErrors.get(step.key) ?? {},
    })),
  };
}

// ---------------------------------------------------------------------------
// Catalog helpers
// ---------------------------------------------------------------------------

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
