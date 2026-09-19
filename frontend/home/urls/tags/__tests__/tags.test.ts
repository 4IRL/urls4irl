import { APP_CONFIG } from "../../../../lib/config.js";
import { bootstrap } from "../../../../lib/globals.js";
import { isCoarsePointer } from "../../../mobile.js";
import {
  createTagBadgeInURL,
  createTagBadgesAndWrap,
  disableTagRemovalInURLCard,
  enableTagRemovalInURLCard,
} from "../tags.js";
import { deleteURLTag } from "../delete.js";

vi.mock("../create.js", () => ({
  createURLTag: vi.fn(),
  hideAndResetCreateURLTagForm: vi.fn(),
}));

vi.mock("../delete.js", () => ({
  deleteURLTag: vi.fn(),
}));

// The ambient test-setup Bootstrap mock returns null from getInstance(), which
// would make the tooltip-hide guards on the per-tag delete button silent no-ops.
// Override lib/globals.js with a shared tooltip instance so they can be asserted
// on. lib/tooltips.js is left unmocked so the real attribute stamp runs here.
const { tooltipInstance, globalsMock } = await vi.hoisted(async () => {
  const { mockGlobalsWithTooltipInstance } = await import(
    "../../../../__tests__/helpers/mock-globals.js"
  );
  return await mockGlobalsWithTooltipInstance();
});

vi.mock("../../../../lib/globals.js", () => globalsMock);

vi.mock("../../../mobile.js", () => ({
  isCoarsePointer: vi.fn(() => false),
}));

const $ = window.jQuery;

describe("createTagBadgesAndWrap - missing tag ID guard", () => {
  beforeEach(() => {
    document.body.innerHTML = `<div class="urlRow"></div>`;
  });

  it("skips tag IDs that are not present in dictTags and throws no error", () => {
    const urlCard = $(".urlRow");
    const dictTags = [{ id: 1, tagString: "exists", tagApplied: 0 }];
    const tagArray = [999]; // 999 is absent from dictTags

    let wrap;
    expect(() => {
      wrap = createTagBadgesAndWrap(dictTags, tagArray, urlCard, 42);
    }).not.toThrow();

    // Wrap was created but no badges appended since the one tag ID was missing
    expect(wrap!.hasClass("urlTagsContainer")).toBe(true);
    expect(wrap!.children().length).toBe(0);
  });

  it("appends a badge only for tag IDs that exist in dictTags", () => {
    const urlCard = $(".urlRow");
    const dictTags = [
      { id: 1, tagString: "exists", tagApplied: 0 },
      { id: 2, tagString: "other", tagApplied: 0 },
    ];
    const tagArray = [1, 999, 2]; // 999 missing; 1 and 2 present

    const wrap = createTagBadgesAndWrap(dictTags, tagArray, urlCard, 42);

    expect(wrap.children().length).toBe(2);
  });
});

describe("createTagBadgeInURL - hover tooltip", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(isCoarsePointer).mockReturnValue(false);
    document.body.innerHTML = `<div class="urlRow"></div>`;
  });

  it("stamps the hover tooltip attribute block on the delete button", () => {
    const badge = createTagBadgeInURL(7, "work", $(".urlRow"), 42);
    const removeButton = badge.find(".urlTagBtnDelete");

    expect(removeButton.attr("data-bs-toggle")).toBe("tooltip");
    expect(removeButton.attr("data-bs-custom-class")).toBe(
      "urlTagBtnDelete-tooltip",
    );
    expect(removeButton.attr("data-bs-placement")).toBe("top");
    expect(removeButton.attr("data-bs-trigger")).toBe("hover");
    expect(removeButton.attr("data-bs-title")).toBe(
      APP_CONFIG.strings.REMOVE_URL_TAG_TOOLTIP,
    );
  });

  it("gives every badge an aria-label naming its own tag, unlike the shared bubble text", () => {
    const workBadge = createTagBadgeInURL(7, "work", $(".urlRow"), 42);
    const homeBadge = createTagBadgeInURL(8, "home", $(".urlRow"), 42);

    expect(workBadge.find(".urlTagBtnDelete").attr("aria-label")).toBe(
      `${APP_CONFIG.strings.REMOVE_URL_TAG_TOOLTIP} work`,
    );
    expect(homeBadge.find(".urlTagBtnDelete").attr("aria-label")).toBe(
      `${APP_CONFIG.strings.REMOVE_URL_TAG_TOOLTIP} home`,
    );
  });

  it("skips the tooltip attributes on a coarse pointer, keeping the aria-label", () => {
    vi.mocked(isCoarsePointer).mockReturnValue(true);

    const badge = createTagBadgeInURL(7, "work", $(".urlRow"), 42);
    const removeButton = badge.find(".urlTagBtnDelete");

    expect(removeButton.attr("data-bs-toggle")).toBeUndefined();
    expect(removeButton.attr("data-bs-title")).toBeUndefined();
    // The accessible name is not a tooltip — touch screen readers still need it.
    expect(removeButton.attr("aria-label")).toBe(
      `${APP_CONFIG.strings.REMOVE_URL_TAG_TOOLTIP} work`,
    );
  });
});

