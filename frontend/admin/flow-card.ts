/**
 * Render one assembled funnel (a `/api/metrics/query/flow` response) as a
 * `.flow-card`. The card is built generically by looping over the response's
 * step list — N `.funnel-step` rows plus N-1 `.funnel-connector` blocks — so a
 * flow with any number of steps (2..N) renders without code changes.
 *
 * Per-step `breakdown` rows become `.cause-pill` chips inside the connector
 * that precedes the step. Following DD-6 graceful-degrade: when a step's
 * `breakdown` is null, only the aggregate connector summary renders and the
 * per-cause pill block is skipped.
 *
 * Pure DOM mutation; no fetching, no event binding.
 */

import type { Schema } from "../types/api-helpers.d.ts";

import { APP_CONFIG } from "../lib/config.js";
import { fillTemplate } from "../lib/string-template.js";

type FlowResponseSchema = Schema<"FlowResponseSchema">;
type FlowStepSchema = Schema<"FlowStepSchema">;
type FlowBreakdownRow = Schema<"FlowBreakdownRow">;
type FlowStream = FlowStepSchema["stream"];

// The `invalid` object of a `flow_invalid` 422 body.
export type FlowInvalidDetail = Schema<"FlowInvalidDetailSchema">;

export type FlowCardState =
  | { kind: "response"; response: FlowResponseSchema }
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "invalid"; invalid: FlowInvalidDetail }
  | { kind: "removed" };

// Per-card state of a custom flow's Delete / in-place confirm group.
export interface FlowCardCustom {
  confirm: "closed" | "open" | "deleting";
  // Inline per-card error (delete failure, rate limit), or null.
  message: string | null;
  // True while another card is being deleted: Delete is aria-disabled.
  deleteLocked: boolean;
}

export interface FlowGridEntry {
  id: string;
  title: string;
  state: FlowCardState;
  // Absent for built-in flows (no Delete); present for custom flows.
  custom?: FlowCardCustom;
}

const NULL_PCT_PLACEHOLDER = "–";
// Reject-causes carry the "reject" pill tint; everything else (cancels) the
// "cancel" tint. The renderer only sees the breakdown event indirectly via the
// step's stream, so the connector that PRECEDES a domain step is a rejection,
// while a connector preceding a ui/api step is a cancel.
const DOMAIN_STREAM: FlowStream = "domain";

function streamLabel({ stream }: { stream: FlowStream }): string {
  if (stream === "ui") {
    return APP_CONFIG.strings.METRICS_FLOW_CATEGORY_UI;
  }
  if (stream === "api") {
    return APP_CONFIG.strings.METRICS_FLOW_CATEGORY_API;
  }
  return APP_CONFIG.strings.METRICS_FLOW_CATEGORY_DOMAIN;
}

function formatPercent({ fraction }: { fraction: number | null }): string {
  if (fraction === null) {
    return NULL_PCT_PLACEHOLDER;
  }
  return `${Math.round(fraction * 100)}%`;
}

// Render the suppressed-count en-dash on `element` as an announced image: a
// bare aria-label on a generic span is not reliably read out, and `title`
// explains it to sighted hover users.
function applySuppressedDash({ element }: { element: HTMLElement }): void {
  element.textContent = NULL_PCT_PLACEHOLDER;
  element.setAttribute("role", "img");
  element.setAttribute(
    "aria-label",
    APP_CONFIG.strings.METRICS_FLOW_COUNT_SUPPRESSED_ARIA,
  );
  element.title = APP_CONFIG.strings.METRICS_FLOW_COUNT_SUPPRESSED_ARIA;
}

function buildSummaryCount({ step }: { step: FlowStepSchema }): Node {
  if (!step.count_suppressed) {
    return document.createTextNode(step.count.toLocaleString());
  }
  const dash = document.createElement("span");
  applySuppressedDash({ element: dash });
  return dash;
}

