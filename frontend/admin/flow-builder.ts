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
  addStep,
  applyServerErrors,
  applyValidationErrors,
  clearDraftError,
  createBlankDraft,
  draftFromEntry,
  isDraftDirty,
  isStaleEndpoint,
  isStaleEvent,
  isStaleMethod,
  isStream,
  listEndpointGroups,
  listEventOptions,
  listFormErrors,
  listMethods,
  listProblems,
  moveStep,
  normalizeDraft,
  removeStep,
  setDisplayName,
  setFormErrors,
  setStepEndpoint,
  setStepEvent,
  setStepLabel,
  setStepMethod,
  setStepStream,
  STREAMS,
  summarizeHidden,
  toRequestBody,
  validateDraft,
} from "./flow-builder-state.js";
import type {
  DraftProblem,
  DraftStep,
  FlowDraft,
  StepStream,
} from "./flow-builder-state.js";
import {
  createMetricFlow,
  deleteMetricFlow,
  fetchMetricFlowCatalog,
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
}

export interface FlowBuilder {
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

function makeElement<Tag extends keyof HTMLElementTagNameMap>({
  tag,
  className,
  text,
  attrs,
}: {
  tag: Tag;
  className?: string;
  text?: string;
  attrs?: Record<string, string>;
}): HTMLElementTagNameMap[Tag] {
  const element = document.createElement(tag);
  if (className) {
    element.className = className;
  }
  if (text !== undefined) {
    element.textContent = text;
  }
  for (const [name, value] of Object.entries(attrs ?? {})) {
    element.setAttribute(name, value);
  }
  return element;
}

function makeOption({
  value,
  text,
  selected = false,
}: {
  value: string;
  text: string;
  selected?: boolean;
}): HTMLOptionElement {
  const option = makeElement({ tag: "option", text, attrs: { value } });
  option.selected = selected;
  return option;
}

function isDisabled({ element }: { element: Element }): boolean {
  return element.getAttribute("aria-disabled") === "true";
}

function setDisabled({
  element,
  disabled,
  reasonId,
}: {
  element: HTMLElement;
  disabled: boolean;
  reasonId: string;
}): void {
  if (disabled) {
    element.setAttribute("aria-disabled", "true");
    element.setAttribute("aria-describedby", reasonId);
  } else {
    element.removeAttribute("aria-disabled");
    element.removeAttribute("aria-describedby");
  }
}

/**
 * Creates the builder inside `container` (kept hidden until `open`).
 * Example: `createFlowBuilder({ container, callbacks }).open({ mode: "create" })`.
 */
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

  const strings = () => APP_CONFIG.strings;
  const constants = () => APP_CONFIG.constants;

  // ---------------------------------------------------------------------
  // Open, close, catalog
  // ---------------------------------------------------------------------

