// End-to-end add-refusal flows over the REAL store, add-refusal, notice, policy,
// stale-data and the real revoke subscription. Only the network, the heavy deck
// builders and the nudge module are mocked.
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { createMockJqXHR } from "../../../__tests__/helpers/mock-jquery.js";
import { makeUtubSummaryItem } from "../../../__tests__/helpers/utub-summary.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { resolveUtubSettings } from "../../../types/settings.js";
import { canAddMembers, learnPolicyOff } from "../../utubs/policy.js";
import { updateUTubOnFindingStaleData } from "../../utubs/stale-data.js";
import {
  fetchUTubForRefresh,
  buildSelectedUTub,
} from "../../utubs/selectors.js";
import { showMemberCombobox } from "../member-combobox.js";
import { submitStagedMembers } from "../member-combobox-submit.js";
import {
  initMemberDeckPolicyAttrs,
  seedMemberDeckPolicySnapshot,
} from "../policy-attrs.js";

import type { RefreshResult } from "../../utubs/selectors.js";
import type { UtubDetail } from "../../../types/utub.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());
vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(),
}));
vi.mock("../../utubs/selectors.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../utubs/selectors.js")
  >("../../utubs/selectors.js");
  return {
    ...actual,
    fetchUTubForRefresh: vi.fn(),
    buildSelectedUTub: vi.fn(),
    makeUTubRoleIcon: vi.fn(() => "<svg></svg>"),
  };
});
vi.mock("../../utubs/deck.js", () => ({
  showUTubLoadingIconAndSetTimeout: vi.fn(() => 0),
  hideUTubLoadingIconAndClearTimeout: vi.fn(),
  setUTubDeckOnUTubSelected: vi.fn(),
}));
vi.mock("../../utubs/header-fit.js", () => ({
  fitUTubHeaderAndSubheader: vi.fn(),
}));
vi.mock("../../utubs/remove-local.js", () => ({ removeUTubLocally: vi.fn() }));
vi.mock("../../urls/deck.js", () => ({ showURLDeckBannerError: vi.fn() }));
vi.mock("../../urls/update-description.js", () => ({
  removeEventListenersForShowCreateUTubDescIfEmptyDesc: vi.fn(),
  showCreateDescriptionButtonAlways: vi.fn(),
}));
vi.mock("../../urls/utub-edit-panel-dirty.js", () => ({
  syncUTubEditPanelDirtyState: vi.fn(),
  bindUTubEditPanelDirtyState: vi.fn(),
  unbindUTubEditPanelDirtyState: vi.fn(),
}));
vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  getCurrentMobilePanel: vi.fn(() => "members"),
  setCurrentMobilePanel: vi.fn(),
  replaceMobilePanelHistoryState: vi.fn(),
  setMobileUIWhenUTubDeckSelected: vi.fn(),
  setMobileUIWhenMemberDeckSelected: vi.fn(),
  setMobileUIWhenUTubSelectedOrURLNavSelected: vi.fn(),
}));
vi.mock("../deck.js", () => ({
  setMemberDeckForUTub: vi.fn(),
  reorderMemberDeck: vi.fn(() => []),
}));
vi.mock("../search.js", () => ({
  closeMemberNameFilter: vi.fn(),
  reapplyMemberFilter: vi.fn(),
}));
vi.mock("../members.js", () => ({
  createMemberBadge: vi.fn(() => window.jQuery(`<span class="member"></span>`)),
}));
vi.mock("../create.js", () => ({
  setupShowCreateMemberFormEventListeners: vi.fn(),
}));
vi.mock("../../utubs/row-counts.js", () => ({
  applyRowCountDelta: vi.fn(),
  setRowCountsFromStore: vi.fn(),
}));
vi.mock("../../onboarding/nudges.js", () => ({
  dismissAddMemberTipIfActive: vi.fn(),
}));
vi.mock("../../../lib/modal-tracking.js", () => ({
  setOpenForm: vi.fn(),
  clearOpenForm: vi.fn(),
}));

const $ = window.jQuery;

const UTUB_ID = 7;
const OWNER_ID = 1000;
const SELF_ID = 2000;
const NOT_ALLOWED = { status: 403, responseJSON: { errorCode: 7 } };

const DECK_HTML = `
  <div id="MemberDeck">
    <button id="MemberDeckHeaderAndCaret" aria-expanded="true"></button>
    <button id="memberBtnCreate" class="green-clickable"></button>
    <div id="MemberDeckNotice" class="hidden"></div>
    <span id="MemberSearchAnnouncement" aria-live="polite"></span>
    <span id="MobilePanelAnnouncement" aria-live="polite"></span>
    <span id="MemberRowActionAnnouncement" aria-live="polite"></span>
    <div id="createMemberWrap" class="hidden"></div>
    <div id="displayMemberWrap">
      <div id="UTubOwner"></div>
      <div id="listMembers"></div>
    </div>
  </div>
`;

const MEMBERS = [
  {
    id: OWNER_ID,
    username: "owner",
    memberRole: "creator" as const,
    joinedAt: null,
  },
  {
    id: SELF_ID,
    username: "self",
    memberRole: "member" as const,
    joinedAt: null,
  },
];

