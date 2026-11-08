import {
  initMemberDeckPolicyAttrs,
  seedMemberDeckPolicySnapshot,
} from "../policy-attrs.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { learnPolicyOff } from "../../utubs/policy.js";
import { resolveUtubSettings } from "../../../types/settings.js";
import { setupShowCreateMemberFormEventListeners } from "../create.js";
import { hideAndResetMemberCombobox } from "../member-combobox.js";
import { dismissAddMemberTipIfActive } from "../../onboarding/nudges.js";

vi.mock("../create.js", () => ({
  setupShowCreateMemberFormEventListeners: vi.fn(),
}));
vi.mock("../member-combobox.js", () => ({
  hideAndResetMemberCombobox: vi.fn(),
}));
vi.mock("../../onboarding/nudges.js", () => ({
  dismissAddMemberTipIfActive: vi.fn(),
}));

const $ = window.jQuery;

function settingsWith({
  membersCanAdd,
  coOwnersCanRemove = false,
}: {
  membersCanAdd: boolean;
  coOwnersCanRemove?: boolean;
}) {
  return resolveUtubSettings({
    members: {
      members_can_add: membersCanAdd,
      co_owners_can_remove: coOwnersCanRemove,
    },
  } as never);
}

function announcement() {
  return $("#MemberRowActionAnnouncement");
}

