import { describe, expect, it } from "vitest";

import type { Schema } from "../../types/api-helpers.d.ts";

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
  summarizeHidden,
  toRequestBody,
  validateDraft,
} from "../flow-builder-state.js";
import type { FlowDraft, StepStream } from "../flow-builder-state.js";

type Entry = Schema<"MetricFlowEntrySchema">;
type Catalog = Schema<"FlowCatalogResponseSchema">;

const DIM_FILTER = ["a", "b"];
const BREAKDOWN = { event_name: "x", dim_filter: null, group_by: "reason" };

function entryFor({
  definition,
  errors = {},
}: {
  definition: Record<string, unknown>;
  errors?: Record<string, string[]>;
}): Entry {
  return {
    id: "custom_1",
    display_name: "My flow",
    is_builtin: false,
    definition,
    errors,
    first_invalid: null,
  };
}

function seededDefinition(): Record<string, unknown> {
  return {
    steps: [
      {
        stream: "ui",
        label: "Open",
        event_name: "modal_open",
        api_endpoint: null,
        api_method: null,
        dim_filter: DIM_FILTER,
        drop_breakdown: BREAKDOWN,
        future_key: 7,
      },
      {
        stream: "api",
        label: "Create",
        event_name: null,
        api_endpoint: "urls.create_url",
        api_method: "POST",
        dim_filter: null,
        drop_breakdown: null,
      },
      {
        stream: "domain",
        label: "Done",
        event_name: "url_created",
        api_endpoint: null,
        api_method: null,
        dim_filter: null,
        drop_breakdown: null,
      },
    ],
  };
}

function seededDraft(): FlowDraft {
  return draftFromEntry({
    entry: entryFor({ definition: seededDefinition() }),
  });
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
          dims: [],
        },
        {
          event_name: "ui_hidden",
          description: "",
          category: "ui",
          step_allowed: false,
          dims: [],
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
    {
      category: "api",
      events: [
        {
          event_name: "api_hit",
          description: "",
          category: "api",
          step_allowed: false,
          dims: [],
        },
      ],
    },
  ],
  api_endpoints: [
    { endpoint: "urls.create_url", blueprint: "urls", methods: ["POST"] },
    { endpoint: "urls.update_url", blueprint: "urls", methods: ["GET", "PUT"] },
    { endpoint: "utubs.create_utub", blueprint: "utubs", methods: ["POST"] },
  ],
};

function filledDraft(): FlowDraft {
  let draft = createBlankDraft();
  draft = setDisplayName({ draft, value: "Flow" });
  for (const step of draft.steps) {
    draft = setStepLabel({ draft, key: step.key, value: "Step" });
    draft = setStepEvent({ draft, key: step.key, eventName: "modal_open" });
  }
  return draft;
}

describe("createBlankDraft", () => {
  it("has two blank ui steps and no flow id", () => {
    const draft = createBlankDraft();
    expect(draft.flowId).toBeNull();
    expect(draft.steps).toHaveLength(2);
    expect(draft.steps.every((step) => step.stream === "ui")).toBe(true);
    expect(new Set(draft.steps.map((step) => step.key)).size).toBe(2);
  });
});

