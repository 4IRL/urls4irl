/**
 * DOM for the custom-flow builder (display name, step rows, catalog loading).
 *
 * Draft logic lives in `flow-builder-state.ts`; this module owns the markup, focus
 * and the catalog request, and reports outward only through `callbacks`. Typing never
 * re-renders a row: inputs write straight into the draft, and only structural changes
 * (add, remove, move, stream or endpoint change) rebuild markup.
 */
import type { Schema } from "../types/api-helpers.d.ts";

import { is429Handled } from "../lib/ajax.js";
import { APP_CONFIG } from "../lib/config.js";
import { fillTemplate } from "../lib/string-template.js";

import {
  appendStaleOption,
  isDisabled,
  makeCell as makeCellElement,
  makeElement,
  makeOption,
  makeSelect,
  setDisabled,
} from "./flow-builder-dom.js";
import {
  ADD_BREAKDOWN_ACTION,
  ADD_BREAKDOWN_FILTER_ACTION,
  ADD_FILTER_ACTION,
  BREAKDOWN_EVENT_FIELD,
  BREAKDOWN_FILTER_DIM_FIELD,
  BREAKDOWN_FILTER_VALUE_FIELD,
  BREAKDOWN_GROUP_BY_FIELD,
  breakdownAddReason,
  breakdownFilterAddReason,
  breakdownState,
  FILTER_DIM_FIELD,
  FILTER_VALUE_FIELD,
  filterAddReason,
  findBreakdownControl,
  findExtrasButton,
  findFilterControl,
  findFilterRemoveButton,
  REMOVE_BREAKDOWN_ACTION,
  REMOVE_BREAKDOWN_FILTER_ACTION,
  REMOVE_FILTER_ACTION,
  renderExtras,
} from "./flow-builder-rows.js";
import {
  addBreakdown,
  addBreakdownFilter,
  addFilter,
  addStep,
  applyServerErrors,
  applyValidationErrors,
  captureSubmitted,
  clearDraftError,
  createBlankDraft,
  draftFromEntry,
  hasNestedContent,
  isDraftDirty,
  isStaleEndpoint,
  isStaleEvent,
  isStaleMethod,
  isStream,
  listEndpointGroups,
  listEventOptions,
  listFormErrors,
  listMethods,
  listNestedMessages,
  listProblems,
  moveStep,
  normalizeDraft,
  removeBreakdown,
  removeBreakdownFilter,
  removeFilter,
  removeStep,
  resolveServerPath,
  setBreakdownEvent,
  setBreakdownFilterDim,
  setBreakdownFilterValue,
  setBreakdownGroupBy,
  setDisplayName,
  setFilterDim,
  setFilterValue,
  setFormErrors,
  setStepEndpoint,
  setStepEvent,
  setStepLabel,
  setStepMethod,
  setStepStream,
  STREAMS,
  toRequestBody,
  validateDraft,
} from "./flow-builder-state.js";
import type {
  DraftAddress,
  DraftProblem,
  DraftStep,
  FlowDraft,
  ResolvedServerPath,
  StepStream,
  SubmittedStep,
} from "./flow-builder-state.js";
import {
  ariaCount,
  formatPercent,
  isAllZero,
  PREVIEW_FLOW_ID,
  renderFlowGrid,
} from "./flow-card.js";
import type { FlowCardState } from "./flow-card.js";
import { createFlowPreview } from "./flow-preview.js";
import type { FlowPreviewState } from "./flow-preview.js";
import {
  createMetricFlow,
  deleteMetricFlow,
  fetchMetricFlowCatalog,
  previewMetricFlow,
  updateMetricFlow,
} from "./metrics-query-client.js";
import {
  BAD_REQUEST_STATUS,
  ERR_FLOW_LIMIT,
  ERR_TARGET_NOT_FOUND,
  NOT_FOUND_STATUS,
  RATE_LIMITED_STATUS,
} from "./metrics-flow-codes.js";

type FlowEntry = Schema<"MetricFlowEntrySchema">;
type FlowCatalog = Schema<"FlowCatalogResponseSchema">;
type SaveResponse = Schema<"SuccessEnvelope"> & FlowEntry;
type SaveErrorBody = {
  errorCode?: number | null;
  errors?: Record<string, string[]> | null;
  message?: string;
};

export type BuilderMode = "create" | "edit";

export interface FlowBuilderCallbacks {
  announce({ message }: { message: string }): void;
  onSaved({ entry, mode }: { entry: FlowEntry; mode: BuilderMode }): void;
  onCancelled(): void;
  onFlowMissing({ id }: { id: string }): void;
  onDeleted({ id, name }: { id: string; name: string }): void;
  onListStale(): void;
  /** The dashboard's current time window key (e.g. "week"), read at each preview send. */
  getWindow(): string;
}

export interface FlowBuilder {
  /** Re-previews the draft for the dashboard's current window (no-op unless idle). */
  refreshPreview(): void;
  open({ mode, entry }: { mode: BuilderMode; entry?: FlowEntry }): void;
  close(): void;
  isOpen(): boolean;
  isDirty(): boolean;
  confirmDiscard(): Promise<boolean>;
  focusPendingConfirm(): boolean;
}

type StepAction = "move-up" | "move-down" | "remove";

/** The one open confirm: its element, the safe button and (discard only) the pending promise. */
interface PendingConfirm {
  kind: "discard" | "delete";
  element: HTMLElement;
  safeButton: HTMLButtonElement;
  confirmButton: HTMLButtonElement;
  resolve: ((discard: boolean) => void) | null;
  onSafe(): void;
}

const ROOT_ERROR_PATH = "__root__";
let builderCount = 0;

function entryFromResponse({ data }: { data: SaveResponse }): FlowEntry {
  return {
    id: data.id,
    display_name: data.display_name,
    is_builtin: data.is_builtin,
    definition: data.definition,
    errors: data.errors,
    first_invalid: data.first_invalid,
  };
}

/**
 * Creates the builder inside `container` (kept hidden until `open`).
 * Example: `createFlowBuilder({ container, callbacks }).open({ mode: "create" })`.
 */
/** The control a preview 400 message is marked on. */
type PreviewTarget =
  | { kind: "step"; stepKey: number; field: string }
  | {
      kind: "entry";
      stepKey: number;
      list: "dim_filter" | "drop_breakdown.dim_filter";
      entryKey: number;
    }
  | {
      kind: "breakdown";
      stepKey: number;
      field: "event_name" | "group_by";
    }
  | { kind: "flow"; field: "display_name" | "steps" };

type PreviewAnnouncement = {
  kind: "result" | "problem" | "failed" | "rate-limited";
  text: string;
  /** Sorted `path: message` pairs for a problem announcement, else null. */
  problems: string | null;
};

const PREVIEW_ERR_PREFIX = "flow-preview-err-";

/** Fails closed: any path without a single known control is listed in the body. */
function previewTargetFor({
  resolved,
}: {
  resolved: ResolvedServerPath;
}): PreviewTarget | null {
  switch (resolved.kind) {
    case "step_field":
      return { kind: "step", stepKey: resolved.stepKey, field: resolved.field };
    case "flow_field":
      return { kind: "flow", field: resolved.field };
    case "nested":
      if (resolved.list === "drop_breakdown") {
        return resolved.field === "entry"
          ? null
          : {
              kind: "breakdown",
              stepKey: resolved.stepKey,
              field: resolved.field,
            };
      }
      return resolved.entryKey === null || resolved.field !== "entry"
        ? null
        : {
            kind: "entry",
            stepKey: resolved.stepKey,
            list: resolved.list,
            entryKey: resolved.entryKey,
          };
    default:
      return null;
  }
}

