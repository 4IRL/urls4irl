import { createMockJqXHR } from "../../../../__tests__/helpers/mock-jquery.js";
import { APP_CONFIG } from "../../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../../lib/ajax.js";
import { emit } from "../../../../lib/metrics-client.js";
import { UI_EVENTS } from "../../../../types/metrics-events.js";
import { SHORT_LINK_COPY_RESULT } from "../../../../types/metrics-dim-values.js";
import { isUtubLockedHandled } from "../../../utub-locked.js";
import { showURLDeckBannerError } from "../../deck.js";
import { deleteURLOnStale } from "../get.js";
import { showURLOutcomeBanner } from "../../outcome-banner.js";
import {
  clearTimeoutIDAndHideLoadingIcon,
  setTimeoutAndShowURLCardLoadingIcon,
} from "../loading.js";
import { isCoarsePointer } from "../../../mobile.js";
import {
  OUTCOME_BANNER_AUTO_HIDE_COARSE_MS,
  OUTCOME_BANNER_AUTO_HIDE_MS,
  OUTCOME_BANNER_AUTO_HIDE_PARTIAL_MS,
} from "../../../../lib/constants.js";
import { createShortLinkBtn } from "../options/short-link-btn.js";
import { renderShortLinkStatus } from "../short-link.js";
import { formatShortLinkExpiry } from "../short-link-state.js";
import {
  clearShortLinkFromCard,
  hasActiveShortLink,
  hideShortLinkStatus,
  restoreShortLinkStatus,
  shortLinkTooltipTitle,
  withShortLinkRemovedSuffix,
} from "../short-link-state.js";
import { applyHoverTooltip } from "../../../../lib/tooltips.js";
import { getState, setState } from "../../../../store/app-store.js";
import type { UtubUrlItem } from "../../../../types/url.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());
vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));
vi.mock("../../../utub-locked.js", () => ({
  isUtubLockedHandled: vi.fn(() => false),
}));
vi.mock("../../deck.js", () => ({ showURLDeckBannerError: vi.fn() }));
vi.mock("../get.js", () => ({ deleteURLOnStale: vi.fn() }));
vi.mock("../loading.js", () => ({
  setTimeoutAndShowURLCardLoadingIcon: vi.fn(() => 1),
  clearTimeoutIDAndHideLoadingIcon: vi.fn(),
}));
vi.mock("../../../../lib/tooltips.js", () => ({
  applyHoverTooltip: vi.fn(),
  disposeTooltipsWithin: vi.fn(),
}));
vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
}));

const $ = window.jQuery;

const UTUB_ID = 3;
const URL_ID = 42;
const SHORT_URL = "https://u4i.link/AbC123";
const EXPIRES_AT = "2026-10-27T12:00:00";
const REUSED_EXPIRES_AT = "2026-11-02T12:00:00";
const SHORT_LINK_NOT_FOUND = 1;
const PAST_AUTO_HIDE_MS = 1000;

const PAGE_HTML = `
  <div id="URLDeck" tabindex="-1">
    <div id="URLDeckOutcomeBanner" class="urlOutcomeBanner hidden" role="status"></div>
    <span id="URLDeckOutcomeAnnouncement"></span>
    <div id="listURLs">
      <div class="urlRow" utuburlid="${URL_ID}" urlSelected="true"></div>
      <div class="urlRow" utuburlid="43" urlSelected="false"></div>
    </div>
  </div>
  <div id="confirmModal">
    <h5 id="confirmModalTitle"></h5>
    <p id="confirmModalBody"></p>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <button id="modalRedirect"></button>
  </div>
`;

type MintDeferred = ReturnType<typeof createMockJqXHR>;

let targetVisible = true;
let modalSpy: ReturnType<typeof vi.fn>;
let clipboardWrite: ReturnType<typeof vi.fn>;
let clipboardWriteText: ReturnType<typeof vi.fn>;
let writtenText: Promise<string> | null;

class FakeClipboardItem {
  constructor(public items: Record<string, Promise<Blob>>) {}
}

function urlItem(): UtubUrlItem {
  return {
    utubUrlID: URL_ID,
    urlString: "https://example.com/42",
    utubUrlTagIDs: [],
    urlTitle: "Title 42",
    canDelete: true,
    shortLinkExpiresAt: null,
    canRevokeShortLink: true,
    addedAt: "2026-10-17T00:00:00",
    addedByUserID: 1,
  };
}

function urlCard(): JQuery {
  return $(`.urlRow[utuburlid=${URL_ID}]`);
}

function banner(): JQuery {
  return $("#URLDeckOutcomeBanner");
}

function bannerMessage(): string {
  return banner().find(".urlOutcomeBannerMessage").text();
}

function bannerDetail(): JQuery {
  return banner().find(".urlOutcomeBannerDetail");
}

function revokeAction(): JQuery {
  return banner().find(".urlOutcomeBannerAction");
}

function announcement(): string {
  return $("#URLDeckOutcomeAnnouncement").text();
}