describe("draftFromEntry hydration", () => {
  it("keeps stored values, stream and step count exactly", () => {
    const draft = seededDraft();
    expect(draft.flowId).toBe("custom_1");
    expect(draft.displayName).toBe("My flow");
    expect(draft.steps.map((step) => step.stream)).toEqual([
      "ui",
      "api",
      "domain",
    ]);
    expect(draft.steps[1].apiEndpoint).toBe("urls.create_url");
  });

  it("never pads a one-step definition to the minimum", () => {
    const entry = entryFor({
      definition: { steps: [{ stream: "ui", label: "Only" }] },
    });
    expect(draftFromEntry({ entry }).steps).toHaveLength(1);
  });

  it("gives two blank steps for non-array steps without throwing", () => {
    for (const definition of [{}, { steps: "x" }, { steps: null }]) {
      const draft = draftFromEntry({ entry: entryFor({ definition }) });
      expect(draft.steps).toHaveLength(2);
    }
  });

  it("replaces a non-object step with a blank one in place", () => {
    const entry = entryFor({
      definition: {
        steps: [{ stream: "domain", label: "A", event_name: "e" }, 5, null],
      },
    });
    const draft = draftFromEntry({ entry });
    expect(draft.steps).toHaveLength(3);
    expect(draft.steps[0].label).toBe("A");
    expect(draft.steps[1]).toMatchObject({ stream: "ui", label: "" });
    expect(draft.steps[2]).toMatchObject({ stream: "ui", eventName: null });
  });

  it("maps unknown stream to ui and a bad label to empty", () => {
    const entry = entryFor({
      definition: { steps: [{ stream: "weird", label: 4, extra: 1 }] },
    });
    const [step] = draftFromEntry({ entry }).steps;
    expect(step.stream).toBe("ui");
    expect(step.label).toBe("");
    expect(step.original.extra).toBe(1);
  });

  it("treats a stored blank event as null so it is not dirty", () => {
    const blank = draftFromEntry({
      entry: entryFor({
        definition: { steps: [{ stream: "ui", label: "A", event_name: "" }] },
      }),
    });
    const nulled = draftFromEntry({
      entry: entryFor({
        definition: { steps: [{ stream: "ui", label: "A", event_name: null }] },
      }),
    });
    expect(blank.steps[0].eventName).toBeNull();
    expect(
      isDraftDirty({
        draft: blank,
        snapshot: normalizeDraft({ draft: nulled }),
      }),
    ).toBe(false);
  });

  it("keeps a stale stored event unchanged", () => {
    const entry = entryFor({
      definition: {
        steps: [{ stream: "ui", label: "A", event_name: "removed_event" }],
      },
    });
    expect(draftFromEntry({ entry }).steps[0].eventName).toBe("removed_event");
  });

  it("attaches entry.errors by path", () => {
    const entry = entryFor({
      definition: seededDefinition(),
      errors: {
        "steps.2.event_name": ["gone"],
        display_name: ["bad name"],
        __root__: ["broken"],
      },
    });
    const draft = draftFromEntry({ entry });
    expect(draft.steps[2].errors.event_name).toEqual(["gone"]);
    expect(draft.serverErrors).toEqual(
      expect.arrayContaining([
        { field: "display_name", stepKey: null, message: "bad name" },
        { field: "form", stepKey: null, message: "broken" },
      ]),
    );
  });
});

describe("toRequestBody pass-through", () => {
  it("equals the original definition after a name-only edit", () => {
    const draft = setDisplayName({ draft: seededDraft(), value: "  Renamed " });
    const body = toRequestBody({ draft });
    expect(body.display_name).toBe("Renamed");
    expect(body.steps).toEqual(
      (seededDefinition() as { steps: unknown[] }).steps,
    );
  });

  it("carries hidden fields with their step through reorder and remove", () => {
    let draft = seededDraft();
    const [first, second] = draft.steps;
    draft = moveStep({ draft, key: first.key, direction: "down" });
    draft = removeStep({ draft, key: second.key });
    const body = toRequestBody({ draft });
    expect(body.steps).toHaveLength(2);
    expect(body.steps[0]).toMatchObject({
      label: "Open",
      dim_filter: DIM_FILTER,
      drop_breakdown: BREAKDOWN,
      future_key: 7,
    });
  });

  it("trims, nulls the other stream's fields and fills missing hidden fields", () => {
    let draft = createBlankDraft();
    const [first] = draft.steps;
    draft = setStepLabel({ draft, key: first.key, value: "  Lbl  " });
    draft = setStepStream({ draft, key: first.key, stream: "api" });
    draft = setStepEndpoint({
      draft,
      key: first.key,
      apiEndpoint: "urls.update_url",
      catalog: CATALOG,
    });
    draft = setStepMethod({ draft, key: first.key, apiMethod: "PUT" });
    const [step] = toRequestBody({ draft }).steps;
    expect(step).toEqual({
      stream: "api",
      label: "Lbl",
      event_name: null,
      api_endpoint: "urls.update_url",
      api_method: "PUT",
      dim_filter: null,
      drop_breakdown: null,
    });
  });
});

