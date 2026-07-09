/**
 * Unit tests for the fragment-swap helpers used by all admin portal dynamic
 * surfaces (health, user search, audit log).
 */

import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../__tests__/helpers/mock-jquery.js";
import { ajaxCallFragment, is429Handled } from "../../lib/ajax.js";
import {
  bindPaginationLinks,
  fetchAndSwap,
  makeDebouncer,
} from "../fragment-swap.js";

vi.mock("../../lib/ajax.js", () => ({
  ajaxCallFragment: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

describe("fetchAndSwap", () => {
  beforeEach(() => {
    vi.mocked(ajaxCallFragment).mockReset();
    vi.mocked(is429Handled).mockReset();
    vi.mocked(is429Handled).mockReturnValue(false);
  });

  it("calls ajaxCallFragment with the provided url and default timeout", () => {
    vi.mocked(ajaxCallFragment).mockReturnValue(createMockJqXHRChainable());
    const target = document.createElement("div");

    fetchAndSwap({ url: "/admin/health/snapshot", targetEl: target });

    expect(ajaxCallFragment).toHaveBeenCalledWith(
      "/admin/health/snapshot",
      5_000,
    );
  });

  it("calls ajaxCallFragment with a custom timeout when provided", () => {
    vi.mocked(ajaxCallFragment).mockReturnValue(createMockJqXHRChainable());
    const target = document.createElement("div");

    fetchAndSwap({
      url: "/admin/users/search",
      targetEl: target,
      timeout: 3_000,
    });

    expect(ajaxCallFragment).toHaveBeenCalledWith("/admin/users/search", 3_000);
  });

  it("sets targetEl innerHTML to the response string on success", () => {
    const HTML_FRAGMENT = "<p>Hello admin</p>";
    let capturedDone: ((html: string) => void) | undefined;
    vi.mocked(ajaxCallFragment).mockReturnValue(
      createMockJqXHRChainable({
        done: (cb) => {
          capturedDone = cb as (html: string) => void;
        },
      }),
    );

    const target = document.createElement("div");
    fetchAndSwap({ url: "/admin/health/snapshot", targetEl: target });
    capturedDone?.(HTML_FRAGMENT);

    expect(target.innerHTML).toBe(HTML_FRAGMENT);
  });

  it("calls is429Handled on failure", () => {
    const mockXhr = createMockXhr();
    let capturedFail: ((xhr: JQuery.jqXHR) => void) | undefined;
    vi.mocked(ajaxCallFragment).mockReturnValue(
      createMockJqXHRChainable({
        fail: (cb) => {
          capturedFail = cb as (xhr: JQuery.jqXHR) => void;
        },
      }),
    );

    const target = document.createElement("div");
    fetchAndSwap({ url: "/admin/health/snapshot", targetEl: target });
    capturedFail?.(mockXhr as JQuery.jqXHR);

    expect(is429Handled).toHaveBeenCalledWith(mockXhr);
  });

  it("does not set innerHTML when the request fails", () => {
    const INITIAL_HTML = "<p>existing content</p>";
    let capturedFail: ((xhr: JQuery.jqXHR) => void) | undefined;
    vi.mocked(ajaxCallFragment).mockReturnValue(
      createMockJqXHRChainable({
        fail: (cb) => {
          capturedFail = cb as (xhr: JQuery.jqXHR) => void;
        },
      }),
    );

    const target = document.createElement("div");
    target.innerHTML = INITIAL_HTML;
    fetchAndSwap({ url: "/admin/health/snapshot", targetEl: target });
    capturedFail?.(createMockXhr() as JQuery.jqXHR);

    expect(target.innerHTML).toBe(INITIAL_HTML);
  });
});

describe("makeDebouncer", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("delays execution by the specified delay", () => {
    const fn = vi.fn();
    const debounced = makeDebouncer(fn, 500);

    debounced();

    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(499);
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("resets the timer on repeated calls so fn fires only once after the last call", () => {
    const fn = vi.fn();
    const debounced = makeDebouncer(fn, 500);

    debounced();
    vi.advanceTimersByTime(400);
    debounced();
    vi.advanceTimersByTime(400);
    expect(fn).not.toHaveBeenCalled();

    vi.advanceTimersByTime(100);
    expect(fn).toHaveBeenCalledTimes(1);
  });

  it("fires again on subsequent calls after the first debounce window elapses", () => {
    const fn = vi.fn();
    const debounced = makeDebouncer(fn, 500);

    debounced();
    vi.advanceTimersByTime(500);
    expect(fn).toHaveBeenCalledTimes(1);

    debounced();
    vi.advanceTimersByTime(500);
    expect(fn).toHaveBeenCalledTimes(2);
  });
});

describe("bindPaginationLinks", () => {
  const FRAGMENT_URL = "/admin/users/search?offset=10";

  beforeEach(() => {
    vi.mocked(ajaxCallFragment).mockReset();
    vi.mocked(ajaxCallFragment).mockReturnValue(createMockJqXHRChainable());
    document.body.innerHTML = "";
  });

  function buildPaginationFixture(): {
    containerEl: HTMLElement;
    targetEl: HTMLElement;
    link: HTMLAnchorElement;
  } {
    const containerEl = document.createElement("div");
    const targetEl = document.createElement("div");
    const link = document.createElement("a");
    link.href = "#";
    link.setAttribute("data-fragment-href", FRAGMENT_URL);
    containerEl.appendChild(link);
    document.body.appendChild(containerEl);
    document.body.appendChild(targetEl);
    return { containerEl, targetEl, link };
  }

  it("fetches the data-fragment-href URL when a pagination link is clicked", () => {
    const { containerEl, targetEl, link } = buildPaginationFixture();

    bindPaginationLinks({ containerEl, targetEl });
    link.dispatchEvent(
      new MouseEvent("click", { bubbles: true, cancelable: true }),
    );

    expect(ajaxCallFragment).toHaveBeenCalledWith(
      FRAGMENT_URL,
      expect.any(Number),
    );
  });

  it("prevents the default navigation when a pagination link is clicked", () => {
    const { containerEl, targetEl, link } = buildPaginationFixture();

    bindPaginationLinks({ containerEl, targetEl });

    const clickEvent = new MouseEvent("click", {
      bubbles: true,
      cancelable: true,
    });
    link.dispatchEvent(clickEvent);

    expect(clickEvent.defaultPrevented).toBe(true);
  });

  it("does not fetch when a non-pagination element inside the container is clicked", () => {
    const { containerEl, targetEl } = buildPaginationFixture();
    const regularButton = document.createElement("button");
    containerEl.appendChild(regularButton);

    bindPaginationLinks({ containerEl, targetEl });
    regularButton.dispatchEvent(
      new MouseEvent("click", { bubbles: true, cancelable: true }),
    );

    // Only the initial ajaxCallFragment for the pagination link should not fire here
    expect(ajaxCallFragment).not.toHaveBeenCalled();
  });

  it("still handles clicks on pagination links dynamically added after binding", () => {
    const { containerEl, targetEl } = buildPaginationFixture();
    bindPaginationLinks({ containerEl, targetEl });

    // Add a new pagination link after binding (simulates innerHTML swap)
    const newLink = document.createElement("a");
    newLink.href = "#";
    newLink.setAttribute("data-fragment-href", "/admin/users/search?offset=20");
    containerEl.appendChild(newLink);

    newLink.dispatchEvent(
      new MouseEvent("click", { bubbles: true, cancelable: true }),
    );

    expect(ajaxCallFragment).toHaveBeenCalledWith(
      "/admin/users/search?offset=20",
      expect.any(Number),
    );
  });

  it("removes the previous click handler when called a second time (idempotent rebind)", () => {
    const { containerEl, targetEl, link } = buildPaginationFixture();

    bindPaginationLinks({ containerEl, targetEl });
    bindPaginationLinks({ containerEl, targetEl });

    link.dispatchEvent(
      new MouseEvent("click", { bubbles: true, cancelable: true }),
    );

    // Should fire exactly once despite two bindPaginationLinks calls
    expect(ajaxCallFragment).toHaveBeenCalledTimes(1);
  });
});
