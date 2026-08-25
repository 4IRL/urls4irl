import {
  cancelCoMemberCandidatesFetch,
  loadCoMemberCandidates,
} from "../co-member-fetch.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { setState } from "../../../store/app-store.js";

// co-member-fetch.ts is the members-deck twin of cross-utub-search.ts's fetch
// path (abort-and-replace over a single module-scoped in-flight jqXHR). This
// spec mirrors cross-utub-search.test.ts: ajaxCall + is429Handled are mocked and
// each jqXHR is hand-built to fire .done/.fail synchronously so the store writes
// can be asserted without real async.
vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../../store/app-store.js", () => ({
  setState: vi.fn(),
}));

// A jqXHR whose .done fires synchronously with `{ members }`.
function buildDoneXhr(members: unknown[]): JQuery.jqXHR {
  return {
    done: vi.fn(function (
      this: JQuery.jqXHR,
      cb: (data: { members: unknown[] }) => void,
    ) {
      cb({ members });
      return this;
    }),
    fail: vi.fn().mockReturnThis(),
    always: vi.fn().mockReturnThis(),
    abort: vi.fn(),
  } as unknown as JQuery.jqXHR;
}

// A jqXHR whose .fail fires synchronously with `{ status }`.
function buildFailXhr(status: number): JQuery.jqXHR {
  return {
    done: vi.fn().mockReturnThis(),
    fail: vi.fn(function (
      this: JQuery.jqXHR,
      cb: (xhr: { status: number }) => void,
    ) {
      cb({ status });
      return this;
    }),
    always: vi.fn().mockReturnThis(),
    abort: vi.fn(),
  } as unknown as JQuery.jqXHR;
}

// A jqXHR that never settles (neither .done nor .fail fire) — used to probe the
// abort-and-replace / teardown-abort behavior against a live in-flight request.
function buildPendingXhr(): JQuery.jqXHR {
  return {
    done: vi.fn().mockReturnThis(),
    fail: vi.fn().mockReturnThis(),
    always: vi.fn().mockReturnThis(),
    abort: vi.fn(),
  } as unknown as JQuery.jqXHR;
}

beforeEach(() => {
  // Reset the module-scoped in-flight guard between tests, then clear mock state.
  cancelCoMemberCandidatesFetch();
  vi.clearAllMocks();
  vi.mocked(is429Handled).mockReturnValue(false);
});

describe("co-member-fetch — loadCoMemberCandidates", () => {
  it("(1) success: writes the candidate list + loaded flag to the store and calls onSettle", () => {
    const members = [{ id: 1, username: "Bob", sharedUtubCount: 2 }];
    vi.mocked(ajaxCall).mockReturnValue(buildDoneXhr(members));
    const onSettle = vi.fn();

    loadCoMemberCandidates(7, onSettle);

    // Fetches the co-member candidates route for the target UTub (GET, no body).
    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(1);
    const [method, url, body] = vi.mocked(ajaxCall).mock.calls[0];
    expect(method).toBe("GET");
    expect(url).toBe(APP_CONFIG.routes.coMemberCandidates(7));
    expect(body).toBeNull();

    expect(vi.mocked(setState)).toHaveBeenCalledWith({
      coMemberCandidates: members,
      coMemberCandidatesLoaded: true,
    });
    expect(onSettle).toHaveBeenCalledTimes(1);
  });

  it("(2) 429: returns early — store untouched, onSettle not called", () => {
    vi.mocked(ajaxCall).mockReturnValue(buildFailXhr(429));
    vi.mocked(is429Handled).mockReturnValue(true);
    const onSettle = vi.fn();

    loadCoMemberCandidates(7, onSettle);

    expect(vi.mocked(setState)).not.toHaveBeenCalled();
    expect(onSettle).not.toHaveBeenCalled();
  });

  it("(3) status 0 (aborted): store untouched, onSettle not called", () => {
    vi.mocked(ajaxCall).mockReturnValue(buildFailXhr(0));
    const onSettle = vi.fn();

    loadCoMemberCandidates(7, onSettle);

    // A newer fetch (abort-and-replace) owns the store; this stale aborted one
    // must not degrade it to empty.
    expect(vi.mocked(setState)).not.toHaveBeenCalled();
    expect(onSettle).not.toHaveBeenCalled();
  });

  it("(4) generic failure: degrades to an empty list with loaded=true and calls onSettle", () => {
    vi.mocked(ajaxCall).mockReturnValue(buildFailXhr(500));
    const onSettle = vi.fn();

    loadCoMemberCandidates(7, onSettle);

    expect(vi.mocked(setState)).toHaveBeenCalledWith({
      coMemberCandidates: [],
      coMemberCandidatesLoaded: true,
    });
    expect(onSettle).toHaveBeenCalledTimes(1);
  });

  it("(5) abort-and-replace: a second load aborts the first in-flight request before firing", () => {
    const first = buildPendingXhr();
    const second = buildPendingXhr();
    vi.mocked(ajaxCall).mockReturnValueOnce(first).mockReturnValueOnce(second);

    loadCoMemberCandidates(7);
    loadCoMemberCandidates(7);

    expect(first.abort).toHaveBeenCalledTimes(1);
    expect(second.abort).not.toHaveBeenCalled();
    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(2);
  });
});

describe("co-member-fetch — cancelCoMemberCandidatesFetch", () => {
  it("(6) aborts the in-flight request without mutating the store", () => {
    const inFlight = buildPendingXhr();
    vi.mocked(ajaxCall).mockReturnValue(inFlight);

    loadCoMemberCandidates(7);
    cancelCoMemberCandidatesFetch();

    expect(inFlight.abort).toHaveBeenCalledTimes(1);
    // Teardown must never degrade the slice — the aborted request surfaces as
    // status 0, which the .fail handler ignores.
    expect(vi.mocked(setState)).not.toHaveBeenCalled();
  });
});
