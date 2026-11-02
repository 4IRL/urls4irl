import { ajaxCall } from "../../../lib/ajax.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { getState, resetStore } from "../../../store/app-store.js";
import {
  createMockJqXHR,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { removeUTubLocally } from "../../utubs/remove-local.js";
import { PATCH_TIMEOUT_MS, patchMemberListPreferences } from "../client.js";

vi.mock("../../../lib/ajax.js", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/ajax.js")>(
    "../../../lib/ajax.js",
  );
  return { ...actual, ajaxCall: vi.fn() };
});
vi.mock("../../utubs/remove-local.js", () => ({ removeUTubLocally: vi.fn() }));
vi.mock("../../urls/deck.js", () => ({ showURLDeckBannerError: vi.fn() }));

const ECHO = {
  status: "Success",
  message: "ok",
  memberSort: "role_then_name",
};

function start(): {
  request: ReturnType<typeof createMockJqXHR>;
  result: ReturnType<typeof patchMemberListPreferences>;
} {
  const request = createMockJqXHR();
  vi.mocked(ajaxCall).mockReturnValue(request);
  const result = patchMemberListPreferences({
    patch: { memberSort: "role_then_name" },
  });
  return { request, result };
}

describe("patchMemberListPreferences", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
  });

  it("PATCHes the members route with exactly the patch and the write timeout", async () => {
    const { request, result } = start();
    request.resolve(ECHO);
    await result;

    expect(ajaxCall).toHaveBeenCalledWith(
      "patch",
      APP_CONFIG.routes.updateMemberListPreferences,
      { memberSort: "role_then_name" },
      PATCH_TIMEOUT_MS,
    );
  });

  it("returns the echoed sort, also for a No change echo", async () => {
    const { request, result } = start();
    request.resolve({ ...ECHO, status: "No change" });

    await expect(result).resolves.toEqual({
      outcome: "ok",
      preferences: { memberSort: "role_then_name" },
    });
  });

  it.each([
    ["an HTML body", "<html></html>"],
    ["a null body", null],
    ["a bad status", { ...ECHO, status: "Failure" }],
    ["a bad sort", { ...ECHO, memberSort: "random" }],
    ["a missing sort", { ...ECHO, memberSort: undefined }],
  ])("treats %s on a 200 as an error", async (_label, body) => {
    const { request, result } = start();
    request.resolve(body);

    await expect(result).resolves.toEqual({
      outcome: "failed",
      result: { outcome: "error" },
      timedOut: false,
    });
  });

  it.each([
    [400, "invalid"],
    [500, "error"],
    [404, "gone"],
  ])(
    "maps status %i to %s without UTub-gone handling",
    async (status, outcome) => {
      const { request, result } = start();
      request.reject(
        createMockXhr({
          status,
          responseJSON: { message: APP_CONFIG.strings.NOT_AUTHORIZED },
          getResponseHeader: () => "application/json",
        }),
      );

      await expect(result).resolves.toMatchObject({
        outcome: "failed",
        result: { outcome },
        timedOut: false,
      });
      expect(removeUTubLocally).not.toHaveBeenCalled();
    },
  );

  it.each([
    [403, true, "error"],
    [405, true, "error"],
  ])("maps an HTML status %i body to %s", async (status, _html, outcome) => {
    const { request, result } = start();
    request.reject(
      createMockXhr({
        status,
        responseJSON: undefined,
        getResponseHeader: () => "text/html",
      }),
    );

    await expect(result).resolves.toMatchObject({
      outcome: "failed",
      result: { outcome },
    });
    expect(removeUTubLocally).not.toHaveBeenCalled();
  });

  it("maps a handled 429 to an error without a resync", async () => {
    const { request, result } = start();
    request.reject(
      createMockXhr({
        status: 429,
        _429Handled: true,
        getResponseHeader: () => "text/html",
      }),
    );

    await expect(result).resolves.toEqual({
      outcome: "failed",
      result: { outcome: "error", resync: false },
      timedOut: false,
    });
  });

  it("works with no UTub selected", async () => {
    expect(getState().activeUTubID).toBeNull();
    const { request, result } = start();
    request.resolve(ECHO);

    await expect(result).resolves.toMatchObject({ outcome: "ok" });
  });

  it("flags a status 0 failure as a timeout", async () => {
    const { request, result } = start();
    request.reject(createMockXhr({ status: 0 }));

    await expect(result).resolves.toEqual({
      outcome: "failed",
      result: { outcome: "error" },
      timedOut: true,
    });
  });
});
