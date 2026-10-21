import {
  submitStagedTags,
  submitStagedTagsSuccess,
  submitStagedTagsFail,
} from "../combobox.js";
import { UI_EVENTS } from "../../../../types/metrics-events.js";
import { ajaxCall, is429Handled } from "../../../../lib/ajax.js";
import { setState } from "../../../../store/app-store.js";
import { enableClickOnSelectedURLCardToHide } from "../../cards/selection.js";
import { deleteURLOnStale } from "../../cards/get.js";
import { showURLDeckBannerError } from "../../deck.js";
import { clearURLOutcomeBanner } from "../../outcome-banner.js";
import { isUtubLockedHandled } from "../../../utub-locked.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../cards/selection.js", () => ({
  disableClickOnSelectedURLCardToHide: vi.fn(),
  enableClickOnSelectedURLCardToHide: vi.fn(),
}));

vi.mock("../../cards/utils.js", () => ({
  disableEditingURLString: vi.fn(),
  disableEditingURLTitle: vi.fn(),
  enableEditingURLString: vi.fn(),
  enableEditingURLTitle: vi.fn(),
}));

vi.mock("../../cards/loading.js", () => ({
  setTimeoutAndShowURLCardLoadingIcon: vi.fn(() => 1),
  clearTimeoutIDAndHideLoadingIcon: vi.fn(),
}));

vi.mock("../../cards/get.js", () => ({
  getUpdatedURL: vi.fn(() => Promise.resolve()),
  handleRejectFromGetURL: vi.fn(),
  deleteURLOnStale: vi.fn(),
}));

vi.mock("../../deck.js", () => ({ showURLDeckBannerError: vi.fn() }));

vi.mock("../../outcome-banner.js", () => ({
  clearURLOutcomeBanner: vi.fn(),
}));

vi.mock("../../../utub-locked.js", () => ({
  isUtubLockedHandled: vi.fn(() => false),
}));

vi.mock("../../cards/options/tag-btn.js", () => ({
  createAddTagIcon: vi.fn(() => window.jQuery("<i></i>")),
}));

vi.mock("../../mobile.js", () => ({ isMobile: vi.fn(() => false) }));

vi.mock("../../../tags/utils.js", () => ({
  isTagInUTubTagDeck: vi.fn(() => false),
}));

vi.mock("../../../tags/tags.js", () => ({
  buildTagFilterInDeck: vi.fn(() => window.jQuery("<div></div>")),
}));

vi.mock("../tags.js", () => ({
  createTagBadgeInURL: vi.fn(() =>
    window.jQuery('<span class="tagBadge"></span>'),
  ),
  createTagDeleteIcon: vi.fn(() => window.jQuery("<svg></svg>")),
  disableTagRemovalInURLCard: vi.fn(),
  enableTagRemovalInURLCard: vi.fn(),
}));

vi.mock("../../cards/filtering.js", () => ({
  updateTagFilterCount: vi.fn(),
  TagCountOperation: { INCREMENT: "increment" },
}));

vi.mock("../../../../lib/jquery-plugins.js", () => ({
  enableTabbableChildElements: vi.fn(),
  disableTabbableChildElements: vi.fn(),
}));

const storeState: {
  activeUTubID: number | null;
  urls: { utubUrlID: number; utubUrlTagIDs: number[] }[];
  tags: { id: number; tagString: string; tagApplied: number }[];
} = { activeUTubID: 1, urls: [], tags: [] };

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => storeState),
  setState: vi.fn((partial: Partial<typeof storeState>) => {
    Object.assign(storeState, partial);
  }),
}));

const $ = window.jQuery;

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="true" data-utub-url-tag-ids="">
    <button class="urlTagBtnCreate fourty-p-width"></button>
    <div class="urlBtnAccess"></div>
    <div class="urlStringBtnUpdate"></div>
    <div class="urlBtnDelete"></div>
    <div class="urlBtnCopy"></div>
    <div class="urlTagsContainer"></div>
    <div class="urlTagComboboxWrap">
      <div class="urlTagCombobox"></div>
      <div class="urlTagListbox"></div>
      <div class="urlTagComboboxMsg"></div>
    </div>
  </div>
  <div id="unselectAllTagFilters"></div>
  <div id="listTags"></div>
  <div id="utubTagBtnUpdateAllOpen"></div>
