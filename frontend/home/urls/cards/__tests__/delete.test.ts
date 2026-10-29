import { ajaxCall } from "../../../../lib/ajax.js";
import { getUpdatedURL, handleRejectFromGetURL } from "../get.js";
import { hideURLSearchIcon } from "../../search.js";
import { showURLsEmptyState } from "../../empty-state.js";
import { showURLDeckBannerError } from "../../deck.js";
import { getState, setState } from "../../../../store/app-store.js";
import { refreshTrashCount } from "../../../trash/count.js";
import { showURLDeletedToast } from "../delete-undo.js";
import { deleteURL, isURLDeleteInFlight } from "../delete.js";

vi.mock("../../../trash/count.js", () => ({ refreshTrashCount: vi.fn() }));

vi.mock("../delete-undo.js", () => ({ showURLDeletedToast: vi.fn() }));

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

// deck.js is pulled in via the shared lock guard (../../utub-locked.js);
// mock it so we can assert the inline banner without loading the real deck.
vi.mock("../../deck.js", () => ({
  showURLDeckBannerError: vi.fn(),
}));

vi.mock("../get.js", () => ({
  getUpdatedURL: vi.fn(() => Promise.resolve()),
  handleRejectFromGetURL: vi.fn(),
}));

vi.mock("../filtering.js", () => ({
  updateTagFilteringOnURLOrURLTagDeletion: vi.fn(),
}));

vi.mock("../../../utubs/row-counts.js", () => ({
  applyRowCountDelta: vi.fn(),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [] })),
  setState: vi.fn(),
}));

vi.mock("../../search.js", () => ({
  hideURLSearchIcon: vi.fn(),
}));

vi.mock("../../empty-state.js", () => ({
  showURLsEmptyState: vi.fn(),
  hideURLsEmptyState: vi.fn(),
}));

const $ = window.jQuery;

const DELETE_URL_HTML = `
  <div id="confirmModal" class="modal"></div>
  <div id="noURLsEmptyState" class="hidden" tabindex="-1">
    <p id="noURLsSubheader"></p>
  </div>
  <div id="URLDeck" tabindex="-1">
    <div id="listURLs"></div>
  </div>
`;

function buildUrlCard(utubUrlID: number): JQuery {
  return $(
    `<div class="urlRow" utuburlid="${utubUrlID}" data-utub-url-tag-ids="" tabindex="-1"><button class="urlBtnDelete"></button></div>`,
  );
}

type DoneCallback = (
  response: Record<string, unknown>,
  status: string,
  xhr: JQuery.jqXHR,
) => void;

function mockRequest(): {
  done: ReturnType<typeof vi.fn>;
  fail: ReturnType<typeof vi.fn>;
  always: ReturnType<typeof vi.fn>;
} {
  const mockXHR = {
    done: vi.fn().mockReturnThis(),
    fail: vi.fn().mockReturnThis(),
    always: vi.fn().mockReturnThis(),
  };
  vi.mocked(ajaxCall).mockReturnValue(mockXHR as unknown as JQuery.jqXHR);
  return mockXHR;
}

async function resolveDone(
  mockXHR: ReturnType<typeof mockRequest>,
  responsePayload: Record<string, unknown>,
): Promise<void> {
  await vi.waitFor(() => {
    expect(mockXHR.done).toHaveBeenCalled();
  });
  const doneCallback = mockXHR.done.mock.calls[0][0] as DoneCallback;
  doneCallback(responsePayload, "success", { status: 200 } as JQuery.jqXHR);
}

async function triggerDeleteFlow(
  utubUrlID: number,
  urlCard: JQuery,
  utubID: number,
  responsePayload: Record<string, unknown>,
): Promise<boolean> {
  const mockXHR = mockRequest();
  const outcome = deleteURL({ utubUrlID, urlCard, utubID });
  await resolveDone(mockXHR, responsePayload);
  return outcome;
}

