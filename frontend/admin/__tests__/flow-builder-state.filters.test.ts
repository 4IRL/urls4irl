import { describe, expect, it } from "vitest";

import { APP_CONFIG } from "../../lib/config.js";
import type { Schema } from "../../types/api-helpers.d.ts";

import {
  addBreakdown,
  addBreakdownFilter,
  addFilter,
  applyValidationErrors,
  draftFromEntry,
  findCatalogEvent,
  hasNestedContent,
  isDraftDirty,
  listBreakdownEventGroups,
  listFilterDims,
  listGroupByDims,
  listNestedMessages,
  listProblems,
  moveStep,
  normalizeDraft,
  removeBreakdown,
  removeBreakdownFilter,
  removeFilter,
  removeStep,
  setBreakdownEvent,
  setBreakdownFilterDim,
  setBreakdownFilterValue,
  setBreakdownGroupBy,
  setFilterDim,
  setFilterValue,
  setStepEndpoint,
  setStepEvent,
  setStepMethod,
  setStepStream,
  toRequestBody,
  validateDraft,
} from "../flow-builder-state.js";
import type { DraftStep, FlowDraft } from "../flow-builder-state.js";
import { FLOW_CATALOG_MOCK } from "./helpers/flow-catalog-mock.js";

type Entry = Schema<"MetricFlowEntrySchema">;

function draftOf(steps: Record<string, unknown>[]): FlowDraft {
  const entry: Entry = {
    id: "custom_1",
    display_name: "My flow",
    is_builtin: false,
    definition: { display_name: "My flow", steps },
    errors: {},
    first_invalid: null,
  };
  return draftFromEntry({ entry });
}

function uiStep(extra: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    stream: "ui",
    label: "Step",
    event_name: "ui_form_submit",
    ...extra,
  };
}

function snapshotOf(draft: FlowDraft): string {
  return normalizeDraft({ draft });
}

function firstStep(draft: FlowDraft) {
  return toRequestBody({ draft }).steps[0] as Record<string, unknown>;
}

const BREAKDOWN = {
  event_name: "ui_form_cancel",
  dim_filter: ["device_type:mobile"],
  group_by: "trigger",
};

describe("hydration and round trip", () => {
  it("is not dirty unedited, including stored dim_filter []", () => {
    const draft = draftOf([
      uiStep({ dim_filter: [] }),
      uiStep({
        dim_filter: ["device_type:desktop"],
        drop_breakdown: BREAKDOWN,
      }),
    ]);
    expect(isDraftDirty({ draft, snapshot: snapshotOf(draft) })).toBe(false);
    expect(firstStep(draft).dim_filter).toBeNull();
    expect(toRequestBody({ draft }).steps[1].drop_breakdown).toEqual(BREAKDOWN);
  });

  it("round-trips a colon inside a value", () => {
    const draft = draftOf([uiStep({ dim_filter: ["a:b:c"] })]);
    expect(draft.steps[0].filters[0]).toMatchObject({
      dim: "a",
      value: "b:c",
      raw: null,
    });
    expect(firstStep(draft).dim_filter).toEqual(["a:b:c"]);
  });

  it.each(["nocolon", ":x", "a:"])(
    "keeps malformed entry %s raw and unchanged",
    (entry) => {
      const draft = draftOf([uiStep({ dim_filter: [entry] })]);
      expect(draft.steps[0].filters[0].raw).toBe(entry);
      expect(firstStep(draft).dim_filter).toEqual([entry]);
      expect(isDraftDirty({ draft, snapshot: snapshotOf(draft) })).toBe(false);
    },
  );

  it("hydrates a non-list dim_filter, non-object drop_breakdown and a list with a non-string as damaged", () => {
    const draft = draftOf([
      uiStep({ dim_filter: "oops", drop_breakdown: ["x"] }),
      uiStep({ dim_filter: ["a:b", 3] }),
    ]);
    expect(draft.steps[0].damaged).toEqual({
      dim_filter: "oops",
      drop_breakdown: ["x"],
    });
    expect(draft.steps[0].filters).toEqual([]);
    expect(draft.steps[0].breakdown).toBeNull();
    expect(draft.steps[1].damaged).toEqual({ dim_filter: ["a:b", 3] });
    const body = toRequestBody({ draft });
    expect(body.steps[0].dim_filter).toBe("oops");
    expect(body.steps[0].drop_breakdown).toEqual(["x"]);
    expect(body.steps[1].dim_filter).toEqual(["a:b", 3]);
    expect(isDraftDirty({ draft, snapshot: snapshotOf(draft) })).toBe(false);
  });

  it.each([0, "", false])("detects falsy damaged value %j", (value) => {
    const draft = draftOf([
      uiStep({ dim_filter: value, drop_breakdown: value }),
    ]);
    expect(draft.steps[0].damaged).not.toBeNull();
    expect("dim_filter" in (draft.steps[0].damaged ?? {})).toBe(true);
    expect("drop_breakdown" in (draft.steps[0].damaged ?? {})).toBe(true);
    expect(firstStep(draft).dim_filter).toBe(value);
    expect(firstStep(draft).drop_breakdown).toBe(value);
  });

  it("round-trips a stored breakdown: malformed entry, damaged list, extra, missing group_by", () => {
    const stored = {
      event_name: "ui_form_cancel",
      dim_filter: ["a:b:c", "bad"],
      mystery: 7,
    };
    const draft = draftOf([uiStep({ drop_breakdown: stored })]);
    const breakdown = draft.steps[0].breakdown;
    expect(breakdown?.groupBy).toBeNull();
    expect(breakdown?.filters[1].raw).toBe("bad");
    expect(breakdown?.extra).toEqual({ mystery: 7 });
    expect(firstStep(draft).drop_breakdown).toEqual(stored);

    const damaged = draftOf([
      uiStep({ drop_breakdown: { ...BREAKDOWN, dim_filter: "x" } }),
    ]);
    expect(damaged.steps[0].breakdown?.damaged).toEqual({ dim_filter: "x" });
    expect(firstStep(damaged).drop_breakdown).toEqual({
      ...BREAKDOWN,
      dim_filter: "x",
    });

    const empty = draftOf([
      uiStep({ drop_breakdown: { ...BREAKDOWN, dim_filter: [] } }),
    ]);
    expect(
      (firstStep(empty).drop_breakdown as Record<string, unknown>).dim_filter,
    ).toBeNull();
  });

  it("hydrates an API step's status_code:200 and is not dirty", () => {
    const draft = draftOf([
      {
        stream: "api",
        label: "Api",
        api_endpoint: "urls.create_url",
        api_method: "POST",
        dim_filter: ["status_code:200"],
      },
    ]);
    expect(draft.steps[0].filters[0]).toMatchObject({
      dim: "status_code",
      value: "200",
    });
    expect(firstStep(draft).dim_filter).toEqual(["status_code:200"]);
    expect(isDraftDirty({ draft, snapshot: snapshotOf(draft) })).toBe(false);
  });

  it("passes unknown step keys through original", () => {
    const draft = draftOf([uiStep({ extra: 1, dim_filter: ["a:b"] })]);
    expect(draft.steps[0].original).toEqual({
      stream: "ui",
      label: "Step",
      event_name: "ui_form_submit",
      extra: 1,
    });
    expect(firstStep(draft).extra).toBe(1);
  });

  it("reorder and remove keep each step's own filters and breakdown", () => {
    const draft = draftOf([
      uiStep({ label: "One", dim_filter: ["device_type:mobile"] }),
      uiStep({ label: "Two", drop_breakdown: BREAKDOWN }),
      uiStep({ label: "Three" }),
    ]);
    const moved = moveStep({
      draft,
      key: draft.steps[0].key,
      direction: "down",
    });
    const removed = removeStep({ draft: moved, key: moved.steps[2].key });
    const steps = toRequestBody({ draft: removed }).steps;
    expect(steps[0].drop_breakdown).toEqual(BREAKDOWN);
    expect(steps[1].dim_filter).toEqual(["device_type:mobile"]);
  });
});

