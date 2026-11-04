import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Schema } from "../../types/api-helpers.d.ts";

import { APP_CONFIG } from "../../lib/config.js";
import { createFlowBuilder } from "../flow-builder.js";
import type { FlowBuilder, FlowBuilderCallbacks } from "../flow-builder.js";
import {
  createMetricFlow,
  deleteMetricFlow,
  fetchMetricFlowCatalog,
  previewMetricFlow,
  updateMetricFlow,
} from "../metrics-query-client.js";

vi.mock("../metrics-query-client.js", () => ({
  fetchMetricFlowCatalog: vi.fn(),
  createMetricFlow: vi.fn(),
  previewMetricFlow: vi.fn(),
  updateMetricFlow: vi.fn(),
  deleteMetricFlow: vi.fn(),
}));

type Catalog = Schema<"FlowCatalogResponseSchema">;
type Entry = Schema<"MetricFlowEntrySchema">;

interface Deferred {
  xhr: JQuery.jqXHR;
  abort: ReturnType<typeof vi.fn>;
  resolve: (response?: unknown) => void;
  reject: (options?: {
    status?: number;
    responseJSON?: unknown;
    readyState?: number;
    statusText?: string;
  }) => void;
}

const CATALOG: Catalog = {
  event_groups: [
    {
      category: "ui",
      events: [
        {
          event_name: "modal_open",
          description: "",
          category: "ui",
          step_allowed: true,
          dims: [
            {
              key: "device_type",
              groupable: false,
              filter_kind: "values",
              values: ["desktop", "mobile"],
            },
          ],
        },
      ],
    },
    {
      category: "domain",
      events: [
        {
          event_name: "url_created",
          description: "",
          category: "domain",
          step_allowed: true,
          dims: [],
        },
      ],
    },
  ],
  api_endpoints: [],
};

const RESPONSE = {
  steps: [
    {
      stream: "ui",
      label: "One",
      event_name: "modal_open",
      count: 10,
      pct_of_top: 1,
      count_suppressed: false,
      breakdown: null,
    },
    {
      stream: "domain",
      label: "Two",
      event_name: "url_created",
      count: 5,
      pct_of_top: 0.5,
      count_suppressed: false,
      breakdown: null,
    },
  ],
};

const STEPS = [
  { stream: "ui", label: "One", event_name: "modal_open" },
  { stream: "domain", label: "Two", event_name: "url_created" },
];

const DEBOUNCE_MS = 300;
const INTERVAL_MS = 2500;

let catalogs: Deferred[];
let previews: Deferred[];
let saves: Deferred[];
let deletes: Deferred[];
let container: HTMLElement;
let callbacks: FlowBuilderCallbacks;
let builder: FlowBuilder;
let windowKey: string;

function makeDeferred(): Deferred {
  const doneCallbacks: Array<(response: unknown) => void> = [];
  const failCallbacks: Array<(xhr: unknown) => void> = [];
  let settled = false;
  const fake = {
    status: 0,
    readyState: 1,
    statusText: "",
    responseJSON: undefined as unknown,
    _429Handled: false,
    done: (callback: (response: unknown) => void) => {
      doneCallbacks.push(callback);
      return fake;
    },
    fail: (callback: (xhr: unknown) => void) => {
      failCallbacks.push(callback);
      return fake;
    },
    always: () => fake,
    abort: vi.fn(() => {
      if (settled) return;
      settled = true;
      fake.readyState = 0;
      fake.statusText = "abort";
      failCallbacks.forEach((callback) => callback(fake));
    }),
  };
  return {
    xhr: fake as unknown as JQuery.jqXHR,
    abort: fake.abort,
    resolve: (response = RESPONSE) => {
      if (settled) return;
      settled = true;
      fake.status = 200;
      fake.readyState = 4;
      doneCallbacks.forEach((callback) => callback(response));
    },
    reject: ({
      status = 500,
      responseJSON = undefined,
      readyState = 4,
      statusText = "error",
    } = {}) => {
      if (settled) return;
      settled = true;
      fake.status = status;
      fake.readyState = readyState;
      fake.statusText = statusText;
      fake.responseJSON = responseJSON;
      failCallbacks.forEach((callback) => callback(fake));
    },
  };
}

function track({ list }: { list: Deferred[] }): never {
  const deferred = makeDeferred();
  list.push(deferred);
  return deferred.xhr as never;
}

function entry({
  steps = STEPS as Record<string, unknown>[],
}: { steps?: Record<string, unknown>[] } = {}): Entry {
  return {
    id: "custom_1",
    display_name: "My flow",
    is_builtin: false,
    definition: { steps },
    errors: {},
    first_invalid: null,
  } as unknown as Entry;
}

function openEdit({ steps }: { steps?: Record<string, unknown>[] } = {}): void {
  builder.open({ mode: "edit", entry: entry({ steps }) });
  catalogs[catalogs.length - 1].resolve(CATALOG);
}

function openCreate(): void {
  builder.open({ mode: "create" });
  catalogs[catalogs.length - 1].resolve(CATALOG);
}

function calls() {
  return vi.mocked(previewMetricFlow).mock.calls.map(
    ([args]) =>
      args as {
        definition: { display_name: string; steps: unknown[] };
        window: string;
      },
  );
}

function advance({ ms }: { ms: number }): void {
  vi.advanceTimersByTime(ms);
}

/** The first send after open, which has no interval to wait out. */
function sendFirst(): Deferred {
  advance({ ms: DEBOUNCE_MS });
  return previews[previews.length - 1];
}

function query<El extends HTMLElement>({ selector }: { selector: string }): El {
  const found = container.querySelector<El>(selector);
  if (found === null) {
    throw new Error(`missing ${selector}`);
  }
  return found;
}

function maybe({ selector }: { selector: string }): HTMLElement | null {
  return container.querySelector<HTMLElement>(selector);
}

