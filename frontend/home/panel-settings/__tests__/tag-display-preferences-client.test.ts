import { ajaxCall } from "../../../lib/ajax.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { getState, resetStore } from "../../../store/app-store.js";
import {
  createMockJqXHR,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { removeUTubLocally } from "../../utubs/remove-local.js";
import { PATCH_TIMEOUT_MS, patchTagDisplayPreferences } from "../client.js";

vi.mock("../../../lib/ajax.js", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/ajax.js")>(
    "../../../lib/ajax.js",
  );
  return { ...actual, ajaxCall: vi.fn() };
});
vi.mock("../../utubs/remove-local.js", () => ({ removeUTubLocally: vi.fn() }));
vi.mock("../../urls/deck.js", () => ({ showURLDeckBannerError: vi.fn() }));

const PREFERENCES = {
  tagSort: "name_az",
  tagMatchMode: "any",
  tagCountStyle: "total_only",
  showTagsOnCollapsed: true,
  collapsedTagsStyle: "all",
  tagDropOpensUrl: false,
};

const ECHO = { status: "Success", message: "ok", ...PREFERENCES };

function start(): {
  request: ReturnType<typeof createMockJqXHR>;
  result: ReturnType<typeof patchTagDisplayPreferences>;
} {
  const request = createMockJqXHR();
  vi.mocked(ajaxCall).mockReturnValue(request);
  const result = patchTagDisplayPreferences({ patch: { tagSort: "name_az" } });
  return { request, result };
}

describe("patchTagDisplayPreferences", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
  });

  it("PATCHes the tags route with exactly the patch and the write timeout", async () => {
    const { request, result } = start();
    request.resolve(ECHO);
    await result;

    expect(ajaxCall).toHaveBeenCalledWith(
      "patch",
      APP_CONFIG.routes.updateTagDisplayPreferences,
      { tagSort: "name_az" },
      PATCH_TIMEOUT_MS,
    );
  });

  it("returns all six echoed values, also for a No change echo", async () => {
    const { request, result } = start();
    request.resolve({ ...ECHO, status: "No change" });

    await expect(result).resolves.toEqual({
      outcome: "ok",
      preferences: PREFERENCES,
    });
  });

  it("writes no store on a valid echo", async () => {
    const before = getState().preferences;
    const { request, result } = start();
    request.resolve(ECHO);
    await result;

    expect(getState().preferences).toEqual(before);
    expect(getState().tagDisplayVersion).toBe(0);
  });

  it.each([
    ["an HTML body", "<html></html>"],
    ["a null body", null],
    ["a bad status", { ...ECHO, status: "Failure" }],
    ["a bad sort", { ...ECHO, tagSort: "random" }],
    ["a missing sort", { ...ECHO, tagSort: undefined }],
    ["a bad match mode", { ...ECHO, tagMatchMode: "some" }],
    ["a bad count style", { ...ECHO, tagCountStyle: 2 }],
    ["a non-boolean collapsed switch", { ...ECHO, showTagsOnCollapsed: "y" }],
    ["a bad collapsed style", { ...ECHO, collapsedTagsStyle: "none" }],
    ["a non-boolean drop switch", { ...ECHO, tagDropOpensUrl: null }],
  ])(
    "treats %s on a 200 as an error and writes no store",
    async (_label, body) => {
      const before = getState().preferences;
      const { request, result } = start();
      request.resolve(body);

      await expect(result).resolves.toEqual({
        outcome: "failed",
        result: { outcome: "error" },
        timedOut: false,
      });
      expect(getState().preferences).toEqual(before);
    },
  );

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

  it("works with no UTub selected", async () => {
    expect(getState().activeUTubID).toBeNull();
    const { request, result } = start();
    request.resolve(ECHO);

    await expect(result).resolves.toMatchObject({ outcome: "ok" });
  });

  it("flags a status 0 failure as a timeout and writes no store", async () => {
    const before = getState().preferences;
    const { request, result } = start();
    request.reject(createMockXhr({ status: 0 }));

    await expect(result).resolves.toEqual({
      outcome: "failed",
      result: { outcome: "error" },
      timedOut: true,
    });
    expect(getState().preferences).toEqual(before);
  });
});