describe("edit functions", () => {
  it("add, set dim (resets value) and set value, order preserved, incomplete serializes", () => {
    let draft = draftOf([uiStep()]);
    const key = draft.steps[0].key;
    draft = addFilter({ draft, key });
    draft = addFilter({ draft, key });
    const [first, second] = draft.steps[0].filters;
    draft = setFilterDim({
      draft,
      key,
      filterKey: first.key,
      dim: "device_type",
    });
    expect(firstStep(draft).dim_filter).toEqual(["device_type:", ":"]);
    expect(
      isDraftDirty({ draft, snapshot: snapshotOf(draftOf([uiStep()])) }),
    ).toBe(true);
    draft = setFilterValue({
      draft,
      key,
      filterKey: first.key,
      value: "mobile",
    });
    draft = setFilterDim({ draft, key, filterKey: second.key, dim: "form" });
    draft = setFilterValue({ draft, key, filterKey: second.key, value: "url" });
    expect(firstStep(draft).dim_filter).toEqual([
      "device_type:mobile",
      "form:url",
    ]);
    draft = setFilterDim({ draft, key, filterKey: first.key, dim: "form" });
    expect(draft.steps[0].filters[0].value).toBeNull();
  });

  it("editing a malformed row clears raw", () => {
    let draft = draftOf([uiStep({ dim_filter: ["bad"] })]);
    const key = draft.steps[0].key;
    const row = draft.steps[0].filters[0];
    draft = setFilterValue({ draft, key, filterKey: row.key, value: "x" });
    expect(draft.steps[0].filters[0].raw).toBeNull();
    const again = draftOf([uiStep({ dim_filter: ["bad"] })]);
    const dimEdit = setFilterDim({
      draft: again,
      key: again.steps[0].key,
      filterKey: again.steps[0].filters[0].key,
      dim: "device_type",
    });
    expect(dimEdit.steps[0].filters[0].raw).toBeNull();
  });

  it("clears server and client list errors on each write", () => {
    let draft = draftOf([uiStep({ dim_filter: ["a:b"] })]);
    const key = draft.steps[0].key;
    const dirtyErrors = {
      serverErrors: ["s"],
      clientErrors: ["c"],
    };
    draft = {
      ...draft,
      steps: [
        {
          ...draft.steps[0],
          listErrors: {
            dim_filter: dirtyErrors,
            drop_breakdown: dirtyErrors,
            drop_breakdown_filters: dirtyErrors,
          },
        },
      ],
    };
    const added = addFilter({ draft, key });
    expect(added.steps[0].listErrors.dim_filter).toEqual({
      serverErrors: [],
      clientErrors: [],
    });
    const withBreakdown = addBreakdown({ draft, key });
    expect(
      withBreakdown.steps[0].listErrors.drop_breakdown.serverErrors,
    ).toEqual([]);
  });

  it("breakdown: add, set event resets group_by and filters, set group_by, filters", () => {
    let draft = draftOf([uiStep()]);
    const key = draft.steps[0].key;
    draft = addBreakdown({ draft, key });
    draft = setBreakdownEvent({ draft, key, eventName: "ui_form_cancel" });
    draft = setBreakdownGroupBy({ draft, key, groupBy: "trigger" });
    draft = addBreakdownFilter({ draft, key });
    const filterKey = draft.steps[0].breakdown?.filters[0].key;
    expect(filterKey).toBeDefined();
    if (filterKey === undefined) {
      return;
    }
    draft = setBreakdownFilterDim({
      draft,
      key,
      filterKey,
      dim: "device_type",
    });
    draft = setBreakdownFilterValue({ draft, key, filterKey, value: "mobile" });
    expect(firstStep(draft).drop_breakdown).toEqual(BREAKDOWN);
    draft = setBreakdownEvent({
      draft,
      key,
      eventName: "url_create_rejected",
    });
    expect(draft.steps[0].breakdown?.groupBy).toBeNull();
    expect(draft.steps[0].breakdown?.filters).toEqual([]);
    expect(addBreakdown({ draft, key }).steps[0].breakdown).toBe(
      draft.steps[0].breakdown,
    );
  });
});