function settingsWith({ membersCanAdd }: { membersCanAdd: boolean }) {
  return resolveUtubSettings({
    members: { members_can_add: membersCanAdd },
  } as never);
}

function seedViewer({ coOwner = false }: { coOwner?: boolean } = {}): void {
  setState({
    activeUTubID: UTUB_ID,
    activeUTubName: "My UTub",
    activeUTubDescription: "desc",
    isCurrentUserOwner: false,
    isCoCreator: coOwner,
    isCurrentUTubLocked: false,
    utubOwnerID: OWNER_ID,
    urls: [],
    tags: [],
    members: structuredClone(MEMBERS),
    utubs: [
      makeUtubSummaryItem({
        id: UTUB_ID,
        name: "My UTub",
        memberRole: coOwner ? "co-creator" : "member",
        isLocked: false,
      }),
    ],
    settings: settingsWith({ membersCanAdd: true }),
  });
}

// What the server returns for the viewer: unchanged content, the given role and
// settings. `isCoCreator` mirrors the viewer's CURRENT role in the store unless
// the test demotes them.
function serverDetail({
  membersCanAdd,
  isCoCreator = false,
}: {
  membersCanAdd: boolean;
  isCoCreator?: boolean;
}): UtubDetail {
  return {
    status: "Success",
    id: UTUB_ID,
    name: "My UTub",
    createdByUserID: OWNER_ID,
    createdAt: "2026-01-01T00:00:00Z",
    description: "desc",
    members: structuredClone(MEMBERS),
    urls: [],
    tags: [],
    isCreator: false,
    isCoCreator,
    isLocked: false,
    currentUser: SELF_ID,
    memberSort: getState().preferences.memberSort,
    settings: { members: { members_can_add: membersCanAdd } },
  } as unknown as UtubDetail;
}

function ok(data: UtubDetail): RefreshResult {
  return { kind: "ok", data };
}

async function flushPromises(): Promise<void> {
  for (let tick = 0; tick < 20; tick += 1) await Promise.resolve();
}

// Counts non-empty text writes to the row-action live region by intercepting
// the element's own `textContent` setter (jQuery `.text(msg)` assigns it).
// Clearing to "" is not a write.
function watchAnnouncementWrites(): { count: () => number; stop: () => void } {
  const target = document.getElementById("MemberRowActionAnnouncement")!;
  // The most-derived accessor for this element (happy-dom defines it below Node).
  let owner: object | null = target;
  while (owner && !Object.getOwnPropertyDescriptor(owner, "textContent")) {
    owner = Object.getPrototypeOf(owner);
  }
  const inherited = Object.getOwnPropertyDescriptor(owner!, "textContent")!;
  let writes = 0;
  Object.defineProperty(target, "textContent", {
    configurable: true,
    get() {
      return inherited.get!.call(this);
    },
    set(value: string) {
      if (value !== "") writes += 1;
      inherited.set!.call(this, value);
    },
  });
  return {
    count: () => writes,
    stop: () => {
      delete (target as { textContent?: string }).textContent;
    },
  };
}

const COMBOBOX_WRAP = ".memberAddComboboxWrap";

function typeIn(value: string): void {
  $(`${COMBOBOX_WRAP} .memberAddComboboxInput`).val(value).trigger("input");
  vi.runAllTimers();
}

let unsubscribe: () => void;

beforeEach(() => {
  document.body.innerHTML = DECK_HTML;
  resetStore();
  vi.clearAllMocks();
  vi.useFakeTimers();
  vi.mocked(is429Handled).mockReturnValue(false);
  vi.mocked(fetchUTubForRefresh).mockResolvedValue({ kind: "error" });
  vi.mocked(buildSelectedUTub).mockImplementation(({ selectedUTub }) => {
    setState({
      isCurrentUserOwner: selectedUTub.isCreator,
      isCoCreator: selectedUTub.isCoCreator,
    });
  });
  seedViewer();
  seedMemberDeckPolicySnapshot();
  unsubscribe = initMemberDeckPolicyAttrs();
});