  function teardown(): void {
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

  function problemText({ problem }: { problem: DraftProblem }): string {
    const base =
      problem.stepNumber === null
        ? problem.message
        : fillTemplate({
            template: strings().METRICS_FLOW_BUILDER_ERR_STEP_LINE,
            values: {
              step: String(problem.stepNumber),
              message: problem.message,
            },
          });
    return problem.field === "hidden"
      ? `${base} ${strings().METRICS_FLOW_BUILDER_NOTE_FILTERS_UNEDITABLE}`
      : base;
  }

  /**
   * Redraws the summary from the draft's errors in place. Lines are plain text until
   * the catalog has loaded (no field exists to focus yet); hidden-field lines never
   * get a button because the form cannot edit them.
   */
  function renderSummary(): void {
    if (summary === null || heading === null) {
      return;
    }
    const problems = listProblems({ draft });
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
      if (catalog === null || problem.field === "hidden") {
        item.textContent = text;
      } else {
        const link = makeElement({
          tag: "button",
          className: "flow-builder-link",
          text,
          attrs: { type: "button", "data-problem-field": problem.field },
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
    const hadProblems = listProblems({ draft }).length > 0;
    const errors = validateDraft({ draft });
    draft = applyValidationErrors({ draft, errors });
    // Rows are rebuilt only when something shown changes, so a valid Save keeps focus.
    if (errors.length > 0 || hadProblems) {
      renderAllErrors();
    }
    if (errors.length > 0) {
      summary?.focus();
      return;
    }
    const submittedKeys = draft.steps.map((step) => step.key);
    const definition = toRequestBody({ draft });
    const flowId = draft.flowId;
    const request =
      mode === "edit" && flowId !== null
        ? updateMetricFlow({ flowId, definition })
        : createMetricFlow({ definition });
    saveXhr = request;
    setSaving({ value: true });
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
      handleSaveFailure({ request, submittedKeys });
    });
  }

  function handleSaveFailure({
    request,
    submittedKeys,
  }: {
    request: JQuery.jqXHR;
    submittedKeys: readonly number[];
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
      draft = applyServerErrors({ draft, errors, submittedKeys });
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
      if (listProblems({ draft }).length > 0) {
        summary?.focus();
      }
    } else {
      setFormMessages({
        messages: [strings().METRICS_FLOW_BUILDER_ERR_SAVE_FAILED],
      });
    }
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
    body.replaceChildren(form);
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
    row.append(head, grid, ...renderNotes({ step }));
    return row;
  }

  function keptNoteText({ step }: { step: DraftStep }): string | null {
    const { filterCount, hasBreakdown } = summarizeHidden({ step });
    const count = String(filterCount);
    if (filterCount > 0 && hasBreakdown) {
      return filterCount === 1
        ? strings().METRICS_FLOW_BUILDER_NOTE_KEPT_FILTERS_BREAKDOWN_ONE
        : fillTemplate({
            template:
              strings().METRICS_FLOW_BUILDER_NOTE_KEPT_FILTERS_BREAKDOWN,
            values: { count },
          });
    }
    if (filterCount > 0) {
      return filterCount === 1
        ? strings().METRICS_FLOW_BUILDER_NOTE_KEPT_FILTERS_ONE
        : fillTemplate({
            template: strings().METRICS_FLOW_BUILDER_NOTE_KEPT_FILTERS,
            values: { count },
          });
    }
    return hasBreakdown
      ? strings().METRICS_FLOW_BUILDER_NOTE_KEPT_BREAKDOWN
      : null;
  }

  /**
   * Row notes for fields the form cannot edit: the "removed" note after a clear, the
   * kept note while filters or a breakdown ride along, and the server's reason for
   * a rejected one.
   */
  function renderNotes({ step }: { step: DraftStep }): HTMLElement[] {
    const notes: HTMLElement[] = [];
    const reasons = step.errors.hidden ?? [];
    const reasonId = `${uid}-${step.key}-hidden-error`;
    if (step.hiddenCleared) {
      notes.push(
        makeElement({
          tag: "p",
          className: "flow-builder-note",
          text: strings().METRICS_FLOW_BUILDER_NOTE_FILTERS_CLEARED,
        }),
      );
    }
    const kept = keptNoteText({ step });
    if (kept !== null) {
      const note = makeElement({
        tag: "p",
        className: "flow-builder-note",
        text: kept,
      });
      if (reasons.length > 0) {
        note.setAttribute("aria-describedby", reasonId);
      }
      notes.push(note);
    }
    if (reasons.length > 0) {
      notes.push(
        makeElement({
          tag: "p",
          className: "flow-builder-error",
          text: reasons.join(" "),
          attrs: { id: reasonId },
        }),
      );
    }
    return notes;
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
    const cell = makeElement({
      tag: "div",
      className: "flow-builder-cell",
      attrs: { "data-cell": field },
    });
    cell.append(control);
    const messages = step.errors[field] ?? [];
    if (messages.length > 0) {
      const errorId = `${uid}-${step.key}-${field}-error`;
      control.setAttribute("aria-invalid", "true");
      control.setAttribute("aria-describedby", errorId);
      cell.append(
        makeElement({
          tag: "p",
          className: "flow-builder-error",
          text: messages.join(" "),
          attrs: { id: errorId },
        }),
      );
    }
    return cell;
  }

  function makeSelect({
    field,
    key,
    label,
  }: {
    field: string;
    key: number;
    label: string;
  }): HTMLSelectElement {
    return makeElement({
      tag: "select",
      className: "flow-builder-select",
      attrs: {
        "data-field": field,
        "data-step-key": String(key),
        "aria-label": label,
      },
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

  /** Keeps a no-longer-valid stored value selected and flags the select. */
  function appendStaleOption({
    select,
    value,
  }: {
    select: HTMLSelectElement;
    value: string;
  }): void {
    select.append(
      makeOption({
        value,
        text: fillTemplate({
          template: strings().METRICS_FLOW_BUILDER_NOTE_STALE_VALUE,
          values: { value },
        }),
        selected: true,
      }),
    );
    select.setAttribute("aria-invalid", "true");
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

  /** Announces politely when this edit just removed a step's hidden filters. */
  function announceIfCleared({
    key,
    wasCleared,
  }: {
    key: number;
    wasCleared: boolean;
  }): void {
    const step = draft.steps.find((item) => item.key === key);
    if (step !== undefined && step.hiddenCleared && !wasCleared) {
      callbacks.announce({
        message: strings().METRICS_FLOW_BUILDER_NOTE_FILTERS_CLEARED,
      });
    }
  }

  function wasHiddenCleared({ key }: { key: number }): boolean {
    return draft.steps.find((item) => item.key === key)?.hiddenCleared ?? false;
  }

  // ---------------------------------------------------------------------
  // Event handlers
  // ---------------------------------------------------------------------

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
      return;
    }
    const key = stepKeyOf({ target });
    if (target.dataset.field === "label" && key !== null) {
      draft = setStepLabel({ draft, key, value: target.value });
      clearFieldError({ key, field: "label" });
    }
  }

  function handleChange(event: Event): void {
    const target = event.target;
    if (!(target instanceof HTMLSelectElement)) {
      return;
    }
    const key = stepKeyOf({ target });
    const field = target.dataset.field;
    if (key === null || field === undefined) {
      return;
    }
    stopDescribingHeading();
    const wasCleared = wasHiddenCleared({ key });
    if (field === "stream" && isStream(target.value)) {
      draft = setStepStream({ draft, key, stream: target.value });
      for (const name of [
        "stream",
        "event_name",
        "api_endpoint",
        "api_method",
        "hidden",
      ]) {
        clearFieldError({ key, field: name });
      }
      replaceRow({ key });
      focusField({ key, field });
    } else if (field === "event_name") {
      draft = setStepEvent({ draft, key, eventName: target.value });
      clearFieldError({ key, field });
      clearHiddenErrorIfCleared({ key });
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
      clearHiddenErrorIfCleared({ key });
      replaceRow({ key });
      focusField({ key, field });
    } else if (field === "api_method") {
      draft = setStepMethod({ draft, key, apiMethod: target.value });
      clearFieldError({ key, field });
      replaceRow({ key });
      focusField({ key, field });
    }
    announceIfCleared({ key, wasCleared });
  }

  /** A rejected filter or breakdown is gone once the edit removed it. */
  function clearHiddenErrorIfCleared({ key }: { key: number }): void {
    if (wasHiddenCleared({ key })) {
      clearFieldError({ key, field: "hidden" });
    }
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

  function handleClick(event: MouseEvent): void {
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
    isDirty,
    confirmDiscard,
    focusPendingConfirm,
  };
}