function ariaCount({ step }: { step: FlowStepSchema }): string {
  return step.count_suppressed
    ? APP_CONFIG.strings.METRICS_FLOW_COUNT_SUPPRESSED_ARIA
    : step.count.toLocaleString();
}

function buildEmptyState(): HTMLParagraphElement {
  const empty = document.createElement("p");
  empty.className = "flow-card-empty";
  empty.tabIndex = 0;
  empty.textContent = APP_CONFIG.strings.METRICS_FLOW_EMPTY;
  return empty;
}

function buildStepRow({ step }: { step: FlowStepSchema }): HTMLDivElement {
  const row = document.createElement("div");
  row.className = `funnel-step ${step.stream}`;
  // Proportional bar width via the `--w` custom property. `pct_of_top` is
  // nullable (null when the funnel top count is zero); fall back to full width
  // so a zero-data row still occupies the column rather than collapsing.
  const widthPct = step.pct_of_top === null ? 100 : step.pct_of_top * 100;
  row.style.setProperty("--w", `${widthPct}%`);

  const kind = document.createElement("span");
  kind.className = "step-kind";
  kind.textContent = streamLabel({ stream: step.stream });

  const labels = document.createElement("div");
  labels.className = "step-labels";
  const labelText = document.createElement("span");
  labelText.className = "step-label";
  labelText.textContent = step.label;
  const eventName = document.createElement("span");
  eventName.className = "step-event";
  eventName.textContent = step.event_name;
  // The visible event text is CSS-clipped; expose the full value to screen
  // readers (title alone is not announced on non-interactive elements).
  eventName.setAttribute("aria-label", step.event_name);
  eventName.title = step.event_name;
  labels.appendChild(labelText);
  labels.appendChild(eventName);

  const count = document.createElement("span");
  count.className = "step-count";
  if (step.count_suppressed) {
    row.classList.add("is-suppressed");
    applySuppressedDash({ element: count });
  } else {
    count.textContent = step.count.toLocaleString();
  }

  const pct = document.createElement("span");
  pct.className = "step-pct";
  pct.textContent = formatPercent({ fraction: step.pct_of_top });

  row.appendChild(kind);
  row.appendChild(labels);
  row.appendChild(count);
  row.appendChild(pct);
  return row;
}

function buildCausePill({
  row,
  isReject,
}: {
  row: FlowBreakdownRow;
  isReject: boolean;
}): HTMLDivElement {
  const pill = document.createElement("div");
  pill.className = `cause-pill ${isReject ? "reject" : "cancel"}`;
  // `pct_of_step` is always a float (never null) — write `--w` unconditionally.
  pill.style.setProperty("--w", `${row.pct_of_step * 100}%`);

  const isSuppressed = row.label === APP_CONFIG.constants.SUPPRESSED_DIM_VALUE;
  const displayLabel = isSuppressed
    ? APP_CONFIG.strings.METRICS_SUPPRESSED_LABEL
    : row.label;
  if (isSuppressed) {
    pill.classList.add("is-suppressed");
  }

  const label = document.createElement("span");
  label.className = "cause-label";
  label.textContent = displayLabel;

  const causeCount = document.createElement("span");
  causeCount.className = "cause-count";
  causeCount.textContent = row.count.toLocaleString();

  pill.appendChild(label);
  pill.appendChild(causeCount);
  pill.setAttribute("aria-label", `${displayLabel}: ${row.count}`);
  return pill;
}