describe("deleteURL — success", () => {
  beforeEach(() => {
    document.body.innerHTML = DELETE_URL_HTML;
    $.fn.modal = vi.fn().mockReturnThis();
    $.fx.off = true;
    vi.clearAllMocks();
    vi.mocked(getUpdatedURL).mockResolvedValue(undefined);
  });

  afterEach(() => {
    $.fx.off = false;
    document.body.innerHTML = "";
  });

  it("checks for staleness then sends the DELETE with no modal shown", async () => {
    const urlCard = buildUrlCard(42);
    $("#listURLs").append(urlCard);

    await triggerDeleteFlow(42, urlCard, 1, { URL: { utubUrlID: 42 } });

    expect(getUpdatedURL).toHaveBeenCalledWith(1, 42, urlCard);
    expect(ajaxCall).toHaveBeenCalledWith("delete", expect.any(String), []);
    expect($.fn.modal).not.toHaveBeenCalledWith("show");
  });

  it("refreshes the trash count, removes the card, shows the toast and resolves true", async () => {
    const urlCard = buildUrlCard(42);
    const nextCard = buildUrlCard(99);
    $("#listURLs").append(urlCard).append(nextCard);

    const outcome = await triggerDeleteFlow(42, urlCard, 1, {
      URL: { utubUrlID: 42 },
    });

    expect(outcome).toBe(true);
    expect(refreshTrashCount).toHaveBeenCalledTimes(1);
    expect($("#listURLs .urlRow").length).toBe(1);
    expect(showURLDeletedToast).toHaveBeenCalledWith({
      utubID: 1,
      deletedIDs: [42],
      skippedCount: 0,
      hiddenCount: 0,
      returnFocusTo: expect.anything(),
    });
    const toastArgs = vi.mocked(showURLDeletedToast).mock.calls[0][0];
    expect(toastArgs.returnFocusTo[0]).toBe(nextCard[0]);
  });

  it("focuses the next row once the card is removed and runs beforeFocus first", async () => {
    const urlCard = buildUrlCard(42);
    const nextCard = buildUrlCard(99);
    $("#listURLs").append(urlCard).append(nextCard);
    const order: string[] = [];
    const beforeFocus = vi.fn(() => order.push("beforeFocus"));
    nextCard.on("focus", () => order.push("focus"));

    const mockXHR = mockRequest();
    const outcome = deleteURL({
      utubUrlID: 42,
      urlCard,
      utubID: 1,
      beforeFocus,
    });
    await resolveDone(mockXHR, { URL: { utubUrlID: 42 } });
    await outcome;

    expect(beforeFocus).toHaveBeenCalledWith(expect.anything());
    expect(order).toEqual(["beforeFocus", "focus"]);
  });

  it("does not steal focus or run beforeFocus when another element holds focus", async () => {
    const urlCard = buildUrlCard(42);
    const nextCard = buildUrlCard(99);
    $("#listURLs").append(urlCard).append(nextCard);
    const otherButton = document.createElement("button");
    document.body.appendChild(otherButton);
    otherButton.focus();
    const beforeFocus = vi.fn();

    const mockXHR = mockRequest();
    const outcome = deleteURL({
      utubUrlID: 42,
      urlCard,
      utubID: 1,
      beforeFocus,
    });
    await resolveDone(mockXHR, { URL: { utubUrlID: 42 } });
    await outcome;

    expect(beforeFocus).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(otherButton);
  });

  it("does not focus or run beforeFocus when the target was detached", async () => {
    const urlCard = buildUrlCard(42);
    const nextCard = buildUrlCard(99);
    $("#listURLs").append(urlCard).append(nextCard);
    const beforeFocus = vi.fn();
    const focusSpy = vi.fn();
    nextCard.on("focus", focusSpy);
    vi.mocked(setState).mockImplementationOnce(() => {
      nextCard.remove();
    });

    const mockXHR = mockRequest();
    const outcome = deleteURL({
      utubUrlID: 42,
      urlCard,
      utubID: 1,
      beforeFocus,
    });
    await resolveDone(mockXHR, { URL: { utubUrlID: 42 } });
    await outcome;

    expect(beforeFocus).not.toHaveBeenCalled();
    expect(focusSpy).not.toHaveBeenCalled();
  });

  it("removes the card from the store before showing the toast", async () => {
    const urlCard = buildUrlCard(42);
    $("#listURLs").append(urlCard);

    await triggerDeleteFlow(42, urlCard, 1, { URL: { utubUrlID: 42 } });

    expect(vi.mocked(setState).mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(showURLDeletedToast).mock.invocationCallOrder[0],
    );
  });

  it("resolves false and re-enables the button when the success handler throws", async () => {
    const urlCard = buildUrlCard(42);
    $("#listURLs").append(urlCard);
    vi.mocked(showURLDeletedToast).mockImplementationOnce(() => {
      throw new Error("toast failed");
    });

    const outcome = await triggerDeleteFlow(42, urlCard, 1, {
      URL: { utubUrlID: 42 },
    });

    expect(outcome).toBe(false);
    expect(urlCard.find(".urlBtnDelete").attr("aria-disabled")).toBeUndefined();
    expect(isURLDeleteInFlight()).toBe(false);
  });

  it("resolves false without a toast when the response status is not 200", async () => {
    const urlCard = buildUrlCard(42);
    $("#listURLs").append(urlCard);
    const mockXHR = mockRequest();

    const outcome = deleteURL({ utubUrlID: 42, urlCard, utubID: 1 });
    await vi.waitFor(() => {
      expect(mockXHR.done).toHaveBeenCalled();
    });
    const doneCallback = mockXHR.done.mock.calls[0][0] as DoneCallback;
    doneCallback({ URL: { utubUrlID: 42 } }, "success", {
      status: 204,
    } as JQuery.jqXHR);

    expect(await outcome).toBe(false);
    expect(urlCard.find(".urlBtnDelete").attr("aria-disabled")).toBeUndefined();
    expect(showURLDeletedToast).not.toHaveBeenCalled();
    expect(isURLDeleteInFlight()).toBe(false);
  });

  it("shows empty state with UTUB_NO_URLS when last URL is removed", async () => {
    const urlCard = buildUrlCard(42);
    $("#listURLs").append(urlCard);

    await triggerDeleteFlow(42, urlCard, 1, { URL: { utubUrlID: 42 } });

    await vi.waitFor(() => {
      expect($("#listURLs .urlRow").length).toBe(0);
    });

    expect(showURLsEmptyState).toHaveBeenCalled();
    expect(hideURLSearchIcon).toHaveBeenCalled();
  });

  it("keeps empty state hidden when other URLs remain after deletion", async () => {
    const urlCardToDelete = buildUrlCard(42);
    const urlCardRemaining = buildUrlCard(99);
    $("#listURLs").append(urlCardToDelete).append(urlCardRemaining);

    await triggerDeleteFlow(42, urlCardToDelete, 1, {
      URL: { utubUrlID: 42 },
    });

    await vi.waitFor(() => {
      expect($("#listURLs .urlRow").length).toBe(1);
    });

    expect(showURLsEmptyState).not.toHaveBeenCalled();
    expect(hideURLSearchIcon).not.toHaveBeenCalled();
  });

  it("removes the deleted URL from the store through the shared deck removal", async () => {
    const urlCardToDelete = buildUrlCard(42);
    const urlCardRemaining = buildUrlCard(99);
    $("#listURLs").append(urlCardToDelete).append(urlCardRemaining);
    vi.mocked(getState).mockReturnValueOnce({
      urls: [{ utubUrlID: 42 }, { utubUrlID: 99 }],
    } as unknown as ReturnType<typeof getState>);

    await triggerDeleteFlow(42, urlCardToDelete, 1, {
      URL: { utubUrlID: 42 },
    });

    await vi.waitFor(() => {
      expect($("#listURLs .urlRow").length).toBe(1);
    });

    expect(setState).toHaveBeenCalledWith({ urls: [{ utubUrlID: 99 }] });
    expect(refreshTrashCount).toHaveBeenCalledTimes(1);
  });
});

