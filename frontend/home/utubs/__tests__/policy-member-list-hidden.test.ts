import { isMemberListHiddenForViewer } from "../policy.js";
import { resetStore, setState } from "../../../store/app-store.js";
import { EMPTY_UTUB_SETTINGS } from "../../../types/settings.js";

function settingsWithHidden({ hidden }: { hidden: boolean }) {
  return {
    ...EMPTY_UTUB_SETTINGS,
    members: { ...EMPTY_UTUB_SETTINGS.members, hide_member_list: hidden },
  };
}

describe("isMemberListHiddenForViewer", () => {
  beforeEach(() => resetStore());

  it("never hides the list from the owner", () => {
    setState({
      isCurrentUserOwner: true,
      settings: settingsWithHidden({ hidden: true }),
    });
    expect(isMemberListHiddenForViewer()).toBe(false);
  });

  it("never hides the list from a co-owner", () => {
    setState({
      isCoCreator: true,
      settings: settingsWithHidden({ hidden: true }),
    });
    expect(isMemberListHiddenForViewer()).toBe(false);
  });

  it("fails closed for a plain member with no settings", () => {
    setState({ isCurrentUserOwner: false, isCoCreator: false, settings: null });
    expect(isMemberListHiddenForViewer()).toBe(true);
  });

  it("hides the list from a plain member when hide_member_list is true", () => {
    setState({ settings: settingsWithHidden({ hidden: true }) });
    expect(isMemberListHiddenForViewer()).toBe(true);
  });

  it("shows the list to a plain member when hide_member_list is false", () => {
    setState({ settings: settingsWithHidden({ hidden: false }) });
    expect(isMemberListHiddenForViewer()).toBe(false);
  });
});