function buildConnector({
  previousStep,
  step,
}: {
  previousStep: FlowStepSchema;
  step: FlowStepSchema;
}): HTMLDivElement {
  const connector = document.createElement("div");
  connector.className = "funnel-connector";

  const arrowRow = document.createElement("div");
  arrowRow.className = "arrow-row";
  const arrow = document.createElement("span");
  arrow.className = "arrow";
  arrow.setAttribute("aria-hidden", "true");
  arrow.textContent = "↓";
  // Number of users that dropped off between the previous step and this step.
  // Never computed from a floored `0`: a suppressed neighbor hides the number.
  const eitherSuppressed =
    previousStep.count_suppressed || step.count_suppressed;
  const dropoff = Math.max(previousStep.count - step.count, 0);
  const dropoffText = document.createElement("span");
  dropoffText.className = "arrow-dropoff";
  dropoffText.textContent = eitherSuppressed
    ? NULL_PCT_PLACEHOLDER
    : `${dropoff.toLocaleString()} ${APP_CONFIG.strings.METRICS_FLOW_DROPOFF}`;
  arrowRow.appendChild(arrow);
  arrowRow.appendChild(dropoffText);
  // Announce the drop-off count even when no per-cause breakdown exists.
  connector.setAttribute(
    "aria-label",
    eitherSuppressed
      ? APP_CONFIG.strings.METRICS_FLOW_COUNT_SUPPRESSED_ARIA
      : `${dropoff.toLocaleString()} ${APP_CONFIG.strings.METRICS_FLOW_DROPOFF}`,
  );
  connector.appendChild(arrowRow);

  // DD-6 graceful-degrade: only render the per-cause pill block when the
  // breakdown has rows; otherwise the connector shows the aggregate arrow only.
  if (step.breakdown !== null && step.breakdown.length > 0) {
    const causes = document.createElement("div");
    causes.className = "causes";
    const isReject = step.stream === DOMAIN_STREAM;
    for (const breakdownRow of step.breakdown) {
      causes.appendChild(buildCausePill({ row: breakdownRow, isReject }));
    }
    connector.appendChild(causes);
  }

  return connector;
}

export function renderFlowCard({
  id,
  title,
  response,
}: {
  id: string;
  title: string;
  response: FlowResponseSchema;
}): HTMLElement {
  const card = document.createElement("section");
  card.className = "flow-card";
  // Stable identity so `renderFlowGrid` can reconcile per-flow (replace one
  // card in place) instead of tearing down and rebuilding the whole grid each
  // time one of the flow XHRs settles.
  card.dataset.flowId = id;

  const steps = response.steps;
  const allZero = steps.every(
    (step) => step.count === 0 && !step.count_suppressed,
  );

  const topStep = steps[0];
  const lastStep = steps[steps.length - 1];
  const conversionPct = formatPercent({ fraction: lastStep.pct_of_top });

  const header = document.createElement("div");
  header.className = "flow-header";
  const titleElement = document.createElement("h3");
  titleElement.className = "flow-title";
  titleElement.textContent = title;
  const summary = document.createElement("span");
  summary.className = "flow-summary";
  summary.append(
    buildSummaryCount({ step: lastStep }),
    " / ",
    buildSummaryCount({ step: topStep }),
    ` ${APP_CONFIG.strings.METRICS_FLOW_SUCCEEDED} · ${conversionPct} ${APP_CONFIG.strings.METRICS_FLOW_CONVERSION}`,
  );
  header.appendChild(titleElement);
  header.appendChild(summary);
  card.appendChild(header);

  // Screen-reader summary of the whole card, e.g.
  // "Create UTub: 638 of 812 succeeded, 79% conversion".
  card.setAttribute(
    "aria-label",
    `${title}: ${ariaCount({ step: lastStep })} of ${ariaCount({ step: topStep })} ${APP_CONFIG.strings.METRICS_FLOW_SUCCEEDED}, ${conversionPct} ${APP_CONFIG.strings.METRICS_FLOW_CONVERSION}`,
  );

  if (allZero) {
    card.appendChild(buildEmptyState());
    return card;
  }

  const funnel = document.createElement("div");
  funnel.className = "funnel";
  steps.forEach((step, index) => {
    if (index > 0) {
      funnel.appendChild(
        buildConnector({ previousStep: steps[index - 1], step }),
      );
    }
    funnel.appendChild(buildStepRow({ step }));
  });
  card.appendChild(funnel);

  return card;
}