`;

beforeEach(() => {
  document.body.innerHTML = URL_CARD_HTML;
  storeState.activeUTubID = 1;
  storeState.urls = [{ utubUrlID: 1, utubUrlTagIDs: [] }];
  storeState.tags = [];
  vi.clearAllMocks();
});

afterEach(() => {
  document.body.innerHTML = "";
});

describe("submitStagedTagsSuccess — happy path", () => {
  const response = {
    status: "Success" as const,
    utubUrlTagIDs: [7, 8],
    appliedTags: [
      { id: 7, tagString: "python", tagApplied: 3 },
      { id: 8, tagString: "backend", tagApplied: 1 },
    ],
  };

  it("merges applied tags into the store, appends badges, and emits UI_TAG_APPLY", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const urlCard = $(".urlRow");

    submitStagedTagsSuccess({ response, urlCard, utubID: 1 });

    expect(emit).toHaveBeenCalledWith({ event: UI_EVENTS.UI_TAG_APPLY });
    expect(storeState.tags).toEqual(response.appliedTags);
    expect(storeState.urls[0].utubUrlTagIDs).toEqual([7, 8]);
    expect(urlCard.find(".urlTagsContainer .tagBadge").length).toBe(2);
    expect(urlCard.attr("data-utub-url-tag-ids")).toBe("7,8");
  });

  it("does NOT emit UI_TAG_APPLY when appliedTags is empty (no-op batch)", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const urlCard = $(".urlRow");

    submitStagedTagsSuccess({
      response: {
        status: "Success" as const,
        utubUrlTagIDs: [],
        appliedTags: [],
      },
      urlCard,
      utubID: 1,
    });

    expect(emit).not.toHaveBeenCalledWith({ event: UI_EVENTS.UI_TAG_APPLY });
    expect(urlCard.find(".urlTagsContainer .tagBadge").length).toBe(0);
  });
});

describe("submitStagedTagsFail — sad paths", () => {
  it("renders an inline error and does NOT emit UI_TAG_APPLY on 400", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const urlCard = $(".urlRow");

    submitStagedTagsFail({
      xhr: {
        status: 400,
        responseJSON: { errors: { tagStrings: ["Too many tags"] } },
      } as unknown as JQuery.jqXHR,
      urlCard,
    });

    expect(urlCard.find(".urlTagComboboxMsg").text()).toBe("Too many tags");
    expect(urlCard.find(".urlTagComboboxMsg").hasClass("warn")).toBe(true);
    expect(emit).not.toHaveBeenCalledWith({ event: UI_EVENTS.UI_TAG_APPLY });
  });

  it("short-circuits when is429Handled returns true", () => {
    vi.mocked(is429Handled).mockReturnValueOnce(true);
    const urlCard = $(".urlRow");

    submitStagedTagsFail({
      xhr: { status: 429 } as unknown as JQuery.jqXHR,
      urlCard,
    });

    expect(urlCard.find(".urlTagComboboxMsg").text()).toBe("");
  });
});

const APPLIED_RESPONSE = {
  status: "Success" as const,
  utubUrlTagIDs: [7],
  appliedTags: [{ id: 7, tagString: "python", tagApplied: 3 }],
};

const NOOP_RESPONSE = {
  status: "Success" as const,
  utubUrlTagIDs: [],
  appliedTags: [],
};

describe("submitStagedTagsSuccess — applySource", () => {
  it("drag source emits UI_TAG_APPLY_DRAG once and not UI_TAG_APPLY", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    submitStagedTagsSuccess({
      response: APPLIED_RESPONSE,
      urlCard: $(".urlRow"),
      utubID: 1,
      applySource: "drag",
    });

    expect(emit).toHaveBeenCalledTimes(1);
    expect(emit).toHaveBeenCalledWith({ event: UI_EVENTS.UI_TAG_APPLY_DRAG });
  });

  it("combobox source (explicit or default) emits only UI_TAG_APPLY", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    submitStagedTagsSuccess({
      response: APPLIED_RESPONSE,
      urlCard: $(".urlRow"),
      utubID: 1,
      applySource: "combobox",
    });

    expect(emit).toHaveBeenCalledTimes(1);
    expect(emit).toHaveBeenCalledWith({ event: UI_EVENTS.UI_TAG_APPLY });
  });

  it("emits nothing for a drag no-op (appliedTags empty)", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    submitStagedTagsSuccess({
      response: NOOP_RESPONSE,
      urlCard: $(".urlRow"),
      utubID: 1,
      applySource: "drag",
    });

    expect(emit).not.toHaveBeenCalled();
  });

  it("drag success leaves a visible combobox untouched and does not re-enable click-to-hide", () => {
    const urlCard = $(".urlRow");
    const wrap = urlCard.find(".urlTagComboboxWrap");
    expect(wrap.hasClass("hidden")).toBe(false);

    submitStagedTagsSuccess({
      response: APPLIED_RESPONSE,
      urlCard,
      utubID: 1,
      applySource: "drag",
    });

    expect(wrap.hasClass("hidden")).toBe(false);
    expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
    expect(urlCard.find(".urlTagsContainer .tagBadge").length).toBe(1);
  });

  it("drag success re-enables click-to-hide when the card is selected and the combobox is hidden", () => {
    const urlCard = $(".urlRow");
    urlCard.find(".urlTagComboboxWrap").addClass("hidden");

    submitStagedTagsSuccess({
      response: APPLIED_RESPONSE,
      urlCard,
      utubID: 1,
      applySource: "drag",
    });

    expect(enableClickOnSelectedURLCardToHide).toHaveBeenCalledTimes(1);
  });

  it("drag success does not re-enable click-to-hide on an unselected card", () => {
    const urlCard = $(".urlRow");
    urlCard.attr("urlSelected", "false");
    urlCard.find(".urlTagComboboxWrap").addClass("hidden");

    submitStagedTagsSuccess({
      response: APPLIED_RESPONSE,
      urlCard,
      utubID: 1,
      applySource: "drag",
    });

    expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
  });

  it("combobox success still resets the combobox", () => {
    const urlCard = $(".urlRow");

    submitStagedTagsSuccess({
      response: APPLIED_RESPONSE,
      urlCard,
      utubID: 1,
    });

    expect(urlCard.find(".urlTagComboboxWrap").hasClass("hidden")).toBe(true);
  });

  it("drag success after a UTub switch touches neither the store nor the DOM", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    storeState.activeUTubID = 2;
    const urlCard = $(".urlRow");

    submitStagedTagsSuccess({
      response: APPLIED_RESPONSE,
      urlCard,
      utubID: 1,
      applySource: "drag",
    });

    expect(emit).toHaveBeenCalledWith({ event: UI_EVENTS.UI_TAG_APPLY_DRAG });
    expect(setState).not.toHaveBeenCalled();
    expect(storeState.urls[0].utubUrlTagIDs).toEqual([]);
    expect(urlCard.find(".urlTagsContainer .tagBadge").length).toBe(0);
    expect(urlCard.find(".urlTagComboboxWrap").hasClass("hidden")).toBe(false);
    expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
  });
});

describe("submitStagedTags — outcome", () => {
  type Callback = (...args: unknown[]) => void;

  function deferredRequest(): {
    callbacks: { done?: Callback; fail?: Callback; always?: Callback };
  } {
    const callbacks: { done?: Callback; fail?: Callback; always?: Callback } =
      {};
    const request: Record<string, unknown> = {};
    for (const method of ["done", "fail", "always"] as const) {
      request[method] = vi.fn((callback: Callback) => {
        callbacks[method] = callback;
        return request;
      });
    }
    vi.mocked(ajaxCall).mockReturnValue(request as unknown as JQuery.jqXHR);
    return { callbacks };
  }

  const submit = () =>
    submitStagedTags({
      urlCard: $(".urlRow"),
      utubID: 1,
      utubUrlID: 1,
      stagedStrings: ["python"],
      applySource: "drag",
    });

  async function flush(): Promise<void> {
    await new Promise((resolve) => setTimeout(resolve, 0));
  }

  it("does not settle before the POST completes", async () => {
    deferredRequest();
    let settled = false;
    void submit().then(() => {
      settled = true;
    });

    await flush();
    expect(settled).toBe(false);
  });

  it("settles 'applied' for a 200 response that applied tags", async () => {
    const { callbacks } = deferredRequest();
    const outcome = submit();
    await flush();

    callbacks.done!(APPLIED_RESPONSE, "success", { status: 200 });
    await expect(outcome).resolves.toBe("applied");
  });

  it("settles 'noop' for a 200 response with appliedTags: []", async () => {
    const { callbacks } = deferredRequest();
    const outcome = submit();
    await flush();

    callbacks.done!(NOOP_RESPONSE, "success", { status: 200 });
    await expect(outcome).resolves.toBe("noop");
  });

  it("settles 'failed' for a failed request", async () => {
    const { callbacks } = deferredRequest();
    const outcome = submit();
    await flush();

    callbacks.fail!({
      status: 400,
      responseJSON: { message: "Too many tags" },
    });
    await expect(outcome).resolves.toBe("failed");
  });

  it("settles even when a 200 response body is malformed (no appliedTags)", async () => {
    const { callbacks } = deferredRequest();
    const outcome = submit();
    await flush();

    expect(() =>
      callbacks.done!({ status: "Success" }, "success", { status: 200 }),
    ).toThrow();
    await expect(outcome).resolves.toBe("failed");
  });

  it("settles 'failed' for a non-200 success status", async () => {
    const { callbacks } = deferredRequest();
    const outcome = submit();
    await flush();

    callbacks.done!(APPLIED_RESPONSE, "success", { status: 204 });
    await expect(outcome).resolves.toBe("failed");
  });

  it("settles 'aborted' when the pre-flight getUpdatedURL rejects, and sends no POST", async () => {
    const { getUpdatedURL } = await import("../../cards/get.js");
    vi.mocked(getUpdatedURL).mockRejectedValueOnce({ status: 404 });
    deferredRequest();

    await expect(submit()).resolves.toBe("aborted");
    expect(ajaxCall).not.toHaveBeenCalled();
  });

  it("still settles 'applied' when the success renderer throws, and rethrows", async () => {
    const { callbacks } = deferredRequest();
    const outcome = submit();
    await flush();

    vi.mocked(setState).mockImplementationOnce(() => {
      throw new Error("renderer threw");
    });
    expect(() =>
      callbacks.done!(APPLIED_RESPONSE, "success", { status: 200 }),
    ).toThrow("renderer threw");
    await expect(outcome).resolves.toBe("applied");
  });

  it("the always fallback settles 'failed' for a promise still pending", async () => {
    const { callbacks } = deferredRequest();
    const outcome = submit();
    await flush();

    callbacks.always!();
    await expect(outcome).resolves.toBe("failed");
  });

  it("a settled outcome is not overwritten by a later always callback", async () => {
    const { callbacks } = deferredRequest();
    const outcome = submit();
    await flush();

    callbacks.done!(APPLIED_RESPONSE, "success", { status: 200 });
    callbacks.always!();
    await expect(outcome).resolves.toBe("applied");
  });
});

describe("submitStagedTagsFail — applySource", () => {
  const LOCKED_MESSAGE = "UTub is locked";
  const FAILED_TEXT = "Couldn't add the tag. Please try again.";
  const assignMock = vi.fn();
  let originalLocation: Location;

  function mountCard({ comboboxHidden }: { comboboxHidden: boolean }): JQuery {
    document.body.innerHTML = `<div id="listURLs">${URL_CARD_HTML}</div>`;
    if (comboboxHidden) $(".urlTagComboboxWrap").addClass("hidden");
    return $(".urlRow");
  }

  function jsonXhr({
    status,
    responseJSON,
  }: {
    status: number;
    responseJSON: unknown;
  }): JQuery.jqXHR {
    return { status, responseJSON } as unknown as JQuery.jqXHR;
  }

  beforeEach(() => {
    originalLocation = window.location;
    assignMock.mockClear();
    Object.defineProperty(window, "location", {
      value: { assign: assignMock },
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
      configurable: true,
    });
  });

  describe("drag source (same result with the combobox hidden or visible)", () => {
    it.each([true, false])(
      "shows a message-only 400 in the deck banner (combobox hidden: %s)",
      (comboboxHidden) => {
        const urlCard = mountCard({ comboboxHidden });
        submitStagedTagsFail({
          xhr: jsonXhr({ status: 400, responseJSON: { message: "Limit" } }),
          urlCard,
          applySource: "drag",
        });

        expect(showURLDeckBannerError).toHaveBeenCalledWith("Limit");
        expect(urlCard.find(".urlTagComboboxMsg").text()).toBe("");
        expect(assignMock).not.toHaveBeenCalled();
      },
    );

    it.each([true, false])(
      "shows the first field message of a field-error 400 (combobox hidden: %s)",
      (comboboxHidden) => {
        const urlCard = mountCard({ comboboxHidden });
        submitStagedTagsFail({
          xhr: jsonXhr({
            status: 400,
            responseJSON: { errors: { tagStrings: ["Too many tags"] } },
          }),
          urlCard,
          applySource: "drag",
        });

        expect(showURLDeckBannerError).toHaveBeenCalledWith("Too many tags");
        expect(urlCard.find(".urlTagComboboxMsg").text()).toBe("");
      },
    );

    it.each([
      ["no errors and no message", {}],
      ["an empty field array", { errors: { tagStrings: [] } }],
      ["an unknown field only", { errors: { other: ["x"] } }],
      ["an empty message", { message: "" }],
    ])("falls back to TAG_DROP_FAILED for a 400 with %s", (_label, body) => {
      submitStagedTagsFail({
        xhr: jsonXhr({ status: 400, responseJSON: body }),
        urlCard: mountCard({ comboboxHidden: true }),
        applySource: "drag",
      });

      expect(showURLDeckBannerError).toHaveBeenCalledWith(FAILED_TEXT);
    });

    it("shows the deleted-URL banner and removes the card on a JSON 404", () => {
      const urlCard = mountCard({ comboboxHidden: true });
      submitStagedTagsFail({
        xhr: jsonXhr({ status: 404, responseJSON: { message: "gone" } }),
        urlCard,
        applySource: "drag",
      });

      expect(showURLDeckBannerError).toHaveBeenCalledWith(
        "Another user has deleted this URL",
      );
      expect(deleteURLOnStale).toHaveBeenCalledWith(urlCard);
      expect(assignMock).not.toHaveBeenCalled();
    });

    it.each([500, 403, 418])(
      "shows TAG_DROP_FAILED without redirecting for a JSON %i",
      (status) => {
        submitStagedTagsFail({
          xhr: jsonXhr({ status, responseJSON: { message: "nope" } }),
          urlCard: mountCard({ comboboxHidden: false }),
          applySource: "drag",
        });

        expect(showURLDeckBannerError).toHaveBeenCalledWith(FAILED_TEXT);
        expect(assignMock).not.toHaveBeenCalled();
        expect(deleteURLOnStale).not.toHaveBeenCalled();
      },
    );

    it("shows TAG_DROP_FAILED for a non-JSON failure instead of redirecting", () => {
      submitStagedTagsFail({
        xhr: {
          status: 502,
          getResponseHeader: () => "text/html; charset=utf-8",
        } as unknown as JQuery.jqXHR,
        urlCard: mountCard({ comboboxHidden: true }),
        applySource: "drag",
      });

      expect(showURLDeckBannerError).toHaveBeenCalledWith(FAILED_TEXT);
      expect(assignMock).not.toHaveBeenCalled();
    });

    it("keeps replacing the body for the CSRF HTML 403", () => {
      submitStagedTagsFail({
        xhr: {
          status: 403,
          responseText: "<p id='csrf'>csrf</p>",
          getResponseHeader: () => "text/html; charset=utf-8",
        } as unknown as JQuery.jqXHR,
        urlCard: mountCard({ comboboxHidden: true }),
        applySource: "drag",
      });

      expect(document.getElementById("csrf")).not.toBeNull();
      expect(showURLDeckBannerError).not.toHaveBeenCalled();
    });

    it("clears the stale outcome banner before the error banner shows", () => {
      const order: string[] = [];
      vi.mocked(clearURLOutcomeBanner).mockImplementationOnce(() => {
        order.push("clear");
      });
      vi.mocked(showURLDeckBannerError).mockImplementationOnce(() => {
        order.push("error");
      });

      submitStagedTagsFail({
        xhr: jsonXhr({ status: 500, responseJSON: {} }),
        urlCard: mountCard({ comboboxHidden: true }),
        applySource: "drag",
      });

      expect(order).toEqual(["clear", "error"]);
    });

    it("does nothing when the card is no longer inside #listURLs", () => {
      const urlCard = mountCard({ comboboxHidden: true });
      urlCard.detach();

      submitStagedTagsFail({
        xhr: jsonXhr({ status: 404, responseJSON: {} }),
        urlCard,
        applySource: "drag",
      });

      expect(clearURLOutcomeBanner).not.toHaveBeenCalled();
      expect(showURLDeckBannerError).not.toHaveBeenCalled();
      expect(deleteURLOnStale).not.toHaveBeenCalled();
    });

    it("shows the lock banner instead of redirecting on a locked-UTub 403", () => {
      vi.mocked(isUtubLockedHandled).mockReturnValueOnce(true);
      submitStagedTagsFail({
        xhr: jsonXhr({
          status: 403,
          responseJSON: { message: LOCKED_MESSAGE },
        }),
        urlCard: mountCard({ comboboxHidden: true }),
        applySource: "drag",
      });

      expect(isUtubLockedHandled).toHaveBeenCalledTimes(1);
      expect(showURLDeckBannerError).not.toHaveBeenCalled();
      expect(assignMock).not.toHaveBeenCalled();
    });
  });

  describe("combobox source (and the default)", () => {
    it.each([undefined, "combobox" as const])(
      "keeps a message-only 400 inline in the open combobox (applySource: %s)",
      (applySource) => {
        const urlCard = mountCard({ comboboxHidden: false });
        submitStagedTagsFail({
          xhr: jsonXhr({ status: 400, responseJSON: { message: "Limit" } }),
          urlCard,
          applySource,
        });

        expect(urlCard.find(".urlTagComboboxMsg").text()).toBe("Limit");
        expect(urlCard.find(".urlTagComboboxMsg").hasClass("warn")).toBe(true);
        expect(showURLDeckBannerError).not.toHaveBeenCalled();
        expect(clearURLOutcomeBanner).not.toHaveBeenCalled();
      },
    );

    it("keeps a field-error 400 inline", () => {
      const urlCard = mountCard({ comboboxHidden: false });
      submitStagedTagsFail({
        xhr: jsonXhr({
          status: 400,
          responseJSON: { errors: { tagStrings: ["Bad tag"] } },
        }),
        urlCard,
        applySource: "combobox",
      });

      expect(urlCard.find(".urlTagComboboxMsg").text()).toBe("Bad tag");
      expect(showURLDeckBannerError).not.toHaveBeenCalled();
    });

    it.each([404, 500, 403])(
      "still redirects to the error page for a JSON %i",
      (status) => {
        submitStagedTagsFail({
          xhr: jsonXhr({ status, responseJSON: { message: "x" } }),
          urlCard: mountCard({ comboboxHidden: false }),
        });

        expect(assignMock).toHaveBeenCalledTimes(1);
        expect(showURLDeckBannerError).not.toHaveBeenCalled();
        expect(clearURLOutcomeBanner).not.toHaveBeenCalled();
        expect(deleteURLOnStale).not.toHaveBeenCalled();
      },
    );

    it("still redirects for a non-JSON failure", () => {
      submitStagedTagsFail({
        xhr: {
          status: 502,
          getResponseHeader: () => "text/html; charset=utf-8",
        } as unknown as JQuery.jqXHR,
        urlCard: mountCard({ comboboxHidden: false }),
      });

      expect(assignMock).toHaveBeenCalledTimes(1);
    });

    it("shows the lock banner with the combobox open and does not redirect", () => {
      vi.mocked(isUtubLockedHandled).mockReturnValueOnce(true);
      submitStagedTagsFail({
        xhr: jsonXhr({
          status: 403,
          responseJSON: { message: LOCKED_MESSAGE },
        }),
        urlCard: mountCard({ comboboxHidden: false }),
        applySource: "combobox",
      });

      expect(isUtubLockedHandled).toHaveBeenCalledTimes(1);
      expect(assignMock).not.toHaveBeenCalled();
    });
  });

  describe("click-to-hide re-enable", () => {
    it("re-enables click-to-hide on a selected card whose combobox is hidden, even on a 429", () => {
      vi.mocked(is429Handled).mockReturnValueOnce(true);
      const urlCard = mountCard({ comboboxHidden: true });

      submitStagedTagsFail({
        xhr: jsonXhr({ status: 429, responseJSON: {} }),
        urlCard,
        applySource: "drag",
      });

      expect(enableClickOnSelectedURLCardToHide).toHaveBeenCalledWith(urlCard);
    });

    it("re-enables click-to-hide on a locked-UTub failure", () => {
      vi.mocked(isUtubLockedHandled).mockReturnValueOnce(true);
      const urlCard = mountCard({ comboboxHidden: true });

      submitStagedTagsFail({
        xhr: jsonXhr({ status: 403, responseJSON: {} }),
        urlCard,
        applySource: "drag",
      });

      expect(enableClickOnSelectedURLCardToHide).toHaveBeenCalledWith(urlCard);
    });

    it("leaves click-to-hide disabled while a combobox is open on the card", () => {
      submitStagedTagsFail({
        xhr: jsonXhr({ status: 500, responseJSON: {} }),
        urlCard: mountCard({ comboboxHidden: false }),
        applySource: "drag",
      });

      expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
    });

    it("does not touch click-to-hide on an unselected card", () => {
      const urlCard = mountCard({ comboboxHidden: true });
      urlCard.attr("urlSelected", "false");

      submitStagedTagsFail({
        xhr: jsonXhr({ status: 500, responseJSON: {} }),
        urlCard,
        applySource: "drag",
      });

      expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
    });
  });
});
