import { canAddMembers, learnPolicyOff } from "../policy.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { resolveUtubSettings } from "../../../types/settings.js";

function settingsWith({ membersCanAdd }: { membersCanAdd: boolean }) {
  return resolveUtubSettings({
    members: { members_can_add: membersCanAdd },
  } as never);
}

describe("canAddMembers", () => {
  beforeEach(() => resetStore());

  it("allows the owner regardless of settings", () => {
    setState({ isCurrentUserOwner: true, settings: null });
    expect(canAddMembers()).toBe(true);
  });

  it("allows a co-owner regardless of settings", () => {
    setState({
      isCoCreator: true,
      settings: settingsWith({ membersCanAdd: false }),
    });
    expect(canAddMembers()).toBe(true);
  });

  it("allows a plain member only while members_can_add is true", () => {
    setState({ settings: settingsWith({ membersCanAdd: true }) });
    expect(canAddMembers()).toBe(true);
    setState({ settings: settingsWith({ membersCanAdd: false }) });
    expect(canAddMembers()).toBe(false);
  });

  it("denies a plain member when settings are missing (fail closed)", () => {
    setState({ settings: null });
    expect(canAddMembers()).toBe(false);
  });

  it("evaluates a passed state instead of the store", () => {
    expect(
      canAddMembers({
        isCurrentUserOwner: false,
        isCoCreator: true,
        settings: null,
      }),
    ).toBe(true);
  });
});

describe("learnPolicyOff", () => {
  beforeEach(() => {
    resetStore();
    setState({
      activeUTubID: 7,
      settings: settingsWith({ membersCanAdd: true }),
    });
  });

  it("turns only the named key off and records its version", () => {
    const before = getState().policyLearnedVersion;

    expect(learnPolicyOff({ utubID: 7, key: "members.members_can_add" })).toBe(
      true,
    );

    const state = getState();
    expect(state.settings?.members.members_can_add).toBe(false);
    expect(state.policyLearnedVersion).toBe(before + 1);
    expect(state.learnedOffPolicies["members.members_can_add"]).toBe(
      before + 1,
    );
    expect(state.learnedOffPolicies["urls.allow_short_links"]).toBeUndefined();
  });

  it("writes nothing for a UTub that is no longer active", () => {
    expect(learnPolicyOff({ utubID: 8, key: "members.members_can_add" })).toBe(
      false,
    );
    expect(getState().settings?.members.members_can_add).toBe(true);
  });

  it("writes nothing when settings were never delivered", () => {
    setState({ settings: null });
    expect(learnPolicyOff({ utubID: 7, key: "members.members_can_add" })).toBe(
      false,
    );
    expect(getState().policyLearnedVersion).toBe(0);
  });

  it("resets the learned map when the active UTub changes", () => {
    learnPolicyOff({ utubID: 7, key: "members.members_can_add" });
    setState({ activeUTubID: 9 });
    expect(getState().learnedOffPolicies).toEqual({});
  });
});
