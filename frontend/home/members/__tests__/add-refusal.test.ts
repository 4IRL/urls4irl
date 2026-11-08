import {
  isMemberAddNotAllowedResponse,
  learnMemberAddRefused,
  MEMBER_ADD_NOT_ALLOWED_ERROR_CODE,
} from "../add-refusal.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { resolveUtubSettings } from "../../../types/settings.js";
import { updateUTubOnFindingStaleData } from "../../utubs/stale-data.js";

vi.mock("../../utubs/stale-data.js", () => ({
  updateUTubOnFindingStaleData: vi.fn(() => Promise.resolve()),
}));

const $ = window.jQuery;

function xhrWith({
  status,
  errorCode,
}: {
  status: number;
  errorCode?: number;
}): JQuery.jqXHR {
  return { status, responseJSON: { errorCode } } as unknown as JQuery.jqXHR;
}

describe("isMemberAddNotAllowedResponse", () => {
  it("matches only a 403 carrying errorCode 7", () => {
    expect(MEMBER_ADD_NOT_ALLOWED_ERROR_CODE).toBe(7);
    expect(
      isMemberAddNotAllowedResponse(xhrWith({ status: 403, errorCode: 7 })),
    ).toBe(true);
    expect(
      isMemberAddNotAllowedResponse(xhrWith({ status: 403, errorCode: 3 })),
    ).toBe(false);
    expect(
      isMemberAddNotAllowedResponse(xhrWith({ status: 400, errorCode: 7 })),
    ).toBe(false);
  });
});

describe("learnMemberAddRefused", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="MemberDeckNotice" class="hidden"></div>
      <span id="MemberRowActionAnnouncement" aria-live="polite"></span>
    `;
    vi.clearAllMocks();
    resetStore();
    setState({
      activeUTubID: 4,
      settings: resolveUtubSettings({
        members: { members_can_add: true },
      } as never),
    });
  });

  it("learns the policy off, shows the notice, announces assertively and refreshes", () => {
    learnMemberAddRefused({ utubID: 4, announce: true });

    expect(getState().settings?.members.members_can_add).toBe(false);
    expect($("#MemberDeckNotice").text()).toBe(
      APP_CONFIG.strings.MEMBER_ADD_NOT_ALLOWED,
    );
    expect($("#MemberRowActionAnnouncement").attr("aria-live")).toBe(
      "assertive",
    );
    expect(updateUTubOnFindingStaleData).toHaveBeenCalledWith({ utubID: 4 });
  });

  it("skips the announcement when the caller writes its own", () => {
    learnMemberAddRefused({ utubID: 4, announce: false });

    expect($("#MemberRowActionAnnouncement").text()).toBe("");
    expect($("#MemberDeckNotice").text()).not.toBe("");
  });

  it("still shows the notice when no settings are loaded (return ignored on purpose)", () => {
    setState({ settings: null });

    learnMemberAddRefused({ utubID: 4, announce: true });

    expect(getState().settings).toBeNull();
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(false);
    expect($("#MemberRowActionAnnouncement").text()).toBe(
      APP_CONFIG.strings.MEMBER_ADD_NOT_ALLOWED,
    );
    expect(updateUTubOnFindingStaleData).toHaveBeenCalledWith({ utubID: 4 });
  });

  it("does nothing for a UTub that is no longer active", () => {
    learnMemberAddRefused({ utubID: 9, announce: true });

    expect(getState().settings?.members.members_can_add).toBe(true);
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(true);
    expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
  });
});
