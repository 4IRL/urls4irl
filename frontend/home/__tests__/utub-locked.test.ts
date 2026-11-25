import { isUtubLockedHandled } from "../utub-locked.js";
import { showURLDeckBannerError } from "../urls/deck.js";
import { APP_CONFIG } from "../../lib/config.js";
import { createMockXhr } from "../../__tests__/helpers/mock-jquery.js";
import { URLErrorCodes, UTubTagErrorCodes } from "../../types/error-codes.js";

vi.mock("../urls/deck.js", () => ({
  showURLDeckBannerError: vi.fn(),
}));

const $ = window.jQuery;

// The bridged locked message (backend UTUB_FAILURE.UTUB_IS_LOCKED) is the
// cross-domain signal the guard keys on — NOT an error code.
const LOCKED_MESSAGE = APP_CONFIG.strings.UTUB_IS_LOCKED;
// Each backend domain assigns its own numeric UTUB_IS_LOCKED code (URL
// operations differ from the UTub/tag/member enums). The guard must handle
// every one, so it cannot key on a single code.

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

  it("handles a locked 403 from a URL operation (URLErrorCodes)", () => {
    const xhr = createMockXhr({
      status: 403,
      responseJSON: {
        errorCode: URLErrorCodes.UTUB_IS_LOCKED,
        message: LOCKED_MESSAGE,
      },
    });

    const handled = isUtubLockedHandled(xhr);

    expect(handled).toBe(true);
    expect(showURLDeckBannerError).toHaveBeenCalledWith(LOCKED_MESSAGE);
  });

  it("handles a locked 403 from a UTub/tag/member operation (UTubTagErrorCodes)", () => {
    const xhr = createMockXhr({
      status: 403,
      responseJSON: {
        errorCode: UTubTagErrorCodes.UTUB_IS_LOCKED,
        message: LOCKED_MESSAGE,
      },
    });

    const handled = isUtubLockedHandled(xhr);

    expect(handled).toBe(true);
    expect(showURLDeckBannerError).toHaveBeenCalledWith(LOCKED_MESSAGE);
  });

  it("returns false for a 403 whose message is not the locked message", () => {
    const xhr = createMockXhr({
      status: 403,
      responseJSON: {
        errorCode: URLErrorCodes.UTUB_IS_LOCKED,
        message: "Some other error",
      },
    });

    expect(isUtubLockedHandled(xhr)).toBe(false);
    expect(showURLDeckBannerError).not.toHaveBeenCalled();
  });

  it("returns false for a non-403 status even with the locked message", () => {
    const xhr = createMockXhr({
      status: 400,
      responseJSON: { message: LOCKED_MESSAGE },
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
