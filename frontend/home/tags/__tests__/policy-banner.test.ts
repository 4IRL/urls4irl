import { showDisabledReasonNote } from "../../../lib/disabled-reason.js";
import { showURLDeckBannerError } from "../../urls/deck.js";
import { isTagSheetOpen } from "../sheet.js";
import {
  getForbiddenErrorCode,
  getRefusalOwnedMessage,
  handleTaggingRefusal,
  runAsRefusal,
  showPolicyBanner,
} from "../policy-banner.js";
import { learnPolicyOff } from "../../utubs/policy.js";

vi.mock("../../utubs/policy.js", () => ({
  learnPolicyOff: vi.fn(() => true),
}));

vi.mock("../../urls/deck.js", () => ({
  showURLDeckBannerError: vi.fn(),
}));

vi.mock("../sheet.js", () => ({
  isTagSheetOpen: vi.fn(() => false),
}));

vi.mock("../../../lib/disabled-reason.js", () => ({
  showDisabledReasonNote: vi.fn(),
}));

const MESSAGE = "Only the owner and co-owners can create tags in this UTub.";

describe("showPolicyBanner", () => {
  let control: HTMLElement;

  beforeEach(() => {
    document.body.innerHTML = `
      <h5 id="URLDeckErrorIndicator"></h5>
      <button id="control"></button>
    `;
    control = document.getElementById("control") as HTMLElement;
    vi.clearAllMocks();
    vi.mocked(isTagSheetOpen).mockReturnValue(false);
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("shows the deck banner without taking focus when the sheet is closed", () => {
    showPolicyBanner({ message: MESSAGE, control });

    expect(showURLDeckBannerError).toHaveBeenCalledTimes(1);
    expect(showURLDeckBannerError).toHaveBeenCalledWith(MESSAGE, {
      takeFocus: false,
    });
    expect(showDisabledReasonNote).not.toHaveBeenCalled();
  });

  it("writes into the control's note, not the deck banner, with the sheet open", () => {
    vi.mocked(isTagSheetOpen).mockReturnValue(true);

    showPolicyBanner({ message: MESSAGE, control });

    expect(showDisabledReasonNote).toHaveBeenCalledWith({
      element: control,
      reason: MESSAGE,
    });
    expect(showURLDeckBannerError).not.toHaveBeenCalled();
  });

  it("falls back to the deck banner with the sheet open and no control", () => {
    vi.mocked(isTagSheetOpen).mockReturnValue(true);

    showPolicyBanner({ message: MESSAGE });

    expect(showURLDeckBannerError).toHaveBeenCalledWith(MESSAGE, {
      takeFocus: false,
    });
    expect(showDisabledReasonNote).not.toHaveBeenCalled();
  });

  it("suppresses a repeat only while the banner already shows the same text", () => {
    const banner = document.getElementById("URLDeckErrorIndicator");
    banner?.classList.add("URLDeckErrorIndicatorShow");
    if (banner) banner.textContent = MESSAGE;

    showPolicyBanner({ message: MESSAGE });
    expect(showURLDeckBannerError).not.toHaveBeenCalled();

    showPolicyBanner({ message: "A different reason." });
    expect(showURLDeckBannerError).toHaveBeenCalledWith("A different reason.", {
      takeFocus: false,
    });
  });

  it("shows the same text again once the banner class is gone", () => {
    const banner = document.getElementById("URLDeckErrorIndicator");
    if (banner) banner.textContent = MESSAGE;

    showPolicyBanner({ message: MESSAGE });

    expect(showURLDeckBannerError).toHaveBeenCalledTimes(1);
  });
});

describe("runAsRefusal", () => {
  it("owns the message inside the callback and resets afterwards", () => {
    expect(getRefusalOwnedMessage()).toBeNull();

    runAsRefusal({
      message: MESSAGE,
      callback: () => {
        expect(getRefusalOwnedMessage()).toBe(MESSAGE);
      },
    });

    expect(getRefusalOwnedMessage()).toBeNull();
  });

  it("resets to null even when the callback throws", () => {
    expect(() =>
      runAsRefusal({
        message: MESSAGE,
        callback: () => {
          throw new Error("boom");
        },
      }),
    ).toThrow("boom");

    expect(getRefusalOwnedMessage()).toBeNull();
  });
});

describe("getForbiddenErrorCode", () => {
  it("reads the numeric errorCode of a 403 only", () => {
    const forbidden = {
      status: 403,
      responseJSON: { errorCode: 4 },
    } as unknown as JQuery.jqXHR;
    const badRequest = {
      status: 400,
      responseJSON: { errorCode: 4 },
    } as unknown as JQuery.jqXHR;
    const noBody = { status: 403 } as unknown as JQuery.jqXHR;

    expect(getForbiddenErrorCode(forbidden)).toBe(4);
    expect(getForbiddenErrorCode(badRequest)).toBeNull();
    expect(getForbiddenErrorCode(noBody)).toBeNull();
  });
});

describe("handleTaggingRefusal", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <h5 id="URLDeckErrorIndicator"></h5>
      <button id="target"></button>
      <button id="control"></button>
    `;
    vi.clearAllMocks();
    vi.mocked(isTagSheetOpen).mockReturnValue(false);
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("learns tags.members_can_tag while owning the message, then focuses and shows once", () => {
    const target = document.getElementById("target") as HTMLElement;
    const control = document.getElementById("control") as HTMLElement;
    let ownedDuringLearn: string | null = null;
    vi.mocked(learnPolicyOff).mockImplementation(() => {
      ownedDuringLearn = getRefusalOwnedMessage();
      return true;
    });

    handleTaggingRefusal({
      message: MESSAGE,
      utubID: 5,
      focusTarget: target,
      control,
    });

    expect(learnPolicyOff).toHaveBeenCalledWith({
      utubID: 5,
      key: "tags.members_can_tag",
    });
    expect(ownedDuringLearn).toBe(MESSAGE);
    expect(document.activeElement).toBe(target);
    expect(showURLDeckBannerError).toHaveBeenCalledTimes(1);
    expect(showURLDeckBannerError).toHaveBeenCalledWith(MESSAGE, {
      takeFocus: false,
    });
  });

  it("leaves focus alone without a focus target and skips the learn with no UTub", () => {
    const before = document.activeElement;

    handleTaggingRefusal({ message: MESSAGE, utubID: null });

    expect(learnPolicyOff).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(before);
    expect(showURLDeckBannerError).toHaveBeenCalledTimes(1);
  });
});
