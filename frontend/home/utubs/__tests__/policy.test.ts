import {
  canAddMembers,
  canDeleteTags,
  canTag,
  learnPolicyOff,
} from "../policy.js";
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

function tagSettingsWith({ tag, del }: { tag?: boolean; del?: boolean }) {
  return resolveUtubSettings({
    tags: { members_can_tag: tag, members_can_delete_tags: del },
  } as never);
}

describe("canTag / canDeleteTags", () => {
  beforeEach(() => resetStore());

  it("allows the owner and a co-owner regardless of settings", () => {
    const off = tagSettingsWith({ tag: false, del: false });
    setState({ isCurrentUserOwner: true, settings: off });
    expect(canTag()).toBe(true);
    expect(canDeleteTags()).toBe(true);
    setState({ isCurrentUserOwner: false, isCoCreator: true, settings: null });
    expect(canTag()).toBe(true);
    expect(canDeleteTags()).toBe(true);
  });

  it("lets a plain member follow the flags", () => {
    setState({ settings: tagSettingsWith({ tag: true, del: true }) });
    expect(canTag()).toBe(true);
    expect(canDeleteTags()).toBe(true);
    setState({ settings: tagSettingsWith({ tag: true, del: false }) });
    expect(canTag()).toBe(true);
    expect(canDeleteTags()).toBe(false);
  });

  it("evaluates a passed state instead of the store", () => {
    const settings = tagSettingsWith({ tag: true, del: false });
    const plain = { isCurrentUserOwner: false, isCoCreator: false, settings };
    expect(canTag(plain)).toBe(true);
    expect(canDeleteTags(plain)).toBe(false);
    expect(canDeleteTags({ ...plain, isCoCreator: true })).toBe(true);
  });

  it("denies delete for a plain member when tagging is off", () => {
    setState({ settings: tagSettingsWith({ tag: false, del: true }) });
    expect(canTag()).toBe(false);
    expect(canDeleteTags()).toBe(false);
  });

  it("denies a plain member when settings are missing or not true", () => {
    setState({ settings: null });
    expect(canTag()).toBe(false);
    expect(canDeleteTags()).toBe(false);
    const nonTrue = {
      ...tagSettingsWith({}),
      tags: { members_can_tag: "yes", members_can_delete_tags: 1 },
    } as never;
    setState({ settings: nonTrue });
    expect(canTag()).toBe(false);
    expect(canDeleteTags()).toBe(false);
  });
});

describe("learnPolicyOff for tags keys", () => {
  beforeEach(() => {
    resetStore();
    setState({
      activeUTubID: 7,
      settings: tagSettingsWith({ tag: true, del: true }),
    });
  });

  it("turns off members_can_tag only, without mutating the old settings", () => {
    const before = getState().settings;
    expect(learnPolicyOff({ utubID: 7, key: "tags.members_can_tag" })).toBe(
      true,
    );
    const state = getState();
    expect(state.settings?.tags.members_can_tag).toBe(false);
    expect(state.settings?.tags.members_can_delete_tags).toBe(true);
    expect(before?.tags.members_can_tag).toBe(true);
    expect(state.settings?.tags).not.toBe(before?.tags);
    expect(state.learnedOffPolicies["tags.members_can_tag"]).toBe(1);
  });

  it("turns off members_can_delete_tags only", () => {
    learnPolicyOff({ utubID: 7, key: "tags.members_can_delete_tags" });
    const state = getState();
    expect(state.settings?.tags.members_can_delete_tags).toBe(false);
    expect(state.settings?.tags.members_can_tag).toBe(true);
    expect(state.learnedOffPolicies["tags.members_can_delete_tags"]).toBe(1);
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
