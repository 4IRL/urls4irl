import type { Schema } from "../../../../types/api-helpers.d.ts";

import { checkForStaleDataOn409 } from "../conflict-handler.js";
import { isURLCurrentlyVisibleInURLDeck } from "../filtering.js";
import { updateUTubOnFindingStaleData } from "../../../utubs/stale-data.js";

vi.mock("../filtering.js", () => ({
  isURLCurrentlyVisibleInURLDeck: vi.fn(() => false),
}));

vi.mock("../../../utubs/stale-data.js", () => ({
  updateUTubOnFindingStaleData: vi.fn(),
}));

type ErrorResponse = Schema<"ErrorResponse">;

function makeErrorResponse(
  overrides: Partial<ErrorResponse> = {},
): ErrorResponse {
  return {
    status: "Failure",
    message: "Duplicate URL",
    errorCode: null,
    errors: null,
    details: null,
    urlString: null,
    ...overrides,
  };
}

describe("checkForStaleDataOn409", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("calls updateUTubOnFindingStaleData when urlString is present and URL is NOT visible", () => {
    vi.mocked(isURLCurrentlyVisibleInURLDeck).mockReturnValue(false);
    const responseJSON = makeErrorResponse({
      urlString: "https://example.com",
    });

    checkForStaleDataOn409(responseJSON, 42);

    expect(isURLCurrentlyVisibleInURLDeck).toHaveBeenCalledWith(
      "https://example.com",
    );
    expect(updateUTubOnFindingStaleData).toHaveBeenCalledWith(42);
  });

  it("does NOT call updateUTubOnFindingStaleData when urlString is present and URL IS already in the deck", () => {
    vi.mocked(isURLCurrentlyVisibleInURLDeck).mockReturnValue(true);
    const responseJSON = makeErrorResponse({
      urlString: "https://example.com",
    });

    checkForStaleDataOn409(responseJSON, 42);

    expect(isURLCurrentlyVisibleInURLDeck).toHaveBeenCalledWith(
      "https://example.com",
    );
    expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
  });

  it("does NOT call updateUTubOnFindingStaleData when urlString is undefined", () => {
    const responseJSON = makeErrorResponse();
    delete (responseJSON as Partial<ErrorResponse>).urlString;

    checkForStaleDataOn409(responseJSON as ErrorResponse, 42);

    expect(isURLCurrentlyVisibleInURLDeck).not.toHaveBeenCalled();
    expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
  });

  it("does NOT call updateUTubOnFindingStaleData when urlString is null", () => {
    const responseJSON = makeErrorResponse({ urlString: null });

    checkForStaleDataOn409(responseJSON, 42);

    expect(isURLCurrentlyVisibleInURLDeck).not.toHaveBeenCalled();
    expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
  });
});