describe("damaged write sites", () => {
  it("step add filter clears damaged.dim_filter only", () => {
    const draft = draftOf([uiStep({ dim_filter: "x", drop_breakdown: 5 })]);
    const next = addFilter({ draft, key: draft.steps[0].key });
    expect(next.steps[0].damaged).toEqual({ drop_breakdown: 5 });
    expect(firstStep(next).dim_filter).toEqual([":"]);
    expect(firstStep(next).drop_breakdown).toBe(5);
  });

  it("add breakdown clears damaged.drop_breakdown", () => {
    const draft = draftOf([uiStep({ dim_filter: "x", drop_breakdown: 5 })]);
    const next = addBreakdown({ draft, key: draft.steps[0].key });
    expect(next.steps[0].damaged).toEqual({ dim_filter: "x" });
    expect(next.steps[0].breakdown).not.toBeNull();
  });

  it("remove breakdown clears damaged.drop_breakdown and nulls damaged when empty", () => {
    const draft = draftOf([uiStep({ drop_breakdown: 0 })]);
    const next = removeBreakdown({ draft, key: draft.steps[0].key });
    expect(next.steps[0].damaged).toBeNull();
    expect(firstStep(next).drop_breakdown).toBeNull();
  });

  it("breakdown add filter clears the breakdown's damaged", () => {
    const draft = draftOf([
      uiStep({ drop_breakdown: { ...BREAKDOWN, dim_filter: "x" } }),
    ]);
    const next = addBreakdownFilter({ draft, key: draft.steps[0].key });
    expect(next.steps[0].breakdown?.damaged).toBeNull();
  });

  it("breakdown set event clears damaged", () => {
    const draft = draftOf([
      uiStep({ drop_breakdown: { ...BREAKDOWN, dim_filter: "x" } }),
    ]);
    const next = setBreakdownEvent({
      draft,
      key: draft.steps[0].key,
      eventName: "url_create_rejected",
    });
    expect(next.steps[0].breakdown?.damaged).toBeNull();
  });

  it("Remove breakdown and a breakdown event change each drop extra", () => {
    const stored = { ...BREAKDOWN, mystery: 7 };
    const draft = draftOf([uiStep({ drop_breakdown: stored })]);
    const key = draft.steps[0].key;
    const kept = setBreakdownGroupBy({ draft, key, groupBy: "trigger" });
    expect(kept.steps[0].breakdown?.extra).toEqual({ mystery: 7 });
    const edited = addBreakdownFilter({ draft, key });
    expect(edited.steps[0].breakdown?.extra).toEqual({ mystery: 7 });

    const changed = setBreakdownEvent({
      draft,
      key,
      eventName: "url_create_rejected",
    });
    expect(changed.steps[0].breakdown?.extra).toEqual({});
    expect(
      (firstStep(changed).drop_breakdown as Record<string, unknown>).mystery,
    ).toBeUndefined();

    const removed = addBreakdown({
      draft: removeBreakdown({ draft, key }),
      key,
    });
    expect(removed.steps[0].breakdown?.extra).toEqual({});
    expect(
      (firstStep(removed).drop_breakdown as Record<string, unknown>).mystery,
    ).toBeUndefined();
  });

  it.each([
    [
      "stream",
      (draft: FlowDraft) =>
        setStepStream({ draft, key: draft.steps[0].key, stream: "domain" }),
    ],
    [
      "event",
      (draft: FlowDraft) =>
        setStepEvent({
          draft,
          key: draft.steps[0].key,
          eventName: "ui_url_create_open",
        }),
    ],
  ])("a %s reset clears filters, breakdown and damaged", (_name, reset) => {
    const draft = draftOf([
      uiStep({ dim_filter: ["a:b"], drop_breakdown: BREAKDOWN }),
      uiStep({ dim_filter: "x", drop_breakdown: 3 }),
    ]);
    const first = reset(draft);
    expect(first.steps[0]).toMatchObject({
      filters: [],
      breakdown: null,
      damaged: null,
    });
    expect(hasNestedContent({ step: first.steps[0] })).toBe(false);
    const second = reset(
      moveStep({ draft, key: draft.steps[1].key, direction: "up" }),
    );
    expect(second.steps[0]).toMatchObject({ damaged: null });
    expect(hasNestedContent({ step: second.steps[0] })).toBe(false);
  });

  it("an endpoint reset clears everything; a method change keeps it", () => {
    const draft = draftOf([
      {
        stream: "api",
        label: "Api",
        api_endpoint: "urls.create_url",
        api_method: "POST",
        dim_filter: ["status_code:200"],
        drop_breakdown: { event_name: "api_hit", group_by: "status_code" },
      },
      {
        stream: "api",
        label: "Api",
        api_endpoint: "urls.create_url",
        api_method: "POST",
        dim_filter: 0,
      },
    ]);
    const method = setStepMethod({
      draft,
      key: draft.steps[0].key,
      apiMethod: "PUT",
    });
    expect(method.steps[0].filters).toHaveLength(1);
    expect(hasNestedContent({ step: method.steps[0] })).toBe(true);
    for (const step of draft.steps) {
      const next = setStepEndpoint({
        draft,
        key: step.key,
        apiEndpoint: "urls.other",
        catalog: FLOW_CATALOG_MOCK,
      });
      const target = next.steps.find((item) => item.key === step.key);
      expect(target).toMatchObject({
        filters: [],
        breakdown: null,
        damaged: null,
      });
      expect(hasNestedContent({ step: target as DraftStep })).toBe(false);
    }
  });

  it("an empty list has no nested content, and a same-value reselect keeps filters", () => {
    const draft = draftOf([uiStep({ dim_filter: [] })]);
    expect(hasNestedContent({ step: draft.steps[0] })).toBe(false);
    const key = draft.steps[0].key;
    const other = setStepEvent({ draft, key, eventName: "ui_url_create_open" });
    expect(hasNestedContent({ step: other.steps[0] })).toBe(false);
    const withFilter = draftOf([uiStep({ dim_filter: ["a:b"] })]);
    const same = setStepEvent({
      draft: withFilter,
      key: withFilter.steps[0].key,
      eventName: "ui_form_submit",
    });
    expect(same.steps[0].filters).toHaveLength(1);
  });
});

const SEEDED = { serverErrors: ["s"], clientErrors: ["c"] };
const CLEARED = { serverErrors: [], clientErrors: [] };
const LIST_NAMES = [
  "dim_filter",
  "drop_breakdown",
  "drop_breakdown_filters",
] as const;

function breakdownBody(draft: FlowDraft): Record<string, unknown> {
  return firstStep(draft).drop_breakdown as Record<string, unknown>;
}

function stepKeyOf(draft: FlowDraft): number {
  return draft.steps[0].key;
}

