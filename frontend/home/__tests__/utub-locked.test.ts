import { isUtubLockedHandled } from "../utub-locked.js";
import { showURLDeckBannerError } from "../urls/deck.js";
import { createMockXhr } from "../../__tests__/helpers/mock-jquery.js";

vi.mock("../urls/deck.js", () => ({
  showURLDeckBannerError: vi.fn(),
}));

const $ = window.jQuery;

// Mirrors backend UTubErrorCodes.UTUB_IS_LOCKED (backend/utubs/constants.py)
const UTUB_IS_LOCKED = 3;
const UNKNOWN_ERROR = 1;
const LOCKED_MESSAGE = "This UTub is locked and cannot be modified.";

describe("isUtubLockedHandled", () => {
  beforeEach(() => {
    document.body.innerHTML = `<div id="confirmModal" class="modal"></div>`;
    ($.fn as unknown as Record<string, unknown>).modal = vi
      .fn()
      .mockReturnThis();
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("surfaces the server message and returns true for a locked 403", () => {
    const xhr = createMockXhr({
      status: 403,
      responseJSON: { errorCode: UTUB_IS_LOCKED, message: LOCKED_MESSAGE },
    });

    const handled = isUtubLockedHandled(xhr);

    expect(handled).toBe(true);
    expect(showURLDeckBannerError).toHaveBeenCalledWith(LOCKED_MESSAGE);
  });

  it("returns false for a non-lock 403 error code", () => {
    const xhr = createMockXhr({
      status: 403,
      responseJSON: { errorCode: UNKNOWN_ERROR, message: "nope" },
    });

    expect(isUtubLockedHandled(xhr)).toBe(false);
    expect(showURLDeckBannerError).not.toHaveBeenCalled();
  });

  it("returns false for a non-403 status even with the lock error code", () => {
    const xhr = createMockXhr({
      status: 400,
      responseJSON: { errorCode: UTUB_IS_LOCKED, message: LOCKED_MESSAGE },
    });

    expect(isUtubLockedHandled(xhr)).toBe(false);
    expect(showURLDeckBannerError).not.toHaveBeenCalled();
  });

  it("returns false when there is no responseJSON (e.g. CSRF 403 HTML)", () => {
    const xhr = createMockXhr({ status: 403 });

    expect(isUtubLockedHandled(xhr)).toBe(false);
    expect(showURLDeckBannerError).not.toHaveBeenCalled();
  });
});