function mintResponse({
  expiresAt = EXPIRES_AT,
  canRevoke = true,
}: { expiresAt?: string; canRevoke?: boolean } = {}) {
  return {
    shortUrl: SHORT_URL,
    expiresAt,
    canRevoke,
    created: true,
  };
}

function nextRequest(): MintDeferred {
  const deferred = createMockJqXHR();
  vi.mocked(ajaxCall).mockReturnValueOnce(deferred);
  return deferred;
}

function xhrError({
  status,
  message,
  errorCode,
}: {
  status: number;
  message?: string;
  errorCode?: number;
}): JQuery.jqXHR {
  return {
    status,
    responseJSON: message === undefined ? undefined : { message, errorCode },
  } as unknown as JQuery.jqXHR;
}

async function flush(): Promise<void> {
  if (vi.isFakeTimers()) {
    await vi.advanceTimersByTimeAsync(0);
    return;
  }
  await new Promise((resolve) => setTimeout(resolve, 0));
}

function shortLinkBtn(): JQuery {
  return $(".urlRow[utuburlid=42] .urlBtnShortLink");
}

function click(): void {
  shortLinkBtn().trigger("click");
}

async function mint({
  canRevoke = true,
  expiresAt = EXPIRES_AT,
}: { canRevoke?: boolean; expiresAt?: string } = {}): Promise<void> {
  const request = nextRequest();
  click();
  request.resolve(mintResponse({ canRevoke, expiresAt }));
  await flush();
}

function closeModal(): void {
  $("#confirmModal").trigger("hidden.bs.modal");
}

function useClipboardItem({ writeSucceeds }: { writeSucceeds: boolean }): void {
  vi.stubGlobal("ClipboardItem", FakeClipboardItem);
  clipboardWrite.mockImplementation((items: FakeClipboardItem[]) => {
    const blobPromise = items[0].items["text/plain"];
    writtenText = blobPromise.then((blob) => blob.text());
    // Rejection is asserted explicitly where wanted; keep it from going unhandled.
    writtenText.catch(() => undefined);
    // Like a browser: the write settles with the blob promise.
    return writeSucceeds
      ? blobPromise.then(() => undefined)
      : Promise.reject(new Error("NotAllowedError"));
  });
}

function useWriteText({ succeeds }: { succeeds: boolean }): void {
  vi.stubGlobal("ClipboardItem", undefined);
  clipboardWriteText.mockImplementation(() =>
    succeeds ? Promise.resolve() : Promise.reject(new Error("denied")),
  );
}