afterEach(() => {
  unsubscribe();
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("add refusal: exactly one live-region write through the real subscription", () => {
  it("a single chip's candidate fetch 403 writes the assertive refusal once", async () => {
    const fetchXhr = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValueOnce(fetchXhr);
    const writes = watchAnnouncementWrites();

    showMemberCombobox(UTUB_ID);
    fetchXhr.reject(NOT_ALLOWED);
    await flushPromises();

    const live = $("#MemberRowActionAnnouncement");
    expect(live.text()).toBe(APP_CONFIG.strings.MEMBER_ADD_NOT_ALLOWED);
    expect(writes.count()).toBe(1);
    expect(live.attr("aria-live")).toBe("assertive");
    // The add UI is gone, the explanation stays.
    expect($("#memberBtnCreate").hasClass("hidden")).toBe(true);
    expect($("#createMemberWrap").children().length).toBe(0);
    expect($("#MemberDeckNotice").text()).toBe(
      APP_CONFIG.strings.MEMBER_ADD_NOT_ALLOWED,
    );
    writes.stop();
  });

  it("a batch of two refused chips writes one combined assertive announcement", async () => {
    const candidatesXhr = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValueOnce(candidatesXhr);
    showMemberCombobox(UTUB_ID);
    candidatesXhr.resolve(
      { members: [{ id: 1, username: "Bob", sharedUtubCount: 2 }] },
      "success",
      { status: 200 },
    );
    typeIn("bo");
    $(`${COMBOBOX_WRAP} .memberAddOption:not(.memberAddOptionOutsider)`)
      .first()
      .trigger("click.memberAddCombobox");
    typeIn("Ghost");
    $(`${COMBOBOX_WRAP} .memberAddOptionOutsider`).trigger(
      "click.memberAddCombobox",
    );
    const firstPost = createMockJqXHR();
    const secondPost = createMockJqXHR();
    vi.mocked(ajaxCall)
      .mockReturnValueOnce(firstPost)
      .mockReturnValueOnce(secondPost);
    const writes = watchAnnouncementWrites();

    const settle = submitStagedMembers({
      utubID: UTUB_ID,
      wrap: $(COMBOBOX_WRAP),
    });
    firstPost.reject(NOT_ALLOWED);
    secondPost.reject(NOT_ALLOWED);
    await settle;
    await flushPromises();

    const live = $("#MemberRowActionAnnouncement");
    expect(writes.count()).toBe(1);
    expect(live.attr("aria-live")).toBe("assertive");
    expect(live.text()).toContain(APP_CONFIG.strings.MEMBER_ADD_NOT_ALLOWED);
    expect($("#memberBtnCreate").hasClass("hidden")).toBe(true);
    expect($("#createMemberWrap").children().length).toBe(0);
    writes.stop();
  });
});

describe("add refusal: a stale in-flight payload cannot re-enable the learned policy", () => {
  it("a refresh captured before the learn lands after it and the add stays off", async () => {
    let deliver: (result: RefreshResult) => void = () => {};
    vi.mocked(fetchUTubForRefresh).mockReturnValueOnce(
      new Promise<RefreshResult>((resolve) => {
        deliver = resolve;
      }),
    );
    // The refresh starts (and captures its versions) before any refusal.
    const inFlight = updateUTubOnFindingStaleData({ utubID: UTUB_ID });
    expect(canAddMembers()).toBe(true);

    learnPolicyOff({ utubID: UTUB_ID, key: "members.members_can_add" });
    expect(canAddMembers()).toBe(false);
    expect($("#memberBtnCreate").hasClass("hidden")).toBe(true);

    // The payload was produced before the owner's revoke reached the server.
    deliver(ok(serverDetail({ membersCanAdd: true })));
    await inFlight;
    await flushPromises();

    expect(getState().settings?.members.members_can_add).toBe(false);
    expect(canAddMembers()).toBe(false);
    expect($("#memberBtnCreate").hasClass("hidden")).toBe(true);
  });

  it("a payload fetched after the learn is authoritative and re-enables the add", async () => {
    learnPolicyOff({ utubID: UTUB_ID, key: "members.members_can_add" });
    expect(canAddMembers()).toBe(false);

    vi.mocked(fetchUTubForRefresh).mockResolvedValueOnce(
      ok(serverDetail({ membersCanAdd: true })),
    );
    await updateUTubOnFindingStaleData({ utubID: UTUB_ID });
    await flushPromises();

    expect(canAddMembers()).toBe(true);
    expect($("#memberBtnCreate").hasClass("hidden")).toBe(false);
  });
});

describe("add refusal: a demoted co-owner ends with the add UI gone", () => {
  it("403, then the refresh reports isCoCreator false: no add button, no combobox, one write", async () => {
    unsubscribe();
    seedViewer({ coOwner: true });
    seedMemberDeckPolicySnapshot();
    unsubscribe = initMemberDeckPolicyAttrs();
    expect(canAddMembers()).toBe(true);

    // The refresh the refusal triggers reports the demotion and add off.
    vi.mocked(fetchUTubForRefresh).mockResolvedValueOnce(
      ok(serverDetail({ membersCanAdd: false, isCoCreator: false })),
    );
    const fetchXhr = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValueOnce(fetchXhr);
    const writes = watchAnnouncementWrites();

    showMemberCombobox(UTUB_ID);
    fetchXhr.reject(NOT_ALLOWED);
    await flushPromises();

    expect(getState().isCoCreator).toBe(false);
    expect(canAddMembers()).toBe(false);
    expect($("#memberBtnCreate").hasClass("hidden")).toBe(true);
    expect($("#createMemberWrap").children().length).toBe(0);
    expect(writes.count()).toBe(1);
    expect($("#MemberRowActionAnnouncement").attr("aria-live")).toBe(
      "assertive",
    );
    expect($("#MemberRowActionAnnouncement").text()).toBe(
      APP_CONFIG.strings.MEMBER_ADD_NOT_ALLOWED,
    );
    writes.stop();
  });
});
