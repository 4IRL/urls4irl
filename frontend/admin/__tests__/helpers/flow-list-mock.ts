/**
 * Shared stubs for the admin flow-list endpoint in dashboard Vitest suites.
 */

export interface ListEntryOverrides {
  id: string;
  display_name?: string;
  is_builtin?: boolean;
  errors?: Record<string, string[]>;
  first_invalid?: {
    step_index: number | null;
    field: string;
    reason: string;
  } | null;
}

export function makeListEntry({
  id,
  display_name = id,
  is_builtin = true,
  errors = {},
  first_invalid = null,
}: ListEntryOverrides) {
  return {
    id,
    display_name,
    is_builtin,
    definition: {},
    errors,
    first_invalid,
  };
}

/**
 * A list xhr that is already resolved with `entries`: `.done` fires at once.
 * `abort()` is a no-op (the request has settled).
 */
export function makeResolvedFlowListXhr({
  entries,
}: {
  entries: ReturnType<typeof makeListEntry>[];
}): JQuery.jqXHR {
  const response = { flows: entries };
  const xhr = {
    status: 200,
    readyState: 4,
    done: (callback: (value: unknown) => void) => {
      callback(response);
      return xhr;
    },
    fail: () => xhr,
    always: (callback: () => void) => {
      callback();
      return xhr;
    },
    abort: () => {},
  };
  return xhr as unknown as JQuery.jqXHR;
}

/** The four built-in ids as list entries (the default Flows-tab list). */
export function makeBuiltinListXhr({
  ids,
}: {
  ids: readonly string[];
}): JQuery.jqXHR {
  return makeResolvedFlowListXhr({
    entries: ids.map((id) => makeListEntry({ id })),
  });
}