function breakdownRowKey(draft: FlowDraft): number {
  const row = draft.steps[0].breakdown?.filters[0];
  if (row === undefined) {
    throw new Error("expected a breakdown filter row");
  }
  return row.key;
}

function seedListErrors(draft: FlowDraft): FlowDraft {
  return {
    ...draft,
    steps: [
      {
        ...draft.steps[0],
        listErrors: {
          dim_filter: SEEDED,
          drop_breakdown: SEEDED,
          drop_breakdown_filters: SEEDED,
        },
      },
      ...draft.steps.slice(1),
    ],
  };
}

const WITH_BOTH = {
  dim_filter: ["a:b"],
  drop_breakdown: { ...BREAKDOWN },
};

describe("unedited save and dirty tracking", () => {
  it("sends the whole stored definition apart from [] becoming null", () => {
    const stored = [
      uiStep({ dim_filter: [] }),
      uiStep({
        dim_filter: ["a:b:c", "bad"],
        drop_breakdown: { ...BREAKDOWN, mystery: 7 },
        extra: 1,
      }),
      uiStep({ drop_breakdown: { ...BREAKDOWN, dim_filter: [] } }),
      uiStep({ dim_filter: "oops", drop_breakdown: ["x"] }),
    ];
    const withNulls = { api_endpoint: null, api_method: null };
    const expected = [
      { ...stored[0], ...withNulls, dim_filter: null, drop_breakdown: null },
      { ...stored[1], ...withNulls },
      {
        ...stored[2],
        ...withNulls,
        dim_filter: null,
        drop_breakdown: { ...BREAKDOWN, dim_filter: null },
      },
      { ...stored[3], ...withNulls },
    ];
    const draft = draftOf(stored);
    expect(toRequestBody({ draft }).steps).toEqual(expected);
    expect(isDraftDirty({ draft, snapshot: snapshotOf(draftOf(stored)) })).toBe(
      false,
    );
  });

  it("is dirty after editing a malformed row", () => {
    const stored = [uiStep({ dim_filter: ["bad"] })];
    const draft = draftOf(stored);
    const edited = setFilterValue({
      draft,
      key: stepKeyOf(draft),
      filterKey: draft.steps[0].filters[0].key,
      value: "x",
    });
    expect(
      isDraftDirty({ draft: edited, snapshot: snapshotOf(draftOf(stored)) }),
    ).toBe(true);
  });

  it("is dirty after Add on a damaged value", () => {
    const stored = [uiStep({ dim_filter: "oops" })];
    const draft = draftOf(stored);
    const added = addFilter({ draft, key: stepKeyOf(draft) });
    expect(
      isDraftDirty({ draft: added, snapshot: snapshotOf(draftOf(stored)) }),
    ).toBe(true);
  });
});

describe("falsy damaged values at write sites", () => {
  it.each([0, "", false])("step add filter clears %j", (value) => {
    const draft = draftOf([uiStep({ dim_filter: value })]);
    const next = addFilter({ draft, key: stepKeyOf(draft) });
    expect(next.steps[0].damaged).toBeNull();
    expect(firstStep(next).dim_filter).toEqual([":"]);
  });

  it.each([0, "", false])("add breakdown clears %j", (value) => {
    const draft = draftOf([uiStep({ drop_breakdown: value })]);
    const next = addBreakdown({ draft, key: stepKeyOf(draft) });
    expect(next.steps[0].damaged).toBeNull();
    expect(next.steps[0].breakdown).not.toBeNull();
  });

  it.each([0, "", false])("breakdown add filter clears %j", (value) => {
    const draft = draftOf([
      uiStep({ drop_breakdown: { ...BREAKDOWN, dim_filter: value } }),
    ]);
    expect(draft.steps[0].breakdown?.damaged).toEqual({ dim_filter: value });
    const next = addBreakdownFilter({ draft, key: stepKeyOf(draft) });
    expect(next.steps[0].breakdown?.damaged).toBeNull();
  });

  it.each([0, "", false])("breakdown set event clears %j", (value) => {
    const draft = draftOf([
      uiStep({ drop_breakdown: { ...BREAKDOWN, dim_filter: value } }),
    ]);
    const next = setBreakdownEvent({
      draft,
      key: stepKeyOf(draft),
      eventName: "url_create_rejected",
    });
    expect(next.steps[0].breakdown?.damaged).toBeNull();
  });

  it.each([0, "", false])("counts a damaged %j as nested content", (value) => {
    const draft = draftOf([
      uiStep({ dim_filter: value, drop_breakdown: value }),
    ]);
    expect(hasNestedContent({ step: draft.steps[0] })).toBe(true);
  });
});

describe("resets drop breakdown extra and damaged", () => {
  const stored = { ...BREAKDOWN, mystery: 7, dim_filter: "x" };

  it.each([
    [
      "stream",
      (draft: FlowDraft) =>
        setStepStream({ draft, key: stepKeyOf(draft), stream: "domain" }),
    ],
    [
      "event",
      (draft: FlowDraft) =>
        setStepEvent({
          draft,
          key: stepKeyOf(draft),
          eventName: "ui_url_create_open",
        }),
    ],
  ])("a %s reset", (_name, reset) => {
    const next = reset(draftOf([uiStep({ drop_breakdown: stored })]));
    expect(next.steps[0].breakdown).toBeNull();
    expect(firstStep(next).drop_breakdown).toBeNull();
  });

  it("an endpoint reset", () => {
    const draft = draftOf([
      {
        stream: "api",
        label: "Api",
        api_endpoint: "urls.create_url",
        api_method: "POST",
        drop_breakdown: { ...stored, event_name: "api_hit" },
      },
    ]);
    const next = setStepEndpoint({
      draft,
      key: stepKeyOf(draft),
      apiEndpoint: "urls.other",
      catalog: FLOW_CATALOG_MOCK,
    });
    expect(next.steps[0].breakdown).toBeNull();
    expect(firstStep(next).drop_breakdown).toBeNull();
  });
});

