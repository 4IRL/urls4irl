import { updateUTubOnFindingStaleData } from "../stale-data.js";
import { buildSelectedUTub, fetchUTubForRefresh } from "../selectors.js";
import { createLeaveUTubAsMemberIcon } from "../../members/delete.js";
import { getState, resetStore } from "../../../store/app-store.js";
import type { UtubDetail } from "../../../types/utub.js";

// Real stale-data.ts, selectors.buildSelectedUTub, event bus, store and member
// deck: a refresh whose payload changes the viewer's role takes the permission
// fallback, whose UTUB_SELECTED emit must reach setMemberDeckOnUTubSelected with
// the NEW role so the co-owner kebabs follow it.
const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());
vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
  getCurrentMobilePanel: vi.fn(() => "urls"),
  setCurrentMobilePanel: vi.fn(),
  replaceMobilePanelHistoryState: vi.fn(),
  setMobileUIWhenUTubDeckSelected: vi.fn(),
  setMobileUIWhenMemberDeckSelected: vi.fn(),
  setMobileUIWhenUTubSelectedOrURLNavSelected: vi.fn(),
}));
vi.mock("../selectors.js", async () => {
  const actual =
    await vi.importActual<typeof import("../selectors.js")>("../selectors.js");
  return { ...actual, fetchUTubForRefresh: vi.fn() };
});
vi.mock("../deck.js", () => ({
  showUTubLoadingIconAndSetTimeout: vi.fn(() => 0),
  hideUTubLoadingIconAndClearTimeout: vi.fn(),
  setUTubDeckOnUTubSelected: vi.fn(),
}));
vi.mock("../remove-local.js", () => ({ removeUTubLocally: vi.fn() }));
vi.mock("../../urls/deck.js", () => ({ showURLDeckBannerError: vi.fn() }));
vi.mock("../../urls/update-description.js", () => ({
  removeEventListenersForShowCreateUTubDescIfEmptyDesc: vi.fn(),
  showCreateDescriptionButtonAlways: vi.fn(),
}));
vi.mock("../header-fit.js", () => ({ fitUTubHeaderAndSubheader: vi.fn() }));
vi.mock("../../members/create.js", () => ({
  setupShowCreateMemberFormEventListeners: vi.fn(),
}));
vi.mock("../../members/delete.js", () => ({
  createLeaveUTubAsMemberIcon: vi.fn(),
  removeMemberShowModal: vi.fn(),
}));
vi.mock("../../btns-forms.js", () => ({ hideInputs: vi.fn() }));
vi.mock("../../urls/cards/selection.js", () => ({
  deselectAllURLs: vi.fn(),
}));

const $ = window.jQuery;

const UTUB_ID = 42;
const VIEWER_ID = 2;

const DOM = `
  <div id="URLDeckHeader">U</div>
  <div id="URLDeckSubheader"></div>
  <div id="UTubDescriptionSubheaderWrap" class="hidden"></div>
  <div id="URLDeckNoDescription" class="hidden"></div>
  <button id="URLDeckSubheaderCreateDescription"></button>
  <input id="utubDescriptionUpdate" />
  <span id="URLDeckLockIcon" class="hidden"></span>
  <div id="MemberDeck">
    <button type="button" id="MemberDeckHeaderAndCaret">
      <span id="MemberDeckHeader">Members<span id="MemberDeckCount"></span></span>
    </button>
    <button id="memberNameFilterBtn" class="hidden"></button>
    <button id="memberNameFilterBtnClose" class="hidden"></button>
    <button id="memberBtnCreate" class="hidden"></button>
    <div id="MemberDeckNotice" class="hidden"></div>
    <button id="memberSelfBtnDelete" class="hidden"></button>
    <input id="MemberNameSearch" type="search" value="" />
    <p id="MemberSearchNoResults" class="hidden"></p>
    <div id="displayMemberWrap" class="flex-column hidden">
      <div id="UTubOwner"></div>
      <div id="listMembers"></div>
    </div>
  </div>
`;

function makeDetail({ isCoCreator }: { isCoCreator: boolean }): UtubDetail {
  return {
    status: "Success",
    id: UTUB_ID,
    name: "U",
    createdByUserID: 1,
    createdAt: "2026-01-01T00:00:00Z",
    description: "",
    members: [
      { id: 1, username: "owner", memberRole: "creator", joinedAt: null },
      {
        id: VIEWER_ID,
        username: "viewer",
        memberRole: isCoCreator ? "cocreator" : "member",
        joinedAt: null,
      },
      { id: 3, username: "plain", memberRole: "member", joinedAt: null },
    ],
    urls: [],
    tags: [],
    isCreator: false,
    isCoCreator,
    isLocked: false,
    currentUser: VIEWER_ID,
    memberSort: "name_az",
  } as unknown as UtubDetail;
}

async function refreshWith({
  isCoCreator,
}: {
  isCoCreator: boolean;
}): Promise<void> {
  vi.mocked(fetchUTubForRefresh).mockResolvedValue({
    kind: "ok",
    data: makeDetail({ isCoCreator }),
  });
  await updateUTubOnFindingStaleData({ utubID: UTUB_ID });
}

describe("permission fallback rebuilds the member deck with the new role", () => {
  beforeEach(() => {
    document.body.innerHTML = DOM;
    resetStore();
    vi.clearAllMocks();
    // Initial render as a plain member through the real select path.
    buildSelectedUTub({ selectedUTub: makeDetail({ isCoCreator: false }) });
  });

  afterEach(() => {
    resetStore();
  });

  it("a viewer promoted to co-owner gets a kebab on plain-member rows only", async () => {
    expect($(".memberRowKebab").length).toBe(0);

    await refreshWith({ isCoCreator: true });

    expect(getState().isCoCreator).toBe(true);
    const kebabs = $("#listMembers .memberRowKebab--coOwner");
    expect(kebabs.length).toBe(1);
    expect(kebabs.closest(".member").attr("memberid")).toBe("3");
    expect(vi.mocked(createLeaveUTubAsMemberIcon)).toHaveBeenLastCalledWith({
      currentUserID: VIEWER_ID,
      utubID: UTUB_ID,
    });
  });

  it("a viewer demoted from co-owner loses every kebab", async () => {
    buildSelectedUTub({ selectedUTub: makeDetail({ isCoCreator: true }) });
    expect($(".memberRowKebab").length).toBe(1);

    await refreshWith({ isCoCreator: false });

    expect(getState().isCoCreator).toBe(false);
    expect($(".memberRowKebab").length).toBe(0);
    expect($(".memberRowMenu").length).toBe(0);
  });
});
