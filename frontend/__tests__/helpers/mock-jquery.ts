// Partial mocks require `as unknown as` because jqXHR/Modal have ~30 required properties we don't need in tests.
type AjaxCallback = (...args: unknown[]) => unknown;

interface MockJqXHRDeferred extends JQuery.jqXHR {
  resolve: JQuery.Deferred<unknown>["resolve"];
  reject: JQuery.Deferred<unknown>["reject"];
  notify: JQuery.Deferred<unknown>["notify"];
}

export function createMockJqXHR(): MockJqXHRDeferred {
  return $.Deferred() as unknown as MockJqXHRDeferred;
}

export function createMockJqXHRChainable(overrides?: {
  done?: AjaxCallback;
  fail?: AjaxCallback;
  always?: AjaxCallback;
}): JQuery.jqXHR {
  const chainable: Record<string, ReturnType<typeof vi.fn>> = {
    done: vi.fn().mockReturnThis(),
    fail: vi.fn().mockReturnThis(),
    always: vi.fn().mockReturnThis(),
  };

  if (overrides?.done) {
    chainable.done.mockImplementation((...args: unknown[]) => {
      overrides.done!(...args);
      return chainable;
    });
  }
  if (overrides?.fail) {
    chainable.fail.mockImplementation((...args: unknown[]) => {
      overrides.fail!(...args);
      return chainable;
    });
  }
  if (overrides?.always) {
    chainable.always.mockImplementation((...args: unknown[]) => {
      overrides.always!(...args);
      return chainable;
    });
  }

  return chainable as unknown as JQuery.jqXHR;
}

export function createImmediateAlwaysJqXHR(): JQuery.jqXHR {
  return {
    always: vi.fn((callback: AjaxCallback) => {
      callback();
      return { always: vi.fn() };
    }),
  } as unknown as JQuery.jqXHR;
}

export function createMockXhr(
  props: Record<string, unknown> = {},
): JQuery.jqXHR {
  return {
    setRequestHeader: vi.fn(),
    ...props,
  } as unknown as JQuery.jqXHR;
}

export function createMockModal(overrides?: {
  show?: ReturnType<typeof vi.fn>;
  hide?: ReturnType<typeof vi.fn>;
}): bootstrap.Modal {
  return {
    show: overrides?.show ?? vi.fn(),
    hide: overrides?.hide ?? vi.fn(),
  } as unknown as bootstrap.Modal;
}
