import {
  initMemberDeckPolicyAttrs,
  seedMemberDeckPolicySnapshot,
} from "../policy-attrs.js";
import { resetStore, setState } from "../../../store/app-store.js";
import { resolveUtubSettings } from "../../../types/settings.js";
import { showMemberCombobox } from "../member-combobox.js";

// Uses the real create.js so a double bind (two openers) would show up as two
// showMemberCombobox calls for one click.
vi.mock("../member-combobox.js", () => ({
  hideAndResetMemberCombobox: vi.fn(),
  showMemberCombobox: vi.fn(),
}));
vi.mock("../../onboarding/nudges.js", () => ({
  dismissAddMemberTipIfActive: vi.fn(),
}));

const $ = window.jQuery;

function settingsWith({ membersCanAdd }: { membersCanAdd: boolean }) {
  return resolveUtubSettings({
    members: { members_can_add: membersCanAdd },
  } as never);
}

describe("initMemberDeckPolicyAttrs with the real opener binder", () => {
  let unsubscribe: () => void;

  beforeEach(() => {
    document.body.innerHTML = `
      <div id="MemberDeck">
        <button id="MemberDeckHeaderAndCaret"></button>
        <button id="memberBtnCreate" class="hidden"></button>
        <div id="createMemberWrap"></div>
        <span id="MemberRowActionAnnouncement"></span>
      </div>
    `;
    vi.clearAllMocks();
    resetStore();
    setState({
      activeUTubID: 3,
      settings: settingsWith({ membersCanAdd: false }),
    });
    seedMemberDeckPolicySnapshot();
    unsubscribe = initMemberDeckPolicyAttrs();
  });

  afterEach(() => unsubscribe());

  it("deny then allow leaves exactly one opener", () => {
    setState({ settings: settingsWith({ membersCanAdd: true }) });
    setState({ settings: settingsWith({ membersCanAdd: false }) });
    setState({ settings: settingsWith({ membersCanAdd: true }) });

    $("#memberBtnCreate").trigger("click");

    expect(showMemberCombobox).toHaveBeenCalledTimes(1);
    expect(showMemberCombobox).toHaveBeenCalledWith(3);
  });

  it("leaves no opener after allowed-to-denied", () => {
    setState({ settings: settingsWith({ membersCanAdd: true }) });
    setState({ settings: settingsWith({ membersCanAdd: false }) });

    $("#memberBtnCreate").trigger("click");

    expect(showMemberCombobox).not.toHaveBeenCalled();
  });
});
