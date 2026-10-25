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

type FlowResponseSchema = Schema<"FlowResponseSchema">;
type FlowStepSchema = Schema<"FlowStepSchema">;
type FlowBreakdownRow = Schema<"FlowBreakdownRow">;
type FlowStream = FlowStepSchema["stream"];

// Local structural type; replaced by the generated `flow_invalid` type later
// without a signature change.
export interface FlowInvalidDetail {
  step_index: number | null;
  field: string;
  reason: string;
}

export type FlowCardState =
  | { kind: "response"; response: FlowResponseSchema }
  | { kind: "loading" }
  | { kind: "error" }
  | { kind: "invalid"; invalid: FlowInvalidDetail }
  | { kind: "removed" };

export interface FlowGridEntry {
  id: string;
  title: string;
  state: FlowCardState;
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
  count.textContent = step.count.toLocaleString();

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

  const label = document.createElement("span");
  label.className = "cause-label";
  label.textContent = row.label;

  const causeCount = document.createElement("span");
  causeCount.className = "cause-count";
  causeCount.textContent = row.count.toLocaleString();

  pill.appendChild(label);
  pill.appendChild(causeCount);
  pill.setAttribute("aria-label", `${row.label}: ${row.count}`);
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
  const dropoff = Math.max(previousStep.count - step.count, 0);
  const dropoffText = document.createElement("span");
  dropoffText.className = "arrow-dropoff";
  dropoffText.textContent = `${dropoff.toLocaleString()} ${APP_CONFIG.strings.METRICS_FLOW_DROPOFF}`;
  arrowRow.appendChild(arrow);
  arrowRow.appendChild(dropoffText);
  // Announce the drop-off count even when no per-cause breakdown exists.
  connector.setAttribute(
    "aria-label",
    `${dropoff.toLocaleString()} ${APP_CONFIG.strings.METRICS_FLOW_DROPOFF}`,
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
  title: displayName,
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
  const allZero = steps.every((step) => step.count === 0);

  const topStep = steps[0];
  const lastStep = steps[steps.length - 1];
  const conversionPct = formatPercent({ fraction: lastStep.pct_of_top });

  const header = document.createElement("div");
  header.className = "flow-header";
  const title = document.createElement("h3");
  title.className = "flow-title";
  title.textContent = displayName;
  const summary = document.createElement("span");
  summary.className = "flow-summary";
  summary.textContent = `${lastStep.count.toLocaleString()} / ${topStep.count.toLocaleString()} ${APP_CONFIG.strings.METRICS_FLOW_SUCCEEDED} · ${conversionPct} ${APP_CONFIG.strings.METRICS_FLOW_CONVERSION}`;
  header.appendChild(title);
  header.appendChild(summary);
  card.appendChild(header);

  // Screen-reader summary of the whole card, e.g.
  // "Create UTub: 638 of 812 succeeded, 79% conversion".
  card.setAttribute(
    "aria-label",
    `${displayName}: ${lastStep.count.toLocaleString()} of ${topStep.count.toLocaleString()} ${APP_CONFIG.strings.METRICS_FLOW_SUCCEEDED}, ${conversionPct} ${APP_CONFIG.strings.METRICS_FLOW_CONVERSION}`,
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
const lastRenderedResponses: WeakMap<
  HTMLElement,
  Map<string, FlowCardState>
> = new WeakMap();

function buildPlaceholder({
  id,
  kind,
}: {
  id: string;
  kind: FlowCardState["kind"];
}): HTMLElement {
  const placeholder = document.createElement("section");
  placeholder.className = "flow-card-placeholder";
  placeholder.dataset.flowId = id;
  placeholder.dataset.flowState = kind;
  placeholder.hidden = true;
  return placeholder;
}

// Reconcile rule: response by reference; loading/error by kind only; invalid by
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
  const { id, title, state } = entry;
  if (state.kind === "response") {
    return renderFlowCard({ id, title, response: state.response });
  }
  return buildPlaceholder({ id, kind: state.kind });
}

/**
 * Render the Flows panel grid from an ordered entry list: one node per entry,
 * in `entries` order. `response` entries render a `.flow-card`; `loading`,
 * `error` and `invalid` entries render a hidden `.flow-card-placeholder`;
 * `removed` entries and ids absent from `entries` have their node removed.
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
  const previousStates = lastRenderedResponses.get(container) ?? new Map();
  const nextStates = new Map<string, FlowCardState>();
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
      isSameState({ previous, next: entry.state })
    ) {
      node = existing;
    } else {
      node = buildNode({ entry });
      if (existing !== undefined) {
        container.replaceChild(node, existing);
      }
    }
    nextStates.set(entry.id, entry.state);
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
  lastRenderedResponses.set(container, nextStates);
}