const previewBody = () => query({ selector: ".flow-builder-preview-body" });
const previewTitle = () => query({ selector: ".flow-builder-preview-title" });
const status = () => query({ selector: ".flow-builder-preview-status" });
const retryButton = () =>
  query<HTMLButtonElement>({
    selector: ".flow-builder-preview-error button",
  });
const nameInput = () =>
  query<HTMLInputElement>({ selector: '[data-field="display_name"]' });

function rows(): HTMLElement[] {
  return [...container.querySelectorAll<HTMLElement>(".flow-builder-step")];
}

function control({
  index,
  field,
}: {
  index: number;
  field: string;
}): HTMLInputElement | HTMLSelectElement {
  return rows()[index].querySelector(
    `[data-field="${field}"]`,
  ) as HTMLInputElement;
}

function type({ input, value }: { input: HTMLElement; value: string }): void {
  (input as HTMLInputElement).value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

function pick({ select, value }: { select: HTMLElement; value: string }): void {
  (select as HTMLSelectElement).value = value;
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

function editLabel({ value = "Changed" }: { value?: string } = {}): void {
  type({ input: control({ index: 0, field: "label" }), value });
}

function fillSteps(): void {
  for (let index = 0; index < rows().length; index += 1) {
    type({ input: control({ index, field: "label" }), value: "Label" });
    pick({
      select: control({ index, field: "event_name" }),
      value: "modal_open",
    });
  }
}

function save(): void {
  query<HTMLButtonElement>({ selector: ".flow-builder-save" }).click();
}

function hasCard(): boolean {
  return (
    maybe({ selector: ".flow-builder-preview-body .funnel-step" }) !== null
  );
}

function hasSkeleton(): boolean {
  return (
    maybe({ selector: ".flow-builder-preview-body .flow-skeleton-bar" }) !==
    null
  );
}

function placeholderText(): string | null {
  return (
    maybe({ selector: ".flow-builder-preview-placeholder" })?.textContent ??
    null
  );
}

function pressEscape({ target }: { target: HTMLElement }): void {
  target.dispatchEvent(
    new KeyboardEvent("keydown", {
      key: "Escape",
      bubbles: true,
      cancelable: true,
    }),
  );
}

/** Opens an edit builder and fails its first preview with a 500. */
function openFailed(): void {
  openEdit();
  sendFirst().reject({ status: 500 });
}

const strings = () => APP_CONFIG.strings;

beforeEach(() => {
  vi.useFakeTimers();
  catalogs = [];
  previews = [];
  saves = [];
  deletes = [];
  windowKey = "day";
  vi.mocked(fetchMetricFlowCatalog)
    .mockReset()
    .mockImplementation(() => track({ list: catalogs }));
  vi.mocked(previewMetricFlow)
    .mockReset()
    .mockImplementation(() => track({ list: previews }));
  vi.mocked(createMetricFlow)
    .mockReset()
    .mockImplementation(() => track({ list: saves }));
  vi.mocked(updateMetricFlow)
    .mockReset()
    .mockImplementation(() => track({ list: saves }));
  vi.mocked(deleteMetricFlow)
    .mockReset()
    .mockImplementation(() => track({ list: deletes }));
  container = document.createElement("div");
  document.body.append(container);
  callbacks = {
    announce: vi.fn(),
    onSaved: vi.fn(),
    onCancelled: vi.fn(),
    onFlowMissing: vi.fn(),
    onDeleted: vi.fn(),
    onListStale: vi.fn(),
    getWindow: () => windowKey,
  };
  builder = createFlowBuilder({ container, callbacks });
});

afterEach(() => {
  builder.close();
  container.remove();
  vi.useRealTimers();
});

describe("placeholder and first send", () => {
  it("create mode shows the placeholder and sends nothing until the draft is valid", () => {
    openCreate();
    expect(placeholderText()).toBe(strings().METRICS_FLOW_PREVIEW_PLACEHOLDER);
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(0);
    fillSteps();
    advance({ ms: DEBOUNCE_MS - 1 });
    expect(calls()).toHaveLength(0);
    advance({ ms: 1 });
    expect(calls()).toHaveLength(1);
  });

  it("sends the heading as display_name, the live window and the steps", () => {
    windowKey = "week";
    openEdit();
    sendFirst();
    expect(calls()[0].window).toBe("week");
    expect(calls()[0].definition.display_name).toBe(
      strings().METRICS_FLOW_PREVIEW_HEADING,
    );
    expect(calls()[0].definition.steps).toHaveLength(2);
  });

  it("renders the layout with a labelled preview section and a polite live region", () => {
    openCreate();
    const section = query({ selector: ".flow-builder-preview" });
    expect(section.getAttribute("aria-labelledby")).toBe(previewTitle().id);
    expect(previewTitle().tabIndex).toBe(-1);
    expect(previewTitle().textContent).toBe(
      strings().METRICS_FLOW_PREVIEW_HEADING,
    );
    const live = query({ selector: ".flow-builder-preview-live" });
    expect(live.getAttribute("aria-live")).toBe("polite");
    expect(live.getAttribute("aria-atomic")).toBe("true");
    expect(previewBody().contains(live)).toBe(false);
    expect(
      query({ selector: ".flow-builder-layout" }).contains(
        query({ selector: "form.flow-builder-form" }),
      ),
    ).toBe(true);
  });

  it("mounts no preview region while the catalog loads or after it fails", () => {
    builder.open({ mode: "edit", entry: entry() });
    expect(maybe({ selector: ".flow-builder-preview" })).toBeNull();
    catalogs[0].reject({ status: 500 });
    expect(maybe({ selector: ".flow-builder-preview" })).toBeNull();
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(0);
  });

  it("previews once after a catalog Try again that succeeds", () => {
    builder.open({ mode: "edit", entry: entry() });
    catalogs[0].reject({ status: 500 });
    query<HTMLButtonElement>({ selector: ".flow-builder-btn" }).click();
    catalogs[1].resolve(CATALOG);
    advance({ ms: DEBOUNCE_MS });
    expect(calls()).toHaveLength(1);
  });

  it("a stale event passes the client gate and sends a preview on open", () => {
    openEdit({ steps: [{ ...STEPS[0], event_name: "gone_event" }, STEPS[1]] });
    advance({ ms: DEBOUNCE_MS });
    expect(calls()).toHaveLength(1);
  });

  it("a stale filter fails the client gate and shows the placeholder on open", () => {
    openEdit({
      steps: [{ ...STEPS[0], dim_filter: ["gone_dim:zzz"] }, STEPS[1]],
    });
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(0);
    expect(placeholderText()).toBe(strings().METRICS_FLOW_PREVIEW_PLACEHOLDER);
  });
});

describe("names", () => {
  it("a name-only edit sends nothing yet retitles the card", () => {
    openEdit();
    sendFirst().resolve();
    expect(hasCard()).toBe(true);
    type({ input: nameInput(), value: "Renamed" });
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(1);
    expect(previewBody().querySelector("h4")?.textContent).toBe("Renamed");
    type({ input: nameInput(), value: "" });
    expect(previewBody().querySelector("h4")?.textContent).toBe(
      strings().METRICS_FLOW_PREVIEW_HEADING,
    );
  });

  it("a blank name does not stop a preview", () => {
    openCreate();
    fillSteps();
    advance({ ms: DEBOUNCE_MS });
    expect(calls()).toHaveLength(1);
  });
});

describe("state rendering", () => {
  it("is busy with a skeleton from open, then shows the card", () => {
    openEdit();
    expect(previewBody().getAttribute("aria-busy")).toBe("true");
    expect(hasSkeleton()).toBe(true);
    expect(status().hidden).toBe(false);
    sendFirst().resolve();
    expect(previewBody().hasAttribute("aria-busy")).toBe(false);
    expect(status().hidden).toBe(true);
    expect(hasCard()).toBe(true);
    expect(maybe({ selector: ".flow-card .flow-card-badge" })).toBeNull();
  });

  it("keeps the previous card, dimmed and busy, while the next one loads", () => {
    openEdit();
    sendFirst().resolve();
    editLabel();
    expect(previewBody().getAttribute("aria-busy")).toBe("true");
    expect(hasCard()).toBe(true);
    expect(hasSkeleton()).toBe(false);
  });

  it("a client-invalid edit replaces the card with the placeholder and aborts", () => {
    openEdit();
    const inFlight = sendFirst();
    pick({ select: control({ index: 0, field: "event_name" }), value: "" });
    expect(inFlight.abort).toHaveBeenCalled();
    expect(placeholderText()).toBe(strings().METRICS_FLOW_PREVIEW_PLACEHOLDER);
    expect(previewBody().hasAttribute("aria-busy")).toBe(false);
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(1);
  });

  it("a 400 shows the fix-fields placeholder and clears busy", () => {
    openEdit();
    sendFirst().reject({
      status: 400,
      responseJSON: { errors: { "steps.0.event_name": ["Unknown event."] } },
    });
    expect(placeholderText()).toBe(strings().METRICS_FLOW_PREVIEW_FIX_FIELDS);
    expect(previewBody().hasAttribute("aria-busy")).toBe(false);
  });
});

describe("failure and Retry", () => {
  it("a 500 shows the message with Retry and keeps every field", () => {
    openFailed();
    expect(
      query({ selector: ".flow-builder-preview-error" }).textContent,
    ).toContain(strings().METRICS_FLOW_PREVIEW_FAILED);
    expect(retryButton().textContent).toBe(strings().METRICS_FLOW_RETRY);
    expect(control({ index: 0, field: "label" }).value).toBe("One");
    expect(previewBody().hasAttribute("aria-busy")).toBe(false);
    expect(hasCard()).toBe(false);
  });

  it("a 429 shows the rate-limit message", () => {
    openEdit();
    sendFirst().reject({ status: 429 });
    expect(
      query({ selector: ".flow-builder-preview-error" }).textContent,
    ).toContain(strings().METRICS_FLOW_RATE_LIMITED);
  });

  it("Retry within the interval defers the send, stays focused and aria-disabled", () => {
    openFailed();
    const button = retryButton();
    button.focus();
    button.click();
    expect(document.activeElement).toBe(button);
    expect(button.getAttribute("aria-disabled")).toBe("true");
    expect(status().hidden).toBe(false);
    expect(previewBody().hasAttribute("aria-busy")).toBe(false);
    expect(hasSkeleton()).toBe(false);
    advance({ ms: DEBOUNCE_MS });
    expect(calls()).toHaveLength(1);
    advance({ ms: INTERVAL_MS });
    expect(calls()).toHaveLength(2);
    expect(calls()[1]).toEqual(calls()[0]);
    previews[1].reject({ status: 429 });
    expect(retryButton()).toBe(button);
    expect(button.hasAttribute("aria-disabled")).toBe(false);
    expect(
      query({ selector: ".flow-builder-preview-error" }).textContent,
    ).toContain(strings().METRICS_FLOW_RATE_LIMITED);
  });

  it("Retry sends the live window, not the failed one", () => {
    openFailed();
    windowKey = "month";
    retryButton().click();
    advance({ ms: DEBOUNCE_MS + INTERVAL_MS });
    expect(calls()[1].window).toBe("month");
  });

  it("a name-only edit after a failure keeps the block and Retry sends the same body", () => {
    openFailed();
    type({ input: nameInput(), value: "Renamed" });
    expect(maybe({ selector: ".flow-builder-preview-error" })).not.toBeNull();
    retryButton().click();
    advance({ ms: DEBOUNCE_MS + INTERVAL_MS });
    expect(calls()[1]).toEqual(calls()[0]);
  });

  it("a body change after a failure replaces the block with the skeleton", () => {
    openFailed();
    editLabel();
    expect(maybe({ selector: ".flow-builder-preview-error" })).toBeNull();
    expect(hasSkeleton()).toBe(true);
    expect(
      maybe({ selector: ".flow-builder-preview-error button" }),
    ).toBeNull();
  });

  it("an edit during a Retry-driven flight changes nothing visible until it settles", () => {
    openFailed();
    retryButton().click();
    editLabel();
    expect(maybe({ selector: ".flow-builder-preview-error" })).not.toBeNull();
    expect(retryButton().getAttribute("aria-disabled")).toBe("true");
    expect(previewBody().hasAttribute("aria-busy")).toBe(false);
    expect(hasSkeleton()).toBe(false);
    advance({ ms: DEBOUNCE_MS + INTERVAL_MS });
    expect(calls()).toHaveLength(2);
    previews[1].resolve();
    expect(maybe({ selector: ".flow-builder-preview-error" })).toBeNull();
    expect(hasCard()).toBe(true);
  });

  it("a client-invalid edit during a Retry-driven flight shows the placeholder", () => {
    openFailed();
    retryButton().click();
    pick({ select: control({ index: 0, field: "event_name" }), value: "" });
    expect(maybe({ selector: ".flow-builder-preview-error" })).toBeNull();
    expect(placeholderText()).toBe(strings().METRICS_FLOW_PREVIEW_PLACEHOLDER);
  });
});

describe("lifecycle", () => {
  it("close aborts an in-flight preview and leaves no timer", () => {
    openEdit();
    const inFlight = sendFirst();
    builder.close();
    expect(inFlight.abort).toHaveBeenCalled();
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(1);
  });

  it("close during the debounce sends nothing", () => {
    openEdit();
    builder.close();
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(0);
  });

  it("close during a deferral sends nothing more", () => {
    openEdit();
    sendFirst().resolve();
    editLabel();
    advance({ ms: DEBOUNCE_MS });
    builder.close();
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(1);
  });

  it("re-opening starts fresh and a late response from the old session writes nothing", () => {
    openEdit();
    const old = sendFirst();
    const oldBody = previewBody();
    builder.close();
    openEdit();
    expect(previewBody().getAttribute("aria-busy")).toBe("true");
    old.resolve();
    expect(oldBody.querySelector(".funnel-step")).toBeNull();
    expect(hasCard()).toBe(false);
    // The controller outlives the session, so the 2.5 s send interval still holds.
    advance({ ms: DEBOUNCE_MS + INTERVAL_MS });
    expect(calls()).toHaveLength(2);
    previews[1].resolve();
    expect(hasCard()).toBe(true);
  });

  it("Save start aborts the preview and freezes the card without a placeholder", () => {
    openEdit();
    sendFirst().resolve();
    save();
    expect(
      previewBody().classList.contains("flow-builder-preview-body--stale"),
    ).toBe(true);
    expect(previewBody().hasAttribute("aria-busy")).toBe(false);
    expect(status().hidden).toBe(true);
    expect(hasCard()).toBe(true);
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(1);
  });

  it("an edit during an in-flight Save sends nothing", () => {
    openEdit();
    sendFirst().resolve();
    save();
    editLabel();
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(1);
  });

  it("freezes the loading skeleton too", () => {
    openEdit();
    const inFlight = sendFirst();
    save();
    expect(inFlight.abort).toHaveBeenCalled();
    expect(hasSkeleton()).toBe(true);
    expect(
      previewBody().classList.contains("flow-builder-preview-body--stale"),
    ).toBe(true);
  });

  it("swaps the fix-fields text for the plain placeholder when Save starts", () => {
    openEdit();
    sendFirst().reject({
      status: 400,
      responseJSON: { errors: { "steps.0.event_name": ["Unknown event."] } },
    });
    save();
    expect(placeholderText()).toBe(strings().METRICS_FLOW_PREVIEW_PLACEHOLDER);
  });

  it("a failed Save recovers with the skeleton and a new request", () => {
    openEdit();
    sendFirst().resolve();
    save();
    saves[0].reject({ status: 500 });
    expect(
      previewBody().classList.contains("flow-builder-preview-body--stale"),
    ).toBe(false);
    expect(hasSkeleton()).toBe(true);
    advance({ ms: DEBOUNCE_MS + INTERVAL_MS });
    expect(calls()).toHaveLength(2);
    previews[1].resolve();
    expect(hasCard()).toBe(true);
  });

  it("a failed Delete recovers the same way", () => {
    openEdit();
    sendFirst().resolve();
    query<HTMLButtonElement>({ selector: '[data-action="delete"]' }).click();
    query<HTMLButtonElement>({ selector: '[data-confirm="confirm"]' }).click();
    expect(deletes).toHaveLength(1);
    expect(
      previewBody().classList.contains("flow-builder-preview-body--stale"),
    ).toBe(true);
    deletes[0].reject({ status: 500 });
    advance({ ms: DEBOUNCE_MS + INTERVAL_MS });
    expect(calls()).toHaveLength(2);
  });

  it("a failed Save on a client-invalid draft shows the placeholder", () => {
    openEdit();
    sendFirst().resolve();
    save();
    pick({ select: control({ index: 0, field: "event_name" }), value: "" });
    saves[0].reject({ status: 500 });
    expect(placeholderText()).toBe(strings().METRICS_FLOW_PREVIEW_PLACEHOLDER);
  });

  it("Retry is inert during a Save and restored when the Save fails", () => {
    openFailed();
    save();
    const button = retryButton();
    expect(button.getAttribute("aria-disabled")).toBe("true");
    button.click();
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(1);
    saves[0].reject({ status: 500 });
    // Recovery re-requests, so the failed block gives way to the skeleton.
    expect(hasSkeleton()).toBe(true);
    advance({ ms: DEBOUNCE_MS + INTERVAL_MS });
    expect(calls()).toHaveLength(2);
  });

  it("Retry is inert while a Delete confirm is open and during the Delete", () => {
    openFailed();
    query<HTMLButtonElement>({ selector: '[data-action="delete"]' }).click();
    expect(retryButton().getAttribute("aria-disabled")).toBe("true");
    retryButton().click();
    query<HTMLButtonElement>({ selector: '[data-confirm="confirm"]' }).click();
    retryButton().click();
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(1);
    deletes[0].reject({ status: 500 });
    expect(hasSkeleton()).toBe(true);
  });

  it("a Save 404 closes the builder and a late handler sends nothing", () => {
    openEdit();
    sendFirst().resolve();
    save();
    vi.mocked(callbacks.onFlowMissing).mockImplementation(() =>
      builder.close(),
    );
    saves[0].reject({ status: 404, responseJSON: { errorCode: 5 } });
    expect(callbacks.onFlowMissing).toHaveBeenCalledTimes(1);
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(1);
  });

  it("a failed Save keeps every field value", () => {
    openEdit();
    sendFirst().resolve();
    editLabel({ value: "Kept label" });
    save();
    saves[0].reject({ status: 500 });
    expect(control({ index: 0, field: "label" }).value).toBe("Kept label");
  });

  it("Cancel, a Save success and a Delete success each leave no preview timer", () => {
    openEdit();
    const inFlight = sendFirst();
    builder.close();
    expect(inFlight.abort).toHaveBeenCalled();
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(1);
    openEdit();
    advance({ ms: DEBOUNCE_MS + INTERVAL_MS });
    expect(calls()).toHaveLength(2);
    save();
    saves[0].resolve();
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(2);
  });

  it("the first update after field errors or a placeholder shows the skeleton", () => {
    openEdit();
    sendFirst().reject({
      status: 400,
      responseJSON: { errors: { "steps.0.event_name": ["Unknown event."] } },
    });
    editLabel();
    expect(hasSkeleton()).toBe(true);
    expect(hasCard()).toBe(false);
  });

  it("Retry is inert while a discard confirm is open and restored when it closes", async () => {
    openFailed();
    // A name edit dirties the draft without touching the failed block.
    type({ input: nameInput(), value: "Renamed" });
    const decision = builder.confirmDiscard();
    expect(retryButton().getAttribute("aria-disabled")).toBe("true");
    retryButton().click();
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(1);
    query<HTMLButtonElement>({ selector: '[data-confirm="safe"]' }).click();
    await expect(decision).resolves.toBe(false);
    expect(retryButton().hasAttribute("aria-disabled")).toBe(false);
  });
});

describe("window", () => {
  it("refreshPreview re-sends with the new window and dims the settled card", () => {
    openEdit();
    sendFirst().resolve();
    windowKey = "week";
    builder.refreshPreview();
    expect(previewBody().getAttribute("aria-busy")).toBe("true");
    expect(hasCard()).toBe(true);
    advance({ ms: DEBOUNCE_MS + INTERVAL_MS });
    expect(calls()).toHaveLength(2);
    expect(calls()[1].window).toBe("week");
    expect(calls()[1].definition).toEqual(calls()[0].definition);
  });

  it("refreshPreview is a no-op before the catalog loads", () => {
    builder.refreshPreview();
    builder.open({ mode: "edit", entry: entry() });
    builder.refreshPreview();
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(0);
  });

  it("refreshPreview is a no-op during Save", () => {
    openEdit();
    sendFirst().resolve();
    save();
    windowKey = "week";
    builder.refreshPreview();
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(1);
  });

  it("refreshPreview is a no-op during Delete", () => {
    openEdit();
    sendFirst().resolve();
    query<HTMLButtonElement>({ selector: '[data-action="delete"]' }).click();
    query<HTMLButtonElement>({ selector: '[data-confirm="confirm"]' }).click();
    windowKey = "week";
    builder.refreshPreview();
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(1);
  });

  it("refreshPreview is a no-op once closed", () => {
    openEdit();
    sendFirst().resolve();
    builder.close();
    builder.refreshPreview();
    advance({ ms: 10_000 });
    expect(calls()).toHaveLength(1);
  });
});

describe("focus", () => {
  it("moves focus to the preview title when a settle removes the focused Retry", () => {
    openFailed();
    retryButton().focus();
    editLabel();
    expect(document.activeElement).toBe(previewTitle());
  });

  it("moves focus to the title when a render removes the focused placeholder", () => {
    openCreate();
    for (let index = 0; index < rows().length; index += 1) {
      pick({
        select: control({ index, field: "event_name" }),
        value: "modal_open",
      });
    }
    // Typing the last label completes the draft without moving focus itself.
    type({ input: control({ index: 0, field: "label" }), value: "A" });
    query<HTMLElement>({
      selector: ".flow-builder-preview-placeholder",
    }).focus();
    type({ input: control({ index: 1, field: "label" }), value: "B" });
    expect(document.activeElement).toBe(previewTitle());
  });

  it("leaves focus in a typing field when the preview settles", () => {
    openEdit();
    const label = control({ index: 0, field: "label" });
    label.focus();
    sendFirst().resolve();
    expect(document.activeElement).toBe(label);
  });

  function retryAndFocus(): void {
    openFailed();
    retryButton().focus();
    retryButton().click();
    advance({ ms: INTERVAL_MS });
    expect(calls()).toHaveLength(2);
  }

  it("moves focus to the title when a Retry result removes the focused Retry", () => {
    retryAndFocus();
    previews[1].resolve();
    expect(document.activeElement).toBe(previewTitle());
  });

  it("moves focus to the title when a Retry settles as field errors", () => {
    retryAndFocus();
    previews[1].reject({
      status: 400,
      responseJSON: { errors: { "steps.0.event_name": ["Unknown event."] } },
    });
    expect(document.activeElement).toBe(previewTitle());
  });

  it("moves focus to the title when a failed Save recovery removes the focused Retry", () => {
    openFailed();
    save();
    retryButton().focus();
    saves[0].reject({ status: 500 });
    expect(document.activeElement).toBe(previewTitle());
  });

  it("does not move focus when a select outside the preview body changes", () => {
    openEdit();
    sendFirst().resolve();
    const select = control({ index: 0, field: "event_name" });
    select.focus();
    pick({ select, value: "modal_open" });
    // The step rows re-render, so compare by position, not identity.
    expect(document.activeElement).not.toBe(previewTitle());
    expect(document.activeElement?.getAttribute("data-field")).toBe(
      "event_name",
    );
  });

  it("does not move focus when the focused Retry survives the render", () => {
    openFailed();
    retryButton().focus();
    type({ input: nameInput(), value: "Renamed" });
    expect(document.activeElement).toBe(retryButton());
  });
});

describe("keyboard", () => {
  it("Escape on Retry starts Cancel through the discard guard", async () => {
    openFailed();
    pressEscape({ target: retryButton() });
    await Promise.resolve();
    await Promise.resolve();
    expect(callbacks.onCancelled).toHaveBeenCalledTimes(1);
  });

  it("Escape on the empty-state paragraph starts Cancel", async () => {
    openCreate();
    pressEscape({
      target: query({ selector: ".flow-builder-preview-placeholder" }),
    });
    await Promise.resolve();
    await Promise.resolve();
    expect(callbacks.onCancelled).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// Preview-origin field errors
// ---------------------------------------------------------------------------

const THREE_STEPS = [
  ...STEPS,
  { stream: "domain", label: "Three", event_name: "url_created" },
];

function rejectWith({
  deferred,
  errors,
}: {
  deferred: Deferred;
  errors: Record<string, string[]>;
}): void {
  deferred.reject({ status: 400, responseJSON: { errors } });
}

function marks(): HTMLElement[] {
  return [...container.querySelectorAll<HTMLElement>("[data-preview-err]")];
}

function describedTexts({ element }: { element: HTMLElement }): string[] {
  return (element.getAttribute("aria-describedby") ?? "")
    .split(" ")
    .filter((id) => id !== "")
    .map((id) => document.getElementById(id)?.textContent ?? "");
}

/** What the preview live region says once its clear-then-set tick has run. */
function spoken(): string {
  advance({ ms: 1 });
  return maybe({ selector: ".flow-builder-preview-live" })?.textContent ?? "";
}

/** Sends the next preview after an edit that changes the body. */
function nextPreview({ value }: { value: string }): Deferred {
  editLabel({ value });
  advance({ ms: DEBOUNCE_MS + INTERVAL_MS });
  return previews[previews.length - 1];
}

function summaryPresent(): boolean {
  const element = maybe({ selector: ".flow-builder-summary" });
  return element !== null && !element.hidden && element.childElementCount > 0;
}

function eventSelect({ index }: { index: number }): HTMLElement {
  return control({ index, field: "event_name" });
}

describe("preview field errors", () => {
  it("marks the control in place without moving focus or opening the summary", () => {
    openEdit({ steps: THREE_STEPS });
    const typing = control({ index: 0, field: "label" });
    typing.focus();
    rejectWith({
      deferred: sendFirst(),
      errors: { "steps.2.event_name": ["Unknown event."] },
    });
    const select = eventSelect({ index: 2 });
    expect(select.getAttribute("aria-invalid")).toBe("true");
    expect(describedTexts({ element: select })).toEqual(["Unknown event."]);
    expect(document.activeElement).toBe(typing);
    expect(summaryPresent()).toBe(false);
    expect(placeholderText()).toBe(strings().METRICS_FLOW_PREVIEW_FIX_FIELDS);
  });

  it("Save on the same draft still shows the summary and keeps its own marks", () => {
    openEdit();
    const errors = { "steps.0.event_name": ["Unknown event."] };
    rejectWith({ deferred: sendFirst(), errors });
    save();
    rejectWith({ deferred: saves[0], errors });
    expect(summaryPresent()).toBe(true);
    expect(document.activeElement).toBe(
      query({ selector: ".flow-builder-summary" }),
    );
    const select = eventSelect({ index: 0 });
    expect(select.getAttribute("aria-invalid")).toBe("true");
    expect(describedTexts({ element: select })).toEqual(["Unknown event."]);
    // A later preview that clears its own marks leaves the Save mark alone.
    nextPreview({ value: "Changed" }).resolve();
    expect(marks()).toHaveLength(0);
    expect(select.getAttribute("aria-invalid")).toBe("true");
    expect(describedTexts({ element: select })).toEqual(["Unknown event."]);
  });

  it("lists a path with no control in the preview body", () => {
    openEdit();
    rejectWith({
      deferred: sendFirst(),
      errors: {
        "steps.0.api_endpoint": ["No such endpoint."],
        __root__: ["Flow rejected."],
      },
    });
    const lines = marks().map((line) => line.textContent);
    expect(lines).toContain("steps.0.api_endpoint: No such endpoint.");
    expect(lines).toContain("Flow rejected.");
    for (const line of marks()) {
      expect(previewBody().contains(line)).toBe(true);
    }
    expect(eventSelect({ index: 0 }).hasAttribute("aria-invalid")).toBe(false);
  });

  it("renders two distinct messages once each and an identical one once", () => {
    openEdit();
    rejectWith({
      deferred: sendFirst(),
      errors: { "steps.0.event_name": ["First.", "Second.", "First."] },
    });
    const select = eventSelect({ index: 0 });
    expect(marks()).toHaveLength(2);
    expect(describedTexts({ element: select })).toEqual(["First.", "Second."]);
    expect(spoken()).toBe(
      strings().METRICS_FLOW_PREVIEW_ANNOUNCE_PROBLEMS.replace("{count}", "2"),
    );
  });

  it("removes every preview mark at the next updating, result or failure", () => {
    openEdit();
    const errors = { "steps.0.event_name": ["Unknown event."] };
    rejectWith({ deferred: sendFirst(), errors });
    const select = eventSelect({ index: 0 });
    expect(marks()).toHaveLength(1);
    editLabel({ value: "Changed" });
    expect(marks()).toHaveLength(0);
    expect(select.hasAttribute("aria-invalid")).toBe(false);
    expect(select.hasAttribute("aria-describedby")).toBe(false);

    advance({ ms: DEBOUNCE_MS + INTERVAL_MS });
    rejectWith({ deferred: previews[1], errors });
    expect(marks()).toHaveLength(1);
    nextPreview({ value: "Again" }).reject({ status: 500 });
    expect(marks()).toHaveLength(0);

    advance({ ms: 0 });
    nextPreview({ value: "Third" }).resolve();
    expect(marks()).toHaveLength(0);
    expect(eventSelect({ index: 0 }).hasAttribute("aria-invalid")).toBe(false);
  });

  it("a 429 after a 400 leaves no preview mark", () => {
    openEdit();
    rejectWith({
      deferred: sendFirst(),
      errors: { "steps.0.event_name": ["Unknown event."] },
    });
    nextPreview({ value: "Changed" }).reject({ status: 429 });
    expect(marks()).toHaveLength(0);
  });

  it("starting Save clears the marks and none return when the Save fails", () => {
    openEdit();
    rejectWith({
      deferred: sendFirst(),
      errors: { "steps.0.event_name": ["Unknown event."] },
    });
    expect(marks()).toHaveLength(1);
    save();
    const select = eventSelect({ index: 0 });
    expect(marks()).toHaveLength(0);
    expect(select.hasAttribute("aria-invalid")).toBe(false);
    expect(select.hasAttribute("aria-describedby")).toBe(false);
    saves[0].reject({ status: 500 });
    expect(marks()).toHaveLength(0);
    expect(eventSelect({ index: 0 }).hasAttribute("aria-invalid")).toBe(false);
  });

  it("marks a stale stored event on edit-open without moving focus, once announced", () => {
    openEdit({ steps: [{ ...STEPS[0], event_name: "gone_event" }, STEPS[1]] });
    const before = document.activeElement;
    rejectWith({
      deferred: sendFirst(),
      errors: { "steps.0.event_name": ["Unknown event."] },
    });
    expect(eventSelect({ index: 0 }).getAttribute("aria-invalid")).toBe("true");
    expect(marks()).toHaveLength(1);
    expect(document.activeElement).toBe(before);
    expect(summaryPresent()).toBe(false);
    expect(spoken()).toBe(strings().METRICS_FLOW_PREVIEW_ANNOUNCE_PROBLEM_ONE);
    expect(callbacks.announce).not.toHaveBeenCalled();
  });

  it("drops a message a Save 400 already shows and adds a different one", () => {
    openEdit();
    sendFirst().resolve();
    save();
    rejectWith({
      deferred: saves[0],
      errors: { "steps.0.event_name": ["Unknown event."] },
    });
    const select = eventSelect({ index: 0 });
    const before = select.getAttribute("aria-describedby");
    rejectWith({
      deferred: nextPreview({ value: "Changed" }),
      errors: { "steps.0.event_name": ["Unknown event."] },
    });
    expect(marks()).toHaveLength(0);
    expect(select.getAttribute("aria-describedby")).toBe(before);
    expect(spoken()).toBe("");
    expect(document.activeElement).toBe(
      query({ selector: ".flow-builder-summary" }),
    );

    rejectWith({
      deferred: nextPreview({ value: "Changed again" }),
      errors: { "steps.0.event_name": ["Unknown event.", "Also wrong."] },
    });
    expect(marks().map((line) => line.textContent)).toEqual(["Also wrong."]);
    expect(describedTexts({ element: select })).toEqual([
      "Unknown event.",
      "Also wrong.",
    ]);
  });

  it("announces the same error set once and a different one again", () => {
    openEdit();
    const first = { "steps.0.event_name": ["Unknown event."] };
    rejectWith({ deferred: sendFirst(), errors: first });
    expect(spoken()).toBe(strings().METRICS_FLOW_PREVIEW_ANNOUNCE_PROBLEM_ONE);
    const live = query({ selector: ".flow-builder-preview-live" });
    live.textContent = "";
    rejectWith({ deferred: nextPreview({ value: "B" }), errors: first });
    expect(spoken()).toBe("");
    rejectWith({
      deferred: nextPreview({ value: "C" }),
      errors: { "steps.0.event_name": ["Different."] },
    });
    expect(spoken()).toBe(strings().METRICS_FLOW_PREVIEW_ANNOUNCE_PROBLEM_ONE);
  });
});

describe("preview field errors, Delete and held problems", () => {
  it("starting Delete clears preview marks, keeps Save marks, none return on failure", () => {
    openEdit();
    const errors = { "steps.0.event_name": ["Unknown event."] };
    rejectWith({ deferred: sendFirst(), errors });
    expect(marks()).toHaveLength(1);
    query<HTMLButtonElement>({ selector: '[data-action="delete"]' }).click();
    query<HTMLButtonElement>({ selector: '[data-confirm="confirm"]' }).click();
    const select = eventSelect({ index: 0 });
    expect(marks()).toHaveLength(0);
    expect(select.hasAttribute("aria-invalid")).toBe(false);
    expect(select.hasAttribute("aria-describedby")).toBe(false);
    deletes[0].reject({ status: 500 });
    expect(marks()).toHaveLength(0);
  });

  it("holds a problem announcement while a confirm is open and speaks it on close", async () => {
    openEdit();
    type({ input: nameInput(), value: "Renamed" });
    const decision = builder.confirmDiscard();
    rejectWith({
      deferred: sendFirst(),
      errors: { "steps.0.event_name": ["Unknown event."] },
    });
    expect(spoken()).toBe("");
    query<HTMLButtonElement>({ selector: '[data-confirm="safe"]' }).click();
    await decision;
    expect(spoken()).toBe(strings().METRICS_FLOW_PREVIEW_ANNOUNCE_PROBLEM_ONE);
  });

  it("returning to the placeholder forgets the last-spoken result", () => {
    openEdit();
    sendFirst().resolve();
    const text = spoken();
    expect(text).not.toBe("");
    pick({ select: control({ index: 0, field: "event_name" }), value: "" });
    expect(placeholderText()).toBe(strings().METRICS_FLOW_PREVIEW_PLACEHOLDER);
    pick({
      select: control({ index: 0, field: "event_name" }),
      value: "modal_open",
    });
    advance({ ms: DEBOUNCE_MS + INTERVAL_MS });
    previews[previews.length - 1].resolve();
    expect(spoken()).toBe(text);
  });
});

describe("preview announcements", () => {
  it("announces the card's own result text, never in the builder region", () => {
    openEdit();
    sendFirst().resolve();
    expect(spoken()).toBe(
      strings()
        .METRICS_FLOW_PREVIEW_ANNOUNCE_RESULT.replace("{succeeded}", "5")
        .replace("{total}", "10")
        .replace("{pct}", "50%"),
    );
    expect(callbacks.announce).not.toHaveBeenCalled();
  });

  it("announces the empty text for an all-zero result", () => {
    openEdit();
    sendFirst().resolve({
      steps: RESPONSE.steps.map((step) => ({ ...step, count: 0 })),
    } as never);
    expect(spoken()).toBe(strings().METRICS_FLOW_PREVIEW_ANNOUNCE_EMPTY);
  });

  it("a suppressed zero count is not all-zero and uses the suppressed text", () => {
    openEdit();
    sendFirst().resolve({
      steps: RESPONSE.steps.map((step, index) => ({
        ...step,
        count: 0,
        count_suppressed: index === 1,
      })),
    } as never);
    expect(spoken()).toContain(strings().METRICS_FLOW_COUNT_SUPPRESSED_ARIA);
    expect(spoken()).not.toBe(strings().METRICS_FLOW_PREVIEW_ANNOUNCE_EMPTY);
  });

  it("speaks a repeated result once, but again after a failure in between", () => {
    openEdit();
    sendFirst().resolve();
    const live = query({ selector: ".flow-builder-preview-live" });
    const text = spoken();
    expect(text).not.toBe("");
    live.textContent = "";
    nextPreview({ value: "B" }).resolve();
    expect(spoken()).toBe("");
    nextPreview({ value: "C" }).reject({ status: 500 });
    expect(spoken()).toBe(strings().METRICS_FLOW_PREVIEW_FAILED);
    nextPreview({ value: "D" }).resolve();
    expect(spoken()).toBe(text);
  });

  it("speaks a problem set, a result, then the same set again twice", () => {
    openEdit();
    const errors = { "steps.0.event_name": ["Unknown event."] };
    rejectWith({ deferred: sendFirst(), errors });
    const live = query({ selector: ".flow-builder-preview-live" });
    expect(spoken()).toBe(strings().METRICS_FLOW_PREVIEW_ANNOUNCE_PROBLEM_ONE);
    nextPreview({ value: "B" }).resolve();
    live.textContent = "";
    rejectWith({ deferred: nextPreview({ value: "C" }), errors });
    expect(spoken()).toBe(strings().METRICS_FLOW_PREVIEW_ANNOUNCE_PROBLEM_ONE);
  });

  it("announces a failure and a 429 on every entry, including after Retry", () => {
    openFailed();
    const live = query({ selector: ".flow-builder-preview-live" });
    expect(spoken()).toBe(strings().METRICS_FLOW_PREVIEW_FAILED);
    live.textContent = "";
    retryButton().click();
    advance({ ms: DEBOUNCE_MS + INTERVAL_MS });
    previews[previews.length - 1].reject({ status: 500 });
    expect(spoken()).toBe(strings().METRICS_FLOW_PREVIEW_FAILED);
    live.textContent = "";
    retryButton().click();
    advance({ ms: DEBOUNCE_MS + INTERVAL_MS });
    previews[previews.length - 1].reject({ status: 429 });
    expect(spoken()).toBe(strings().METRICS_FLOW_RATE_LIMITED);
    expect(callbacks.announce).not.toHaveBeenCalled();
  });

  it("holds an announcement while a discard confirm is open and speaks only the latest", async () => {
    openEdit();
    sendFirst().resolve();
    const live = query({ selector: ".flow-builder-preview-live" });
    expect(spoken()).not.toBe("");
    live.textContent = "";
    type({ input: nameInput(), value: "Renamed" });
    const decision = builder.confirmDiscard();
    nextPreview({ value: "B" }).reject({ status: 500 });
    nextPreview({ value: "C" }).reject({ status: 429 });
    expect(spoken()).toBe("");
    query<HTMLButtonElement>({ selector: '[data-confirm="safe"]' }).click();
    await expect(decision).resolves.toBe(false);
    expect(spoken()).toBe(strings().METRICS_FLOW_RATE_LIMITED);
  });

  it("speaks a held failure on confirm close even if it repeats the last one", async () => {
    openFailed();
    expect(spoken()).toBe(strings().METRICS_FLOW_PREVIEW_FAILED);
    retryButton().click();
    advance({ ms: DEBOUNCE_MS + INTERVAL_MS });
    type({ input: nameInput(), value: "Renamed" });
    const decision = builder.confirmDiscard();
    previews[previews.length - 1].reject({ status: 500 });
    const live = query({ selector: ".flow-builder-preview-live" });
    live.textContent = "";
    expect(spoken()).toBe("");
    query<HTMLButtonElement>({ selector: '[data-confirm="safe"]' }).click();
    await decision;
    expect(spoken()).toBe(strings().METRICS_FLOW_PREVIEW_FAILED);
  });

  it("drops a held result that repeats the last spoken one on confirm close", async () => {
    openEdit();
    sendFirst().resolve();
    expect(spoken()).not.toBe("");
    const live = query({ selector: ".flow-builder-preview-live" });
    live.textContent = "";
    type({ input: nameInput(), value: "Renamed" });
    const decision = builder.confirmDiscard();
    nextPreview({ value: "B" }).resolve();
    query<HTMLButtonElement>({ selector: '[data-confirm="safe"]' }).click();
    await decision;
    expect(spoken()).toBe("");
  });
});