describe("tag delete button - stuck tooltip guards", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(isCoarsePointer).mockReturnValue(false);
    // clearAllMocks() wipes call history but NOT implementations — restore the
    // shared-instance default so a sad-path test cannot leak its null override.
    vi.mocked(bootstrap.Tooltip.getInstance).mockReturnValue(
      tooltipInstance as unknown as ReturnType<
        typeof bootstrap.Tooltip.getInstance
      >,
    );
    document.body.innerHTML = `<div class="urlRow"></div>`;
  });

  it("hides the open tooltip when a single tag badge is deleted by click", () => {
    const urlCard = $(".urlRow");
    const badge = createTagBadgeInURL(7, "work", urlCard, 42);
    urlCard.append(badge);

    badge.find(".urlTagBtnDelete").trigger("click");

    expect(tooltipInstance.hide).toHaveBeenCalled();
    expect(vi.mocked(deleteURLTag)).toHaveBeenCalledTimes(1);
  });

  it("hides open tooltips before disableTagRemovalInURLCard hides the buttons", () => {
    const urlCard = $(".urlRow");
    urlCard.append(createTagBadgeInURL(7, "work", urlCard, 42));
    urlCard.append(createTagBadgeInURL(8, "home", urlCard, 42));

    disableTagRemovalInURLCard(urlCard);

    // One hide per delete button, and the buttons still end up hidden.
    expect(tooltipInstance.hide).toHaveBeenCalledTimes(2);
    expect(urlCard.find(".urlTagBtnDelete.hidden").length).toBe(2);
  });

  it("is a safe no-op on click when the button has no Tooltip instance", () => {
    // The real touch-device case: isCoarsePointer() skipped instantiation, so
    // getInstance() legitimately returns null and the guard must not throw.
    vi.mocked(bootstrap.Tooltip.getInstance).mockReturnValue(
      null as unknown as ReturnType<typeof bootstrap.Tooltip.getInstance>,
    );
    const urlCard = $(".urlRow");
    const badge = createTagBadgeInURL(7, "work", urlCard, 42);
    urlCard.append(badge);

    expect(() => badge.find(".urlTagBtnDelete").trigger("click")).not.toThrow();
    expect(tooltipInstance.hide).not.toHaveBeenCalled();
    expect(vi.mocked(deleteURLTag)).toHaveBeenCalledTimes(1);
  });

  it("is a safe no-op in disableTagRemovalInURLCard when no Tooltip instance exists", () => {
    const urlCard = $(".urlRow");
    urlCard.append(createTagBadgeInURL(7, "work", urlCard, 42));
    vi.mocked(bootstrap.Tooltip.getInstance).mockReturnValue(
      null as unknown as ReturnType<typeof bootstrap.Tooltip.getInstance>,
    );

    expect(() => disableTagRemovalInURLCard(urlCard)).not.toThrow();
    expect(tooltipInstance.hide).not.toHaveBeenCalled();
    expect(urlCard.find(".urlTagBtnDelete.hidden").length).toBe(1);
  });

  it("does not touch tooltips when re-showing the buttons", () => {
    const urlCard = $(".urlRow");
    urlCard.append(createTagBadgeInURL(7, "work", urlCard, 42));
    disableTagRemovalInURLCard(urlCard);
    tooltipInstance.hide.mockClear();

    enableTagRemovalInURLCard(urlCard);

    expect(tooltipInstance.hide).not.toHaveBeenCalled();
    expect(urlCard.find(".urlTagBtnDelete.hidden").length).toBe(0);
  });
});