export function createFlowBuilder({
  container,
  callbacks,
}: {
  container: HTMLElement;
  callbacks: FlowBuilderCallbacks;
}): FlowBuilder {
  builderCount += 1;
  const uid = `flow-builder-${builderCount}`;
  const headingId = `${uid}-heading`;
  const addReasonId = `${uid}-add-reason`;
  const firstReasonId = `${uid}-first-reason`;
  const lastReasonId = `${uid}-last-reason`;
  const summaryId = `${uid}-summary`;
  const summaryHeadingId = `${uid}-summary-heading`;
  const nameErrorId = `${uid}-name-error`;
  const stepsErrorId = `${uid}-steps-error`;
  const formErrorsId = `${uid}-form-errors`;
  const confirmTitleId = `${uid}-confirm-title`;
  const confirmBodyId = `${uid}-confirm-body`;

  let opened = false;
  let saving = false;
  let deleting = false;
  let deleteXhr: JQuery.jqXHR | null = null;
  let storedName = "";
  let pendingConfirm: PendingConfirm | null = null;
  let formElement: HTMLFormElement | null = null;
  let cancelButton: HTMLButtonElement | null = null;
  let deleteButton: HTMLButtonElement | null = null;
  let saveXhr: JQuery.jqXHR | null = null;
  // True while the heading is described by the open-time summary.
  let describesHeading = false;
  let summary: HTMLElement | null = null;
  let nameInput: HTMLInputElement | null = null;
  let nameError: HTMLElement | null = null;
  let stepsError: HTMLElement | null = null;
  let formErrorRegion: HTMLElement | null = null;
  let saveButton: HTMLButtonElement | null = null;
  let mode: BuilderMode = "create";
  let draft: FlowDraft = createBlankDraft();
  let snapshot = "";
  let catalog: FlowCatalog | null = null;
  let catalogXhr: JQuery.jqXHR | null = null;
  let heading: HTMLElement | null = null;
  let body: HTMLElement | null = null;
  let retryButton: HTMLButtonElement | null = null;
  let stepList: HTMLElement | null = null;
  let addButton: HTMLButtonElement | null = null;
  let reasonLine: HTMLElement | null = null;
  // Live preview column (mounted by renderForm, so absent while the catalog loads).
  let previewTitle: HTMLElement | null = null;
  let previewStatus: HTMLElement | null = null;
  let previewBody: HTMLElement | null = null;
  let previewGrid: HTMLElement | null = null;
  let previewPlaceholder: HTMLElement | null = null;
  let previewErrorBlock: HTMLElement | null = null;
  let previewErrorText: HTMLElement | null = null;
  let previewRetryButton: HTMLButtonElement | null = null;
  // What the body shows now; drives the frozen render and in-place title updates.
  let previewShown: "placeholder" | "skeleton" | "card" | "error" | "fields" =
    "placeholder";
  let previewResponse: Schema<"FlowResponseSchema"> | null = null;
  // True from an accepted Retry click until the first non-updating render.
  let retryDriven = false;
  let previewLive: HTMLElement | null = null;
  // Preview-origin field errors: kept apart from draft.serverErrors, which Save owns.
  const previewErrors = new Map<string, string[]>();
  const previewTargets = new Map<
    string,
    { target: PreviewTarget; path: string }
  >();
  let previewBodyLines: string[] = [];
  // Messages the open-time reason already shows: announced, never rendered twice.
  let previewAnnouncedOnly = 0;
  let previewLastSpoken: PreviewAnnouncement | null = null;
  let previewHeld: PreviewAnnouncement | null = null;
  let previewAnnounceTimer: number | null = null;

  const preview = createFlowPreview({
    send: ({ body: definition, window: windowKey }) =>
      previewMetricFlow({ definition, window: windowKey }),
    onState: (state) => renderPreviewState({ state }),
  });

  const strings = () => APP_CONFIG.strings;
  const constants = () => APP_CONFIG.constants;

  // ---------------------------------------------------------------------
  // Open, close, catalog
  // ---------------------------------------------------------------------

  function teardown(): void {
    preview.cancel();
    if (catalogXhr !== null) {
      const pending = catalogXhr;
      catalogXhr = null;
      pending.abort();
    }
    if (saveXhr !== null) {
      const inFlight = saveXhr;
      saveXhr = null;
      inFlight.abort();
    }
    if (deleteXhr !== null) {
      const inFlight = deleteXhr;
      deleteXhr = null;
      inFlight.abort();
    }
    // A pending discard promise must never dangle: closing the builder denies it.
    const abandoned = pendingConfirm;
    pendingConfirm = null;
    abandoned?.resolve?.(false);
    opened = false;
    saving = false;
    deleting = false;
    formElement = null;
    cancelButton = null;
    deleteButton = null;
    describesHeading = false;
    catalog = null;
    summary = null;
    nameInput = null;
    nameError = null;
    stepsError = null;
    formErrorRegion = null;
    saveButton = null;
    heading = null;
    body = null;
    retryButton = null;
    stepList = null;
    addButton = null;
    reasonLine = null;
    previewTitle = null;
    previewStatus = null;
    previewBody = null;
    previewGrid = null;
    previewPlaceholder = null;
    previewErrorBlock = null;
    previewErrorText = null;
    previewRetryButton = null;
    previewShown = "placeholder";
    previewResponse = null;
    retryDriven = false;
    previewLive = null;
    resetPreviewAnnouncements();
    previewErrors.clear();
    previewTargets.clear();
    previewBodyLines = [];
    previewAnnouncedOnly = 0;
    container.replaceChildren();
    container.hidden = true;
  }

  function renderShell(): void {
    container.replaceChildren();
    container.classList.add("flow-builder");
    heading = makeElement({
      tag: "h3",
      className: "flow-builder-heading",
      text:
        mode === "edit"
          ? strings().METRICS_FLOW_BUILDER_TITLE_EDIT
          : strings().METRICS_FLOW_BUILDER_TITLE_NEW,
      attrs: { id: headingId, tabindex: "-1" },
    });
    // Mounted once and kept through loading, failure and success, so the
    // heading's aria-describedby target never changes.
    summary = makeElement({
      tag: "div",
      className: "flow-builder-summary",
      attrs: { id: summaryId, tabindex: "-1" },
    });
    summary.hidden = true;
    summary.addEventListener("click", handleSummaryClick);
    body = makeElement({ tag: "div", className: "flow-builder-body" });
    container.append(heading, summary, body);
  }

  function showCatalogStatus({
    message,
    failed,
    retrying,
  }: {
    message: string;
    failed: boolean;
    retrying: boolean;
  }): void {
    if (body === null) {
      return;
    }
    let wrapper = body.querySelector<HTMLElement>(".flow-builder-catalog");
    if (wrapper === null) {
      body.replaceChildren();
      wrapper = makeElement({ tag: "div", className: "flow-builder-catalog" });
      const status = makeElement({
        tag: "div",
        className: "flow-builder-status",
        attrs: { role: "status" },
      });
      status.append(
        makeElement({ tag: "p", className: "flow-builder-status-text" }),
      );
      wrapper.append(status);
      body.append(wrapper);
    }
    const text = wrapper.querySelector(".flow-builder-status-text");
    if (text !== null) {
      text.textContent = message;
    }
    if (!failed && !retrying) {
      return;
    }
    if (retryButton === null) {
      retryButton = makeElement({
        tag: "button",
        className: "flow-builder-btn",
        text: strings().METRICS_FLOW_BUILDER_CATALOG_RETRY,
        attrs: { type: "button" },
      });
      retryButton.addEventListener("click", handleRetry);
      // Outside the live region so only the message is announced.
      wrapper.append(retryButton);
    }
    if (retrying) {
      retryButton.setAttribute("aria-disabled", "true");
    } else {
      retryButton.removeAttribute("aria-disabled");
    }
  }

  function handleRetry(): void {
    if (retryButton === null || isDisabled({ element: retryButton })) {
      return;
    }
    loadCatalog({ retrying: true });
  }

  function loadCatalog({ retrying }: { retrying: boolean }): void {
    showCatalogStatus({
      message: strings().METRICS_FLOW_BUILDER_CATALOG_LOADING,
      failed: false,
      retrying,
    });
    const request = fetchMetricFlowCatalog();
    catalogXhr = request;
    request.done((data) => {
      if (catalogXhr !== request) {
        return;
      }
      catalogXhr = null;
      catalog = data;
      retryButton = null;
      renderForm();
      heading?.focus();
      schedulePreview();
    });
    request.fail(() => {
      if (catalogXhr !== request) {
        return;
      }
      catalogXhr = null;
      // A handled 429 already raised the global toast; only the builder's own
      // state is restored here so Try again never stays disabled.
      const rateLimited =
        is429Handled(request) || request.status === RATE_LIMITED_STATUS;
      showCatalogStatus({
        message: rateLimited
          ? strings().METRICS_FLOW_RATE_LIMITED
          : strings().METRICS_FLOW_BUILDER_ERR_CATALOG_FAILED,
        failed: true,
        retrying: false,
      });
      retryButton?.focus();
    });
  }

  function open({
    mode: nextMode,
    entry,
  }: {
    mode: BuilderMode;
    entry?: FlowEntry;
  }): void {
    if (nextMode === "edit" && entry === undefined) {
      throw new Error("Edit mode requires an entry");
    }
    teardown();
    mode = nextMode;
    draft =
      nextMode === "edit" && entry !== undefined
        ? draftFromEntry({ entry })
        : createBlankDraft();
    storedName =
      nextMode === "edit" && entry !== undefined ? entry.display_name : "";
    snapshot = normalizeDraft({ draft });
    opened = true;
    container.hidden = false;
    renderShell();
    describesHeading = true;
    renderSummary();
    loadCatalog({ retrying: false });
    heading?.focus();
  }

  // ---------------------------------------------------------------------
  // Error surfaces
  // ---------------------------------------------------------------------

  /** 1-based position of a filter within its list, for "filter N" lines. */
  function filterPosition({
    stepKey,
    address,
  }: {
    stepKey: number;
    address: DraftAddress;
  }): string {
    const step = draft.steps.find((item) => item.key === stepKey);
    if (
      step === undefined ||
      (address.kind !== "filter" && address.kind !== "breakdown_filter")
    ) {
      return "";
    }
    const list =
      address.kind === "filter"
        ? step.filters
        : (step.breakdown?.filters ?? []);
    return String(
      list.findIndex((filter) => filter.key === address.filterKey) + 1,
    );
  }

  function nestedLineTemplate({ address }: { address: DraftAddress }): string {
    switch (address.kind) {
      case "filters":
        return strings().METRICS_FLOW_BUILDER_ERR_FILTERS_LINE;
      case "filter":
        return strings().METRICS_FLOW_BUILDER_ERR_FILTER_LINE;
      case "breakdown":
        return strings().METRICS_FLOW_BUILDER_ERR_BREAKDOWN_LINE;
      case "breakdown_filters":
        return strings().METRICS_FLOW_BUILDER_ERR_BREAKDOWN_FILTERS_LINE;
      case "breakdown_filter":
        return strings().METRICS_FLOW_BUILDER_ERR_BREAKDOWN_FILTER_LINE;
    }
  }

  function problemText({ problem }: { problem: DraftProblem }): string {
    if (problem.stepNumber === null) {
      return problem.message;
    }
    const step = String(problem.stepNumber);
    if (
      problem.field === "nested" &&
      problem.address !== undefined &&
      problem.stepKey !== null
    ) {
      return fillTemplate({
        template: nestedLineTemplate({ address: problem.address }),
        values: {
          step,
          n: filterPosition({
            stepKey: problem.stepKey,
            address: problem.address,
          }),
          message: problem.message,
        },
      });
    }
    return fillTemplate({
      template: strings().METRICS_FLOW_BUILDER_ERR_STEP_LINE,
      values: { step, message: problem.message },
    });
  }

  /** Writes the address onto a summary link so a click can find its control. */
  function addressAttrs({
    address,
  }: {
    address: DraftAddress;
  }): Record<string, string> {
    const attrs: Record<string, string> = {
      "data-problem-kind": address.kind,
    };
    if ("part" in address) {
      attrs["data-problem-part"] = address.part;
    }
    if ("filterKey" in address) {
      attrs["data-problem-filter"] = String(address.filterKey);
    }
    return attrs;
  }

  /**
   * Redraws the summary from the draft's errors in place. Lines are plain text until
   * the catalog has loaded (no field exists to focus yet).
   */
  function renderSummary(): void {
    if (summary === null || heading === null) {
      return;
    }
    const problems = listProblems({ draft, catalog });
    if (problems.length === 0) {
      summary.hidden = true;
      summary.replaceChildren();
      heading.removeAttribute("aria-describedby");
      describesHeading = false;
      return;
    }
    const title = makeElement({
      tag: "h4",
      className: "flow-builder-summary-title",
      text:
        problems.length === 1
          ? strings().METRICS_FLOW_BUILDER_ERR_PROBLEM_ONE
          : fillTemplate({
              template: strings().METRICS_FLOW_BUILDER_ERR_PROBLEMS,
              values: { count: String(problems.length) },
            }),
      attrs: { id: summaryHeadingId },
    });
    const list = makeElement({
      tag: "ul",
      className: "flow-builder-summary-list",
    });
    for (const problem of problems) {
      const item = makeElement({ tag: "li" });
      const text = problemText({ problem });
      if (catalog === null) {
        item.textContent = text;
      } else {
        const link = makeElement({
          tag: "button",
          className: "flow-builder-link",
          text,
          attrs: {
            type: "button",
            "data-problem-field": problem.field,
            ...(problem.address === undefined
              ? {}
              : addressAttrs({ address: problem.address })),
          },
        });
        if (problem.stepKey !== null) {
          link.setAttribute("data-problem-key", String(problem.stepKey));
        }
        item.append(link);
      }
      list.append(item);
    }
    summary.replaceChildren(title, list);
    summary.hidden = false;
    if (describesHeading) {
      heading.setAttribute("aria-describedby", summaryHeadingId);
    } else {
      heading.removeAttribute("aria-describedby");
    }
  }

  /** The first edit or Save replaces the open-time summary, so the heading stops describing it. */
  function stopDescribingHeading(): void {
    describesHeading = false;
    heading?.removeAttribute("aria-describedby");
    // Any edit also retires a stale form-level message such as "rate limited".
    if (listFormErrors({ draft }).length > 0) {
      draft = clearDraftError({ draft, field: "form" });
      renderFormErrors();
    }
  }

  function handleSummaryClick(event: MouseEvent): void {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    const link = target.closest<HTMLElement>("[data-problem-field]");
    if (link === null) {
      return;
    }
    const field = link.dataset.problemField;
    const rawKey = link.dataset.problemKey;
    if (field === "display_name") {
      nameInput?.focus();
    } else if (field === "steps") {
      addButton?.focus();
    } else if (rawKey !== undefined && field === "nested") {
      focusNested({ key: Number(rawKey), dataset: link.dataset });
    } else if (rawKey !== undefined && field !== undefined) {
      focusField({ key: Number(rawKey), field });
      if (document.activeElement === link) {
        // The named control is not rendered; land on the row's first control.
        findRow({ key: Number(rawKey) })
          ?.querySelector<HTMLElement>("[data-field]")
          ?.focus();
      }
    }
  }

  /**
   * The fixed focus-target table for filter and breakdown summary links: Add
   * buttons for list-level and damaged messages, the named select for a row, the
   * event select for a breakdown-level message, and the row's Remove button when
   * its controls are read-only. The first focusable candidate wins.
   */
  function focusNested({
    key,
    dataset,
  }: {
    key: number;
    dataset: DOMStringMap;
  }): void {
    const row = findRow({ key });
    if (row === null) {
      return;
    }
    const kind = dataset.problemKind;
    const part = dataset.problemPart;
    const filterKey = Number(dataset.problemFilter);
    const focusFirst = (candidates: (HTMLElement | null)[]): void => {
      for (const candidate of candidates) {
        if (
          candidate !== null &&
          !(candidate instanceof HTMLSelectElement && candidate.disabled)
        ) {
          candidate.focus();
          return;
        }
      }
    };
    if (kind === "filters") {
      focusFirst([findExtrasButton({ row, action: ADD_FILTER_ACTION })]);
    } else if (kind === "filter") {
      focusFirst([
        findFilterControl({
          row,
          filterKey,
          field: part === "value" ? FILTER_VALUE_FIELD : FILTER_DIM_FIELD,
        }),
        findFilterControl({ row, filterKey, field: FILTER_DIM_FIELD }),
        findFilterRemoveButton({
          row,
          action: REMOVE_FILTER_ACTION,
          filterKey,
        }),
      ]);
    } else if (kind === "breakdown") {
      const event = findBreakdownControl({ row, field: BREAKDOWN_EVENT_FIELD });
      if (part === "add") {
        focusFirst([findExtrasButton({ row, action: ADD_BREAKDOWN_ACTION })]);
      } else if (part === "group_by") {
        focusFirst([
          findBreakdownControl({ row, field: BREAKDOWN_GROUP_BY_FIELD }),
          event,
        ]);
      } else {
        focusFirst([event]);
      }
    } else if (kind === "breakdown_filters") {
      focusFirst([
        findExtrasButton({ row, action: ADD_BREAKDOWN_FILTER_ACTION }),
      ]);
    } else if (kind === "breakdown_filter") {
      focusFirst([
        findFilterControl({
          row,
          filterKey,
          field:
            part === "value"
              ? BREAKDOWN_FILTER_VALUE_FIELD
              : BREAKDOWN_FILTER_DIM_FIELD,
        }),
        findFilterControl({
          row,
          filterKey,
          field: BREAKDOWN_FILTER_DIM_FIELD,
        }),
        findFilterRemoveButton({
          row,
          action: REMOVE_BREAKDOWN_FILTER_ACTION,
          filterKey,
        }),
      ]);
    }
  }

  function renderNameError(): void {
    if (nameInput === null || nameError === null) {
      return;
    }
    const messages = draft.serverErrors
      .filter((error) => error.field === "display_name")
      .map((error) => error.message);
    nameError.textContent = messages.join(" ");
    nameError.hidden = messages.length === 0;
    if (messages.length > 0) {
      nameInput.setAttribute("aria-invalid", "true");
      nameInput.setAttribute("aria-describedby", nameErrorId);
    } else {
      nameInput.removeAttribute("aria-invalid");
      nameInput.removeAttribute("aria-describedby");
    }
  }

  function renderStepsError(): void {
    if (stepsError === null) {
      return;
    }
    const messages = draft.serverErrors
      .filter((error) => error.field === "steps")
      .map((error) => error.message);
    stepsError.textContent = messages.join(" ");
    stepsError.hidden = messages.length === 0;
    if (addButton === null) {
      return;
    }
    if (messages.length > 0) {
      addButton.setAttribute("aria-invalid", "true");
      addButton.setAttribute("aria-describedby", stepsErrorId);
    } else {
      addButton.removeAttribute("aria-invalid");
      // refreshControls owns aria-describedby while Add is disabled.
      if (!isDisabled({ element: addButton })) {
        addButton.removeAttribute("aria-describedby");
      }
    }
  }

  /** The one `role="alert"` region: each message is set here and nowhere else. */
  function renderFormErrors(): void {
    if (formErrorRegion === null) {
      return;
    }
    const messages = listFormErrors({ draft });
    formErrorRegion.replaceChildren(
      ...messages.map((message) =>
        makeElement({
          tag: "p",
          className: "flow-builder-error",
          text: message,
        }),
      ),
    );
    if (messages.length === 0) {
      deleteButton?.removeAttribute("aria-describedby");
    }
  }

  function renderAllErrors(): void {
    renderNameError();
    renderSteps();
    renderStepsError();
    renderFormErrors();
    renderSummary();
  }

  function setFormMessages({
    messages,
  }: {
    messages: readonly string[];
  }): void {
    draft = setFormErrors({ draft, messages });
    renderFormErrors();
  }

  function setSaving({ value }: { value: boolean }): void {
    saving = value;
    refreshBusy();
    if (saveButton === null) {
      return;
    }
    saveButton.textContent = value
      ? strings().METRICS_FLOW_BUILDER_SAVING
      : strings().METRICS_FLOW_BUILDER_SAVE;
    if (value) {
      saveButton.setAttribute("aria-disabled", "true");
    } else {
      saveButton.removeAttribute("aria-disabled");
    }
  }

  /** Cancel and Delete are unavailable while a Save or Delete is in flight. */
  function refreshBusy(): void {
    const busy = saving || deleting;
    for (const button of [cancelButton, deleteButton]) {
      if (button === null) {
        continue;
      }
      if (busy) {
        button.setAttribute("aria-disabled", "true");
      } else {
        button.removeAttribute("aria-disabled");
      }
    }
    if (deleteButton !== null) {
      deleteButton.textContent = deleting
        ? strings().METRICS_FLOW_DELETING
        : strings().METRICS_FLOW_BUILDER_DELETE;
    }
  }

  // ---------------------------------------------------------------------
  // Save
  // ---------------------------------------------------------------------

  function handleSubmit(event: Event): void {
    event.preventDefault();
    if (saving || deleting || pendingConfirm !== null) {
      return;
    }
    save();
  }

  function save(): void {
    stopDescribingHeading();
    const hadProblems = listProblems({ draft, catalog }).length > 0;
    const errors = validateDraft({ draft, catalog });
    draft = applyValidationErrors({ draft, errors });
    // Rows are rebuilt only when something shown changes, so a valid Save keeps focus.
    if (errors.length > 0 || hadProblems) {
      renderAllErrors();
    }
    if (errors.length > 0) {
      summary?.focus();
      return;
    }
    const submitted = captureSubmitted({ draft });
    const definition = toRequestBody({ draft });
    const flowId = draft.flowId;
    const request =
      mode === "edit" && flowId !== null
        ? updateMetricFlow({ flowId, definition })
        : createMetricFlow({ definition });
    saveXhr = request;
    setSaving({ value: true });
    freezePreview();
    request.done((data) => {
      if (saveXhr !== request) {
        return;
      }
      saveXhr = null;
      setSaving({ value: false });
      callbacks.onSaved({
        entry: entryFromResponse({ data: data as SaveResponse }),
        mode,
      });
    });
    request.fail(() => {
      if (saveXhr !== request) {
        return;
      }
      saveXhr = null;
      setSaving({ value: false });
      handleSaveFailure({ request, submitted });
      // The failure may have closed the builder; both calls guard themselves.
      syncRetryDisabled();
      schedulePreview();
    });
  }

  function handleSaveFailure({
    request,
    submitted,
  }: {
    request: JQuery.jqXHR;
    submitted: readonly SubmittedStep[];
  }): void {
    if (is429Handled(request)) {
      return;
    }
    // Only a real abort is silent; a network failure also has readyState 0.
    if (request.readyState === 0 && request.statusText === "abort") {
      return;
    }
    const body: SaveErrorBody = request.responseJSON ?? {};
    const errors = body.errors ?? {};
    if (request.status === RATE_LIMITED_STATUS) {
      setFormMessages({ messages: [strings().METRICS_FLOW_RATE_LIMITED] });
    } else if (
      request.status === NOT_FOUND_STATUS &&
      mode === "edit" &&
      draft.flowId !== null &&
      body.errorCode === ERR_TARGET_NOT_FOUND
    ) {
      callbacks.onFlowMissing({ id: draft.flowId });
    } else if (
      request.status === BAD_REQUEST_STATUS &&
      (Object.keys(errors).length > 0 || body.errorCode === ERR_FLOW_LIMIT)
    ) {
      draft = applyServerErrors({ draft, errors, submitted });
      if (body.errorCode === ERR_FLOW_LIMIT && !(ROOT_ERROR_PATH in errors)) {
        draft = setFormErrors({
          draft,
          messages: [
            ...listFormErrors({ draft }),
            body.message ?? strings().METRICS_FLOW_BUILDER_ERR_SAVE_FAILED,
          ],
        });
      }
      renderAllErrors();
      if (listProblems({ draft, catalog }).length > 0) {
        summary?.focus();
      }
    } else {
      setFormMessages({
        messages: [strings().METRICS_FLOW_BUILDER_ERR_SAVE_FAILED],
      });
    }
  }

  // ---------------------------------------------------------------------
  // Live preview
  // ---------------------------------------------------------------------

  /** Drops every preview-owned element, describedby id and invalid flag; Save/client marks stay. */
  function stripPreviewMarks(): void {
    for (const element of container.querySelectorAll<HTMLElement>(
      "[data-preview-err]",
    )) {
      element.remove();
    }
    for (const control of container.querySelectorAll<HTMLElement>(
      "[aria-describedby]",
    )) {
      const current = control.getAttribute("aria-describedby") ?? "";
      if (!current.includes(PREVIEW_ERR_PREFIX)) {
        continue;
      }
      const rest = current
        .split(" ")
        .filter((id) => id !== "" && !id.includes(PREVIEW_ERR_PREFIX));
      if (rest.length > 0) {
        control.setAttribute("aria-describedby", rest.join(" "));
      } else {
        control.removeAttribute("aria-describedby");
      }
    }
    for (const control of container.querySelectorAll<HTMLElement>(
      "[data-preview-invalid]",
    )) {
      // Only a flag the preview itself set is removed; a Save/client message
      // that landed since keeps its own aria-invalid.
      if (!control.hasAttribute("aria-describedby")) {
        control.removeAttribute("aria-invalid");
      }
      control.removeAttribute("data-preview-invalid");
    }
  }

  /** Forgets the stored preview errors and removes their marks. */
  function clearPreviewMarks(): void {
    previewErrors.clear();
    previewTargets.clear();
    previewBodyLines = [];
    previewAnnouncedOnly = 0;
    stripPreviewMarks();
  }

  function findPreviewControl({
    target,
  }: {
    target: PreviewTarget;
  }): HTMLElement | null {
    if (target.kind === "flow") {
      return target.field === "display_name" ? nameInput : addButton;
    }
    const row = findRow({ key: target.stepKey });
    if (row === null) {
      return null;
    }
    switch (target.kind) {
      case "step":
        return row.querySelector<HTMLElement>(`[data-field="${target.field}"]`);
      case "entry":
        return findFilterControl({
          row,
          filterKey: target.entryKey,
          field:
            target.list === "dim_filter"
              ? FILTER_DIM_FIELD
              : BREAKDOWN_FILTER_DIM_FIELD,
        });
      case "breakdown":
        return findBreakdownControl({
          row,
          field:
            target.field === "event_name"
              ? BREAKDOWN_EVENT_FIELD
              : BREAKDOWN_GROUP_BY_FIELD,
        });
      default:
        return null;
    }
  }

  /**
   * Messages the control already shows: `shown` come from a Save 400 or client
   * validation (a preview duplicate is dropped); `derived` are open-time reasons
   * (a preview duplicate is announced but not rendered twice).
   */
  function existingMessages({ target }: { target: PreviewTarget }): {
    shown: string[];
    derived: string[];
  } {
    if (target.kind === "flow") {
      return {
        shown: draft.serverErrors
          .filter((error) => error.field === target.field)
          .map((error) => error.message),
        derived: [],
      };
    }
    const step = draft.steps.find((item) => item.key === target.stepKey);
    if (step === undefined) {
      return { shown: [], derived: [] };
    }
    if (target.kind === "step") {
      return { shown: step.errors[target.field] ?? [], derived: [] };
    }
    const shown: string[] = [];
    const derived: string[] = [];
    for (const error of listNestedMessages({ step, catalog })) {
      const address = error.address;
      const matches =
        address !== undefined &&
        (target.kind === "entry"
          ? address.kind ===
              (target.list === "dim_filter" ? "filter" : "breakdown_filter") &&
            address.filterKey === target.entryKey
          : address.kind === "breakdown" &&
            address.part ===
              (target.field === "event_name" ? "event" : "group_by"));
      if (matches) {
        (error.stored === true || error.server === true ? shown : derived).push(
          error.message,
        );
      }
    }
    return { shown, derived };
  }

  /** Stores a preview 400 against the current draft (via `submitted`); renders nothing. */
  function storePreviewErrors({
    errors,
    submitted,
  }: {
    errors: Record<string, string[]>;
    submitted: SubmittedStep[];
  }): void {
    clearPreviewMarks();
    const lines = new Set<string>();
    const derivedSeen = new Set<string>();
    for (const [path, messages] of Object.entries(errors)) {
      const resolved = resolveServerPath({ path, submitted, draft });
      const target = previewTargetFor({ resolved });
      for (const message of messages) {
        if (target === null) {
          lines.add(path === "__root__" ? message : `${path}: ${message}`);
          continue;
        }
        const existing = existingMessages({ target });
        if (existing.shown.includes(message)) {
          continue;
        }
        const key = JSON.stringify(target);
        const stored = previewErrors.get(key) ?? [];
        if (stored.includes(message)) {
          continue;
        }
        if (existing.derived.includes(message)) {
          // Counted for the announcement once, never stored or rendered twice.
          const seen = `${key}|${message}`;
          if (!derivedSeen.has(seen)) {
            derivedSeen.add(seen);
            previewAnnouncedOnly += 1;
          }
          continue;
        }
        stored.push(message);
        previewErrors.set(key, stored);
        previewTargets.set(key, { target, path });
      }
    }
    previewBodyLines = [...lines];
  }

  /**
   * Marks every stored preview error in place (and lists the rest in the preview
   * body). Idempotent: it strips its own marks first, so it can run after any row
   * rebuild. Returns how many message elements it rendered.
   */
  function applyPreviewMarks(): number {
    stripPreviewMarks();
    if (previewErrors.size === 0 && previewBodyLines.length === 0) {
      return 0;
    }
    let rendered = 0;
    let sequence = 0;
    const lines = new Set(previewBodyLines);
    for (const [key, messages] of previewErrors) {
      const entry = previewTargets.get(key);
      const control =
        entry === undefined
          ? null
          : findPreviewControl({ target: entry.target });
      if (entry === undefined || control === null) {
        for (const message of messages) {
          lines.add(
            entry === undefined || entry.path === "__root__"
              ? message
              : `${entry.path}: ${message}`,
          );
        }
        continue;
      }
      let tail: Element =
        entry.target.kind === "flow"
          ? ((entry.target.field === "display_name" ? nameError : stepsError) ??
            control)
          : control;
      const ids: string[] = [];
      for (const message of messages) {
        sequence += 1;
        const id = `${uid}-${PREVIEW_ERR_PREFIX}${sequence}`;
        const line = makeElement({
          tag: "p",
          className: "flow-builder-error",
          text: message,
          attrs: { id, "data-preview-err": "true" },
        });
        if (entry.target.kind === "flow") {
          tail.after(line);
          tail = line;
        } else {
          control.parentElement?.append(line);
        }
        ids.push(id);
        rendered += 1;
      }
      if (ids.length === 0) {
        continue;
      }
      if (control.getAttribute("aria-invalid") !== "true") {
        control.setAttribute("aria-invalid", "true");
        control.setAttribute("data-preview-invalid", "true");
      }
      const described = control.getAttribute("aria-describedby");
      control.setAttribute(
        "aria-describedby",
        [described, ...ids].filter((id) => id).join(" "),
      );
    }
    for (const text of lines) {
      previewBody?.append(
        makeElement({
          tag: "p",
          className: "flow-builder-error",
          text,
          attrs: { "data-preview-err": "true" },
        }),
      );
      rendered += 1;
    }
    return rendered;
  }

  // ---- Preview announcements (their own live region, never the builder's) ----

  function speakPreview({ text }: { text: string }): void {
    const region = previewLive;
    if (region === null) {
      return;
    }
    // Clear, then set on the next tick so a repeated message is re-read.
    region.textContent = "";
    if (previewAnnounceTimer !== null) {
      window.clearTimeout(previewAnnounceTimer);
    }
    previewAnnounceTimer = window.setTimeout(() => {
      previewAnnounceTimer = null;
      region.textContent = text;
    }, 0);
  }

  function deliverPreviewAnnouncement({
    item,
  }: {
    item: PreviewAnnouncement;
  }): void {
    const repeatable = item.kind === "result" || item.kind === "problem";
    if (
      repeatable &&
      previewLastSpoken !== null &&
      previewLastSpoken.text === item.text &&
      previewLastSpoken.problems === item.problems
    ) {
      return;
    }
    previewLastSpoken = item;
    speakPreview({ text: item.text });
  }

  /** Speaks now, or holds (latest only) while a discard/delete confirm is open. */
  function announcePreview({ item }: { item: PreviewAnnouncement }): void {
    if (pendingConfirm !== null) {
      previewHeld = item;
      return;
    }
    deliverPreviewAnnouncement({ item });
  }

  function flushHeldPreviewAnnouncement(): void {
    const held = previewHeld;
    previewHeld = null;
    if (held !== null) {
      deliverPreviewAnnouncement({ item: held });
    }
  }

  /** Forgets the last-spoken text, any held announcement and a pending speak timer. */
  function resetPreviewAnnouncements(): void {
    previewLastSpoken = null;
    previewHeld = null;
    if (previewAnnounceTimer !== null) {
      window.clearTimeout(previewAnnounceTimer);
      previewAnnounceTimer = null;
    }
  }

  function announceProblems({
    errors,
    rendered,
  }: {
    errors: Record<string, string[]>;
    rendered: number;
  }): void {
    const count = rendered + previewAnnouncedOnly;
    if (count === 0) {
      return;
    }
    const pairs = Object.entries(errors)
      .flatMap(([path, messages]) =>
        messages.map((message) => `${path}: ${message}`),
      )
      .sort();
    announcePreview({
      item: {
        kind: "problem",
        text:
          count === 1
            ? strings().METRICS_FLOW_PREVIEW_ANNOUNCE_PROBLEM_ONE
            : fillTemplate({
                template: strings().METRICS_FLOW_PREVIEW_ANNOUNCE_PROBLEMS,
                values: { count: String(count) },
              }),
        problems: JSON.stringify(pairs),
      },
    });
  }

  function announceResult({
    response,
  }: {
    response: Schema<"FlowResponseSchema">;
  }): void {
    const steps = response.steps;
    if (steps.length === 0) {
      return;
    }
    const top = steps[0];
    const last = steps[steps.length - 1];
    announcePreview({
      item: {
        kind: "result",
        problems: null,
        text: isAllZero({ steps })
          ? strings().METRICS_FLOW_PREVIEW_ANNOUNCE_EMPTY
          : fillTemplate({
              template: strings().METRICS_FLOW_PREVIEW_ANNOUNCE_RESULT,
              values: {
                succeeded: ariaCount({ step: last }),
                total: ariaCount({ step: top }),
                pct: formatPercent({ fraction: last.pct_of_top }),
              },
            }),
      },
    });
  }

  function previewCardTitle(): string {
    return draft.displayName.trim() || strings().METRICS_FLOW_PREVIEW_HEADING;
  }

  function buildPreviewSection(): HTMLElement {
    const titleId = `${uid}-preview-title`;
    const section = makeElement({
      tag: "section",
      className: "flow-builder-preview",
      attrs: { "aria-labelledby": titleId },
    });
    previewTitle = makeElement({
      tag: "h4",
      className: "flow-builder-preview-title",
      text: strings().METRICS_FLOW_PREVIEW_HEADING,
      attrs: { id: titleId, tabindex: "-1" },
    });
    previewStatus = makeElement({
      tag: "p",
      className: "flow-builder-preview-status",
    });
    previewStatus.append(
      makeElement({
        tag: "span",
        className: "flow-builder-preview-spinner",
        attrs: { "aria-hidden": "true" },
      }),
      document.createTextNode(strings().METRICS_FLOW_PREVIEW_UPDATING),
    );
    previewStatus.hidden = true;
    previewBody = makeElement({
      tag: "div",
      className: "flow-builder-preview-body",
    });
    previewGrid = makeElement({
      tag: "div",
      className: "flow-builder-preview-grid",
    });
    previewBody.append(previewGrid);
    previewPlaceholder = null;
    previewErrorBlock = null;
    previewErrorText = null;
    previewRetryButton = null;
    previewResponse = null;
    retryDriven = false;
    showPreviewText({ text: strings().METRICS_FLOW_PREVIEW_PLACEHOLDER });
    previewShown = "placeholder";
    previewLive = makeElement({
      tag: "span",
      className: "visually-hidden flow-builder-preview-live",
      attrs: { "aria-live": "polite", "aria-atomic": "true" },
    });
    section.append(
      previewTitle,
      previewStatus,
      previewBody,
      makeElement({
        tag: "p",
        className: "flow-builder-hint",
        text: strings().METRICS_FLOW_PREVIEW_HINT,
      }),
      // Outside the busy body, and separate from the builder status region.
      previewLive,
    );
    return section;
  }

  function clearPreviewBlocks({
    placeholder,
    error,
    grid,
  }: {
    placeholder: boolean;
    error: boolean;
    grid: boolean;
  }): void {
    if (placeholder) {
      previewPlaceholder?.remove();
      previewPlaceholder = null;
    }
    if (error) {
      previewErrorBlock?.remove();
      previewErrorBlock = null;
      previewErrorText = null;
      previewRetryButton = null;
    }
    if (grid && previewGrid !== null) {
      // An empty render also resets the grid's reconcile cache.
      renderFlowGrid({ container: previewGrid, entries: [] });
    }
  }

  function showPreviewText({ text }: { text: string }): void {
    if (previewBody === null) {
      return;
    }
    clearPreviewBlocks({ placeholder: false, error: true, grid: true });
    if (previewPlaceholder === null) {
      previewPlaceholder = makeElement({
        tag: "p",
        className: "flow-builder-preview-placeholder",
        attrs: { tabindex: "0" },
      });
      previewBody.append(previewPlaceholder);
    }
    previewPlaceholder.textContent = text;
  }

  function showPreviewCard({ state }: { state: FlowCardState }): void {
    if (previewGrid === null) {
      return;
    }
    clearPreviewBlocks({ placeholder: true, error: true, grid: false });
    renderFlowGrid({
      container: previewGrid,
      entries: [
        {
          id: PREVIEW_FLOW_ID,
          title: previewCardTitle(),
          preview: true,
          state,
        },
      ],
    });
  }

  function showPreviewError({ message }: { message: string }): void {
    if (previewBody === null) {
      return;
    }
    clearPreviewBlocks({ placeholder: true, error: false, grid: true });
    if (previewErrorBlock === null) {
      previewErrorBlock = makeElement({
        tag: "div",
        className: "flow-builder-preview-error",
      });
      previewErrorText = makeElement({ tag: "p" });
      previewRetryButton = makeElement({
        tag: "button",
        className: "flow-builder-btn",
        text: strings().METRICS_FLOW_RETRY,
        attrs: { type: "button" },
      });
      previewRetryButton.addEventListener("click", handlePreviewRetry);
      previewErrorBlock.append(previewErrorText, previewRetryButton);
      previewBody.append(previewErrorBlock);
    }
    if (previewErrorText !== null) {
      previewErrorText.textContent = message;
    }
  }

  /**
   * Retry is inert (aria-disabled, so it keeps focus) while a Retry flight runs and
   * while a Save, a Delete or a confirm owns the builder.
   */
  function syncRetryDisabled(): void {
    if (previewRetryButton === null) {
      return;
    }
    if (retryDriven || saving || deleting || pendingConfirm !== null) {
      previewRetryButton.setAttribute("aria-disabled", "true");
    } else {
      previewRetryButton.removeAttribute("aria-disabled");
    }
  }

  function handlePreviewRetry(): void {
    if (
      previewRetryButton === null ||
      retryDriven ||
      saving ||
      deleting ||
      pendingConfirm !== null
    ) {
      return;
    }
    retryDriven = true;
    syncRetryDisabled();
    schedulePreview();
  }

  /**
   * Runs a preview render; when it removed the element that held focus inside the
   * preview body, focus moves to the preview title. Nothing else here moves focus.
   */
  function withPreviewFocusGuard({ render }: { render: () => void }): void {
    const active = document.activeElement;
    const held =
      previewBody !== null &&
      active instanceof HTMLElement &&
      previewBody.contains(active);
    render();
    if (held && active instanceof HTMLElement && !active.isConnected) {
      previewTitle?.focus();
    }
  }

  function renderPreviewState({ state }: { state: FlowPreviewState }): void {
    if (previewBody === null || previewStatus === null) {
      return;
    }
    const bodyElement = previewBody;
    const statusElement = previewStatus;
    withPreviewFocusGuard({
      render: () => {
        if (state.kind !== "updating") {
          retryDriven = false;
        }
        bodyElement.classList.remove("flow-builder-preview-body--stale");
        clearPreviewMarks();
        statusElement.hidden = state.kind !== "updating";
        if (state.kind === "updating") {
          if (retryDriven && previewErrorBlock !== null) {
            // A busy region would hide the focused Retry from assistive tech.
            bodyElement.removeAttribute("aria-busy");
            syncRetryDisabled();
            return;
          }
          bodyElement.setAttribute("aria-busy", "true");
          if (state.previous !== null) {
            previewResponse = state.previous;
            showPreviewCard({
              state: { kind: "response", response: state.previous },
            });
            previewShown = "card";
          } else {
            previewResponse = null;
            showPreviewCard({ state: { kind: "loading" } });
            previewShown = "skeleton";
          }
          return;
        }
        bodyElement.removeAttribute("aria-busy");
        previewResponse = null;
        if (state.kind === "placeholder") {
          showPreviewText({ text: strings().METRICS_FLOW_PREVIEW_PLACEHOLDER });
          previewShown = "placeholder";
          resetPreviewAnnouncements();
        } else if (state.kind === "result") {
          previewResponse = state.response;
          showPreviewCard({
            state: { kind: "response", response: state.response },
          });
          previewShown = "card";
          announceResult({ response: state.response });
        } else if (state.kind === "field-errors") {
          showPreviewText({ text: strings().METRICS_FLOW_PREVIEW_FIX_FIELDS });
          previewShown = "fields";
          storePreviewErrors({
            errors: state.errors,
            submitted: state.submitted,
          });
          announceProblems({
            errors: state.errors,
            rendered: applyPreviewMarks(),
          });
        } else {
          const message =
            state.kind === "rate-limited"
              ? strings().METRICS_FLOW_RATE_LIMITED
              : strings().METRICS_FLOW_PREVIEW_FAILED;
          showPreviewError({ message });
          previewShown = "error";
          syncRetryDisabled();
          announcePreview({
            item: { kind: state.kind, text: message, problems: null },
          });
        }
      },
    });
  }

  /** Save/Delete start: the controller is silent after `cancel()`, so freeze by hand. */
  function freezePreview(): void {
    preview.cancel();
    retryDriven = false;
    clearPreviewMarks();
    resetPreviewAnnouncements();
    if (previewLive !== null) {
      previewLive.textContent = "";
    }
    if (previewBody === null || previewStatus === null) {
      return;
    }
    const bodyElement = previewBody;
    const statusElement = previewStatus;
    withPreviewFocusGuard({
      render: () => {
        statusElement.hidden = true;
        bodyElement.removeAttribute("aria-busy");
        if (previewShown === "card" || previewShown === "skeleton") {
          bodyElement.classList.add("flow-builder-preview-body--stale");
        } else if (previewShown === "fields") {
          // The marks are gone, so "Fix the marked fields" would no longer be true.
          showPreviewText({ text: strings().METRICS_FLOW_PREVIEW_PLACEHOLDER });
          previewShown = "placeholder";
        }
        syncRetryDisabled();
      },
    });
  }

  /** Only the card title follows a name edit; the request body never contains it. */
  function refreshPreviewTitle(): void {
    if (previewShown === "card" && previewResponse !== null) {
      showPreviewCard({
        state: { kind: "response", response: previewResponse },
      });
    }
  }

  /**
   * Feeds the preview controller from the current draft. Called after every edit
   * except a rename; a draft that is not client-valid (ignoring the name) shows
   * the placeholder instead of sending.
   */
  function schedulePreview(): void {
    if (
      !opened ||
      catalog === null ||
      previewBody === null ||
      saving ||
      deleting
    ) {
      return;
    }
    const blocking = validateDraft({ draft, catalog }).filter(
      (error) => error.field !== "display_name",
    );
    if (blocking.length > 0) {
      preview.invalidate();
      return;
    }
    preview.update({
      body: {
        ...toRequestBody({ draft }),
        display_name: strings().METRICS_FLOW_PREVIEW_HEADING,
      },
      window: callbacks.getWindow(),
      submitted: captureSubmitted({ draft }),
    });
  }

  // ---------------------------------------------------------------------
  // Form rendering
  // ---------------------------------------------------------------------

  function renderForm(): void {
    if (body === null) {
      return;
    }
    const form = makeElement({
      tag: "form",
      className: "flow-builder-form",
      attrs: { novalidate: "", "aria-labelledby": headingId },
    });
    form.addEventListener("submit", handleSubmit);
    form.addEventListener("click", handleClick);
    form.addEventListener("input", handleInput);
    form.addEventListener("change", handleChange);
    formElement = form;

    const nameId = `${uid}-name`;
    const nameField = makeElement({
      tag: "div",
      className: "flow-builder-field",
    });
    nameInput = makeElement({
      tag: "input",
      className: "flow-builder-input",
      attrs: {
        id: nameId,
        type: "text",
        autocomplete: "off",
        "data-field": "display_name",
        maxlength: String(constants().METRIC_FLOWS_NAME_MAX_LENGTH),
      },
    });
    nameInput.value = draft.displayName;
    nameError = makeElement({
      tag: "p",
      className: "flow-builder-error",
      attrs: { id: nameErrorId },
    });
    nameField.append(
      makeElement({
        tag: "label",
        className: "flow-builder-label",
        text: strings().METRICS_FLOW_BUILDER_FIELD_NAME,
        attrs: { for: nameId },
      }),
      nameInput,
      nameError,
    );
    stepsError = makeElement({
      tag: "p",
      className: "flow-builder-error",
      attrs: { id: stepsErrorId },
    });
    formErrorRegion = makeElement({
      tag: "div",
      className: "flow-builder-form-errors",
      attrs: { role: "alert", id: formErrorsId },
    });
    saveButton = makeElement({
      tag: "button",
      className: "flow-builder-btn flow-builder-save",
      text: strings().METRICS_FLOW_BUILDER_SAVE,
      attrs: { type: "submit" },
    });

    stepList = makeElement({ tag: "ol", className: "flow-builder-steps" });
    addButton = makeElement({
      tag: "button",
      className: "flow-builder-btn flow-builder-add",
      attrs: { type: "button", "data-action": "add" },
    });
    reasonLine = makeElement({
      tag: "p",
      className: "flow-builder-reason",
      attrs: { id: addReasonId },
    });
    const addRow = makeElement({
      tag: "div",
      className: "flow-builder-add-row",
    });
    addRow.append(addButton, reasonLine);

    const actions = makeElement({
      tag: "div",
      className: "flow-builder-actions",
    });
    cancelButton = makeElement({
      tag: "button",
      className: "flow-builder-btn",
      text: strings().METRICS_FLOW_BUILDER_CANCEL,
      attrs: { type: "button", "data-action": "cancel" },
    });
    actions.append(saveButton, cancelButton);
    deleteButton = null;
    if (mode === "edit") {
      deleteButton = makeElement({
        tag: "button",
        className: "flow-builder-btn flow-builder-delete",
        text: strings().METRICS_FLOW_BUILDER_DELETE,
        attrs: { type: "button", "data-action": "delete" },
      });
      actions.append(deleteButton);
    }

    form.append(
      nameField,
      makeElement({
        tag: "p",
        className: "flow-builder-hint",
        text: strings().METRICS_FLOW_BUILDER_HINT_FIRST_STEP,
      }),
      stepList,
      addRow,
      stepsError,
      makeElement({
        tag: "span",
        className: "visually-hidden",
        text: strings().METRICS_FLOW_BUILDER_HINT_ALREADY_FIRST,
        attrs: { id: firstReasonId },
      }),
      makeElement({
        tag: "span",
        className: "visually-hidden",
        text: strings().METRICS_FLOW_BUILDER_HINT_ALREADY_LAST,
        attrs: { id: lastReasonId },
      }),
      formErrorRegion,
      actions,
    );
    const layout = makeElement({
      tag: "div",
      className: "flow-builder-layout",
    });
    layout.append(form, buildPreviewSection());
    body.replaceChildren(layout);
    renderSteps();
    renderNameError();
    renderStepsError();
    renderFormErrors();
    // Upgrades the open-time lines to link-buttons now that fields exist.
    renderSummary();
  }

  function renderSteps(): void {
    if (stepList === null) {
      return;
    }
    stepList.replaceChildren(
      ...draft.steps.map((step, index) => renderRow({ step, index })),
    );
    refreshControls();
  }

  function replaceRow({ key }: { key: number }): void {
    const index = draft.steps.findIndex((step) => step.key === key);
    const existing = findRow({ key });
    if (index === -1 || existing === null) {
      return;
    }
    existing.replaceWith(renderRow({ step: draft.steps[index], index }));
    refreshControls();
  }

  /** Disabled flags and reason text that depend on the step count and position. */
  function refreshControls(): void {
    if (stepList === null || addButton === null || reasonLine === null) {
      return;
    }
    const count = draft.steps.length;
    const atMax = count >= constants().METRIC_FLOWS_MAX_STEPS;
    const atMin = count <= constants().METRIC_FLOWS_MIN_STEPS;
    addButton.textContent = fillTemplate({
      template: strings().METRICS_FLOW_BUILDER_ADD_STEP,
      values: {
        count: String(count),
        max: String(constants().METRIC_FLOWS_MAX_STEPS),
      },
    });
    setDisabled({ element: addButton, disabled: atMax, reasonId: addReasonId });
    // setDisabled owns aria-describedby; re-apply the steps-error link on top.
    renderStepsError();
    if (atMax) {
      reasonLine.textContent = fillTemplate({
        template: strings().METRICS_FLOW_BUILDER_HINT_MAX_STEPS,
        values: { max: String(constants().METRIC_FLOWS_MAX_STEPS) },
      });
    } else if (atMin) {
      reasonLine.textContent = fillTemplate({
        template: strings().METRICS_FLOW_BUILDER_HINT_MIN_STEPS,
        values: { min: String(constants().METRIC_FLOWS_MIN_STEPS) },
      });
    } else {
      reasonLine.textContent = "";
    }
    draft.steps.forEach((step, index) => {
      const row = findRow({ key: step.key });
      if (row === null) {
        return;
      }
      const up = findAction({ row, action: "move-up" });
      const down = findAction({ row, action: "move-down" });
      const remove = findAction({ row, action: "remove" });
      if (up !== null) {
        setDisabled({
          element: up,
          disabled: index === 0,
          reasonId: firstReasonId,
        });
      }
      if (down !== null) {
        setDisabled({
          element: down,
          disabled: index === count - 1,
          reasonId: lastReasonId,
        });
      }
      if (remove !== null) {
        setDisabled({
          element: remove,
          disabled: atMin,
          reasonId: addReasonId,
        });
      }
    });
    // Rebuilt rows and re-linked controls lose their marks; put them back.
    applyPreviewMarks();
  }

  function renderRow({
    step,
    index,
  }: {
    step: DraftStep;
    index: number;
  }): HTMLElement {
    const position = String(index + 1);
    const row = makeElement({
      tag: "li",
      className: "flow-builder-step",
      attrs: { "data-step-key": String(step.key) },
    });
    const head = makeElement({
      tag: "div",
      className: "flow-builder-step-head",
    });
    const controls = makeElement({
      tag: "div",
      className: "flow-builder-step-actions",
    });
    controls.append(
      makeIconButton({
        action: "move-up",
        template: strings().METRICS_FLOW_BUILDER_MOVE_UP,
        position,
      }),
      makeIconButton({
        action: "move-down",
        template: strings().METRICS_FLOW_BUILDER_MOVE_DOWN,
        position,
      }),
      makeIconButton({
        action: "remove",
        template: strings().METRICS_FLOW_BUILDER_REMOVE_STEP,
        position,
      }),
    );
    head.append(
      makeElement({
        tag: "h4",
        className: "flow-builder-step-title",
        text: fillTemplate({
          template: strings().METRICS_FLOW_BUILDER_STEP_HEADING,
          values: { step: position },
        }),
      }),
      controls,
    );

    const grid = makeElement({
      tag: "div",
      className: "flow-builder-step-grid",
    });
    grid.append(
      renderLabelCell({ step, position }),
      renderStreamCell({ step, position }),
    );
    if (step.stream === "api") {
      grid.append(
        renderEndpointCell({ step, position }),
        renderMethodCell({ step, position }),
      );
    } else {
      grid.append(renderEventCell({ step, position }));
    }
    row.append(head, grid, renderExtras({ uid, catalog, step, position }));
    return row;
  }

  /** Re-renders only a step's filter group and Add row; the rest of the row stays. */
  function replaceExtras({ key }: { key: number }): void {
    const index = draft.steps.findIndex((step) => step.key === key);
    const existing = findRow({ key })?.querySelector(".flow-builder-extras");
    if (index === -1 || existing === null || existing === undefined) {
      return;
    }
    existing.replaceWith(
      renderExtras({
        uid,
        catalog,
        step: draft.steps[index],
        position: String(index + 1),
      }),
    );
    applyPreviewMarks();
  }

  function focusFilterControl({
    key,
    filterKey,
    field,
  }: {
    key: number;
    filterKey: number;
    field: string;
  }): void {
    const row = findRow({ key });
    if (row !== null) {
      findFilterControl({ row, filterKey, field })?.focus();
    }
  }

  function filterKeyOf({ target }: { target: HTMLElement }): number | null {
    const raw = target.dataset.filterKey;
    const filterKey = raw === undefined ? NaN : Number(raw);
    return Number.isInteger(filterKey) ? filterKey : null;
  }

  function handleAddFilter({ key }: { key: number }): void {
    stopDescribingHeading();
    const before = draft.steps.find((step) => step.key === key);
    if (before === undefined) {
      return;
    }
    if (filterAddReason({ catalog, step: before }) !== null) {
      return;
    }
    const replacedDamaged =
      before.damaged !== null && "dim_filter" in before.damaged;
    draft = addFilter({ draft, key });
    const after = draft.steps.find((step) => step.key === key);
    const added = after?.filters[after.filters.length - 1];
    replaceExtras({ key });
    renderSummary();
    if (added !== undefined) {
      focusFilterControl({
        key,
        filterKey: added.key,
        field: FILTER_DIM_FIELD,
      });
    }
    callbacks.announce({
      message: replacedDamaged
        ? strings().METRICS_FLOW_BUILDER_ANNOUNCE_DAMAGED_FILTERS_REPLACED
        : strings().METRICS_FLOW_BUILDER_ANNOUNCE_FILTER_ADDED,
    });
  }

  function handleRemoveFilter({
    key,
    filterKey,
  }: {
    key: number;
    filterKey: number;
  }): void {
    stopDescribingHeading();
    const before = draft.steps.find((step) => step.key === key);
    const index = before?.filters.findIndex((item) => item.key === filterKey);
    if (before === undefined || index === undefined || index === -1) {
      return;
    }
    draft = removeFilter({ draft, key, filterKey });
    const remaining =
      draft.steps.find((step) => step.key === key)?.filters ?? [];
    replaceExtras({ key });
    renderSummary();
    const neighbour = remaining[index] ?? remaining[index - 1];
    if (neighbour !== undefined) {
      focusFilterControl({
        key,
        filterKey: neighbour.key,
        field: FILTER_DIM_FIELD,
      });
    } else {
      const row = findRow({ key });
      if (row !== null) {
        findExtrasButton({ row, action: ADD_FILTER_ACTION })?.focus();
      }
    }
    callbacks.announce({
      message: strings().METRICS_FLOW_BUILDER_ANNOUNCE_FILTER_REMOVED,
    });
  }

  /** A filter select changed: update the draft, re-render the group, keep focus. */
  function handleFilterSelect({
    key,
    filterKey,
    field,
    value,
  }: {
    key: number;
    filterKey: number;
    field: string;
    value: string;
  }): void {
    stopDescribingHeading();
    draft =
      field === FILTER_DIM_FIELD
        ? setFilterDim({
            draft,
            key,
            filterKey,
            dim: value === "" ? null : value,
          })
        : setFilterValue({ draft, key, filterKey, value });
    replaceExtras({ key });
    renderSummary();
    focusFilterControl({ key, filterKey, field });
  }

  function focusExtrasButton({
    key,
    action,
  }: {
    key: number;
    action: string;
  }): void {
    const row = findRow({ key });
    if (row !== null) {
      findExtrasButton({ row, action })?.focus();
    }
  }

  function handleAddBreakdown({ key }: { key: number }): void {
    stopDescribingHeading();
    const before = draft.steps.find((step) => step.key === key);
    if (
      before === undefined ||
      before.breakdown !== null ||
      breakdownAddReason({ catalog, step: before }) !== null
    ) {
      return;
    }
    const replacedDamaged =
      before.damaged !== null && "drop_breakdown" in before.damaged;
    draft = addBreakdown({ draft, key });
    replaceExtras({ key });
    renderSummary();
    const row = findRow({ key });
    if (row !== null) {
      findBreakdownControl({ row, field: BREAKDOWN_EVENT_FIELD })?.focus();
    }
    callbacks.announce({
      message: replacedDamaged
        ? strings().METRICS_FLOW_BUILDER_ANNOUNCE_DAMAGED_BREAKDOWN_REPLACED
        : strings().METRICS_FLOW_BUILDER_ANNOUNCE_BREAKDOWN_ADDED,
    });
  }

  function handleRemoveBreakdown({ key }: { key: number }): void {
    stopDescribingHeading();
    const before = draft.steps.find((step) => step.key === key);
    if (before === undefined || before.breakdown === null) {
      return;
    }
    draft = removeBreakdown({ draft, key });
    replaceExtras({ key });
    renderSummary();
    focusExtrasButton({ key, action: ADD_BREAKDOWN_ACTION });
    callbacks.announce({
      message: strings().METRICS_FLOW_BUILDER_ANNOUNCE_BREAKDOWN_REMOVED,
    });
  }

  function handleAddBreakdownFilter({ key }: { key: number }): void {
    stopDescribingHeading();
    const breakdown = draft.steps.find((step) => step.key === key)?.breakdown;
    if (
      breakdown === null ||
      breakdown === undefined ||
      breakdownFilterAddReason({ catalog, breakdown }) !== null
    ) {
      return;
    }
    const replacedDamaged = breakdown.damaged !== null;
    draft = addBreakdownFilter({ draft, key });
    const filters =
      draft.steps.find((step) => step.key === key)?.breakdown?.filters ?? [];
    const added = filters[filters.length - 1];
    replaceExtras({ key });
    renderSummary();
    if (added !== undefined) {
      focusFilterControl({
        key,
        filterKey: added.key,
        field: BREAKDOWN_FILTER_DIM_FIELD,
      });
    }
    callbacks.announce({
      message: replacedDamaged
        ? strings()
            .METRICS_FLOW_BUILDER_ANNOUNCE_DAMAGED_BREAKDOWN_FILTERS_REPLACED
        : strings().METRICS_FLOW_BUILDER_ANNOUNCE_FILTER_ADDED,
    });
  }

  function handleRemoveBreakdownFilter({
    key,
    filterKey,
  }: {
    key: number;
    filterKey: number;
  }): void {
    stopDescribingHeading();
    const before = draft.steps.find((step) => step.key === key)?.breakdown;
    const index = before?.filters.findIndex((item) => item.key === filterKey);
    if (
      before === null ||
      before === undefined ||
      index === undefined ||
      index === -1
    ) {
      return;
    }
    draft = removeBreakdownFilter({ draft, key, filterKey });
    const after = draft.steps.find((step) => step.key === key)?.breakdown;
    const remaining = after?.filters ?? [];
    replaceExtras({ key });
    renderSummary();
    const neighbour = remaining[index] ?? remaining[index - 1];
    const row = findRow({ key });
    if (neighbour === undefined || row === null) {
      focusExtrasButton({ key, action: ADD_BREAKDOWN_FILTER_ACTION });
    } else if (
      after !== null &&
      after !== undefined &&
      breakdownState({ catalog, breakdown: after }) !== "normal"
    ) {
      // A read-only row has no focusable dim: land on its Remove instead.
      findFilterRemoveButton({
        row,
        action: REMOVE_BREAKDOWN_FILTER_ACTION,
        filterKey: neighbour.key,
      })?.focus();
    } else {
      focusFilterControl({
        key,
        filterKey: neighbour.key,
        field: BREAKDOWN_FILTER_DIM_FIELD,
      });
    }
    callbacks.announce({
      message: strings().METRICS_FLOW_BUILDER_ANNOUNCE_FILTER_REMOVED,
    });
  }

  /** A breakdown select changed: update the draft, re-render the block, keep focus. */
  function handleBreakdownSelect({
    key,
    field,
    filterKey,
    value,
  }: {
    key: number;
    field: string;
    filterKey: number | null;
    value: string;
  }): void {
    stopDescribingHeading();
    const breakdownBefore = draft.steps.find(
      (step) => step.key === key,
    )?.breakdown;
    const hadDamaged =
      breakdownBefore !== null &&
      breakdownBefore !== undefined &&
      breakdownBefore.damaged !== null;
    if (field === BREAKDOWN_EVENT_FIELD) {
      draft = setBreakdownEvent({ draft, key, eventName: value });
    } else if (field === BREAKDOWN_GROUP_BY_FIELD) {
      draft = setBreakdownGroupBy({ draft, key, groupBy: value });
    } else if (filterKey !== null && field === BREAKDOWN_FILTER_DIM_FIELD) {
      draft = setBreakdownFilterDim({
        draft,
        key,
        filterKey,
        dim: value === "" ? null : value,
      });
    } else if (filterKey !== null && field === BREAKDOWN_FILTER_VALUE_FIELD) {
      draft = setBreakdownFilterValue({ draft, key, filterKey, value });
    } else {
      return;
    }
    replaceExtras({ key });
    renderSummary();
    if (filterKey !== null) {
      focusFilterControl({ key, filterKey, field });
      return;
    }
    const row = findRow({ key });
    if (row !== null) {
      findBreakdownControl({ row, field })?.focus();
    }
    const breakdownAfter = draft.steps.find(
      (step) => step.key === key,
    )?.breakdown;
    if (
      field === BREAKDOWN_EVENT_FIELD &&
      hadDamaged &&
      breakdownAfter !== null &&
      breakdownAfter !== undefined &&
      breakdownAfter.damaged === null
    ) {
      callbacks.announce({
        message:
          strings()
            .METRICS_FLOW_BUILDER_ANNOUNCE_DAMAGED_BREAKDOWN_FILTERS_REPLACED,
      });
    }
  }

  function makeIconButton({
    action,
    template,
    position,
  }: {
    action: StepAction;
    template: string;
    position: string;
  }): HTMLButtonElement {
    // The glyph is drawn by CSS (::before on [data-action]); aria-label names it.
    return makeElement({
      tag: "button",
      className: "flow-builder-icon-btn",
      attrs: {
        type: "button",
        "data-action": action,
        "aria-label": fillTemplate({ template, values: { step: position } }),
      },
    });
  }

  function makeCell({
    control,
    step,
    field,
  }: {
    control: HTMLElement;
    step: DraftStep;
    field: string;
  }): HTMLElement {
    return makeCellElement({
      control,
      field,
      messages: step.errors[field] ?? [],
      errorId: `${uid}-${step.key}-${field}-error`,
    });
  }

  function stepLabel({
    template,
    position,
  }: {
    template: string;
    position: string;
  }): string {
    return fillTemplate({ template, values: { step: position } });
  }

  function renderLabelCell({
    step,
    position,
  }: {
    step: DraftStep;
    position: string;
  }): HTMLElement {
    const input = makeElement({
      tag: "input",
      className: "flow-builder-input",
      attrs: {
        type: "text",
        autocomplete: "off",
        "data-field": "label",
        "data-step-key": String(step.key),
        "aria-label": stepLabel({
          template: strings().METRICS_FLOW_BUILDER_STEP_LABEL,
          position,
        }),
        maxlength: String(constants().METRIC_FLOWS_LABEL_MAX_LENGTH),
      },
    });
    input.value = step.label;
    return makeCell({ control: input, step, field: "label" });
  }

  function renderStreamCell({
    step,
    position,
  }: {
    step: DraftStep;
    position: string;
  }): HTMLElement {
    const select = makeSelect({
      field: "stream",
      key: step.key,
      label: stepLabel({
        template: strings().METRICS_FLOW_BUILDER_STEP_STREAM,
        position,
      }),
    });
    const labels: Record<StepStream, string> = {
      ui: strings().METRICS_FLOW_BUILDER_STREAM_UI,
      api: strings().METRICS_FLOW_BUILDER_STREAM_API,
      domain: strings().METRICS_FLOW_BUILDER_STREAM_DOMAIN,
    };
    for (const stream of STREAMS) {
      select.append(
        makeOption({
          value: stream,
          text: labels[stream],
          selected: stream === step.stream,
        }),
      );
    }
    return makeCell({ control: select, step, field: "stream" });
  }

  function renderEventCell({
    step,
    position,
  }: {
    step: DraftStep;
    position: string;
  }): HTMLElement {
    const select = makeSelect({
      field: "event_name",
      key: step.key,
      label: stepLabel({
        template: strings().METRICS_FLOW_BUILDER_STEP_EVENT,
        position,
      }),
    });
    select.append(
      makeOption({
        value: "",
        text: strings().METRICS_FLOW_BUILDER_CHOOSE_EVENT,
        selected: step.eventName === null,
      }),
    );
    if (catalog !== null) {
      if (
        step.eventName !== null &&
        isStaleEvent({
          catalog,
          stream: step.stream,
          eventName: step.eventName,
        })
      ) {
        appendStaleOption({ select, value: step.eventName });
      }
      for (const event of listEventOptions({ catalog, stream: step.stream })) {
        select.append(
          makeOption({
            value: event.event_name,
            text: event.event_name,
            selected: event.event_name === step.eventName,
          }),
        );
      }
    }
    return makeCell({ control: select, step, field: "event_name" });
  }

  function renderEndpointCell({
    step,
    position,
  }: {
    step: DraftStep;
    position: string;
  }): HTMLElement {
    const select = makeSelect({
      field: "api_endpoint",
      key: step.key,
      label: stepLabel({
        template: strings().METRICS_FLOW_BUILDER_STEP_ENDPOINT,
        position,
      }),
    });
    select.append(
      makeOption({
        value: "",
        text: strings().METRICS_FLOW_BUILDER_CHOOSE_ENDPOINT,
        selected: step.apiEndpoint === null,
      }),
    );
    if (catalog !== null) {
      if (
        step.apiEndpoint !== null &&
        isStaleEndpoint({ catalog, apiEndpoint: step.apiEndpoint })
      ) {
        appendStaleOption({ select, value: step.apiEndpoint });
      }
      for (const group of listEndpointGroups({ catalog })) {
        const optgroup = makeElement({
          tag: "optgroup",
          attrs: { label: group.blueprint },
        });
        for (const endpoint of group.endpoints) {
          optgroup.append(
            makeOption({
              value: endpoint.endpoint,
              text: endpoint.endpoint,
              selected: endpoint.endpoint === step.apiEndpoint,
            }),
          );
        }
        select.append(optgroup);
      }
    }
    return makeCell({ control: select, step, field: "api_endpoint" });
  }

  function renderMethodCell({
    step,
    position,
  }: {
    step: DraftStep;
    position: string;
  }): HTMLElement {
    const select = makeSelect({
      field: "api_method",
      key: step.key,
      label: stepLabel({
        template: strings().METRICS_FLOW_BUILDER_STEP_METHOD,
        position,
      }),
    });
    select.append(
      makeOption({
        value: "",
        text: strings().METRICS_FLOW_BUILDER_CHOOSE_METHOD,
        selected: step.apiMethod === null,
      }),
    );
    if (catalog !== null) {
      if (
        step.apiMethod !== null &&
        isStaleMethod({
          catalog,
          apiEndpoint: step.apiEndpoint,
          apiMethod: step.apiMethod,
        })
      ) {
        appendStaleOption({ select, value: step.apiMethod });
      }
      if (step.apiEndpoint !== null) {
        for (const method of listMethods({
          catalog,
          endpoint: step.apiEndpoint,
        })) {
          select.append(
            makeOption({
              value: method,
              text: method,
              selected: method === step.apiMethod,
            }),
          );
        }
      }
    }
    return makeCell({ control: select, step, field: "api_method" });
  }

  // ---------------------------------------------------------------------
  // Lookup and focus helpers
  // ---------------------------------------------------------------------

  function findRow({ key }: { key: number }): HTMLElement | null {
    return (
      stepList?.querySelector<HTMLElement>(`[data-step-key="${key}"]`) ?? null
    );
  }

  function findAction({
    row,
    action,
  }: {
    row: HTMLElement;
    action: StepAction;
  }): HTMLButtonElement | null {
    return row.querySelector<HTMLButtonElement>(`[data-action="${action}"]`);
  }

  function focusField({ key, field }: { key: number; field: string }): void {
    findRow({ key })
      ?.querySelector<HTMLElement>(`[data-field="${field}"]`)
      ?.focus();
  }

  function stepKeyOf({ target }: { target: HTMLElement }): number | null {
    const raw = target.closest<HTMLElement>("[data-step-key]")?.dataset.stepKey;
    const key = raw === undefined ? NaN : Number(raw);
    return Number.isInteger(key) ? key : null;
  }

  /** Per-field errors are cleared as soon as the field is edited. */
  function clearFieldError({
    key,
    field,
  }: {
    key: number;
    field: string;
  }): void {
    const step = draft.steps.find((item) => item.key === key);
    if (step === undefined || !(field in step.errors)) {
      return;
    }
    const rest = Object.fromEntries(
      Object.entries(step.errors).filter(([name]) => name !== field),
    );
    draft = {
      ...draft,
      steps: draft.steps.map((item) =>
        item.key === key ? { ...item, errors: rest } : item,
      ),
    };
    const cell = findRow({ key })?.querySelector(`[data-cell="${field}"]`);
    cell?.querySelector(".flow-builder-error")?.remove();
    const control = cell?.querySelector("[data-field]");
    control?.removeAttribute("aria-invalid");
    control?.removeAttribute("aria-describedby");
    renderSummary();
  }

  function stepHasNested({ key }: { key: number }): boolean {
    const step = draft.steps.find((item) => item.key === key);
    return step !== undefined && hasNestedContent({ step });
  }

  /** Announces politely when this edit just dropped a step's filters and breakdown. */
  function announceIfCleared({
    key,
    hadNested,
  }: {
    key: number;
    hadNested: boolean;
  }): void {
    if (hadNested && !stepHasNested({ key })) {
      callbacks.announce({
        message: strings().METRICS_FLOW_BUILDER_ANNOUNCE_FILTERS_CLEARED,
      });
    }
  }

  // ---------------------------------------------------------------------
  // Event handlers
  // ---------------------------------------------------------------------

  /** Typing in a row's value input retires that row's error and its aria links. */
  function clearRowError({ target }: { target: HTMLElement }): void {
    const row = target.closest<HTMLElement>(".flow-builder-filter");
    const messages = row?.querySelectorAll<HTMLElement>(".flow-builder-error");
    if (
      row === null ||
      row === undefined ||
      !messages ||
      messages.length === 0
    ) {
      return;
    }
    const messageIds = new Set<string>();
    for (const message of messages) {
      messageIds.add(message.id);
      message.remove();
    }
    for (const control of row.querySelectorAll<HTMLElement>("[data-field]")) {
      control.removeAttribute("aria-invalid");
      const rest = (control.getAttribute("aria-describedby") ?? "")
        .split(" ")
        .filter((id) => id !== "" && !messageIds.has(id));
      if (rest.length > 0) {
        control.setAttribute("aria-describedby", rest.join(" "));
      } else {
        control.removeAttribute("aria-describedby");
      }
    }
  }

  function handleInput(event: Event): void {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) {
      return;
    }
    stopDescribingHeading();
    if (target.dataset.field === "display_name") {
      draft = setDisplayName({ draft, value: target.value });
      draft = clearDraftError({ draft, field: "display_name" });
      renderNameError();
      renderSummary();
      refreshPreviewTitle();
      return;
    }
    const key = stepKeyOf({ target });
    if (target.dataset.field === "label" && key !== null) {
      draft = setStepLabel({ draft, key, value: target.value });
      clearFieldError({ key, field: "label" });
      schedulePreview();
      return;
    }
    const filterKey = filterKeyOf({ target });
    if (
      target.dataset.field === FILTER_VALUE_FIELD &&
      key !== null &&
      filterKey !== null
    ) {
      // Typing writes straight into the draft; the input keeps focus.
      draft = setFilterValue({
        draft,
        key,
        filterKey,
        value: target.value,
      });
      clearRowError({ target });
      renderSummary();
      schedulePreview();
    }
    if (
      target.dataset.field === BREAKDOWN_FILTER_VALUE_FIELD &&
      key !== null &&
      filterKey !== null
    ) {
      draft = setBreakdownFilterValue({
        draft,
        key,
        filterKey,
        value: target.value,
      });
      clearRowError({ target });
      renderSummary();
      schedulePreview();
    }
  }

  /** Every select change is structural, so it ends in a preview refresh. */
  function handleChange(event: Event): void {
    const before = draft;
    applyChange(event);
    if (draft !== before && event.target instanceof HTMLSelectElement) {
      schedulePreview();
    }
  }

  function applyChange(event: Event): void {
    const target = event.target;
    if (
      target instanceof HTMLInputElement &&
      (target.dataset.field === FILTER_VALUE_FIELD ||
        target.dataset.field === BREAKDOWN_FILTER_VALUE_FIELD)
    ) {
      // handleInput already wrote the draft; a re-render would swallow the next click.
      return;
    }
    if (!(target instanceof HTMLSelectElement)) {
      return;
    }
    const key = stepKeyOf({ target });
    const field = target.dataset.field;
    if (key === null || field === undefined) {
      return;
    }
    const filterKey = filterKeyOf({ target });
    if (
      filterKey !== null &&
      (field === FILTER_DIM_FIELD || field === FILTER_VALUE_FIELD)
    ) {
      handleFilterSelect({ key, filterKey, field, value: target.value });
      return;
    }
    if (
      field === BREAKDOWN_EVENT_FIELD ||
      field === BREAKDOWN_GROUP_BY_FIELD ||
      (filterKey !== null &&
        (field === BREAKDOWN_FILTER_DIM_FIELD ||
          field === BREAKDOWN_FILTER_VALUE_FIELD))
    ) {
      handleBreakdownSelect({ key, field, filterKey, value: target.value });
      return;
    }
    stopDescribingHeading();
    const hadNested = stepHasNested({ key });
    if (field === "stream" && isStream(target.value)) {
      draft = setStepStream({ draft, key, stream: target.value });
      for (const name of [
        "stream",
        "event_name",
        "api_endpoint",
        "api_method",
      ]) {
        clearFieldError({ key, field: name });
      }
      replaceRow({ key });
      focusField({ key, field });
    } else if (field === "event_name") {
      draft = setStepEvent({ draft, key, eventName: target.value });
      clearFieldError({ key, field });
      replaceRow({ key });
      focusField({ key, field });
    } else if (field === "api_endpoint") {
      draft = setStepEndpoint({
        draft,
        key,
        apiEndpoint: target.value,
        catalog,
      });
      clearFieldError({ key, field });
      clearFieldError({ key, field: "api_method" });
      replaceRow({ key });
      focusField({ key, field });
    } else if (field === "api_method") {
      draft = setStepMethod({ draft, key, apiMethod: target.value });
      clearFieldError({ key, field });
      replaceRow({ key });
      focusField({ key, field });
    }
    announceIfCleared({ key, hadNested });
  }

  /**
   * Escape, on the builder root only. A focused select is ignored (browsers do not
   * say whether it is open); an open confirm takes Escape as its safe choice; else
   * Cancel runs through the gate. No other key is handled.
   */
  function handleKeydown(event: KeyboardEvent): void {
    if (event.key === "Tab" && opened && pendingConfirm !== null) {
      trapConfirmFocus({ event, confirm: pendingConfirm });
      return;
    }
    if (
      event.key === "Enter" &&
      opened &&
      event.target instanceof HTMLInputElement &&
      (event.target.dataset.field === FILTER_VALUE_FIELD ||
        event.target.dataset.field === BREAKDOWN_FILTER_VALUE_FIELD)
    ) {
      // Same path as the form's submit; Enter on selects stays native.
      handleSubmit(event);
      return;
    }
    if (event.key !== "Escape" || event.defaultPrevented || !opened) {
      return;
    }
    if (pendingConfirm !== null) {
      event.stopPropagation();
      event.preventDefault();
      if (!deleting) {
        pendingConfirm.onSafe();
      }
      return;
    }
    if (event.target instanceof HTMLSelectElement) {
      event.stopPropagation();
      return;
    }
    handleCancel();
  }

  /** Keeps Tab inside the open alertdialog; the form behind it is inert. */
  function trapConfirmFocus({
    event,
    confirm,
  }: {
    event: KeyboardEvent;
    confirm: PendingConfirm;
  }): void {
    const first = confirm.confirmButton;
    const last = confirm.safeButton;
    const active = document.activeElement;
    if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    } else if (active !== first && active !== last) {
      event.preventDefault();
      last.focus();
    }
  }

  function handleCancel(): void {
    const prompts =
      isDirty() && !saving && !deleting && pendingConfirm === null;
    void confirmDiscard().then((discard) => {
      if (discard) {
        callbacks.onCancelled();
      } else if (prompts && opened) {
        cancelButton?.focus();
      }
    });
  }

  /** Step, filter and breakdown buttons change the draft; Cancel and Delete do not. */
  function handleClick(event: MouseEvent): void {
    const before = draft;
    applyClick(event);
    if (draft !== before) {
      schedulePreview();
    }
  }

  function applyClick(event: MouseEvent): void {
    const target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    const button = target.closest<HTMLButtonElement>("button[data-action]");
    if (button === null) {
      return;
    }
    if (isDisabled({ element: button })) {
      event.preventDefault();
      return;
    }
    const action = button.dataset.action;
    const key = stepKeyOf({ target: button });
    if (key !== null && action === ADD_FILTER_ACTION) {
      handleAddFilter({ key });
      return;
    }
    const filterKey = filterKeyOf({ target: button });
    if (key !== null && filterKey !== null && action === REMOVE_FILTER_ACTION) {
      handleRemoveFilter({ key, filterKey });
      return;
    }
    if (key !== null && action === ADD_BREAKDOWN_ACTION) {
      handleAddBreakdown({ key });
      return;
    }
    if (key !== null && action === REMOVE_BREAKDOWN_ACTION) {
      handleRemoveBreakdown({ key });
      return;
    }
    if (key !== null && action === ADD_BREAKDOWN_FILTER_ACTION) {
      handleAddBreakdownFilter({ key });
      return;
    }
    if (
      key !== null &&
      filterKey !== null &&
      action === REMOVE_BREAKDOWN_FILTER_ACTION
    ) {
      handleRemoveBreakdownFilter({ key, filterKey });
      return;
    }
    if (action === "add") {
      handleAdd();
    } else if (action === "cancel") {
      handleCancel();
    } else if (action === "delete") {
      handleDeleteClick();
    } else if (key !== null && action === "remove") {
      handleRemove({ key });
    } else if (
      key !== null &&
      (action === "move-up" || action === "move-down")
    ) {
      handleMove({ key, action });
    }
  }

  function handleAdd(): void {
    if (draft.steps.length >= constants().METRIC_FLOWS_MAX_STEPS) {
      return;
    }
    stopDescribingHeading();
    draft = clearDraftError({ draft: addStep({ draft }), field: "steps" });
    renderSteps();
    renderStepsError();
    renderSummary();
    const added = draft.steps[draft.steps.length - 1];
    focusField({ key: added.key, field: "label" });
    callbacks.announce({
      message: strings().METRICS_FLOW_BUILDER_ANNOUNCE_ADDED,
    });
  }

  function handleRemove({ key }: { key: number }): void {
    if (draft.steps.length <= constants().METRIC_FLOWS_MIN_STEPS) {
      return;
    }
    const index = draft.steps.findIndex((step) => step.key === key);
    if (index === -1) {
      return;
    }
    stopDescribingHeading();
    draft = clearDraftError({
      draft: removeStep({ draft, key }),
      field: "steps",
    });
    renderSteps();
    renderStepsError();
    renderSummary();
    const neighbour = draft.steps[index] ?? draft.steps[index - 1];
    if (neighbour !== undefined) {
      focusField({ key: neighbour.key, field: "label" });
    } else {
      addButton?.focus();
    }
    callbacks.announce({
      message: strings().METRICS_FLOW_BUILDER_ANNOUNCE_REMOVED,
    });
  }

  function handleMove({
    key,
    action,
  }: {
    key: number;
    action: "move-up" | "move-down";
  }): void {
    const next = moveStep({
      draft,
      key,
      direction: action === "move-up" ? "up" : "down",
    });
    if (next === draft) {
      return;
    }
    stopDescribingHeading();
    draft = next;
    renderSteps();
    renderSummary();
    const row = findRow({ key });
    if (row !== null) {
      findAction({ row, action })?.focus();
    }
    callbacks.announce({
      message: fillTemplate({
        template: strings().METRICS_FLOW_BUILDER_ANNOUNCE_MOVED,
        values: {
          position: String(
            draft.steps.findIndex((step) => step.key === key) + 1,
          ),
          total: String(draft.steps.length),
        },
      }),
    });
  }

  // ---------------------------------------------------------------------
  // Public surface
  // ---------------------------------------------------------------------

  function isDirty(): boolean {
    return opened && isDraftDirty({ draft, snapshot });
  }

  // ---------------------------------------------------------------------
  // Confirms (one at a time)
  // ---------------------------------------------------------------------

  function closeConfirm(): void {
    const closing = pendingConfirm;
    pendingConfirm = null;
    closing?.element.remove();
    formElement?.removeAttribute("inert");
    syncRetryDisabled();
    flushHeldPreviewAnnouncement();
  }

  function openConfirm({
    kind,
    title,
    text,
    confirmText,
    safeText,
    onConfirm,
    onSafe,
    resolve,
  }: {
    kind: PendingConfirm["kind"];
    title: string;
    text: string;
    confirmText: string;
    safeText: string;
    onConfirm(): void;
    onSafe(): void;
    resolve: PendingConfirm["resolve"];
  }): void {
    if (body === null) {
      resolve?.(false);
      return;
    }
    const element = makeElement({
      tag: "div",
      className: "flow-builder-confirm",
      attrs: {
        role: "alertdialog",
        "data-kind": kind,
        "aria-labelledby": confirmTitleId,
        "aria-describedby": confirmBodyId,
      },
    });
    const confirmButton = makeElement({
      tag: "button",
      className:
        kind === "delete"
          ? "flow-builder-btn flow-builder-delete"
          : "flow-builder-btn",
      text: confirmText,
      attrs: { type: "button", "data-confirm": "confirm" },
    });
    const safeButton = makeElement({
      tag: "button",
      className: "flow-builder-btn flow-builder-save",
      text: safeText,
      attrs: { type: "button", "data-confirm": "safe" },
    });
    confirmButton.addEventListener("click", () => {
      if (!isDisabled({ element: confirmButton })) {
        onConfirm();
      }
    });
    safeButton.addEventListener("click", () => {
      if (!isDisabled({ element: safeButton })) {
        onSafe();
      }
    });
    const buttons = makeElement({
      tag: "div",
      className: "flow-builder-actions",
    });
    buttons.append(confirmButton, safeButton);
    element.append(
      makeElement({
        tag: "h4",
        text: title,
        attrs: { id: confirmTitleId },
      }),
      makeElement({ tag: "p", text, attrs: { id: confirmBodyId } }),
      buttons,
    );
    pendingConfirm = {
      kind,
      element,
      safeButton,
      confirmButton,
      resolve,
      onSafe,
    };
    formElement?.setAttribute("inert", "");
    body.append(element);
    syncRetryDisabled();
    safeButton.focus();
  }

  function flowDisplayName(): string {
    return mode === "edit" && storedName !== ""
      ? storedName
      : strings().METRICS_FLOW_BUILDER_TITLE_NEW;
  }

  /**
   * Resolves `true` when the draft may be thrown away. Clean drafts pass at once; a
   * Save or Delete in flight, or an already open confirm, denies without a prompt.
   * The caller owns focus afterwards.
   */
  function confirmDiscard(): Promise<boolean> {
    if (!isDirty()) {
      return Promise.resolve(!(saving || deleting));
    }
    if (saving || deleting || pendingConfirm !== null) {
      return Promise.resolve(false);
    }
    return new Promise<boolean>((resolve) => {
      const settle = ({ discard }: { discard: boolean }) => {
        closeConfirm();
        resolve(discard);
      };
      openConfirm({
        kind: "discard",
        title: fillTemplate({
          template: strings().METRICS_FLOW_BUILDER_DISCARD_TITLE,
          values: { name: flowDisplayName() },
        }),
        text: strings().METRICS_FLOW_BUILDER_DISCARD_BODY,
        confirmText: strings().METRICS_FLOW_BUILDER_DISCARD_CONFIRM,
        safeText: strings().METRICS_FLOW_BUILDER_DISCARD_KEEP,
        onConfirm: () => settle({ discard: true }),
        onSafe: () => settle({ discard: false }),
        resolve,
      });
    });
  }

  function focusPendingConfirm(): boolean {
    if (pendingConfirm === null) {
      return false;
    }
    pendingConfirm.safeButton.focus();
    return true;
  }

  // ---------------------------------------------------------------------
  // Delete
  // ---------------------------------------------------------------------

  function handleDeleteClick(): void {
    if (
      mode !== "edit" ||
      draft.flowId === null ||
      saving ||
      deleting ||
      pendingConfirm !== null
    ) {
      return;
    }
    openConfirm({
      kind: "delete",
      title: fillTemplate({
        template: strings().METRICS_FLOW_BUILDER_DELETE_TITLE,
        values: { name: storedName },
      }),
      text: isDirty()
        ? strings().METRICS_FLOW_BUILDER_DELETE_BODY
        : strings().METRICS_FLOW_BUILDER_DELETE_BODY_CLEAN,
      confirmText: strings().METRICS_FLOW_DELETE_CONFIRM,
      safeText: strings().METRICS_FLOW_DELETE_CANCEL,
      onConfirm: startDelete,
      onSafe: () => {
        closeConfirm();
        deleteButton?.focus();
      },
      resolve: null,
    });
  }

  function startDelete(): void {
    const flowId = draft.flowId;
    const confirm = pendingConfirm;
    if (flowId === null || deleting || confirm === null) {
      return;
    }
    deleting = true;
    refreshBusy();
    freezePreview();
    confirm.confirmButton.textContent = strings().METRICS_FLOW_DELETING;
    confirm.confirmButton.setAttribute("aria-disabled", "true");
    confirm.safeButton.setAttribute("aria-disabled", "true");
    const request = deleteMetricFlow({ flowId });
    deleteXhr = request;
    request.done(() => {
      if (deleteXhr !== request) {
        return;
      }
      deleteXhr = null;
      deleting = false;
      closeConfirm();
      refreshBusy();
      callbacks.onDeleted({ id: flowId, name: storedName });
    });
    request.fail(() => {
      if (deleteXhr !== request) {
        return;
      }
      deleteXhr = null;
      deleting = false;
      closeConfirm();
      refreshBusy();
      deleteButton?.focus();
      handleDeleteFailure({ request });
      syncRetryDisabled();
      schedulePreview();
    });
  }

  function handleDeleteFailure({ request }: { request: JQuery.jqXHR }): void {
    if (is429Handled(request)) {
      return;
    }
    if (request.readyState === 0 && request.statusText === "abort") {
      return;
    }
    const errorBody: SaveErrorBody = request.responseJSON ?? {};
    let message = strings().METRICS_FLOW_DELETE_FAILED;
    let stale = false;
    if (request.status === RATE_LIMITED_STATUS) {
      message = strings().METRICS_FLOW_RATE_LIMITED;
    } else if (
      request.status === NOT_FOUND_STATUS &&
      errorBody.errorCode === ERR_TARGET_NOT_FOUND
    ) {
      message = fillTemplate({
        template: strings().METRICS_FLOW_ALREADY_DELETED,
        values: { name: storedName },
      });
      stale = true;
    }
    setFormMessages({ messages: [message] });
    deleteButton?.setAttribute("aria-describedby", formErrorsId);
    if (stale) {
      callbacks.onListStale();
    }
  }

  container.addEventListener("keydown", handleKeydown);

  return {
    open,
    close: teardown,
    isOpen: () => opened,
    refreshPreview: schedulePreview,
    isDirty,
    confirmDiscard,
    focusPendingConfirm,
  };
}
