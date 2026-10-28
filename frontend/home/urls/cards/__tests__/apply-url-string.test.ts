import type { SuccessResponse } from "../../../../types/api-helpers.d.ts";
import type { UtubUrlItem } from "../../../../types/url.js";

import { getState, setState } from "../../../../store/app-store.js";
import { APP_CONFIG } from "../../../../lib/config.js";
import {
  applyHoverTooltip,
  disposeTooltipsWithin,
} from "../../../../lib/tooltips.js";
import { applyUpdatedURLString } from "../apply-url-string.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());
vi.mock("../access.js", () => ({ accessLink: vi.fn() }));
vi.mock("../copy.js", () => ({ copyURLString: vi.fn() }));
vi.mock("../../url-context.js", () => ({
  isURLSearchActive: vi.fn(() => false),
  getActiveTagCount: vi.fn(() => 0),
}));
vi.mock("../../../../lib/tooltips.js", () => ({
  applyHoverTooltip: vi.fn(),
  disposeTooltipsWithin: vi.fn(),
}));

const $ = window.jQuery;

const URL_ID = 42;
const EXPIRES_AT = "2026-10-27T12:00:00";

function seedUrl(): void {
  const url: UtubUrlItem = {
    utubUrlID: URL_ID,
    urlString: "https://example.com/old",
    utubUrlTagIDs: [],
    urlTitle: "Title",
    canDelete: true,
    shortLinkExpiresAt: EXPIRES_AT,
    canRevokeShortLink: true,
    addedAt: "2026-10-17T00:00:00",
    addedByUserID: 1,
  };
  setState({ urls: [url] });
}

function responseWith(status: string): SuccessResponse<"updateUrl"> {
  return {
    status,
    URL: {
      utubUrlID: URL_ID,
      urlString: "https://example.com/new",
      urlTitle: "Title",
      urlTags: [],
    },
  } as unknown as SuccessResponse<"updateUrl">;
}

function card(): JQuery {
  return $(`.urlRow[utuburlid=${URL_ID}]`);
}

describe("applyUpdatedURLString short-link clearing", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = `
      <div class="urlRow" utuburlid="${URL_ID}">
        <div class="urlOptions"><button class="urlBtnShortLink"></button></div>
        <div class="shortLinkStatusRow"><button class="shortLinkRevoke"></button></div>
        <a class="urlString"></a>
      </div>`;
    seedUrl();
  });

  it("drops the link from the store and removes the status row when the address changed", () => {
    applyUpdatedURLString({
      response: responseWith("Success"),
      urlCard: card(),
    });

    const stored = getState().urls[0];
    expect(stored.shortLinkExpiresAt).toBeNull();
    expect(stored.canRevokeShortLink).toBe(false);
    expect(card().find(".shortLinkStatusRow").length).toBe(0);
  });

  it("resets the short-link button tooltip to the plain title when the address changed", () => {
    applyUpdatedURLString({
      response: responseWith("Success"),
      urlCard: card(),
    });

    expect(disposeTooltipsWithin).toHaveBeenCalledTimes(1);
    expect(applyHoverTooltip).toHaveBeenCalledTimes(1);
    const call = vi.mocked(applyHoverTooltip).mock.calls[0][0];
    expect(call.btn[0]).toBe(card().find(".urlBtnShortLink")[0]);
    expect(call.tooltip?.title).toBe(APP_CONFIG.strings.SHORT_LINK_TOOLTIP);
  });

  it("re-syncs the full-URL tooltip on a line-view card (unmocked helper)", () => {
    setState({
      preferences: { ...getState().preferences, defaultView: "url_line" },
    });
    card().attr("urlSelected", "false");
    applyUpdatedURLString({
      response: responseWith("Success"),
      urlCard: card(),
    });

    expect(card().find(".urlString").attr("title")).toBe(
      card().find(".urlString").attr("href"),
    );
  });

  it("leaves the tooltip and Revoke untouched on a 'No change' response", () => {
    applyUpdatedURLString({
      response: responseWith("No change"),
      urlCard: card(),
    });

    expect(applyHoverTooltip).not.toHaveBeenCalled();
    expect(disposeTooltipsWithin).not.toHaveBeenCalled();
    expect(card().find(".shortLinkRevoke").length).toBe(1);
  });

  it("keeps the link on a 'No change' response", () => {
    applyUpdatedURLString({
      response: responseWith("No change"),
      urlCard: card(),
    });

    const stored = getState().urls[0];
    expect(stored.shortLinkExpiresAt).toBe(EXPIRES_AT);
    expect(stored.canRevokeShortLink).toBe(true);
    expect(card().find(".shortLinkStatusRow").length).toBe(1);
  });
});