// Remembers the state last rendered for each flow id, per grid container, so
// `renderFlowGrid` can leave an unchanged node alone (a held element reference
// must not go stale when an unrelated flow settles). WeakMap-keyed by the
// container so a detached/replaced grid element does not leak state.
const lastRenderedStates: WeakMap<
  HTMLElement,
  Map<string, FlowGridEntry>
> = new WeakMap();

const SVG_NS = "http://www.w3.org/2000/svg";
const SKELETON_BAR_COUNT = 3;
const TRASH_OUTER_PATH = "M0 0h24v24H0V0z";
const TRASH_INNER_PATH =
  "M16 9v10H8V9h8m-1.5-6h-5l-1 1H5v2h14V4h-3.5l-1-1zM18 7H6v12c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7z";

function buildTrashIcon(): SVGSVGElement {
  const svg = document.createElementNS(SVG_NS, "svg");
  svg.setAttribute("class", "bi bi-trash");
  svg.setAttribute("aria-hidden", "true");
  svg.setAttribute("width", "28px");
  svg.setAttribute("height", "28px");
  svg.setAttribute("fill", "currentColor");
  svg.setAttribute("viewBox", "0 0 24 24");
  const outer = document.createElementNS(SVG_NS, "path");
  outer.setAttribute("fill", "none");
  outer.setAttribute("d", TRASH_OUTER_PATH);
  const inner = document.createElementNS(SVG_NS, "path");
  inner.setAttribute("d", TRASH_INNER_PATH);
  svg.appendChild(outer);
  svg.appendChild(inner);
  return svg;
}

function buildBadge({ isCustom }: { isCustom: boolean }): HTMLSpanElement {
  const badge = document.createElement("span");
  badge.className = isCustom ? "flow-badge custom" : "flow-badge";
  badge.textContent = isCustom
    ? APP_CONFIG.strings.METRICS_FLOW_BADGE_CUSTOM
    : APP_CONFIG.strings.METRICS_FLOW_BADGE_BUILTIN;
  return badge;
}

function buildButton({
  className,
  dataAttribute,
  text,
}: {
  className: string;
  dataAttribute: string;
  text?: string;
}): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = className;
  button.setAttribute(dataAttribute, "");
  if (text !== undefined) {
    button.textContent = text;
  }
  return button;
}

// Delete button (closed) or the in-place confirm group (open / deleting).
function buildActions({
  id,
  title,
  custom,
}: {
  id: string;
  title: string;
  custom: FlowCardCustom;
}): HTMLDivElement {
  const actions = document.createElement("div");
  actions.className = "flow-actions";

  if (custom.confirm === "closed") {
    const deleteButton = buildButton({
      className: "flow-delete-btn",
      dataAttribute: "data-flow-delete",
    });
    deleteButton.setAttribute(
      "aria-label",
      fillTemplate({
        template: APP_CONFIG.strings.METRICS_FLOW_DELETE_LABEL,
        values: { name: title },
      }),
    );
    deleteButton.appendChild(buildTrashIcon());
    actions.appendChild(deleteButton);
    if (custom.deleteLocked) {
      const lockedId = `FlowDeleteLocked-${id}`;
      deleteButton.setAttribute("aria-disabled", "true");
      deleteButton.setAttribute("aria-describedby", lockedId);
      const lockedHint = document.createElement("span");
      lockedHint.id = lockedId;
      lockedHint.className = "visually-hidden";
      lockedHint.textContent = APP_CONFIG.strings.METRICS_FLOW_DELETE_LOCKED;
      actions.appendChild(lockedHint);
    }
    return actions;
  }

  const isDeleting = custom.confirm === "deleting";
  const promptId = `FlowConfirmPrompt-${id}`;
  const group = document.createElement("div");
  group.className = "flow-confirm";
  group.setAttribute("role", "group");
  group.setAttribute("data-flow-confirm", "");
  group.setAttribute("aria-labelledby", promptId);

  const prompt = document.createElement("span");
  prompt.id = promptId;
  prompt.className = "flow-confirm-prompt";
  prompt.textContent = fillTemplate({
    template: APP_CONFIG.strings.METRICS_FLOW_DELETE_PROMPT,
    values: { name: title },
  });
  const confirmButton = buildButton({
    className: "flow-confirm-btn",
    dataAttribute: "data-flow-confirm-delete",
    text: isDeleting
      ? APP_CONFIG.strings.METRICS_FLOW_DELETING
      : APP_CONFIG.strings.METRICS_FLOW_DELETE_CONFIRM,
  });
  const cancelButton = buildButton({
    className: "flow-cancel-btn",
    dataAttribute: "data-flow-confirm-cancel",
    text: APP_CONFIG.strings.METRICS_FLOW_DELETE_CANCEL,
  });
  if (isDeleting) {
    // aria-disabled (not disabled) so focus stays on the pressed button.
    confirmButton.setAttribute("aria-disabled", "true");
    cancelButton.setAttribute("aria-disabled", "true");
  }
  group.appendChild(prompt);
  group.appendChild(confirmButton);
  group.appendChild(cancelButton);
  actions.appendChild(group);
  return actions;
}

