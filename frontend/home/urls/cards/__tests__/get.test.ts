import type { SuccessResponse } from "../../../../types/api-helpers.d.ts";

import { isTagInUTubTagDeck } from "../../../tags/utils.js";
import { buildTagFilterInDeck } from "../../../tags/tags.js";
import { getUpdatedURL } from "../get.js";

vi.mock("../../../../lib/page-utils.js", () => ({
  showNewPageOnAJAXHTMLResponse: vi.fn(),
}));

vi.mock("../../../../lib/tooltips.js", () => ({
  disposeTooltipsWithin: vi.fn(),
}));

vi.mock("../url-string.js", () => ({
  modifyURLStringForDisplay: vi.fn((urlString: string) => urlString),
}));

vi.mock("../filtering.js", () => ({
  updateTagFilteringOnURLOrURLTagDeletion: vi.fn(),
}));

vi.mock("../../deck.js", () => ({
  showURLDeckBannerError: vi.fn(),
}));

vi.mock("../../tags/tags.js", () => ({
  createTagBadgeInURL: vi.fn(() =>
    window.jQuery('<span class="tagBadge"></span>'),
  ),
}));

vi.mock("../../../tags/utils.js", () => ({
  isTagInUTubTagDeck: vi.fn(() => false),
}));

vi.mock("../../../tags/search.js", () => ({
  reapplyTagFilter: vi.fn(),
}));

vi.mock("../../../tags/tags.js", () => ({
  buildTagFilterInDeck: vi.fn((_utubID, tagID, tagString) =>
    window.jQuery(
      `<div class="tagFilter" data-utub-tag-id="${tagID}">${tagString}</div>`,
    ),
  ),
}));

const $ = window.jQuery;

const PAGE_HTML = `
  <span id="TagDeckCount"></span>
  <div id="listTags">
    <div class="tagFilter" data-utub-tag-id="1">alpha</div>
  </div>
  <div class="urlRow" utuburlid="1">
    <span class="urlTitle">Title</span>
    <a class="urlString" href="https://a.com"></a>
    <div class="urlTagsContainer">
      <span class="tagBadge" data-utub-tag-id="1"></span>
    </div>
  </div>
`;

/**
 * Drive getUpdatedURL()'s success path synchronously. get.ts calls raw
 * `$.ajax` rather than the ajaxCall() wrapper, so the stub replaces
 * `$.ajax` itself instead of mocking lib/ajax.js the way sibling specs do.
 */
function resolveGetURLWith(
  urlTags: { utubTagID: number; tagString: string }[],
) {
  const response = {
    URL: {
      utubUrlID: 1,
      urlTitle: "Title",
      urlString: "https://a.com",
      urlTags,
    },
  } as unknown as SuccessResponse<"getUrl">;

  ($ as unknown as Record<string, unknown>).ajax = (
    settings: Record<string, unknown>,
  ) => {
    (
      settings.success as (
        r: unknown,
        t: unknown,
        x: { status: number },
      ) => void
    )(response, "success", { status: 200 });
    return undefined;
  };

  return getUpdatedURL(1, 1, $(".urlRow"));
}

describe("getUpdatedURL — keeps the #TagDeckCount tag total in sync", () => {
  const originalAjax = ($ as unknown as Record<string, unknown>).ajax;

  beforeEach(() => {
    document.body.innerHTML = PAGE_HTML;
    vi.clearAllMocks();
    vi.mocked(isTagInUTubTagDeck).mockReturnValue(false);
  });

  afterEach(() => {
    ($ as unknown as Record<string, unknown>).ajax = originalAjax;
    document.body.innerHTML = "";
  });

  it("bumps the count when the server reports a tag new to the UTub deck", async () => {
    await resolveGetURLWith([
      { utubTagID: 1, tagString: "alpha" },
      { utubTagID: 2, tagString: "beta" },
    ]);

    expect(buildTagFilterInDeck).toHaveBeenCalledWith(1, 2, "beta");
    expect($("#listTags > .tagFilter").length).toBe(2);
    expect($("#TagDeckCount").text()).toBe("(2)");
  });

  it("drops the count when the server reports a tag gone from the UTub", async () => {
    // The URL's only badge (tag 1) is absent from the response, and
    // isTagInUTubTagDeck() reports the tag is no longer in the UTub at all, so
    // its deck row is removed too.
    await resolveGetURLWith([]);

    expect($("#listTags > .tagFilter").length).toBe(0);
    expect($("#TagDeckCount").text()).toBe("(0)");
  });

  it("leaves the count alone when the URL's tags are unchanged", async () => {
    $("#TagDeckCount").text("(1)");
    vi.mocked(isTagInUTubTagDeck).mockReturnValue(true);

    await resolveGetURLWith([{ utubTagID: 1, tagString: "alpha" }]);

    expect(buildTagFilterInDeck).not.toHaveBeenCalled();
    expect($("#listTags > .tagFilter").length).toBe(1);
    expect($("#TagDeckCount").text()).toBe("(1)");
  });
});