describe("stale hidden fields", () => {
  it("clears hidden fields on event change and stays dirty after reverting", () => {
    const base = seededDraft();
    const snapshot = normalizeDraft({ draft: base });
    const [first] = base.steps;
    let draft = setStepEvent({
      draft: base,
      key: first.key,
      eventName: "other",
    });
    expect(draft.steps[0].hiddenCleared).toBe(true);
    expect(toRequestBody({ draft }).steps[0]).toMatchObject({
      dim_filter: null,
      drop_breakdown: null,
    });
    draft = setStepEvent({ draft, key: first.key, eventName: "modal_open" });
    expect(toRequestBody({ draft }).steps[0].dim_filter).toBeNull();
    expect(isDraftDirty({ draft, snapshot })).toBe(true);
  });

  it("does not flag hiddenCleared when nothing was cleared", () => {
    const clean = seededDraft();
    const changed = setStepEvent({
      draft: clean,
      key: clean.steps[2].key,
      eventName: "other",
    });
    expect(changed.steps[2].hiddenCleared).toBe(false);
  });

  it("clears on stream and endpoint change but not on method change", () => {
    const base = seededDraft();
    const viaStream = setStepStream({
      draft: base,
      key: base.steps[0].key,
      stream: "domain",
    });
    expect(viaStream.steps[0].hiddenCleared).toBe(true);

    const apiEntry = entryFor({
      definition: {
        steps: [
          {
            stream: "api",
            label: "A",
            api_endpoint: "urls.update_url",
            api_method: "GET",
            dim_filter: ["200"],
            drop_breakdown: null,
          },
        ],
      },
    });
    const apiDraft = draftFromEntry({ entry: apiEntry });
    const key = apiDraft.steps[0].key;
    const viaMethod = setStepMethod({ draft: apiDraft, key, apiMethod: "PUT" });
    expect(viaMethod.steps[0].hiddenCleared).toBe(false);
    expect(toRequestBody({ draft: viaMethod }).steps[0].dim_filter).toEqual([
      "200",
    ]);
    const viaEndpoint = setStepEndpoint({
      draft: apiDraft,
      key,
      apiEndpoint: "urls.create_url",
      catalog: CATALOG,
    });
    expect(viaEndpoint.steps[0].hiddenCleared).toBe(true);
  });
});

describe("stream-specific edits and empty hidden values", () => {
  it("ignores setStepEvent on an api step and setStepEndpoint on a non-api step", () => {
    const base = seededDraft();
    const apiStep = base.steps[1];
    const uiStep = base.steps[0];
    const viaEvent = setStepEvent({
      draft: base,
      key: apiStep.key,
      eventName: "modal_open",
    });
    expect(viaEvent).toEqual(base);
    expect(viaEvent.steps[1].eventName).toBeNull();
    const viaEndpoint = setStepEndpoint({
      draft: base,
      key: uiStep.key,
      apiEndpoint: "urls.create_url",
      catalog: CATALOG,
    });
    expect(viaEndpoint).toEqual(base);
    expect(viaEndpoint.steps[0].hiddenCleared).toBe(false);
  });

  it("does not flag hiddenCleared for empty-array hidden values", () => {
    const draft = draftFromEntry({
      entry: entryFor({
        definition: {
          steps: [
            {
              stream: "ui",
              label: "A",
              event_name: "modal_open",
              dim_filter: [],
              drop_breakdown: null,
            },
          ],
        },
      }),
    });
    const changed = setStepEvent({
      draft,
      key: draft.steps[0].key,
      eventName: "other",
    });
    expect(changed.steps[0].eventName).toBe("other");
    expect(changed.steps[0].hiddenCleared).toBe(false);
  });
});