describe("remove and breakdown row edits", () => {
  it("removeFilter keeps the others in order and empties to null", () => {
    let draft = draftOf([uiStep({ dim_filter: ["a:1", "b:2", "c:3"] })]);
    const key = stepKeyOf(draft);
    const [, middle] = draft.steps[0].filters;
    draft = removeFilter({ draft, key, filterKey: middle.key });
    expect(firstStep(draft).dim_filter).toEqual(["a:1", "c:3"]);
    for (const filter of draft.steps[0].filters) {
      draft = removeFilter({ draft, key, filterKey: filter.key });
    }
    expect(firstStep(draft).dim_filter).toBeNull();
  });

  it("removeBreakdownFilter keeps the others in order and empties to null", () => {
    let draft = draftOf([
      uiStep({ drop_breakdown: { ...BREAKDOWN, dim_filter: ["a:1", "b:2"] } }),
    ]);
    const key = stepKeyOf(draft);
    const [first, second] = draft.steps[0].breakdown?.filters ?? [];
    draft = removeBreakdownFilter({ draft, key, filterKey: first.key });
    expect(breakdownBody(draft).dim_filter).toEqual(["b:2"]);
    draft = removeBreakdownFilter({ draft, key, filterKey: second.key });
    expect(breakdownBody(draft).dim_filter).toBeNull();
  });

  it("removeBreakdownFilter on a damaged breakdown keeps the damaged value", () => {
    const draft = draftOf([
      uiStep({ drop_breakdown: { ...BREAKDOWN, dim_filter: "x" } }),
    ]);
    const next = removeBreakdownFilter({
      draft,
      key: stepKeyOf(draft),
      filterKey: -1,
    });
    expect(next.steps[0].breakdown?.damaged).toEqual({ dim_filter: "x" });
    expect(breakdownBody(next).dim_filter).toBe("x");
  });

  it("editing a breakdown filter's dim or value clears raw", () => {
    const draft = draftOf([
      uiStep({ drop_breakdown: { ...BREAKDOWN, dim_filter: ["bad"] } }),
    ]);
    const key = stepKeyOf(draft);
    expect(draft.steps[0].breakdown?.filters[0].raw).toBe("bad");
    const filterKey = breakdownRowKey(draft);
    const value = setBreakdownFilterValue({
      draft,
      key,
      filterKey,
      value: "x",
    });
    expect(value.steps[0].breakdown?.filters[0].raw).toBeNull();
    const dim = setBreakdownFilterDim({
      draft,
      key,
      filterKey,
      dim: "device_type",
    });
    expect(dim.steps[0].breakdown?.filters[0].raw).toBeNull();
  });

  it("removeBreakdown alone serializes drop_breakdown null", () => {
    const draft = draftOf([
      uiStep({ drop_breakdown: { ...BREAKDOWN, mystery: 7 } }),
    ]);
    const next = removeBreakdown({ draft, key: stepKeyOf(draft) });
    expect(firstStep(next).drop_breakdown).toBeNull();
  });
});

describe("list errors cleared by each write", () => {
  const filterKeyOf = (draft: FlowDraft) => draft.steps[0].filters[0].key;
  const rowKeyOf = (draft: FlowDraft) => breakdownRowKey(draft);
  const withRows = {
    dim_filter: ["a:b"],
    drop_breakdown: { ...BREAKDOWN, dim_filter: ["x:y"] },
  };

  it.each([
    [
      "addFilter",
      WITH_BOTH,
      (draft: FlowDraft) => addFilter({ draft, key: stepKeyOf(draft) }),
      ["dim_filter"],
    ],
    [
      "removeFilter",
      withRows,
      (draft: FlowDraft) =>
        removeFilter({
          draft,
          key: stepKeyOf(draft),
          filterKey: filterKeyOf(draft),
        }),
      ["dim_filter"],
    ],
    [
      "setFilterDim",
      withRows,
      (draft: FlowDraft) =>
        setFilterDim({
          draft,
          key: stepKeyOf(draft),
          filterKey: filterKeyOf(draft),
          dim: "form",
        }),
      ["dim_filter"],
    ],
    [
      "setFilterValue",
      withRows,
      (draft: FlowDraft) =>
        setFilterValue({
          draft,
          key: stepKeyOf(draft),
          filterKey: filterKeyOf(draft),
          value: "v",
        }),
      ["dim_filter"],
    ],
    [
      "addBreakdown",
      { dim_filter: ["a:b"] },
      (draft: FlowDraft) => addBreakdown({ draft, key: stepKeyOf(draft) }),
      ["drop_breakdown", "drop_breakdown_filters"],
    ],
    [
      "removeBreakdown",
      withRows,
      (draft: FlowDraft) => removeBreakdown({ draft, key: stepKeyOf(draft) }),
      ["drop_breakdown", "drop_breakdown_filters"],
    ],
    [
      "setBreakdownEvent",
      withRows,
      (draft: FlowDraft) =>
        setBreakdownEvent({
          draft,
          key: stepKeyOf(draft),
          eventName: "url_create_rejected",
        }),
      ["drop_breakdown", "drop_breakdown_filters"],
    ],
    [
      "setBreakdownGroupBy",
      withRows,
      (draft: FlowDraft) =>
        setBreakdownGroupBy({
          draft,
          key: stepKeyOf(draft),
          groupBy: "trigger",
        }),
      ["drop_breakdown"],
    ],
    [
      "addBreakdownFilter",
      withRows,
      (draft: FlowDraft) =>
        addBreakdownFilter({ draft, key: stepKeyOf(draft) }),
      ["drop_breakdown_filters"],
    ],
    [
      "removeBreakdownFilter",
      withRows,
      (draft: FlowDraft) =>
        removeBreakdownFilter({
          draft,
          key: stepKeyOf(draft),
          filterKey: rowKeyOf(draft),
        }),
      ["drop_breakdown_filters"],
    ],
    [
      "setBreakdownFilterDim",
      withRows,
      (draft: FlowDraft) =>
        setBreakdownFilterDim({
          draft,
          key: stepKeyOf(draft),
          filterKey: rowKeyOf(draft),
          dim: "form",
        }),
      ["drop_breakdown_filters"],
    ],
    [
      "setBreakdownFilterValue",
      withRows,
      (draft: FlowDraft) =>
        setBreakdownFilterValue({
          draft,
          key: stepKeyOf(draft),
          filterKey: rowKeyOf(draft),
          value: "v",
        }),
      ["drop_breakdown_filters"],
    ],
  ])("%s", (_name, stored, write, cleared) => {
    const draft = seedListErrors(draftOf([uiStep(stored)]));
    const next = write(draft);
    for (const list of LIST_NAMES) {
      expect(next.steps[0].listErrors[list]).toEqual(
        cleared.includes(list) ? CLEARED : SEEDED,
      );
    }
  });

  it("setFilterDim and setFilterValue clear the row's own errors", () => {
    const draft = draftOf([uiStep({ dim_filter: ["a:b"] })]);
    const key = stepKeyOf(draft);
    const seeded: FlowDraft = {
      ...draft,
      steps: [
        {
          ...draft.steps[0],
          filters: [
            { ...draft.steps[0].filters[0], ...SEEDED },
            ...draft.steps[0].filters.slice(1),
          ],
        },
      ],
    };
    const filterKey = filterKeyOf(seeded);
    const dim = setFilterDim({ draft: seeded, key, filterKey, dim: "form" });
    expect(dim.steps[0].filters[0]).toMatchObject(CLEARED);
    const value = setFilterValue({ draft: seeded, key, filterKey, value: "v" });
    expect(value.steps[0].filters[0]).toMatchObject(CLEARED);
  });
});