function buildCardShell({
  id,
  kind,
}: {
  id: string;
  kind: FlowCardState["kind"];
}): HTMLElement {
  const card = document.createElement("section");
  card.className = "flow-card";
  card.dataset.flowId = id;
  card.dataset.flowState = kind;
  // Programmatic focus target (per-card Retry); never in the tab order.
  card.tabIndex = -1;
  return card;
}

function buildCardHeader({
  title,
  custom,
}: {
  title: string;
  custom?: FlowCardCustom;
}): HTMLDivElement {
  const header = document.createElement("div");
  header.className = "flow-header";
  const titleElement = document.createElement("h3");
  titleElement.className = "flow-title";
  titleElement.appendChild(buildBadge({ isCustom: custom !== undefined }));
  titleElement.appendChild(document.createTextNode(" "));
  titleElement.appendChild(document.createTextNode(title));
  header.appendChild(titleElement);
  return header;
}

function buildCardMessage({
  custom,
}: {
  custom?: FlowCardCustom;
}): HTMLSpanElement | null {
  if (custom === undefined || custom.message === null) {
    return null;
  }
  const message = document.createElement("span");
  message.className = "flow-card-message";
  message.textContent = custom.message;
  return message;
}

// Shared top of the loading / error / invalid cards: header (with the custom
// actions) followed by the optional inline message.
function appendCardTop({
  card,
  entry,
}: {
  card: HTMLElement;
  entry: FlowGridEntry;
}): void {
  const header = buildCardHeader({ title: entry.title, custom: entry.custom });
  if (entry.custom !== undefined) {
    header.appendChild(
      buildActions({ id: entry.id, title: entry.title, custom: entry.custom }),
    );
  }
  card.appendChild(header);
  const message = buildCardMessage({ custom: entry.custom });
  if (message !== null) {
    card.appendChild(message);
  }
}

function buildLoadingCard({ entry }: { entry: FlowGridEntry }): HTMLElement {
  const card = buildCardShell({ id: entry.id, kind: "loading" });
  card.setAttribute(
    "aria-label",
    fillTemplate({
      template: APP_CONFIG.strings.METRICS_FLOW_LOADING_LABEL,
      values: { title: entry.title },
    }),
  );
  appendCardTop({ card, entry });
  const skeleton = document.createElement("div");
  skeleton.className = "flow-skeleton";
  skeleton.setAttribute("aria-hidden", "true");
  for (let bar = 0; bar < SKELETON_BAR_COUNT; bar++) {
    const barElement = document.createElement("div");
    barElement.className = "flow-skeleton-bar";
    skeleton.appendChild(barElement);
  }
  card.appendChild(skeleton);
  return card;
}

