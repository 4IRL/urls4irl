import { ajaxCall } from "../../../../lib/ajax.js";
import { getUpdatedURL } from "../get.js";
import { hideURLSearchIcon } from "../../search.js";
import { showURLsEmptyState } from "../../empty-state.js";
import { showURLDeckBannerError } from "../../deck.js";
import { deleteURLShowModal } from "../delete.js";

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
  <div id="confirmModal" class="modal">
    <span id="confirmModalTitle"></span>
    <span id="confirmModalBody"></span>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <div id="modalRedirect"></div>
  </div>
  <div id="noURLsEmptyState" class="hidden">
    <p id="noURLsSubheader"></p>
  </div>
  <div id="listURLs"></div>
`;

function buildUrlCard(utubUrlID: number): JQuery {
  return $(
    `<div class="urlRow" utuburlid="${utubUrlID}" data-utub-url-tag-ids=""></div>`,
  );
}

function triggerDeleteFlow(
  utubUrlID: number,
  urlCard: JQuery,
  utubID: number,
  responsePayload: Record<string, unknown>,
): void {
  type DoneCallback = (
    response: Record<string, unknown>,
    status: string,
    xhr: JQuery.jqXHR,
  ) => void;

  const mockXHR = {
    done: vi.fn().mockReturnThis(),
    fail: vi.fn().mockReturnThis(),
    always: vi.fn().mockReturnThis(),
  };
  vi.mocked(ajaxCall).mockReturnValue(mockXHR as unknown as JQuery.jqXHR);

  deleteURLShowModal(utubUrlID, urlCard, utubID);
  $("#modalSubmit").trigger("click");

  setTimeout(() => {
    const doneCallback = mockXHR.done.mock.calls[0][0] as DoneCallback;
    doneCallback(responsePayload, "success", {
      status: 200,
    } as JQuery.jqXHR);
  }, 0);
}

describe("deleteURLSuccess — empty-state branches", () => {
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

  it("shows empty state with UTUB_NO_URLS when last URL is removed", async () => {
    const urlCard = buildUrlCard(42);
    $("#listURLs").append(urlCard);

    const responsePayload = { URL: { utubUrlID: 42 } };
    triggerDeleteFlow(42, urlCard, 1, responsePayload);

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

    const responsePayload = { URL: { utubUrlID: 42 } };
    triggerDeleteFlow(42, urlCardToDelete, 1, responsePayload);

    await vi.waitFor(() => {
      expect($("#listURLs .urlRow").length).toBe(1);
    });

    expect(showURLsEmptyState).not.toHaveBeenCalled();
    expect(hideURLSearchIcon).not.toHaveBeenCalled();
  });
});

describe("deleteURLFail — locked UTub 403", () => {
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

  it("shows the inline banner and does not redirect to the error page", async () => {
    const locationAssignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});

    const urlCard = buildUrlCard(42);
    $("#listURLs").append(urlCard);

    const mockXHR = {
      done: vi.fn().mockReturnThis(),
      fail: vi.fn().mockReturnThis(),
      always: vi.fn().mockReturnThis(),
    };
    vi.mocked(ajaxCall).mockReturnValue(mockXHR as unknown as JQuery.jqXHR);

    deleteURLShowModal(42, urlCard, 1);
    $("#modalSubmit").trigger("click");

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

    expect(showURLDeckBannerError).toHaveBeenCalledWith(LOCKED_MESSAGE);
    expect(locationAssignSpy).not.toHaveBeenCalled();
  });
});