describe("stored breakdown scalars the draft cannot hold", () => {
  it.each([
    ["event_name", 5],
    ["event_name", { a: 1 }],
    ["event_name", null],
    ["group_by", 0],
    ["group_by", ["x"]],
    ["group_by", null],
    ["group_by", ""],
  ])("round-trips %s = %j unchanged and not dirty", (field, value) => {
    const stored = [
      uiStep({
        drop_breakdown: { ...BREAKDOWN, dim_filter: ["a:b"], [field]: value },
      }),
    ];
    const draft = draftOf(stored);
    expect(breakdownBody(draft)).toEqual(
      stored[0].drop_breakdown as Record<string, unknown>,
    );
    expect(isDraftDirty({ draft, snapshot: snapshotOf(draftOf(stored)) })).toBe(
      false,
    );
  });

  it("editing group_by or the event drops the stored raw value", () => {
    const draft = draftOf([
      uiStep({ drop_breakdown: { event_name: 5, group_by: { a: 1 } } }),
    ]);
    const key = stepKeyOf(draft);
    const grouped = setBreakdownGroupBy({ draft, key, groupBy: "trigger" });
    expect(breakdownBody(grouped).group_by).toBe("trigger");
    expect(breakdownBody(grouped).event_name).toBe(5);
    const cleared = setBreakdownGroupBy({ draft, key, groupBy: null });
    expect("group_by" in breakdownBody(cleared)).toBe(false);
    const evented = setBreakdownEvent({
      draft,
      key,
      eventName: "ui_form_cancel",
    });
    expect(breakdownBody(evented)).toEqual({
      event_name: "ui_form_cancel",
      dim_filter: null,
    });
  });

  it("a stored breakdown without dim_filter gains dim_filter null (accepted shape change)", () => {
    // Absent and null dim_filter are treated alike (see normalizeDraft); the key is not tracked.
    const draft = draftOf([
      uiStep({ drop_breakdown: { event_name: "ui_form_cancel" } }),
    ]);
    expect(breakdownBody(draft)).toEqual({
      event_name: "ui_form_cancel",
      dim_filter: null,
    });
    expect(
      isDraftDirty({
        draft,
        snapshot: snapshotOf(
          draftOf([
            uiStep({ drop_breakdown: { event_name: "ui_form_cancel" } }),
          ]),
        ),
      }),
    ).toBe(false);
  });
});

describe("catalog helpers", () => {
  it("listBreakdownEventGroups excludes zero-groupable and includes step_allowed false", () => {
    const names = listBreakdownEventGroups({ catalog: FLOW_CATALOG_MOCK })
      .flatMap((group) => group.events)
      .map((event) => event.event_name);
    expect(names).toContain("ui_form_cancel");
    expect(names).toContain("api_hit");
    expect(names).not.toContain("ui_form_submit");
    expect(names).not.toContain("ui_url_create_open");
  });

  it("listFilterDims excludes group_by_only; listGroupByDims keeps groupable", () => {
    const filterKeys = listFilterDims({
      catalog: FLOW_CATALOG_MOCK,
      eventName: "url_create_rejected",
    }).map((dim) => dim.key);
    expect(filterKeys).toEqual(["device_type", "reason"]);
    expect(
      listGroupByDims({
        catalog: FLOW_CATALOG_MOCK,
        eventName: "ui_form_cancel",
      }).map((dim) => dim.key),
    ).toEqual(["trigger"]);
  });

  it("API steps resolve dims from api_hit", () => {
    expect(
      listFilterDims({
        catalog: FLOW_CATALOG_MOCK,
        eventName: null,
        stream: "api",
      }).map((dim) => dim.key),
    ).toEqual(["status_code"]);
  });

  it("findCatalogEvent searches every group and returns null when missing", () => {
    expect(
      findCatalogEvent({ catalog: FLOW_CATALOG_MOCK, eventName: "api_hit" })
        ?.event_name,
    ).toBe("api_hit");
    expect(
      findCatalogEvent({ catalog: FLOW_CATALOG_MOCK, eventName: "gone" }),
    ).toBeNull();
  });
});