function buildErrorCard({ entry }: { entry: FlowGridEntry }): HTMLElement {
  const card = buildCardShell({ id: entry.id, kind: "error" });
  card.setAttribute(
    "aria-label",
    `${entry.title}: ${APP_CONFIG.strings.METRICS_FLOW_LOAD_FAILED}`,
  );
  appendCardTop({ card, entry });
  const error = document.createElement("p");
  error.className = "flow-error";
  const errorText = document.createElement("span");
  errorText.textContent = APP_CONFIG.strings.METRICS_FLOW_LOAD_FAILED;
  error.appendChild(errorText);
  error.appendChild(
    buildButton({
      className: "flow-retry-btn",
      dataAttribute: "data-flow-retry",
      text: APP_CONFIG.strings.METRICS_FLOW_RETRY,
    }),
  );
  card.appendChild(error);
  return card;
}

function buildInvalidCard({
  entry,
  invalid,
}: {
  entry: FlowGridEntry;
  invalid: FlowInvalidDetail;
}): HTMLElement {
  const card = buildCardShell({ id: entry.id, kind: "invalid" });
  const stepText =
    invalid.step_index === null
      ? invalid.reason
      : fillTemplate({
          template: APP_CONFIG.strings.METRICS_FLOW_NEEDS_ATTENTION_STEP,
          values: {
            step: String(invalid.step_index + 1),
            reason: invalid.reason,
          },
        });
  const labelTitle =
    entry.custom === undefined
      ? entry.title
      : `${entry.title} ${APP_CONFIG.strings.METRICS_FLOW_CUSTOM_SUFFIX}`;
  card.setAttribute(
    "aria-label",
    `${labelTitle}: ${APP_CONFIG.strings.METRICS_FLOW_NEEDS_ATTENTION} ${stepText}`,
  );
  appendCardTop({ card, entry });

  const attention = document.createElement("p");
  attention.className = "flow-attention";
  const label = document.createElement("strong");
  label.textContent = APP_CONFIG.strings.METRICS_FLOW_NEEDS_ATTENTION;
  attention.appendChild(label);
  attention.appendChild(document.createTextNode(` ${stepText} `));
  attention.appendChild(
    document.createTextNode(
      APP_CONFIG.strings.METRICS_FLOW_NEEDS_ATTENTION_HELP,
    ),
  );
  card.appendChild(attention);
  return card;
}

// Wraps the existing response card with the grid-level extras: Built-in /
// Custom badge, custom actions, message, custom aria-label suffix, tabindex.
function buildResponseCard({
  entry,
  response,
}: {
  entry: FlowGridEntry;
  response: FlowResponseSchema;
}): HTMLElement {
  const card = renderFlowCard({
    id: entry.id,
    title: entry.title,
    response,
  });
  card.dataset.flowState = "response";
  card.tabIndex = -1;

  const titleElement = card.querySelector(".flow-title");
  titleElement?.prepend(
    buildBadge({ isCustom: entry.custom !== undefined }),
    " ",
  );

  if (entry.custom !== undefined) {
    const prefix = `${entry.title}:`;
    const label = card.getAttribute("aria-label") ?? "";
    if (label.startsWith(prefix)) {
      card.setAttribute(
        "aria-label",
        `${entry.title} ${APP_CONFIG.strings.METRICS_FLOW_CUSTOM_SUFFIX}:${label.slice(prefix.length)}`,
      );
    }
    const header = card.querySelector(".flow-header");
    header?.appendChild(
      buildActions({
        id: entry.id,
        title: entry.title,
        custom: entry.custom,
      }),
    );
    const message = buildCardMessage({ custom: entry.custom });
    if (header !== null && message !== null) {
      header.after(message);
    }
  }
  return card;
}

function isSameCustom({
  previous,
  next,
}: {
  previous: FlowCardCustom | undefined;
  next: FlowCardCustom | undefined;
}): boolean {
  if (previous === undefined || next === undefined) {
    return previous === next;
  }
  return (
    previous.confirm === next.confirm &&
    previous.message === next.message &&
    previous.deleteLocked === next.deleteLocked
  );
}

