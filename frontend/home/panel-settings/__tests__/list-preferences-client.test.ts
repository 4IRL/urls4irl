import { ajaxCall } from "../../../lib/ajax.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { getState, resetStore } from "../../../store/app-store.js";
import {
  createMockJqXHR,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { removeUTubLocally } from "../../utubs/remove-local.js";
import { PATCH_TIMEOUT_MS, patchUtubListPreferences } from "../client.js";

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
  utubSort: "name_az",
  showRowCounts: true,
  showListTotals: false,
};

function failXhr({
  status,
  html = false,
}: {
  status: number;
  html?: boolean;
}): JQuery.jqXHR {
  return createMockXhr({
    status,
    responseJSON: html
      ? undefined
      : { message: APP_CONFIG.strings.NOT_AUTHORIZED },
    getResponseHeader: () => (html ? "text/html" : "application/json"),
  });
}

function start(): {
  request: ReturnType<typeof createMockJqXHR>;
  result: ReturnType<typeof patchUtubListPreferences>;
} {
  const request = createMockJqXHR();
  vi.mocked(ajaxCall).mockReturnValue(request);
  const result = patchUtubListPreferences({ patch: { showRowCounts: true } });
  return { request, result };
}

describe("patchUtubListPreferences", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
  });

  it("PATCHes the preferences route with exactly the patch and the write timeout", async () => {
    const { request, result } = start();
    request.resolve(ECHO);
    await result;

    expect(ajaxCall).toHaveBeenCalledWith(
      "patch",
      APP_CONFIG.routes.updateUtubListPreferences,
      { showRowCounts: true },
      PATCH_TIMEOUT_MS,
    );
  });

  it("works with no UTub selected and returns the echoed values", async () => {
    expect(getState().activeUTubID).toBeNull();
    const { request, result } = start();
    request.resolve(ECHO);

    await expect(result).resolves.toEqual({
      outcome: "ok",
      preferences: {
        utubSort: "name_az",
        showRowCounts: true,
        showListTotals: false,
      },
    });
  });

  it("accepts a No change echo", async () => {
    const { request, result } = start();
    request.resolve({ ...ECHO, status: "No change" });

    await expect(result).resolves.toMatchObject({ outcome: "ok" });
  });

  it.each([
    ["an HTML body", "<html></html>"],
    ["a null body", null],
    ["a bad status", { ...ECHO, status: "Failure" }],
    ["a bad sort", { ...ECHO, utubSort: "random" }],
    ["a non-boolean toggle", { ...ECHO, showRowCounts: "yes" }],
    ["a missing toggle", { ...ECHO, showListTotals: undefined }],
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
    [400, false, "invalid"],
    [500, false, "error"],
    [403, false, "forbidden"],
    [404, false, "gone"],
    [403, true, "error"],
    [405, true, "error"],
  ])(
    "maps status %i (html %s) to %s without UTub-gone handling",
    async (status, html, outcome) => {
      const { request, result } = start();
      request.reject(failXhr({ status, html }));
      const resolved = await result;

      expect(resolved).toMatchObject({
        outcome: "failed",
        result: { outcome },
        timedOut: false,
      });
      expect(removeUTubLocally).not.toHaveBeenCalled();
    },
  );

  it("maps a handled 429 to an error without a resync or UTub-gone handling", async () => {
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
    expect(removeUTubLocally).not.toHaveBeenCalled();
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