describe("deleteURL — in-flight guard", () => {
  beforeEach(() => {
    document.body.innerHTML = DELETE_URL_HTML;
    $.fn.modal = vi.fn().mockReturnThis();
    $.fx.off = true;
    vi.clearAllMocks();
    vi.mocked(getUpdatedURL).mockResolvedValue(undefined);
  });

  afterEach(() => {
    $.fx.off = false;
    document.body.innerHTML = "";
  });

  it("is a no-op for a second delete of the same id while one is in flight", async () => {
    const urlCard = buildUrlCard(4242);
    $("#listURLs").append(urlCard);
    const mockXHR = mockRequest();

    expect(isURLDeleteInFlight()).toBe(false);
    const first = deleteURL({ utubUrlID: 4242, urlCard, utubID: 1 });
    expect(isURLDeleteInFlight()).toBe(true);
    expect(urlCard.find(".urlBtnDelete").attr("aria-disabled")).toBe("true");
    expect(urlCard.find(".urlBtnDelete").prop("disabled")).toBe(false);

    const second = await deleteURL({ utubUrlID: 4242, urlCard, utubID: 1 });
    expect(second).toBe(false);

    await resolveDone(mockXHR, { URL: { utubUrlID: 4242 } });
    expect(await first).toBe(true);
    expect(ajaxCall).toHaveBeenCalledTimes(1);
    expect(isURLDeleteInFlight()).toBe(false);
  });
});