// Reconcile rule: title and custom by value, then the state (see isSameState).
function isSameEntry({
  previous,
  next,
}: {
  previous: FlowGridEntry;
  next: FlowGridEntry;
}): boolean {
  return (
    previous.title === next.title &&
    isSameCustom({ previous: previous.custom, next: next.custom }) &&
    isSameState({ previous: previous.state, next: next.state })
  );
}

// State rule: response by reference; loading/error by kind only; invalid by
// field equality; any kind change is a change.
function isSameState({
  previous,
  next,
}: {
  previous: FlowCardState;
  next: FlowCardState;
}): boolean {
  if (previous.kind !== next.kind) {
    return false;
  }
  if (previous.kind === "response" && next.kind === "response") {
    return previous.response === next.response;
  }
  if (previous.kind === "invalid" && next.kind === "invalid") {
    return (
      previous.invalid.step_index === next.invalid.step_index &&
      previous.invalid.field === next.invalid.field &&
      previous.invalid.reason === next.invalid.reason
    );
  }
  return true;
}

function buildNode({ entry }: { entry: FlowGridEntry }): HTMLElement {
  const { state } = entry;
  if (state.kind === "response") {
    return buildResponseCard({ entry, response: state.response });
  }
  if (state.kind === "loading") {
    return buildLoadingCard({ entry });
  }
  if (state.kind === "error") {
    return buildErrorCard({ entry });
  }
  if (state.kind === "invalid") {
    return buildInvalidCard({ entry, invalid: state.invalid });
  }
  // `removed` entries are skipped by `renderFlowGrid` and never built.
  throw new Error(`Cannot build a flow card for state ${state.kind}`);
}

/**
 * Render the Flows panel grid from an ordered entry list: one node per entry,
 * in `entries` order. Every visible state (`response`, `loading`, `error`,
 * `invalid`) renders a `.flow-card[data-flow-state]`; `removed` entries and
 * ids absent from `entries` have their node removed.
 *
 * Reconciles per id rather than clearing and rebuilding the container: flow
 * XHRs settle independently and each settle re-invokes this function. A node
 * whose state is unchanged (see `isSameState`) is never detached; a changed
 * one is replaced in place.
 */
export function renderFlowGrid({
  container,
  entries,
}: {
  container: HTMLElement;
  entries: readonly FlowGridEntry[];
}): void {
  const previousStates = lastRenderedStates.get(container) ?? new Map();
  const nextStates = new Map<string, FlowGridEntry>();
  // Index existing nodes by id in a Map (no selector, so raw ids are safe).
  const existingNodes = new Map<string, HTMLElement>();
  for (const child of Array.from(container.children)) {
    if (child instanceof HTMLElement && child.dataset.flowId !== undefined) {
      existingNodes.set(child.dataset.flowId, child);
    }
  }

  const desiredNodes: HTMLElement[] = [];
  for (const entry of entries) {
    if (entry.state.kind === "removed" || nextStates.has(entry.id)) {
      continue;
    }
    const existing = existingNodes.get(entry.id);
    const previous = previousStates.get(entry.id);
    let node: HTMLElement;
    if (
      existing !== undefined &&
      previous !== undefined &&
      isSameEntry({ previous, next: entry })
    ) {
      node = existing;
    } else {
      node = buildNode({ entry });
      if (existing !== undefined) {
        container.replaceChild(node, existing);
      }
    }
    nextStates.set(entry.id, entry);
    desiredNodes.push(node);
  }

  const desiredSet = new Set(desiredNodes);
  for (const existing of existingNodes.values()) {
    if (!desiredSet.has(existing) && existing.parentNode === container) {
      container.removeChild(existing);
    }
  }

  // Place nodes in entry order, moving only those out of position.
  let cursor: ChildNode | null = container.firstChild;
  for (const node of desiredNodes) {
    if (node === cursor) {
      cursor = cursor.nextSibling;
    } else {
      container.insertBefore(node, cursor);
    }
  }
  lastRenderedStates.set(container, nextStates);
}