describe("initMemberDeckPolicyAttrs", () => {
  let unsubscribe: () => void;

  beforeEach(() => {
    document.body.innerHTML = `
      <div id="MemberDeck">
        <button id="MemberDeckHeaderAndCaret"></button>
        <button id="memberBtnCreate" class="hidden"></button>
        <div id="MemberDeckNotice" class="hidden"></div>
        <div id="createMemberWrap"></div>
        <span id="MemberRowActionAnnouncement" aria-live="off"></span>
      </div>
    `;
    vi.clearAllMocks();
    resetStore();
    setState({
      activeUTubID: 1,
      settings: settingsWith({ membersCanAdd: false }),
    });
    seedMemberDeckPolicySnapshot();
    unsubscribe = initMemberDeckPolicyAttrs();
  });

  afterEach(() => unsubscribe());

  it("shows, binds (once) and announces when add is granted in the same UTub", () => {
    setState({ settings: settingsWith({ membersCanAdd: true }) });

    expect($("#memberBtnCreate").hasClass("hidden")).toBe(false);
    expect(setupShowCreateMemberFormEventListeners).toHaveBeenCalledTimes(1);
    expect(setupShowCreateMemberFormEventListeners).toHaveBeenCalledWith(1);
    expect(announcement().attr("aria-live")).toBe("polite");
    expect(announcement().text()).toBe(
      APP_CONFIG.strings.MEMBER_ADD_NOW_ALLOWED_ANNOUNCEMENT,
    );
  });

  it("does not rebind while a combobox is open", () => {
    $("#createMemberWrap").append(`<div class="memberAddComboboxWrap"></div>`);
    setState({ settings: settingsWith({ membersCanAdd: true }) });

    expect(setupShowCreateMemberFormEventListeners).not.toHaveBeenCalled();
  });

  it("leaves an unrelated settings write with the combobox open untouched", () => {
    setState({ settings: settingsWith({ membersCanAdd: true }) });
    vi.clearAllMocks();
    announcement().text("");
    $("#createMemberWrap").append(`<div class="memberAddComboboxWrap"></div>`);

    setState({
      settings: settingsWith({ membersCanAdd: true, coOwnersCanRemove: true }),
    });

    expect(setupShowCreateMemberFormEventListeners).not.toHaveBeenCalled();
    expect(hideAndResetMemberCombobox).not.toHaveBeenCalled();
    expect(announcement().text()).toBe("");
  });

  it("unbinds, hides, dismisses the tip and announces on a revoke", () => {
    setState({ settings: settingsWith({ membersCanAdd: true }) });
    const opener = vi.fn();
    $("#memberBtnCreate").on("click", opener);

    setState({ settings: settingsWith({ membersCanAdd: false }) });
    $("#memberBtnCreate").trigger("click");

    expect($("#memberBtnCreate").hasClass("hidden")).toBe(true);
    expect(opener).not.toHaveBeenCalled();
    expect(dismissAddMemberTipIfActive).toHaveBeenCalled();
    expect(hideAndResetMemberCombobox).not.toHaveBeenCalled();
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(true);
    expect(announcement().attr("aria-live")).toBe("polite");
    expect(announcement().text()).toBe(
      APP_CONFIG.strings.MEMBER_ADD_NO_LONGER_ALLOWED_ANNOUNCEMENT,
    );
  });

  it("closes an open combobox, shows the notice and announces on a revoke", () => {
    setState({ settings: settingsWith({ membersCanAdd: true }) });
    $("#createMemberWrap").append(`<div class="memberAddComboboxWrap"></div>`);

    setState({ settings: settingsWith({ membersCanAdd: false }) });

    expect(hideAndResetMemberCombobox).toHaveBeenCalled();
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(false);
    expect($("#MemberDeckNotice").text()).toBe(
      APP_CONFIG.strings.MEMBER_ADD_NOT_ALLOWED,
    );
    expect(announcement().attr("aria-live")).toBe("polite");
    expect(announcement().text()).toBe(
      APP_CONFIG.strings.MEMBER_ADD_NOT_ALLOWED,
    );
  });

  it("moves focus from the hidden add button to the deck header", () => {
    setState({ settings: settingsWith({ membersCanAdd: true }) });
    const original = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      "offsetParent",
    );
    Object.defineProperty(HTMLElement.prototype, "offsetParent", {
      configurable: true,
      get() {
        return (this as HTMLElement).closest(".hidden") ? null : document.body;
      },
    });
    try {
      $("#memberBtnCreate").trigger("focus");
      expect(document.activeElement?.id).toBe("memberBtnCreate");

      setState({ settings: settingsWith({ membersCanAdd: false }) });

      expect(document.activeElement?.id).toBe("MemberDeckHeaderAndCaret");
    } finally {
      if (original) {
        Object.defineProperty(HTMLElement.prototype, "offsetParent", original);
      }
    }
  });

  it("skips its own notice and announcement for a learn-driven revoke", () => {
    setState({ settings: settingsWith({ membersCanAdd: true }) });
    seedMemberDeckPolicySnapshot();
    announcement().text("");

    learnPolicyOff({ utubID: 1, key: "members.members_can_add" });

    expect($("#memberBtnCreate").hasClass("hidden")).toBe(true);
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(true);
    expect(announcement().text()).toBe("");
  });

  it("shows the notice and announcement for a revoke after refuse, grant, revoke", () => {
    setState({ settings: settingsWith({ membersCanAdd: true }) });
    seedMemberDeckPolicySnapshot();
    learnPolicyOff({ utubID: 1, key: "members.members_can_add" });

    setState({ settings: settingsWith({ membersCanAdd: true }) });
    announcement().text("");
    $("#createMemberWrap").append(`<div class="memberAddComboboxWrap"></div>`);

    setState({ settings: settingsWith({ membersCanAdd: false }) });

    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(false);
    expect(announcement().text()).toBe(
      APP_CONFIG.strings.MEMBER_ADD_NOT_ALLOWED,
    );
  });

  it("closes an open combobox on a learn-driven revoke without a second announcement", () => {
    setState({ settings: settingsWith({ membersCanAdd: true }) });
    seedMemberDeckPolicySnapshot();
    $("#createMemberWrap").append(`<div class="memberAddComboboxWrap"></div>`);
    announcement().attr("aria-live", "assertive").text("refusal");

    learnPolicyOff({ utubID: 1, key: "members.members_can_add" });

    expect(hideAndResetMemberCombobox).toHaveBeenCalled();
    expect(announcement().text()).toBe("refusal");
    expect(announcement().attr("aria-live")).toBe("assertive");
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(true);
  });

  it("keeps a demoted co-owner's assertive refusal when the role refresh lands", () => {
    setState({
      isCoCreator: true,
      settings: settingsWith({ membersCanAdd: false }),
    });
    seedMemberDeckPolicySnapshot();
    announcement().attr("aria-live", "assertive").text("refusal");

    learnPolicyOff({ utubID: 1, key: "members.members_can_add" });
    expect(announcement().text()).toBe("refusal");

    setState({ isCoCreator: false });

    expect($("#memberBtnCreate").hasClass("hidden")).toBe(true);
    expect(announcement().text()).toBe("refusal");
    expect(announcement().attr("aria-live")).toBe("assertive");
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(true);
  });

  it("acts on nothing across a UTub change, only syncing visibility", () => {
    setState({
      activeUTubID: 2,
      settings: settingsWith({ membersCanAdd: true }),
    });

    expect($("#memberBtnCreate").hasClass("hidden")).toBe(false);
    expect(setupShowCreateMemberFormEventListeners).not.toHaveBeenCalled();
    expect(announcement().text()).toBe("");
  });

  it("emits no notice or announcement when the UTub is left or deleted", () => {
    setState({ settings: settingsWith({ membersCanAdd: true }) });
    announcement().text("");

    setState({ activeUTubID: null, settings: null });

    expect($("#memberBtnCreate").hasClass("hidden")).toBe(true);
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(true);
    expect(announcement().text()).toBe("");
  });

  it("emits nothing when a manager's effective ability does not change", () => {
    setState({ isCurrentUserOwner: true });
    seedMemberDeckPolicySnapshot();
    announcement().text("");
    vi.clearAllMocks();

    setState({ settings: settingsWith({ membersCanAdd: true }) });
    setState({ settings: settingsWith({ membersCanAdd: false }) });

    expect(announcement().text()).toBe("");
    expect(setupShowCreateMemberFormEventListeners).not.toHaveBeenCalled();
    expect(dismissAddMemberTipIfActive).not.toHaveBeenCalled();
  });

  it("emits nothing at init (the seeded baseline is not a flip)", () => {
    expect(announcement().text()).toBe("");
    expect($("#MemberDeckNotice").hasClass("hidden")).toBe(true);
  });

  it("sets data-co-owners-can-remove true only for exactly true, else false", () => {
    expect($("#MemberDeck").attr("data-co-owners-can-remove")).toBe("false");

    setState({
      settings: settingsWith({ membersCanAdd: false, coOwnersCanRemove: true }),
    });
    expect($("#MemberDeck").attr("data-co-owners-can-remove")).toBe("true");

    setState({ settings: null });
    expect($("#MemberDeck").attr("data-co-owners-can-remove")).toBe("false");
    expect(getState().settings).toBeNull();
  });
});