describe("short-link copy flow", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    document.body.innerHTML = PAGE_HTML;
    targetVisible = true;
    writtenText = null;
    const originalIs = $.fn.is;
    vi.spyOn($.fn, "is").mockImplementation(function (
      this: JQuery,
      selector: unknown,
    ) {
      if (selector === ":visible") return targetVisible;
      return originalIs.call(this, selector as string);
    });
    modalSpy = vi.fn().mockReturnThis();
    ($.fn as unknown as Record<string, unknown>).modal = modalSpy;
    clipboardWrite = vi.fn();
    clipboardWriteText = vi.fn();
    Object.defineProperty(navigator, "clipboard", {
      value: { write: clipboardWrite, writeText: clipboardWriteText },
      configurable: true,
    });
    vi.mocked(is429Handled).mockReturnValue(false);
    vi.mocked(isUtubLockedHandled).mockReturnValue(false);
    vi.mocked(isCoarsePointer).mockReturnValue(false);

    const button = createShortLinkBtn({
      url: urlItem(),
      urlCard: urlCard(),
      utubID: UTUB_ID,
    });
    urlCard().append(button);
    useClipboardItem({ writeSucceeds: true });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    vi.useRealTimers();
    $("#confirmModal, #modalSubmit, #modalDismiss").off();
  });

  describe("minting and copying", () => {
    it("starts the clipboard write inside the click, then copies the exact short URL", async () => {
      const request = nextRequest();
      click();

      // Safari: the write must begin synchronously in the user gesture.
      expect(clipboardWrite).toHaveBeenCalledTimes(1);
      expect(clipboardWriteText).not.toHaveBeenCalled();
      expect(ajaxCall).toHaveBeenCalledWith(
        "post",
        `/utubs/${UTUB_ID}/urls/${URL_ID}/short-link`,
        [],
        expect.any(Number),
      );

      request.resolve(mintResponse());
      await flush();

      expect(await writtenText).toBe(SHORT_URL);
      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_SHORT_LINK_COPY,
        result: SHORT_LINK_COPY_RESULT.SUCCESS,
      });
    });

    it("shows the success banner with the expiry date, link and Revoke, and announces it", async () => {
      await mint();

      const expected = APP_CONFIG.strings.SHORT_LINK_COPIED.replace(
        "{date}",
        formatShortLinkExpiry(EXPIRES_AT),
      );
      expect(bannerMessage()).toBe(expected);
      expect(bannerDetail().text()).toBe(SHORT_URL);
      expect(revokeAction().text()).toBe(
        APP_CONFIG.strings.SHORT_LINK_REVOKE_LABEL,
      );
      expect(announcement()).toBe(expected);
      expect(shortLinkBtn().attr("aria-disabled")).toBeUndefined();
    });

    it("uses the response expiry for a reused link", async () => {
      await mint({ expiresAt: REUSED_EXPIRES_AT });

      expect(bannerMessage()).toContain(
        formatShortLinkExpiry(REUSED_EXPIRES_AT),
      );
      expect(bannerMessage()).not.toContain(formatShortLinkExpiry(EXPIRES_AT));
    });

    it("omits Revoke when the viewer cannot revoke", async () => {
      await mint({ canRevoke: false });

      expect(bannerMessage()).not.toBe("");
      expect(revokeAction()).toHaveLength(0);
    });

    it("falls back to writeText without ClipboardItem", async () => {
      useWriteText({ succeeds: true });
      const request = nextRequest();
      click();

      expect(clipboardWrite).not.toHaveBeenCalled();
      expect(clipboardWriteText).not.toHaveBeenCalled();

      request.resolve(mintResponse());
      await flush();

      expect(clipboardWriteText).toHaveBeenCalledWith(SHORT_URL);
      expect(bannerMessage()).toContain(formatShortLinkExpiry(EXPIRES_AT));
    });

    it("sends one mint for a double click", async () => {
      const request = nextRequest();
      click();
      expect(shortLinkBtn().attr("aria-disabled")).toBe("true");
      click();

      expect(ajaxCall).toHaveBeenCalledTimes(1);
      expect(clipboardWrite).toHaveBeenCalledTimes(1);

      request.resolve(mintResponse());
      await flush();
      expect(shortLinkBtn().attr("aria-disabled")).toBeUndefined();
    });
  });

  describe("clipboard rejection", () => {
    it.each([
      ["ClipboardItem", () => useClipboardItem({ writeSucceeds: false })],
      ["writeText", () => useWriteText({ succeeds: false })],
    ])(
      "shows a selectable partial banner that does not auto-hide (%s)",
      async (_name, arrange) => {
        arrange();
        await mint();

        expect(bannerMessage()).toBe(
          APP_CONFIG.strings.SHORT_LINK_CLIPBOARD_FALLBACK,
        );
        expect(banner().find(".urlOutcomeBannerDetailSelectable").text()).toBe(
          SHORT_URL,
        );
        expect(document.activeElement).toBe(bannerDetail()[0]);
        expect(bannerDetail().attr("tabindex")).toBe("-1");
        expect(window.getSelection()?.toString()).toBe(SHORT_URL);
        expect(showURLDeckBannerError).not.toHaveBeenCalled();
        expect(revokeAction()).toHaveLength(0);
        expect(emit).toHaveBeenCalledWith({
          event: UI_EVENTS.UI_SHORT_LINK_COPY,
          result: SHORT_LINK_COPY_RESULT.FALLBACK,
        });
        expect(emit).not.toHaveBeenCalledWith({
          event: UI_EVENTS.UI_SHORT_LINK_COPY,
          result: SHORT_LINK_COPY_RESULT.SUCCESS,
        });
      },
    );

    it("describes the focused link by its explanatory message", async () => {
      useClipboardItem({ writeSucceeds: false });
      await mint();

      const messageId = banner().find(".urlOutcomeBannerMessage").attr("id");
      expect(messageId).toBeTruthy();
      expect(bannerDetail().attr("aria-describedby")).toBe(messageId);
    });

    it("survives focus pause and resume with no countdown", async () => {
      vi.useFakeTimers();
      useClipboardItem({ writeSucceeds: false });
      await mint();

      banner().trigger("focusin");
      banner().trigger("focusout");
      await vi.advanceTimersByTimeAsync(
        OUTCOME_BANNER_AUTO_HIDE_PARTIAL_MS + PAST_AUTO_HIDE_MS,
      );

      expect(banner().hasClass("hidden")).toBe(false);
      expect(bannerDetail().text()).toBe(SHORT_URL);
    });

    it("has no countdown on a coarse pointer either", async () => {
      vi.useFakeTimers();
      vi.mocked(isCoarsePointer).mockReturnValue(true);
      useClipboardItem({ writeSucceeds: false });
      await mint();

      await vi.advanceTimersByTimeAsync(
        OUTCOME_BANNER_AUTO_HIDE_COARSE_MS + PAST_AUTO_HIDE_MS,
      );

      expect(banner().hasClass("hidden")).toBe(false);
    });

    it("control: a success banner under the same timers does auto-hide", async () => {
      vi.useFakeTimers();
      await mint();
      expect(banner().hasClass("hidden")).toBe(false);

      await vi.advanceTimersByTimeAsync(
        OUTCOME_BANNER_AUTO_HIDE_MS + PAST_AUTO_HIDE_MS,
      );

      expect(banner().hasClass("hidden")).toBe(true);
    });

    it("falls back to writeText when ClipboardItem throws synchronously", async () => {
      useWriteText({ succeeds: true });
      vi.stubGlobal(
        "ClipboardItem",
        class {
          constructor() {
            throw new Error("unsupported type");
          }
        },
      );
      await mint();

      expect(clipboardWriteText).toHaveBeenCalledWith(SHORT_URL);
      expect(bannerMessage()).toContain(formatShortLinkExpiry(EXPIRES_AT));
    });
  });

  describe("loading ring", () => {
    it("shows on click and clears once the mint succeeded", async () => {
      const request = nextRequest();
      click();
      expect(setTimeoutAndShowURLCardLoadingIcon).toHaveBeenCalledTimes(1);
      expect(clearTimeoutIDAndHideLoadingIcon).not.toHaveBeenCalled();

      request.resolve(mintResponse());
      await flush();

      expect(clearTimeoutIDAndHideLoadingIcon).toHaveBeenCalledTimes(1);
    });

    it("clears when the mint fails", async () => {
      const request = nextRequest();
      click();
      request.reject(xhrError({ status: 500 }));
      await flush();

      expect(clearTimeoutIDAndHideLoadingIcon).toHaveBeenCalledTimes(1);
    });

    it("clears before a pending clipboard permission prompt settles", async () => {
      clipboardWrite.mockImplementation(() => new Promise(() => undefined));
      const request = nextRequest();
      click();
      request.resolve(mintResponse());
      await flush();

      expect(clearTimeoutIDAndHideLoadingIcon).toHaveBeenCalledTimes(1);
      expect(shortLinkBtn().attr("aria-disabled")).toBeUndefined();
    });
  });

  describe("failed mint", () => {
    it("shows only an error, never the partial banner, and leaves the clipboard alone (ClipboardItem)", async () => {
      useClipboardItem({ writeSucceeds: true });
      const request = nextRequest();
      click();
      request.reject(xhrError({ status: 500 }));
      await flush();

      expect(showURLDeckBannerError).toHaveBeenCalledWith(
        APP_CONFIG.strings.SHORT_LINK_COPY_FAILED,
      );
      expect(bannerMessage()).toBe("");
      expect(clipboardWriteText).not.toHaveBeenCalled();
      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_SHORT_LINK_COPY,
        result: SHORT_LINK_COPY_RESULT.FAILURE,
      });
      expect(shortLinkBtn().attr("aria-disabled")).toBeUndefined();
    });

    it("never writes text and never shows the partial banner (writeText)", async () => {
      useWriteText({ succeeds: true });
      const request = nextRequest();
      click();
      request.reject(xhrError({ status: 500 }));
      await flush();

      expect(clipboardWriteText).not.toHaveBeenCalled();
      expect(bannerMessage()).toBe("");
      expect(showURLDeckBannerError).toHaveBeenCalledTimes(1);
    });

    it("shows the server message and removes the card on a 404", async () => {
      const request = nextRequest();
      click();
      request.reject(xhrError({ status: 404, message: "URL not found" }));
      await flush();

      expect(showURLDeckBannerError).toHaveBeenCalledWith("URL not found");
      expect(deleteURLOnStale).toHaveBeenCalledTimes(1);
    });

    it("lets the 429 handler own a rate-limited mint", async () => {
      vi.mocked(is429Handled).mockReturnValue(true);
      const request = nextRequest();
      click();
      request.reject(xhrError({ status: 429 }));
      await flush();

      expect(showURLDeckBannerError).not.toHaveBeenCalled();
      expect(deleteURLOnStale).not.toHaveBeenCalled();
    });

    it("lets the locked-UTub handler own a locked mint", async () => {
      vi.mocked(isUtubLockedHandled).mockReturnValue(true);
      const request = nextRequest();
      click();
      request.reject(xhrError({ status: 403 }));
      await flush();

      expect(showURLDeckBannerError).not.toHaveBeenCalled();
    });
  });

  describe("stale responses", () => {
    function supersedeBanner(): void {
      showURLOutcomeBanner({
        variant: "success",
        message: "something newer",
        returnFocusTo: $("#URLDeck"),
      });
    }

    function selectOtherCard(): void {
      urlCard().attr("urlSelected", "false");
      $(".urlRow[utuburlid=43]").attr("urlSelected", "true");
    }

    it.each([
      ["a newer banner", () => supersedeBanner()],
      ["another selected card", () => selectOtherCard()],
    ])(
      "abandons the ClipboardItem write and shows nothing after %s",
      async (_name, supersede) => {
        const request = nextRequest();
        click();
        supersede();
        const messageBefore = bannerMessage();
        request.resolve(mintResponse());
        await flush();

        await expect(writtenText).rejects.toThrow();
        expect(bannerMessage()).toBe(messageBefore);
        expect(emit).not.toHaveBeenCalledWith({
          event: UI_EVENTS.UI_SHORT_LINK_COPY,
          result: SHORT_LINK_COPY_RESULT.SUCCESS,
        });
        expect(shortLinkBtn().attr("aria-disabled")).toBeUndefined();
        expect(clearTimeoutIDAndHideLoadingIcon).toHaveBeenCalledTimes(1);
      },
    );

    it("stays stale when the card is reselected after the write was abandoned", async () => {
      const request = nextRequest();
      click();
      selectOtherCard();
      request.resolve(mintResponse());
      await expect(writtenText).rejects.toThrow();
      // The user comes back to the original card before the write settles.
      $(".urlRow[utuburlid=43]").attr("urlSelected", "false");
      urlCard().attr("urlSelected", "true");
      await flush();

      expect(bannerMessage()).toBe("");
      expect(emit).not.toHaveBeenCalledWith({
        event: UI_EVENTS.UI_SHORT_LINK_COPY,
        result: SHORT_LINK_COPY_RESULT.FALLBACK,
      });
    });

    it.each([
      ["a newer banner", () => supersedeBanner()],
      ["another selected card", () => selectOtherCard()],
    ])("skips writeText and the banner after %s", async (_name, supersede) => {
      useWriteText({ succeeds: true });
      const request = nextRequest();
      click();
      supersede();
      const messageBefore = bannerMessage();
      request.resolve(mintResponse());
      await flush();

      expect(clipboardWriteText).not.toHaveBeenCalled();
      expect(bannerMessage()).toBe(messageBefore);
    });
  });

  describe("revoke", () => {
    async function openRevokeModal(): Promise<void> {
      await mint();
      revokeAction().trigger("click");
    }

    function confirm(): void {
      $("#modalSubmit").trigger("click");
    }

    it("sends nothing until Confirm and keeps the banner action disabled meanwhile", async () => {
      await openRevokeModal();

      expect(modalSpy).toHaveBeenCalledWith("show");
      expect($("#confirmModalTitle").text()).toBe(
        APP_CONFIG.strings.SHORT_LINK_REVOKE_CONFIRM_TITLE,
      );
      expect($("#confirmModalBody").text()).toContain(
        formatShortLinkExpiry(EXPIRES_AT),
      );
      expect($("#modalSubmit").text()).toBe(
        APP_CONFIG.strings.SHORT_LINK_REVOKE_LABEL,
      );
      expect(revokeAction().attr("aria-disabled")).toBe("true");
      expect(ajaxCall).toHaveBeenCalledTimes(1); // the mint only
    });

    it("Cancel sends nothing, re-arms Revoke and returns focus to the button", async () => {
      await openRevokeModal();

      $("#modalDismiss").trigger("click");
      expect(modalSpy).toHaveBeenCalledWith("hide");
      closeModal();

      expect(ajaxCall).toHaveBeenCalledTimes(1);
      expect(revokeAction().attr("aria-disabled")).toBeUndefined();
      expect(document.activeElement).toBe(shortLinkBtn()[0]);
    });

    it("Esc (modal closes on its own) behaves like Cancel", async () => {
      await openRevokeModal();

      closeModal();

      expect(ajaxCall).toHaveBeenCalledTimes(1);
      expect(revokeAction().attr("aria-disabled")).toBeUndefined();
      expect(document.activeElement).toBe(shortLinkBtn()[0]);
    });

    it("sends one DELETE for a double-click on Confirm, then announces the revoke", async () => {
      await openRevokeModal();
      const request = nextRequest();

      confirm();
      confirm();

      expect(ajaxCall).toHaveBeenCalledTimes(2);
      expect(ajaxCall).toHaveBeenLastCalledWith(
        "delete",
        `/utubs/${UTUB_ID}/urls/${URL_ID}/short-link`,
        [],
        expect.any(Number),
      );
      expect($("#modalSubmit").prop("disabled")).toBe(true);

      request.resolve({ utubUrlID: URL_ID });
      await flush();
      closeModal();

      expect(modalSpy).toHaveBeenLastCalledWith("hide");
      expect(bannerMessage()).toBe(APP_CONFIG.strings.SHORT_LINK_REVOKED);
      expect(announcement()).toBe(APP_CONFIG.strings.SHORT_LINK_REVOKED);
      expect(document.activeElement).toBe(shortLinkBtn()[0]);
    });

    it("falls back to the deck when the short-link button is not visible", async () => {
      await openRevokeModal();
      const request = nextRequest();
      confirm();
      request.resolve({ utubUrlID: URL_ID });
      await flush();
      targetVisible = false;
      closeModal();

      expect(document.activeElement).toBe($("#URLDeck")[0]);
    });

    it("treats a SHORT_LINK_NOT_FOUND 404 as already revoked", async () => {
      await openRevokeModal();
      const request = nextRequest();
      confirm();
      request.reject(
        xhrError({
          status: 404,
          message: "gone",
          errorCode: SHORT_LINK_NOT_FOUND,
        }),
      );
      await flush();
      closeModal();

      expect(bannerMessage()).toBe(APP_CONFIG.strings.SHORT_LINK_REVOKED);
      expect(showURLDeckBannerError).not.toHaveBeenCalled();
      expect(deleteURLOnStale).not.toHaveBeenCalled();
      expect(document.activeElement).toBe(shortLinkBtn()[0]);
    });

    it("shows the server message, removes the card and focuses the deck on a guard 404", async () => {
      await openRevokeModal();
      const request = nextRequest();
      confirm();
      request.reject(xhrError({ status: 404, message: "URL not found" }));
      await flush();
      closeModal();

      expect(showURLDeckBannerError).toHaveBeenCalledWith("URL not found");
      expect(deleteURLOnStale).toHaveBeenCalledTimes(1);
      expect(document.activeElement).toBe($("#URLDeck")[0]);
      // No stale Revoke is left for the removed card.
      expect(revokeAction()).toHaveLength(0);
    });

    it("keeps focus on the deck when the modal is already closed before a guard 404 lands", async () => {
      await openRevokeModal();
      const request = nextRequest();
      confirm();
      closeModal(); // closed while the request is in flight
      request.reject(xhrError({ status: 404, message: "URL not found" }));
      await flush();

      expect(document.activeElement).toBe($("#URLDeck")[0]);
    });

    it("ignores the outcome UI when the banner changed under the open modal, but still returns focus", async () => {
      await openRevokeModal();
      showURLOutcomeBanner({
        variant: "success",
        message: "something newer",
        actionLabel: "Undo",
        onAction: vi.fn(),
        returnFocusTo: $("#URLDeck"),
      });
      const request = nextRequest();
      confirm();
      request.resolve({ utubUrlID: URL_ID });
      await flush();
      closeModal();

      expect(bannerMessage()).toBe("something newer");
      expect(document.activeElement).toBe(shortLinkBtn()[0]);
    });

    it("does not re-arm a newer banner's action when Cancel follows a replaced banner", async () => {
      await openRevokeModal();
      showURLOutcomeBanner({
        variant: "success",
        message: "something newer",
        actionLabel: "Undo",
        onAction: vi.fn(),
        returnFocusTo: $("#URLDeck"),
      });
      revokeAction().attr("aria-disabled", "true"); // its action is in flight
      closeModal();

      expect(revokeAction().attr("aria-disabled")).toBe("true");
      expect(document.activeElement).toBe(shortLinkBtn()[0]);
    });

    it("restarts the auto-hide countdown after Cancel", async () => {
      vi.useFakeTimers();
      await openRevokeModal();

      // The countdown fires while the confirmation is open and is deferred.
      await vi.advanceTimersByTimeAsync(
        OUTCOME_BANNER_AUTO_HIDE_MS + PAST_AUTO_HIDE_MS,
      );
      expect(banner().hasClass("hidden")).toBe(false);

      closeModal();
      await vi.advanceTimersByTimeAsync(
        OUTCOME_BANNER_AUTO_HIDE_MS + PAST_AUTO_HIDE_MS,
      );

      expect(banner().hasClass("hidden")).toBe(true);
    });

    it("restarts the auto-hide countdown after a failed revoke", async () => {
      vi.useFakeTimers();
      await openRevokeModal();
      const request = nextRequest();
      confirm();
      await vi.advanceTimersByTimeAsync(
        OUTCOME_BANNER_AUTO_HIDE_MS + PAST_AUTO_HIDE_MS,
      );
      expect(banner().hasClass("hidden")).toBe(false);

      request.reject(xhrError({ status: 403, message: "Forbidden" }));
      await flush();
      closeModal();
      await vi.advanceTimersByTimeAsync(
        OUTCOME_BANNER_AUTO_HIDE_MS + PAST_AUTO_HIDE_MS,
      );

      expect(banner().hasClass("hidden")).toBe(true);
    });

    it("shows the revoke failure, re-arms Revoke and returns focus on a 403", async () => {
      await openRevokeModal();
      const request = nextRequest();
      confirm();
      request.reject(xhrError({ status: 403, message: "Forbidden" }));
      await flush();
      closeModal();

      expect(showURLDeckBannerError).toHaveBeenCalledWith(
        APP_CONFIG.strings.SHORT_LINK_REVOKE_FAILED,
      );
      expect(deleteURLOnStale).not.toHaveBeenCalled();
      expect(revokeAction().attr("aria-disabled")).toBeUndefined();
      expect(document.activeElement).toBe(shortLinkBtn()[0]);
    });

    it("lets the 429 handler own a rate-limited revoke and re-arms Revoke", async () => {
      await openRevokeModal();
      vi.mocked(is429Handled).mockReturnValue(true);
      const request = nextRequest();
      confirm();
      request.reject(xhrError({ status: 429 }));
      await flush();
      closeModal();

      expect(showURLDeckBannerError).not.toHaveBeenCalled();
      expect(revokeAction().attr("aria-disabled")).toBeUndefined();
    });

    it("lets the locked-UTub handler own a locked revoke", async () => {
      await openRevokeModal();
      vi.mocked(isUtubLockedHandled).mockReturnValue(true);
      const request = nextRequest();
      confirm();
      request.reject(xhrError({ status: 403 }));
      await flush();

      expect(showURLDeckBannerError).not.toHaveBeenCalled();
      expect(deleteURLOnStale).not.toHaveBeenCalled();
    });
  });

  describe("card status row", () => {
    function statusRow(): JQuery {
      return urlCard().find(".shortLinkStatusRow");
    }

    function cardRevoke(): JQuery {
      return urlCard().find(".shortLinkRevoke");
    }

    function renderRow({
      expiresAt,
      canRevoke = true,
    }: {
      expiresAt: string | null;
      canRevoke?: boolean;
    }): void {
      renderShortLinkStatus({
        urlCard: urlCard(),
        utubID: UTUB_ID,
        utubUrlID: URL_ID,
        expiresAt,
        canRevoke,
      });
    }

    beforeEach(() => {
      urlCard().prepend('<div class="urlOptions"></div>');
      setState({ urls: [urlItem()] });
    });

    it("renders nothing when there is no active link", () => {
      renderRow({ expiresAt: null });

      expect(statusRow().length).toBe(0);
    });

    it("renders the status line below .urlOptions with an enabled Revoke on a selected card", () => {
      renderRow({ expiresAt: EXPIRES_AT });

      expect(statusRow().prev().hasClass("urlOptions")).toBe(true);
      expect(statusRow().find(".shortLinkStatus").text()).toContain(
        formatShortLinkExpiry(EXPIRES_AT),
      );
      expect(cardRevoke().attr("aria-label")).toBe(
        APP_CONFIG.strings.SHORT_LINK_REVOKE_ARIA,
      );
      expect(cardRevoke().attr("tabindex")).toBe("0");
    });

    it("moves focus to the short-link button when a rebuild removes the focused Revoke", () => {
      renderRow({ expiresAt: EXPIRES_AT });
      cardRevoke()[0].focus();
      expect(document.activeElement).toBe(cardRevoke()[0]);

      renderRow({ expiresAt: REUSED_EXPIRES_AT });

      expect(document.activeElement).toBe(shortLinkBtn()[0]);
    });

    it("leaves focus alone when a rebuild happens while focus is elsewhere", () => {
      renderRow({ expiresAt: EXPIRES_AT });
      $(".urlRow[utuburlid=43]").append('<button id="elsewhere"></button>');
      const elsewhere = $("#elsewhere")[0];
      elsewhere.focus();

      renderRow({ expiresAt: REUSED_EXPIRES_AT });

      expect(document.activeElement).toBe(elsewhere);
    });

    it("writes the minted link to the store and row even after a different card was selected", async () => {
      const request = nextRequest();
      click();
      urlCard().attr("urlSelected", "false");
      $(".urlRow[utuburlid=43]").attr("urlSelected", "true");
      request.resolve(mintResponse());
      await flush();

      const stored = getState().urls.find((url) => url.utubUrlID === URL_ID);
      expect(stored?.shortLinkExpiresAt).toBe(EXPIRES_AT);
      expect(stored?.canRevokeShortLink).toBe(true);
      expect(statusRow().length).toBe(1);
    });

    it("keeps Revoke out of the tab order on an unselected card", () => {
      urlCard().attr("urlSelected", "false");
      renderRow({ expiresAt: EXPIRES_AT });

      expect(cardRevoke().attr("tabindex")).toBe("-1");
    });

    it("omits Revoke when the viewer cannot revoke", () => {
      renderRow({ expiresAt: EXPIRES_AT, canRevoke: false });

      expect(statusRow().length).toBe(1);
      expect(cardRevoke().length).toBe(0);
    });

    it("is a no-op when the card already shows this state", () => {
      renderRow({ expiresAt: EXPIRES_AT });
      const first = statusRow()[0];

      renderRow({ expiresAt: EXPIRES_AT });

      expect(statusRow()[0]).toBe(first);
    });

    it("updates the row in place when the expiry or revoke right changes, and removes it on null", () => {
      renderRow({ expiresAt: EXPIRES_AT });
      renderRow({ expiresAt: REUSED_EXPIRES_AT, canRevoke: false });

      expect(statusRow().length).toBe(1);
      expect(statusRow().text()).toContain(
        formatShortLinkExpiry(REUSED_EXPIRES_AT),
      );
      expect(cardRevoke().length).toBe(0);

      renderRow({ expiresAt: null });
      expect(statusRow().length).toBe(0);
    });

    it("renders hidden while a URL edit form is open", () => {
      urlCard().append('<div class="updateUrlStringWrap"></div>');
      renderRow({ expiresAt: EXPIRES_AT });

      expect(statusRow().hasClass("hidden")).toBe(true);
    });

    it("writes the minted link to the store and the row, even after the card was deselected", async () => {
      const request = nextRequest();
      click();
      urlCard().attr("urlSelected", "false");
      request.resolve(mintResponse());
      await flush();

      const stored = getState().urls[0];
      expect(stored.shortLinkExpiresAt).toBe(EXPIRES_AT);
      expect(stored.canRevokeShortLink).toBe(true);
      expect(statusRow().length).toBe(1);
      expect(bannerMessage()).toBe("");
    });

    it("sets the active tooltip title on the short-link button", () => {
      renderRow({ expiresAt: EXPIRES_AT });

      expect(applyHoverTooltip).toHaveBeenLastCalledWith(
        expect.objectContaining({
          tooltip: expect.objectContaining({
            title: shortLinkTooltipTitle({ expiresAt: EXPIRES_AT }),
          }),
        }),
      );
      expect(shortLinkTooltipTitle({ expiresAt: EXPIRES_AT })).toBe(
        `Copy short link (expires ${formatShortLinkExpiry(EXPIRES_AT)})`,
      );
    });

    it("card Revoke confirms, then removes the row and announces the revoke", async () => {
      await mint();
      expect(statusRow().length).toBe(1);

      cardRevoke().trigger("click");
      expect(modalSpy).toHaveBeenCalledWith("show");
      expect(ajaxCall).toHaveBeenCalledTimes(1); // the mint only

      const request = nextRequest();
      $("#modalSubmit").trigger("click");
      request.resolve({ utubUrlID: URL_ID });
      await flush();
      closeModal();

      expect(statusRow().length).toBe(0);
      expect(getState().urls[0].shortLinkExpiresAt).toBeNull();
      expect(getState().urls[0].canRevokeShortLink).toBe(false);
      expect(bannerMessage()).toBe(APP_CONFIG.strings.SHORT_LINK_REVOKED);
      expect(announcement()).toBe(APP_CONFIG.strings.SHORT_LINK_REVOKED);
      expect(document.activeElement).toBe(shortLinkBtn()[0]);
    });

    it("clears the row on a SHORT_LINK_NOT_FOUND 404", async () => {
      await mint();
      cardRevoke().trigger("click");
      const request = nextRequest();
      $("#modalSubmit").trigger("click");
      request.reject(
        xhrError({
          status: 404,
          message: "gone",
          errorCode: SHORT_LINK_NOT_FOUND,
        }),
      );
      await flush();
      closeModal();

      expect(statusRow().length).toBe(0);
      expect(getState().urls[0].shortLinkExpiresAt).toBeNull();
    });

    it("leaves the row when the confirm is cancelled", async () => {
      await mint();
      cardRevoke().trigger("click");
      closeModal();

      expect(statusRow().length).toBe(1);
      expect(ajaxCall).toHaveBeenCalledTimes(1);
    });
  });

  describe("edit-panel hide and restore", () => {
    beforeEach(() => {
      urlCard().prepend('<div class="urlOptions"></div>');
      setState({ urls: [urlItem()] });
      renderShortLinkStatus({
        urlCard: urlCard(),
        utubID: UTUB_ID,
        utubUrlID: URL_ID,
        expiresAt: EXPIRES_AT,
        canRevoke: true,
      });
    });

    it("hides the row and Revoke's tab while an edit panel is open, then restores both", () => {
      hideShortLinkStatus(urlCard());
      expect(urlCard().find(".shortLinkStatusRow").hasClass("hidden")).toBe(
        true,
      );
      expect(urlCard().find(".shortLinkRevoke").attr("tabindex")).toBe("-1");

      restoreShortLinkStatus(urlCard());
      expect(urlCard().find(".shortLinkStatusRow").hasClass("hidden")).toBe(
        false,
      );
      expect(urlCard().find(".shortLinkRevoke").attr("tabindex")).not.toBe(
        "-1",
      );
    });

    it("stays hidden on restore while a URL or title form is still open", () => {
      hideShortLinkStatus(urlCard());
      urlCard().append('<div class="updateUrlTitleWrap"></div>');

      restoreShortLinkStatus(urlCard());

      expect(urlCard().find(".shortLinkStatusRow").hasClass("hidden")).toBe(
        true,
      );
    });

    it("clearShortLinkFromCard removes the row and resets the tooltip", () => {
      clearShortLinkFromCard(urlCard());

      expect(urlCard().find(".shortLinkStatusRow").length).toBe(0);
      expect(applyHoverTooltip).toHaveBeenLastCalledWith(
        expect.objectContaining({
          tooltip: expect.objectContaining({
            title: APP_CONFIG.strings.SHORT_LINK_TOOLTIP,
          }),
        }),
      );
    });
  });

  describe("removed-link suffix", () => {
    it("appends the suffix only when a link was removed", () => {
      expect(
        withShortLinkRemovedSuffix({
          message: "URL updated.",
          linkRemoved: true,
        }),
      ).toBe("URL updated. Its short link was removed.");
      expect(
        withShortLinkRemovedSuffix({
          message: "URL updated.",
          linkRemoved: false,
        }),
      ).toBe("URL updated.");
    });

    it("hasActiveShortLink reads the store", () => {
      setState({
        urls: [{ ...urlItem(), shortLinkExpiresAt: EXPIRES_AT }],
      });
      expect(hasActiveShortLink({ utubUrlID: URL_ID })).toBe(true);
      expect(hasActiveShortLink({ utubUrlID: 999 })).toBe(false);
    });

    it("hasActiveShortLink fails closed on a missing field", () => {
      const legacy: Partial<UtubUrlItem> = urlItem();
      delete legacy.shortLinkExpiresAt;
      setState({ urls: [legacy as UtubUrlItem] });
      expect(hasActiveShortLink({ utubUrlID: URL_ID })).toBe(false);
    });
  });
});
