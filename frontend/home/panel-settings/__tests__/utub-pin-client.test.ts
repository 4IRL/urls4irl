import { ajaxCall } from "../../../lib/ajax.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { resetStore } from "../../../store/app-store.js";
import {
  createMockJqXHR,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { removeUTubLocally } from "../../utubs/remove-local.js";
import { PATCH_TIMEOUT_MS, patchUtubPin } from "../client.js";

vi.mock("../../../lib/ajax.js", async () => {
  const actual = await vi.importActual<typeof import("../../../lib/ajax.js")>(
    "../../../lib/ajax.js",
  );
  return { ...actual, ajaxCall: vi.fn() };
});
vi.mock("../../utubs/remove-local.js", () => ({ removeUTubLocally: vi.fn() }));
vi.mock("../../urls/deck.js", () => ({ showURLDeckBannerError: vi.fn() }));

const OK_BODY = {
  status: "Success",
  message: "ok",
  utubID: 7,
  isPinned: true,
  pinnedCount: 3,
};

function start(): {
  request: ReturnType<typeof createMockJqXHR>;
  result: ReturnType<typeof patchUtubPin>;
} {
  const request = createMockJqXHR();
  vi.mocked(ajaxCall).mockReturnValue(request);
  const result = patchUtubPin({ utubID: 7, pinned: true });
  return { request, result };
}

function jsonXhr({
  status,
  body,
}: {
  status: number;
  body: unknown;
}): ReturnType<typeof createMockXhr> {
  return createMockXhr({
    status,
    responseJSON: body,
    getResponseHeader: () => "application/json",
  });
}

describe("patchUtubPin", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
  });

  it("PATCHes the UTub's pin route with exactly { pinned } and the write timeout", async () => {
    const { request, result } = start();
    request.resolve(OK_BODY);
    await result;

    expect(ajaxCall).toHaveBeenCalledWith(
      "patch",
      APP_CONFIG.routes.updateUTubPin(7),
      { pinned: true },
      PATCH_TIMEOUT_MS,
    );
  });

  it("returns isPinned and pinnedCount from the response, also for No change", async () => {
    const { request, result } = start();
    request.resolve({ ...OK_BODY, status: "No change", pinnedCount: 5 });

    await expect(result).resolves.toEqual({
      outcome: "ok",
      isPinned: true,
      pinnedCount: 5,
    });
  });

  it.each([
    ["an HTML body", "<html></html>"],
    ["a null body", null],
    ["a bad status", { ...OK_BODY, status: "Failure" }],
    ["a missing utubID", { ...OK_BODY, utubID: undefined }],
    ["a missing isPinned", { ...OK_BODY, isPinned: undefined }],
    ["a missing pinnedCount", { ...OK_BODY, pinnedCount: undefined }],
  ])("classes %s on a 200 as an error", async (_label, body) => {
    const { request, result } = start();
    request.resolve(body);

    await expect(result).resolves.toEqual({ outcome: "error" });
  });

  it("maps a 409 with the pin-limit code to cap", async () => {
    const { request, result } = start();
    request.reject(jsonXhr({ status: 409, body: { errorCode: 6 } }));

    await expect(result).resolves.toEqual({ outcome: "cap" });
  });

  it("classes a 409 with any other code as an error", async () => {
    const { request, result } = start();
    request.reject(jsonXhr({ status: 409, body: { errorCode: 2 } }));

    await expect(result).resolves.toEqual({ outcome: "error" });
  });

  it("classes a 409 with no error code as an error", async () => {
    const { request, result } = start();
    request.reject(jsonXhr({ status: 409, body: { message: "x" } }));

    await expect(result).resolves.toEqual({ outcome: "error" });
  });

  it("maps a JSON 404 to gone without the UTub-gone handling", async () => {
    const { request, result } = start();
    request.reject(jsonXhr({ status: 404, body: { message: "nope" } }));

    await expect(result).resolves.toEqual({ outcome: "gone" });
    expect(removeUTubLocally).not.toHaveBeenCalled();
  });

  it("classes a non-JSON 404 as an error", async () => {
    const { request, result } = start();
    request.reject(
      createMockXhr({
        status: 404,
        responseJSON: undefined,
        getResponseHeader: () => "text/html",
      }),
    );

    await expect(result).resolves.toEqual({ outcome: "error" });
  });

  it.each([400, 403, 429, 500, 502, 503, 0])(
    "classes status %i as an error",
    async (status) => {
      const { request, result } = start();
      request.reject(jsonXhr({ status, body: { message: "x" } }));

      await expect(result).resolves.toEqual({ outcome: "error" });
      expect(removeUTubLocally).not.toHaveBeenCalled();
    },
  );
});
