import { UI_EVENTS } from "../../../types/metrics-events.js";
import { setupShowCreateMemberFormEventListeners } from "../create.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

// showMemberCombobox (member-combobox.ts) is exercised end-to-end here to prove
// the invite-open metric still fires on open; stub its side-effecting deps so
// the emit assertion is isolated from the fetch / filter / modal machinery.
vi.mock("../co-member-fetch.js", () => ({
  loadCoMemberCandidates: vi.fn(),
  cancelCoMemberCandidatesFetch: vi.fn(),
}));

vi.mock("../search.js", () => ({
  closeMemberNameFilter: vi.fn(),
}));

vi.mock("../../../lib/modal-tracking.js", () => ({
  setOpenForm: vi.fn(),
  clearOpenForm: vi.fn(),
}));

vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
}));

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({
    members: [],
    coMemberCandidates: [],
    coMemberCandidatesLoaded: false,
    activeUTubID: 7,
    isCurrentUserOwner: true,
  })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const CREATE_MEMBER_FORM_HTML = `
  <div>
    <div id="createMemberWrap" class="hidden"></div>
    <div id="displayMemberWrap"></div>
    <button id="memberBtnCreate"></button>
  </div>
`;

describe("create-metrics — UI_MEMBER_INVITE_OPEN", () => {
  beforeEach(() => {
    document.body.innerHTML = CREATE_MEMBER_FORM_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits ui_member_invite_open when the invite button is clicked", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupShowCreateMemberFormEventListeners(7);
    $("#memberBtnCreate").trigger("click.createMember");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_MEMBER_INVITE_OPEN,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does not emit when listeners are set up but no interaction occurs", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setupShowCreateMemberFormEventListeners(7);

    expect(emit).not.toHaveBeenCalled();
  });
});