describe("initMemberDeckPolicyAttrs — co-owner remove flips", () => {
  let unsubscribe: () => void;

  // happy-dom has no layout: model the CSS rule (display:none unless the deck
  // attribute is exactly "true") for the co-owner kebab and its menu.
  function stubCssHideRule(): void {
    Object.defineProperty(HTMLElement.prototype, "offsetParent", {
      configurable: true,
      get(this: HTMLElement) {
        const hidden =
          this.closest(".memberRowKebab--coOwner, .memberRowMenu") !== null &&
          document.getElementById("MemberDeck")?.dataset.coOwnersCanRemove !==
            "true";
        return hidden ? null : document.body;
      },
    });
  }

  beforeEach(() => {
    document.body.innerHTML = `
      <div id="MemberDeck">
        <button id="MemberDeckHeaderAndCaret"></button>
        <button id="memberBtnCreate" class="hidden"></button>
        <div id="createMemberWrap"></div>
        <div id="listMembers">
          <span class="member" memberid="5">
            <span class="member-right">
              <button class="memberRowKebab memberRowKebab--coOwner" aria-expanded="true">k</button>
              <div class="memberRowMenu open"><button class="memberRowMenuItem" id="item5">Remove</button></div>
            </span>
          </span>
        </div>
        <span id="MemberRowActionAnnouncement" aria-live="off"></span>
      </div>
    `;
    stubCssHideRule();
    vi.clearAllMocks();
    resetStore();
    setState({
      activeUTubID: 1,
      isCurrentUserOwner: false,
      isCoCreator: true,
      settings: settingsWith({ membersCanAdd: true, coOwnersCanRemove: true }),
    });
    seedMemberDeckPolicySnapshot();
    unsubscribe = initMemberDeckPolicyAttrs();
  });

  afterEach(() => {
    unsubscribe();
    delete (HTMLElement.prototype as unknown as Record<string, unknown>)
      .offsetParent;
  });

  it("closes an open row menu and moves focus to the row when the switch goes off", () => {
    $("#item5")[0].focus();
    setState({
      settings: settingsWith({ membersCanAdd: true, coOwnersCanRemove: false }),
    });

    expect($(".memberRowMenu").hasClass("open")).toBe(false);
    expect($(".memberRowKebab--coOwner").attr("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe($(".member[memberid=5]")[0]);
    expect(announcement().attr("aria-live")).toBe("polite");
    expect(announcement().text()).toBe(
      APP_CONFIG.strings.MEMBERS_PERMISSIONS_CO_OWNERS_REMOVE_OFF_NOTICE,
    );
  });

  it("announces politely when the switch goes on", () => {
    setState({
      settings: settingsWith({ membersCanAdd: true, coOwnersCanRemove: false }),
    });
    announcement().text("").attr("aria-live", "off");

    setState({
      settings: settingsWith({ membersCanAdd: true, coOwnersCanRemove: true }),
    });

    expect(announcement().attr("aria-live")).toBe("polite");
    expect(announcement().text()).toBe(
      APP_CONFIG.strings.MEMBERS_PERMISSIONS_CO_OWNERS_REMOVE_ON_NOTICE,
    );
  });

  it("hides the kebab but stays silent when the change is a learned refusal", () => {
    learnPolicyOff({ utubID: 1, key: "members.co_owners_can_remove" });

    expect($("#MemberDeck").attr("data-co-owners-can-remove")).toBe("false");
    expect($(".memberRowMenu").hasClass("open")).toBe(false);
    expect(announcement().text()).toBe("");
  });

  it("stays silent when a viewer who is not a co-owner sees the setting change", () => {
    setState({ isCoCreator: false });
    seedMemberDeckPolicySnapshot();
    announcement().text("");

    setState({
      settings: settingsWith({ membersCanAdd: true, coOwnersCanRemove: false }),
    });

    expect(announcement().text()).toBe("");
  });

  it("stays silent when a demotion (a role change) ends the remove ability", () => {
    setState({ isCoCreator: false });

    expect(announcement().text()).toBe("");
  });

  it("stays silent across a UTub switch", () => {
    setState({
      activeUTubID: 2,
      settings: settingsWith({ membersCanAdd: true, coOwnersCanRemove: false }),
    });

    expect(announcement().text()).toBe("");
  });

  it("stays silent when the ability did not change", () => {
    setState({
      settings: settingsWith({ membersCanAdd: false, coOwnersCanRemove: true }),
    });

    expect(announcement().text()).toBe("");
  });
});