describe("dependent reset", () => {
  it("clears the endpoint and method when an api step becomes ui, and event when ui becomes api", () => {
    const base = seededDraft();
    const uiKey = base.steps[0].key;
    const draft = setStepStream({ draft: base, key: uiKey, stream: "api" });
    expect(draft.steps[0]).toMatchObject({
      stream: "api",
      eventName: null,
      apiEndpoint: null,
      apiMethod: null,
    });
  });

  it("clears event, endpoint and method on stream change", () => {
    const base = seededDraft();
    const apiKey = base.steps[1].key;
    const draft = setStepStream({ draft: base, key: apiKey, stream: "ui" });
    expect(draft.steps[1]).toMatchObject({
      stream: "ui",
      eventName: null,
      apiEndpoint: null,
      apiMethod: null,
    });
  });

  it("clears the method on endpoint change unless exactly one is allowed", () => {
    const base = seededDraft();
    const key = base.steps[1].key;
    const multi = setStepEndpoint({
      draft: base,
      key,
      apiEndpoint: "urls.update_url",
      catalog: CATALOG,
    });
    expect(multi.steps[1].apiMethod).toBeNull();
    const single = setStepEndpoint({
      draft: multi,
      key,
      apiEndpoint: "utubs.create_utub",
      catalog: CATALOG,
    });
    expect(single.steps[1].apiMethod).toBe("POST");
    const noCatalog = setStepEndpoint({
      draft: single,
      key,
      apiEndpoint: "urls.create_url",
      catalog: null,
    });
    expect(noCatalog.steps[1].apiMethod).toBeNull();
  });
});

describe("dirty tracking", () => {
  it("is clean for a hand-reverted edit", () => {
    const base = seededDraft();
    const snapshot = normalizeDraft({ draft: base });
    const key = base.steps[0].key;
    let draft = setStepLabel({ draft: base, key, value: "Changed" });
    expect(isDraftDirty({ draft, snapshot })).toBe(true);
    draft = setStepLabel({ draft, key, value: "Open" });
    expect(isDraftDirty({ draft, snapshot })).toBe(false);
  });

  it("is clean for a defaults-only create draft and for whitespace-only changes", () => {
    const blank = createBlankDraft();
    const snapshot = normalizeDraft({ draft: blank });
    expect(isDraftDirty({ draft: blank, snapshot })).toBe(false);
    const spaced = setDisplayName({ draft: blank, value: "   " });
    expect(isDraftDirty({ draft: spaced, snapshot })).toBe(false);
    const named = setDisplayName({ draft: blank, value: "x" });
    expect(isDraftDirty({ draft: named, snapshot })).toBe(true);
  });

  it("is clean for a needs-attention draft opened with pre-set errors", () => {
    const entry = entryFor({
      definition: seededDefinition(),
      errors: { "steps.0.event_name": ["gone"], __root__: ["x"] },
    });
    const draft = draftFromEntry({ entry });
    const plain = draftFromEntry({
      entry: entryFor({ definition: seededDefinition() }),
    });
    expect(
      isDraftDirty({ draft, snapshot: normalizeDraft({ draft: plain }) }),
    ).toBe(false);
  });

  it("treats a missing key and null as equal", () => {
    const withNull = draftFromEntry({
      entry: entryFor({
        definition: { steps: [{ stream: "ui", label: "A", dim_filter: null }] },
      }),
    });
    const missing = draftFromEntry({
      entry: entryFor({
        definition: { steps: [{ stream: "ui", label: "A" }] },
      }),
    });
    expect(
      isDraftDirty({
        draft: missing,
        snapshot: normalizeDraft({ draft: withNull }),
      }),
    ).toBe(false);
  });
});

describe("moveStep and removeStep edge cases", () => {
  it("no-ops at boundaries and for unknown keys", () => {
    const base = seededDraft();
    const first = base.steps[0].key;
    const last = base.steps[2].key;
    expect(moveStep({ draft: base, key: first, direction: "up" })).toBe(base);
    expect(moveStep({ draft: base, key: last, direction: "down" })).toBe(base);
    expect(moveStep({ draft: base, key: -1, direction: "up" })).toBe(base);
    expect(removeStep({ draft: base, key: -1 }).steps).toEqual(base.steps);
  });
});