describe("deleteURL — failures", () => {
  const LOCKED_MESSAGE = "This UTub is locked and cannot be modified.";
  // URL operations return URLErrorCodes.UTUB_IS_LOCKED (8), NOT the 3 the
  // UTub/tag/member enums use — the guard must key on the message, not the
  // code, or URL deletes on a locked UTub redirect to the error page.
  const URL_UTUB_IS_LOCKED = 8;

  beforeEach(() => {
    document.body.innerHTML = DELETE_URL_HTML;
    $.fn.modal = vi.fn().mockReturnThis();
    $.fx.off = true;
    vi.clearAllMocks();
    vi.mocked(getUpdatedURL).mockResolvedValue(undefined);
  });

  afterEach(() => {
    $.fx.off = false;
    document.body.innerHTML = "";
  });

  it("shows the inline banner on a locked 403, re-enables the button and resolves false", async () => {
    const locationAssignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});

    const urlCard = buildUrlCard(42);
    $("#listURLs").append(urlCard);
    const mockXHR = mockRequest();

    const outcome = deleteURL({ utubUrlID: 42, urlCard, utubID: 1 });

    await vi.waitFor(() => {
      expect(mockXHR.fail).toHaveBeenCalled();
    });

    const failCallback = mockXHR.fail.mock.calls[0][0] as (
      xhr: JQuery.jqXHR,
    ) => void;
    failCallback({
      status: 403,
      responseJSON: { errorCode: URL_UTUB_IS_LOCKED, message: LOCKED_MESSAGE },
    } as unknown as JQuery.jqXHR);

    expect(await outcome).toBe(false);
    expect(showURLDeckBannerError).toHaveBeenCalledWith(LOCKED_MESSAGE);
    expect(locationAssignSpy).not.toHaveBeenCalled();
    expect(refreshTrashCount).not.toHaveBeenCalled();
    expect(showURLDeletedToast).not.toHaveBeenCalled();
    expect(urlCard.find(".urlBtnDelete").attr("aria-disabled")).toBeUndefined();
    expect(isURLDeleteInFlight()).toBe(false);
  });

  it("resolves false and re-enables the button when the staleness pre-check rejects", async () => {
    const urlCard = buildUrlCard(42);
    $("#listURLs").append(urlCard);
    vi.mocked(getUpdatedURL).mockRejectedValueOnce({ status: 404 });

    const outcome = await deleteURL({ utubUrlID: 42, urlCard, utubID: 1 });

    expect(outcome).toBe(false);
    expect(handleRejectFromGetURL).toHaveBeenCalled();
    expect(ajaxCall).not.toHaveBeenCalled();
    expect(urlCard.find(".urlBtnDelete").attr("aria-disabled")).toBeUndefined();
    expect(isURLDeleteInFlight()).toBe(false);
  });
});