describe("Save validation and the problem list", () => {
  const catalog = FLOW_CATALOG_MOCK;
  const ZERO_BREAKDOWN = {
    event_name: "ui_url_create_open",
    group_by: "device_type",
    dim_filter: ["device_type:mobile"],
  };

  function draftWithErrors({
    steps,
    errors,
  }: {
    steps: Record<string, unknown>[];
    errors: Record<string, string[]>;
  }): FlowDraft {
    const entry: Entry = {
      id: "custom_1",
      display_name: "My flow",
      is_builtin: false,
      definition: { display_name: "My flow", steps },
      errors,
      first_invalid: null,
    };
    return draftFromEntry({ entry });
  }

  function blocking({
    draft,
    withCatalog = true,
  }: {
    draft: FlowDraft;
    withCatalog?: boolean;
  }): string[] {
    return validateDraft({ draft, catalog: withCatalog ? catalog : null })
      .filter((error) => error.field === "nested")
      .map((error) => error.message);
  }

  function listed({
    draft,
    withCatalog = true,
  }: {
    draft: FlowDraft;
    withCatalog?: boolean;
  }): string[] {
    return listProblems({ draft, catalog: withCatalog ? catalog : null })
      .filter((problem) => problem.field === "nested")
      .map((problem) => problem.message);
  }

  function staleDim(dim: string): string {
    return APP_CONFIG.strings.METRICS_FLOW_BUILDER_FILTER_STALE_DIM.replace(
      "{dim}",
      dim,
    );
  }

  it("blocks an incomplete filter and breakdown, and listProblems agrees after Save", () => {
    const strings = APP_CONFIG.strings;
    let draft = draftOf([uiStep(), uiStep()]);
    draft = addFilter({ draft, key: draft.steps[0].key });
    draft = addBreakdown({ draft, key: draft.steps[0].key });
    const errors = validateDraft({ draft, catalog });
    expect(blocking({ draft })).toEqual([
      strings.METRICS_FLOW_BUILDER_FILTER_INCOMPLETE,
      strings.METRICS_FLOW_BUILDER_BREAKDOWN_INCOMPLETE,
    ]);
    draft = applyValidationErrors({ draft, errors });
    expect(listed({ draft })).toEqual(blocking({ draft }));
    // Removing the row unblocks it.
    draft = removeFilter({
      draft,
      key: draft.steps[0].key,
      filterKey: draft.steps[0].filters[0].key,
    });
    expect(blocking({ draft })).toEqual([
      strings.METRICS_FLOW_BUILDER_BREAKDOWN_INCOMPLETE,
    ]);
  });

  it("reports a raw row only as incomplete, never as a stale dim", () => {
    const draft = draftOf([uiStep({ dim_filter: ["nocolon"] }), uiStep()]);
    const incomplete = [
      APP_CONFIG.strings.METRICS_FLOW_BUILDER_FILTER_INCOMPLETE,
    ];
    expect(blocking({ draft })).toEqual(incomplete);
    expect(listed({ draft })).toEqual(incomplete);
    expect(blocking({ draft, withCatalog: false })).toEqual(incomplete);
  });

  it("judges stale dims and values, never a status_code value, and a group_by_only dim as stale", () => {
    const staleValue =
      APP_CONFIG.strings.METRICS_FLOW_BUILDER_FILTER_STALE_VALUE;
    const cases: [Record<string, unknown>, string[]][] = [
      [uiStep({ dim_filter: ["trigger:a"] }), [staleDim("trigger")]],
      [uiStep({ dim_filter: ["device_type:bogus"] }), [staleValue]],
      [uiStep({ dim_filter: ["device_type:mobile"] }), []],
      [
        {
          stream: "domain",
          label: "Step",
          event_name: "url_create_rejected",
          dim_filter: ["bucket_only:x"],
        },
        [staleDim("bucket_only")],
      ],
      [
        {
          stream: "api",
          label: "Step",
          api_endpoint: "urls.create_url",
          api_method: "POST",
          dim_filter: ["status_code:99"],
        },
        [],
      ],
    ];
    for (const [step, expected] of cases) {
      const draft = draftOf([step, uiStep()]);
      expect(blocking({ draft })).toEqual(expected);
      expect(listed({ draft })).toEqual(expected);
      expect(blocking({ draft, withCatalog: false })).toEqual([]);
      expect(listed({ draft, withCatalog: false })).toEqual([]);
    }
  });

  it("skips every catalog check under a stale or unset step event, and under a null catalog", () => {
    const nested = {
      dim_filter: ["bogus:x"],
      drop_breakdown: { event_name: "ui_old_event", group_by: "x" },
    };
    // ui_form_cancel exists but is not a step option; null is unset.
    for (const eventName of ["ui_form_cancel", "gone_event", null]) {
      const draft = draftOf([
        uiStep({ event_name: eventName, ...nested }),
        uiStep(),
      ]);
      expect(blocking({ draft })).toEqual([]);
      expect(listed({ draft })).toEqual([]);
    }
    const valid = draftOf([uiStep(nested), uiStep()]);
    const expected = [
      staleDim("bogus"),
      APP_CONFIG.strings.METRICS_FLOW_BUILDER_BREAKDOWN_EVENT_MISSING,
    ];
    expect(blocking({ draft: valid })).toEqual(expected);
    expect(listed({ draft: valid })).toEqual(expected);
    expect(blocking({ draft: valid, withCatalog: false })).toEqual([]);
  });

  it("derives damaged problems with a null catalog and lets a server message win", () => {
    const strings = APP_CONFIG.strings;
    const steps = [
      uiStep({ dim_filter: "oops", drop_breakdown: ["x"] }),
      uiStep({ drop_breakdown: { ...BREAKDOWN, dim_filter: "x" } }),
    ];
    const draft = draftOf(steps);
    const expected = [
      strings.METRICS_FLOW_BUILDER_DAMAGED_FILTERS,
      strings.METRICS_FLOW_BUILDER_DAMAGED_BREAKDOWN,
      strings.METRICS_FLOW_BUILDER_DAMAGED_BREAKDOWN_FILTERS,
    ];
    expect(listed({ draft, withCatalog: false })).toEqual(expected);
    expect(blocking({ draft, withCatalog: false })).toEqual(expected);
    const served = draftWithErrors({
      steps,
      errors: { "steps.0.dim_filter": ["Server filters."] },
    });
    expect(listed({ draft: served, withCatalog: false })).toEqual([
      "Server filters.",
      expected[1],
      expected[2],
    ]);
  });

  it("reports a removed step event once, with a damaged list as its own problem", () => {
    const draft = draftWithErrors({
      steps: [
        uiStep({
          event_name: "gone_event",
          dim_filter: "oops",
          drop_breakdown: { event_name: "ui_old_event", group_by: "x" },
        }),
        uiStep(),
      ],
      errors: { "steps.0.event_name": ["Unknown event."] },
    });
    expect(
      listProblems({ draft, catalog }).map((problem) => problem.message),
    ).toEqual([
      "Unknown event.",
      APP_CONFIG.strings.METRICS_FLOW_BUILDER_DAMAGED_FILTERS,
    ]);
  });

  it("keeps server rejections on a client revalidation and skips a client message beside one", () => {
    const draft = draftWithErrors({
      steps: [
        uiStep({ drop_breakdown: { event_name: "ui_form_cancel" } }),
        uiStep(),
      ],
      errors: { "steps.0.drop_breakdown.group_by": ["Server group."] },
    });
    const errors = validateDraft({ draft, catalog });
    const revalidated = applyValidationErrors({ draft, errors });
    expect(revalidated.steps[0].breakdown?.serverErrors.group_by).toEqual([
      "Server group.",
    ]);
    expect(listed({ draft: revalidated })).toEqual(["Server group."]);
  });

  it("stores a breakdown client message under its own part, beside a group_by server message", () => {
    const draft = draftWithErrors({
      steps: [uiStep({ drop_breakdown: { group_by: "trigger" } }), uiStep()],
      errors: { "steps.0.drop_breakdown.group_by": ["Server group."] },
    });
    const revalidated = applyValidationErrors({
      draft,
      errors: validateDraft({ draft, catalog }),
    });
    const breakdown = revalidated.steps[0].breakdown;
    expect(breakdown?.serverErrors.group_by).toEqual(["Server group."]);
    expect(breakdown?.clientErrors.event_name).toEqual([
      APP_CONFIG.strings.METRICS_FLOW_BUILDER_BREAKDOWN_INCOMPLETE,
    ]);
    expect(breakdown?.clientErrors.group_by).toEqual([]);
    const messages = listNestedMessages({
      step: revalidated.steps[0],
      catalog,
    });
    expect(messages.map((error) => [error.message, error.address])).toEqual([
      [
        APP_CONFIG.strings.METRICS_FLOW_BUILDER_BREAKDOWN_INCOMPLETE,
        { kind: "breakdown", part: "event" },
      ],
      ["Server group.", { kind: "breakdown", part: "group_by" }],
    ]);
  });

  describe("a stored zero-groupable breakdown", () => {
    const errors = {
      "steps.0.drop_breakdown.group_by": ["Bad group."],
      "steps.0.drop_breakdown.dim_filter.0": ["Bad filter."],
    };

    it("is one summary entry; the other server messages share the event select", () => {
      const draft = draftWithErrors({
        steps: [uiStep({ drop_breakdown: ZERO_BREAKDOWN }), uiStep()],
        errors,
      });
      const problems = listProblems({ draft, catalog });
      expect(problems.map((problem) => problem.message)).toEqual([
        "Bad group.",
      ]);
      expect(problems[0].address).toEqual({ kind: "breakdown", part: "event" });
      const messages = listNestedMessages({ step: draft.steps[0], catalog });
      expect(messages.map((error) => error.message)).toEqual([
        "Bad group.",
        "Bad filter.",
      ]);
      expect(
        messages.every((error) => error.address?.kind === "breakdown"),
      ).toBe(true);
      // Nothing is redirected without a catalog.
      expect(listed({ draft, withCatalog: false })).toEqual([
        "Bad group.",
        "Bad filter.",
      ]);
    });

    it("stays one entry under a stale step event, and falls back to the derived message", () => {
      const stale = draftWithErrors({
        steps: [
          uiStep({
            event_name: "ui_form_cancel",
            drop_breakdown: ZERO_BREAKDOWN,
          }),
          uiStep(),
        ],
        errors,
      });
      expect(listed({ draft: stale })).toEqual(["Bad group."]);
      const quiet = draftOf([
        uiStep({ drop_breakdown: ZERO_BREAKDOWN }),
        uiStep(),
      ]);
      expect(listed({ draft: quiet })).toEqual([
        APP_CONFIG.strings.METRICS_FLOW_BUILDER_BREAKDOWN_UNAVAILABLE,
      ]);
      const staleQuiet = draftOf([
        uiStep({
          event_name: "ui_form_cancel",
          drop_breakdown: ZERO_BREAKDOWN,
        }),
        uiStep(),
      ]);
      expect(listed({ draft: staleQuiet })).toEqual([]);
    });

    it("moves incomplete and raw rows to the event select in both stored-event states", () => {
      const strings = APP_CONFIG.strings;
      const rawRows = ["nocolon", ":x"];
      const cases: [string, string][] = [
        [
          "ui_url_create_open",
          strings.METRICS_FLOW_BUILDER_BREAKDOWN_UNAVAILABLE,
        ],
        ["ui_old_event", strings.METRICS_FLOW_BUILDER_BREAKDOWN_EVENT_MISSING],
      ];
      for (const [eventName, summary] of cases) {
        const draft = draftOf([
          uiStep({
            drop_breakdown: {
              event_name: eventName,
              group_by: "device_type",
              dim_filter: rawRows,
            },
          }),
          uiStep(),
        ]);
        expect(listed({ draft })).toEqual([summary]);
        const messages = listNestedMessages({ step: draft.steps[0], catalog });
        expect(messages.map((error) => error.message)).toEqual([
          summary,
          strings.METRICS_FLOW_BUILDER_FILTER_INCOMPLETE,
        ]);
        expect(
          messages.every((error) => error.address?.kind === "breakdown"),
        ).toBe(true);
        expect(blocking({ draft })).toEqual([
          summary,
          strings.METRICS_FLOW_BUILDER_FILTER_INCOMPLETE,
          strings.METRICS_FLOW_BUILDER_FILTER_INCOMPLETE,
        ]);
      }
    });
  });

  it("resets announce each time something was removed, via hasNestedContent", () => {
    let draft = draftOf([uiStep(), uiStep()]);
    const key = draft.steps[0].key;
    const events = [
      "url_create_rejected",
      "ui_form_submit",
      "ui_url_create_open",
    ];
    for (const eventName of events) {
      draft = addFilter({ draft, key });
      expect(hasNestedContent({ step: draft.steps[0] })).toBe(true);
      draft = setStepEvent({ draft, key, eventName });
      expect(hasNestedContent({ step: draft.steps[0] })).toBe(false);
    }
    // A reset with nothing to remove leaves nothing behind either.
    draft = setStepEvent({ draft, key, eventName: "ui_form_submit" });
    expect(hasNestedContent({ step: draft.steps[0] })).toBe(false);
    const damaged = draftOf([uiStep({ dim_filter: "oops" }), uiStep()]);
    expect(hasNestedContent({ step: damaged.steps[0] })).toBe(true);
    const cleared = setStepEvent({
      draft: damaged,
      key: damaged.steps[0].key,
      eventName: "url_create_rejected",
    });
    expect(hasNestedContent({ step: cleared.steps[0] })).toBe(false);
  });
});