describe("applyServerErrors", () => {
  it("sends out-of-range and suffix-less step paths to form level", () => {
    const base = seededDraft();
    const submittedKeys = base.steps.map((step) => step.key);
    const draft = applyServerErrors({
      draft: base,
      errors: { "steps.99.label": ["far"], "steps.0": ["whole"] },
      submittedKeys,
    });
    expect(draft.serverErrors.map((error) => error.field)).toEqual([
      "form",
      "form",
    ]);
    expect(draft.serverErrors.map((error) => error.message)).toEqual([
      "steps.99.label: far",
      "steps.0: whole",
    ]);
    expect(
      draft.steps.every((step) => Object.keys(step.errors).length === 0),
    ).toBe(true);
  });

  it("lands on the right step by key after a reorder", () => {
    const base = seededDraft();
    const submittedKeys = base.steps.map((step) => step.key);
    const moved = moveStep({
      draft: base,
      key: submittedKeys[2],
      direction: "up",
    });
    const draft = applyServerErrors({
      draft: moved,
      errors: { "steps.2.event_name": ["bad"], "steps.0.label": ["short"] },
      submittedKeys,
    });
    const byKey = new Map(draft.steps.map((step) => [step.key, step]));
    expect(byKey.get(submittedKeys[2])?.errors.event_name).toEqual(["bad"]);
    expect(byKey.get(submittedKeys[0])?.errors.label).toEqual(["short"]);
  });

  it("surfaces at form level when the submitted step was removed", () => {
    const base = seededDraft();
    const submittedKeys = base.steps.map((step) => step.key);
    const removed = removeStep({ draft: base, key: submittedKeys[2] });
    const draft = applyServerErrors({
      draft: removed,
      errors: { "steps.2.event_name": ["bad"] },
      submittedKeys,
    });
    expect(
      draft.steps.every((step) => Object.keys(step.errors).length === 0),
    ).toBe(true);
    expect(draft.serverErrors).toHaveLength(1);
    expect(draft.serverErrors[0]).toMatchObject({
      field: "form",
      stepKey: null,
    });
    expect(draft.serverErrors[0].message).toContain("bad");
  });

  it("maps hidden-field paths, step count and unknown paths", () => {
    const base = seededDraft();
    const submittedKeys = base.steps.map((step) => step.key);
    const draft = applyServerErrors({
      draft: base,
      errors: {
        "steps.0.dim_filter.1": ["bad filter"],
        "steps.0.drop_breakdown.group_by": ["bad group"],
        steps: ["too few"],
        "steps.1.stream": ["odd"],
        mystery: ["??"],
        __root__: ["root"],
      },
      submittedKeys,
    });
    expect(draft.steps[0].errors.hidden).toEqual(["bad filter", "bad group"]);
    const fields = draft.serverErrors.map((error) => error.field);
    expect(fields).toEqual(["steps", "form", "form", "form"]);
    expect(draft.serverErrors.map((error) => error.message)).toEqual(
      expect.arrayContaining(["too few", "root"]),
    );
  });

  it("replaces errors from an earlier submit", () => {
    const base = seededDraft();
    const keys = base.steps.map((step) => step.key);
    const first = applyServerErrors({
      draft: base,
      errors: { "steps.0.label": ["x"] },
      submittedKeys: keys,
    });
    const second = applyServerErrors({
      draft: first,
      errors: {},
      submittedKeys: keys,
    });
    expect(second.steps[0].errors).toEqual({});
    expect(second.serverErrors).toEqual([]);
  });
});

