import { UI_EVENTS } from "../../../types/metrics-events.js";
import {
  closeMemberNameFilter,
  hideMemberFilterBar,
  openMemberNameFilter,
  resetMemberFilter,
  setMemberSelectorSearchEventListener,
  showMemberFilterBar,
} from "../search.js";
import {
  MEMBER_SEARCH_CLOSE_TARGET,
  MEMBER_SEARCH_OPEN_TARGET,
} from "../../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../logic/member-search.js", () => ({
  filterMembersByName: vi.fn(() => []),
}));

const $ = window.jQuery;

const FILTER_HTML = `
  <div id="MemberDeck">
    <button id="memberNameFilterBtn" aria-expanded="false"></button>
    <button id="memberNameFilterBtnClose" class="hidden"></button>
    <div id="SearchMemberWrap">
      <input id="MemberNameSearch" type="search" value="" />
    </div>
    <p id="MemberSearchNoResults" class="hidden"></p>
    <span id="MemberSearchAnnouncement"></span>
    <div id="displayMemberWrap">
      <div id="UTubOwner">
        <span class="member" memberid="0"><b>alice_owner</b></span>
      </div>
      <div id="listMembers">
        <span class="member" memberid="1"><b>bob_dev</b></span>
        <span class="member" memberid="2"><b>carol_design</b></span>
      </div>
    </div>
  </div>
`;

// Module-level _memberSearchOpen flag persists across tests; explicitly reset
// by triggering a blur on the input after attaching the listener. The blur
// must use the member adapter's namespace (blur.memberSearchInputEsc), not the
// tag/utub namespace, or the member blur handler will never fire and the flag
// stays true between tests.
function resetSearchModuleState(): void {
  setMemberSelectorSearchEventListener();
  $("#MemberNameSearch").trigger("blur.memberSearchInputEsc");
}

describe("Member search metrics — UI_MEMBER_SEARCH_OPEN / UI_MEMBER_SEARCH_CLOSE", () => {
  beforeEach(() => {
    document.body.innerHTML = FILTER_HTML;
    resetSearchModuleState();
    vi.clearAllMocks();
  });

  afterEach(() => {
    $("#MemberNameSearch").trigger("blur.memberSearchInputEsc");
    document.body.innerHTML = "";
  });

  it("emits ui_member_search_open with target 'members' when input gains focus", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#MemberNameSearch").trigger("focus.memberSearchInputEsc");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_MEMBER_SEARCH_OPEN,
      target: MEMBER_SEARCH_OPEN_TARGET.MEMBERS,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does not double-emit when focus fires a second time without a blur between", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#MemberNameSearch").trigger("focus.memberSearchInputEsc");
    $("#MemberNameSearch").trigger("focus.memberSearchInputEsc");

    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("re-emits ui_member_search_open after a blur resets the flag", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#MemberNameSearch").trigger("focus.memberSearchInputEsc");
    $("#MemberNameSearch").trigger("blur.memberSearchInputEsc");
    $("#MemberNameSearch").trigger("focus.memberSearchInputEsc");

    expect(emit).toHaveBeenCalledTimes(2);
    expect(emit).toHaveBeenNthCalledWith(1, {
      event: UI_EVENTS.UI_MEMBER_SEARCH_OPEN,
      target: MEMBER_SEARCH_OPEN_TARGET.MEMBERS,
    });
    expect(emit).toHaveBeenNthCalledWith(2, {
      event: UI_EVENTS.UI_MEMBER_SEARCH_OPEN,
      target: MEMBER_SEARCH_OPEN_TARGET.MEMBERS,
    });
  });

  it("emits a single ui_member_search_close on closeMemberNameFilter when open", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    openMemberNameFilter();
    vi.mocked(emit).mockClear();

    closeMemberNameFilter();

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_MEMBER_SEARCH_CLOSE,
      target: MEMBER_SEARCH_CLOSE_TARGET.MEMBERS,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does not emit close on closeMemberNameFilter when the deck was never opened (init path)", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    closeMemberNameFilter();

    expect(emit).not.toHaveBeenCalled();
  });

  it("emits ui_member_search_close from a direct resetMemberFilter call when open", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#MemberNameSearch").trigger("focus.memberSearchInputEsc");
    vi.mocked(emit).mockClear();

    resetMemberFilter();

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_MEMBER_SEARCH_CLOSE,
      target: MEMBER_SEARCH_CLOSE_TARGET.MEMBERS,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does not emit close from a direct resetMemberFilter call when not open", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    resetMemberFilter();

    expect(emit).not.toHaveBeenCalled();
  });

  it("does not emit on listener setup alone (no init emit)", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    // beforeEach already attached the listener and blurred to reset state.
    expect(emit).not.toHaveBeenCalled();
  });

  describe("funnel toggle show/hide", () => {
    it("showMemberFilterBar leaves the open emit count unchanged", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      showMemberFilterBar();

      expect(emit).not.toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MEMBER_SEARCH_OPEN,
        target: MEMBER_SEARCH_OPEN_TARGET.MEMBERS,
      });
    });

    it("hideMemberFilterBar emits close via resetMemberFilter's guard when the filter is open", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      $("#MemberNameSearch").trigger("focus.memberSearchInputEsc");
      vi.mocked(emit).mockClear();

      hideMemberFilterBar();

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MEMBER_SEARCH_CLOSE,
        target: MEMBER_SEARCH_CLOSE_TARGET.MEMBERS,
      });
      expect(emit).toHaveBeenCalledTimes(1);
    });

    it("still emits ui_member_search_close when the input blurred first (X-button race)", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      openMemberNameFilter();
      // Clicking the X button blurs the input before the click handler runs,
      // clearing the focus flag — the DOM-state guard must still record close.
      $("#MemberNameSearch").trigger("blur.memberSearchInputEsc");
      vi.mocked(emit).mockClear();

      closeMemberNameFilter();

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MEMBER_SEARCH_CLOSE,
        target: MEMBER_SEARCH_CLOSE_TARGET.MEMBERS,
      });
      expect(emit).toHaveBeenCalledTimes(1);
    });

    it("does not emit close when the funnel was not open (X button while collapsed)", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      closeMemberNameFilter();

      expect(emit).not.toHaveBeenCalled();
    });
  });

  it("does not double-emit close when closeMemberNameFilter delegates to resetMemberFilter", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    openMemberNameFilter();

    closeMemberNameFilter();

    const openCalls = vi
      .mocked(emit)
      .mock.calls.filter(
        (call) => call[0].event === UI_EVENTS.UI_MEMBER_SEARCH_OPEN,
      );
    const closeCalls = vi
      .mocked(emit)
      .mock.calls.filter(
        (call) => call[0].event === UI_EVENTS.UI_MEMBER_SEARCH_CLOSE,
      );
    expect(openCalls).toHaveLength(1);
    expect(closeCalls).toHaveLength(1);
  });
});
