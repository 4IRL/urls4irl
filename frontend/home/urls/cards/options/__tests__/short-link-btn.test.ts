import type { UtubUrlItem } from "../../../../../types/url.js";

import { createShortLinkBtn } from "../short-link-btn.js";
import { createURLOptionsButtons } from "../btns.js";
import { copyShortLink } from "../../short-link.js";
import {
  disableTabbingOnURLCardElements,
  enableTabbingOnURLCardElements,
} from "../../utils.js";
import { applyHoverTooltip } from "../../../../../lib/tooltips.js";

vi.mock("../../short-link.js", () => ({
  copyShortLink: vi.fn(() => Promise.resolve()),
}));
vi.mock("../../../../../lib/tooltips.js", () => ({
  applyHoverTooltip: vi.fn(),
}));
vi.mock("../access-btn.js", () => ({
  createAccessLinkBtn: vi.fn(() =>
    window.jQuery("<button class='urlBtnAccess'>"),
  ),
}));
vi.mock("../copy-btn.js", () => ({
  createCopyURLBtn: vi.fn(() => window.jQuery("<button class='urlBtnCopy'>")),
}));
vi.mock("../tag-btn.js", () => ({
  createAddTagBtn: vi.fn(() => window.jQuery("<button class='urlBtnAddTag'>")),
}));
vi.mock("../edit-string-btn.js", () => ({
  createEditURLBtn: vi.fn(() => window.jQuery("<button class='urlBtnUpdate'>")),
}));
vi.mock("../delete-btn.js", () => ({
  createDeleteURLBtn: vi.fn(() =>
    window.jQuery("<button class='urlBtnDelete'>"),
  ),
}));

const $ = window.jQuery;

function urlItem({ canDelete }: { canDelete: boolean }): UtubUrlItem {
  return {
    utubUrlID: 7,
    urlString: "https://example.com/7",
    utubUrlTagIDs: [],
    urlTitle: "Title 7",
    canDelete,
    shortLinkExpiresAt: null,
    canRevokeShortLink: false,
    addedAt: "2026-10-17T00:00:00",
    addedByUserID: 1,
  };
}

describe("createShortLinkBtn", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders an icon button with the tooltip and is out of the tab order", () => {
    const urlCard = $('<div class="urlRow"></div>');
    const button = createShortLinkBtn({
      url: urlItem({ canDelete: true }),
      urlCard,
      utubID: 3,
    });

    expect(button.is("button.urlBtnShortLink")).toBe(true);
    expect(button.attr("type")).toBe("button");
    expect(button.attr("tabindex")).toBe("-1");
    expect(button.find("svg path")).toHaveLength(2);
    expect(applyHoverTooltip).toHaveBeenCalledWith({
      btn: button,
      tooltip: {
        title: "Copy short link",
        customClass: "urlBtnShortLink-tooltip",
      },
    });
  });

  it("is labelled for assistive tech by the real tooltip helper", async () => {
    const { applyHoverTooltip: realApplyHoverTooltip } = await vi.importActual<
      typeof import("../../../../../lib/tooltips.js")
    >("../../../../../lib/tooltips.js");
    vi.mocked(applyHoverTooltip).mockImplementationOnce(realApplyHoverTooltip);

    const button = createShortLinkBtn({
      url: urlItem({ canDelete: true }),
      urlCard: $('<div class="urlRow"></div>'),
      utubID: 3,
    });

    expect(button.attr("aria-label")).toBe("Copy short link");
  });

  it("joins the tab order only while its card is selected", () => {
    const urlCard = $('<div class="urlRow"></div>');
    const button = createShortLinkBtn({
      url: urlItem({ canDelete: true }),
      urlCard,
      utubID: 3,
    });
    urlCard.append(button);

    enableTabbingOnURLCardElements(urlCard);
    expect(button.attr("tabindex")).toBe("0");

    disableTabbingOnURLCardElements(urlCard);
    expect(button.attr("tabindex")).toBe("-1");
  });

  it("starts the copy flow for its URL on click", () => {
    const urlCard = $('<div class="urlRow"></div>');
    const button = createShortLinkBtn({
      url: urlItem({ canDelete: false }),
      urlCard,
      utubID: 3,
    });

    button.trigger("click");

    expect(copyShortLink).toHaveBeenCalledTimes(1);
    expect(copyShortLink).toHaveBeenCalledWith({
      button,
      urlCard,
      utubID: 3,
      utubUrlID: 7,
    });
  });
});

describe("createURLOptionsButtons — short-link button", () => {
  it.each([true, false])(
    "renders right after Copy URL when canDelete is %s",
    (canDelete) => {
      const options = createURLOptionsButtons(
        urlItem({ canDelete }),
        $('<div class="urlRow"></div>'),
        3,
      );

      expect(options.find(".urlBtnCopy").next().is(".urlBtnShortLink")).toBe(
        true,
      );
      expect(options.find(".urlBtnUpdate").length).toBe(canDelete ? 1 : 0);
    },
  );
});