describe("validateDraft", () => {
  it("accepts a filled draft", () => {
    expect(validateDraft({ draft: filledDraft() })).toEqual([]);
  });

  it("rejects whitespace-only name and label", () => {
    let draft = filledDraft();
    draft = setDisplayName({ draft, value: "   " });
    draft = setStepLabel({ draft, key: draft.steps[0].key, value: "  " });
    const errors = validateDraft({ draft });
    expect(errors.map((error) => error.field)).toEqual([
      "display_name",
      "label",
    ]);
    expect(errors[1].stepKey).toBe(draft.steps[0].key);
  });

  it("rejects 1 and 9 steps", () => {
    let draft = filledDraft();
    draft = removeStep({ draft, key: draft.steps[0].key });
    expect(validateDraft({ draft }).map((error) => error.field)).toEqual([
      "steps",
    ]);
    draft = filledDraft();
    for (let count = 0; count < 7; count += 1) {
      draft = addStep({ draft });
    }
    expect(draft.steps).toHaveLength(9);
    const fields = validateDraft({ draft }).map((error) => error.field);
    expect(fields).toContain("steps");
  });

  it("accepts 2 and 8 steps", () => {
    let draft = filledDraft();
    expect(draft.steps).toHaveLength(2);
    expect(validateDraft({ draft })).toEqual([]);
    for (let count = 0; count < 6; count += 1) {
      draft = addStep({ draft });
      const added = draft.steps[draft.steps.length - 1];
      draft = setStepLabel({ draft, key: added.key, value: "Step" });
      draft = setStepEvent({
        draft,
        key: added.key,
        eventName: "modal_open",
      });
    }
    expect(draft.steps).toHaveLength(8);
    expect(validateDraft({ draft })).toEqual([]);
  });

  it("gives the label length message for a 65-character label", () => {
    const draft = filledDraft();
    const errors = validateDraft({
      draft: setStepLabel({
        draft,
        key: draft.steps[0].key,
        value: "l".repeat(65),
      }),
    });
    expect(errors).toHaveLength(1);
    expect(errors[0].message).toBe("Enter a label of 1 to 64 characters.");
  });

  it("accepts a 64-character name and rejects 65", () => {
    const draft = filledDraft();
    expect(
      validateDraft({
        draft: setDisplayName({ draft, value: "n".repeat(64) }),
      }),
    ).toEqual([]);
    const errors = validateDraft({
      draft: setDisplayName({ draft, value: "n".repeat(65) }),
    });
    expect(errors.map((error) => error.field)).toEqual(["display_name"]);
  });

  it("requires event, or endpoint plus method for an api step", () => {
    let draft = filledDraft();
    const [first, second] = draft.steps;
    draft = setStepEvent({ draft, key: first.key, eventName: null });
    draft = setStepStream({ draft, key: second.key, stream: "api" });
    const errors = validateDraft({ draft });
    expect(errors.map((error) => error.field)).toEqual([
      "event_name",
      "api_endpoint",
      "api_method",
    ]);
  });
});

describe("error surfaces", () => {
  it("applyValidationErrors puts name errors on the draft and step errors on steps", () => {
    const draft = createBlankDraft();
    const errors = validateDraft({ draft });
    const next = applyValidationErrors({ draft, errors });
    expect(next.serverErrors.map((error) => error.field)).toEqual([
      "display_name",
    ]);
    expect(next.steps[0].errors.label).toHaveLength(1);
    expect(next.steps[1].errors.event_name).toHaveLength(1);
  });

  it("applyValidationErrors keeps a rejected hidden-field error until it is cleared", () => {
    const base = draftFromEntry({
      entry: entryFor({ definition: seededDefinition() }),
    });
    const withHidden = applyServerErrors({
      draft: base,
      errors: { "steps.0.dim_filter.0": ["Bad filter."] },
      submittedKeys: base.steps.map((step) => step.key),
    });
    const kept = applyValidationErrors({
      draft: withHidden,
      errors: validateDraft({ draft: withHidden }),
    });
    expect(kept.steps[0].errors.hidden).toEqual(["Bad filter."]);
    const cleared = {
      ...withHidden,
      steps: withHidden.steps.map((step, index) =>
        index === 0 ? { ...step, hiddenCleared: true } : step,
      ),
    };
    const dropped = applyValidationErrors({
      draft: cleared,
      errors: validateDraft({ draft: cleared }),
    });
    expect(dropped.steps[0].errors.hidden).toBeUndefined();
  });

  it("listProblems orders name, steps count, then each step's fields; skips form errors", () => {
    const base = draftFromEntry({
      entry: entryFor({ definition: seededDefinition() }),
    });
    let draft = applyServerErrors({
      draft: base,
      errors: {
        display_name: ["Taken."],
        "steps.1.label": ["Short."],
        "steps.0.dim_filter.0": ["Bad filter."],
        stray: ["Odd."],
      },
      submittedKeys: base.steps.map((step) => step.key),
    });
    draft = setFormErrors({ draft, messages: ["Form-level."] });
    const problems = listProblems({ draft });
    expect(
      problems.map((problem) => [problem.stepNumber, problem.field]),
    ).toEqual([
      [null, "display_name"],
      [1, "hidden"],
      [2, "label"],
    ]);
    expect(listFormErrors({ draft })).toEqual(["Form-level."]);
  });

  it("clearDraftError removes one field's errors and setFormErrors replaces form errors", () => {
    let draft = applyServerErrors({
      draft: createBlankDraft(),
      errors: { display_name: ["Taken."], __root__: ["Full."] },
      submittedKeys: [],
    });
    draft = clearDraftError({ draft, field: "display_name" });
    expect(listProblems({ draft })).toEqual([]);
    expect(listFormErrors({ draft })).toEqual(["Full."]);
    draft = setFormErrors({ draft, messages: ["Again."] });
    expect(listFormErrors({ draft })).toEqual(["Again."]);
  });

  it("summarizeHidden counts filters and detects a breakdown", () => {
    const draft = draftFromEntry({
      entry: entryFor({ definition: seededDefinition() }),
    });
    expect(summarizeHidden({ step: draft.steps[0] })).toEqual({
      filterCount: 2,
      hasBreakdown: true,
    });
    expect(summarizeHidden({ step: createBlankDraft().steps[0] })).toEqual({
      filterCount: 0,
      hasBreakdown: false,
    });
  });
});

describe("catalog helpers", () => {
  it("lists only step_allowed events in the stream's category", () => {
    expect(
      listEventOptions({ catalog: CATALOG, stream: "ui" }).map(
        (event) => event.event_name,
      ),
    ).toEqual(["modal_open"]);
    expect(listEventOptions({ catalog: CATALOG, stream: "api" })).toEqual([]);
  });

  it("groups endpoints by blueprint and lists methods", () => {
    const groups = listEndpointGroups({ catalog: CATALOG });
    expect(groups.map((group) => group.blueprint)).toEqual(["urls", "utubs"]);
    expect(groups[0].endpoints).toHaveLength(2);
    expect(
      listMethods({ catalog: CATALOG, endpoint: "urls.update_url" }),
    ).toEqual(["GET", "PUT"]);
    expect(listMethods({ catalog: CATALOG, endpoint: "nope" })).toEqual([]);
  });

  it("reports stale values without coercing them", () => {
    const stale = ({
      stream,
      eventName,
    }: {
      stream: StepStream;
      eventName: string | null;
    }) => isStaleEvent({ catalog: CATALOG, stream, eventName });
    expect(stale({ stream: "ui", eventName: "modal_open" })).toBe(false);
    expect(stale({ stream: "ui", eventName: "removed_event" })).toBe(true);
    expect(stale({ stream: "ui", eventName: "url_created" })).toBe(true);
    expect(stale({ stream: "ui", eventName: "ui_hidden" })).toBe(true);
    expect(stale({ stream: "ui", eventName: null })).toBe(false);
    expect(stale({ stream: "api", eventName: "anything" })).toBe(false);

    expect(
      isStaleEndpoint({ catalog: CATALOG, apiEndpoint: "urls.create_url" }),
    ).toBe(false);
    expect(isStaleEndpoint({ catalog: CATALOG, apiEndpoint: "gone.x" })).toBe(
      true,
    );
    expect(
      isStaleMethod({
        catalog: CATALOG,
        apiEndpoint: "urls.create_url",
        apiMethod: "DELETE",
      }),
    ).toBe(true);
    expect(
      isStaleMethod({
        catalog: CATALOG,
        apiEndpoint: "urls.create_url",
        apiMethod: "POST",
      }),
    ).toBe(false);
    expect(
      isStaleMethod({
        catalog: CATALOG,
        apiEndpoint: "gone.x",
        apiMethod: "GET",
      }),
    ).toBe(true);
  });

  it("does not mutate the draft on edits", () => {
    const base = filledDraft();
    const before = JSON.stringify(base);
    setStepLabel({ draft: base, key: base.steps[0].key, value: "zzz" });
    moveStep({ draft: base, key: base.steps[0].key, direction: "down" });
    expect(JSON.stringify(base)).toBe(before);
  });
});
