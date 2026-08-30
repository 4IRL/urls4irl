import {
  closeTransferPicker,
  initTransferPicker,
  isTransferPickerOpen,
  openTransferPicker,
} from "../transfer-picker.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { AppEvents, emit } from "../../../lib/event-bus.js";
import { transferOwnershipShowModal } from "../transfer.js";
import { hideAndResetMemberCombobox } from "../member-combobox.js";
import { closeMemberNameFilter } from "../search.js";
import { closeAllMemberRowMenus } from "../row-menu.js";
import { isMobile } from "../../mobile.js";

vi.mock("../transfer.js", () => ({
  transferOwnershipShowModal: vi.fn(),
}));
vi.mock("../member-combobox.js", () => ({
  hideAndResetMemberCombobox: vi.fn(),
}));
vi.mock("../search.js", () => ({
  closeMemberNameFilter: vi.fn(),
}));
vi.mock("../row-menu.js", () => ({
  closeAllMemberRowMenus: vi.fn(),
}));
// Role helpers are stubbed — the picker rows carry decorative role affordances,
// but this suite asserts selection/filter/hand-off behaviour, not the glyph.
vi.mock("../../utubs/selectors.js", () => ({
  makeUTubRoleIcon: vi.fn(() => '<svg class="memberRole"></svg>'),
}));
vi.mock("../members.js", () => ({
  roleLabelFor: vi.fn((memberRole: string) => memberRole),
}));
// Desktop by default so the mobile tap-outside drawer path stays dormant.
vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
}));
vi.mock("../../../lib/modal-tracking.js", () => ({
  setOpenForm: vi.fn(),
  clearOpenForm: vi.fn(),
}));

interface Member {
  id: number;
  username: string;
  memberRole: string;
}
const storeState: {
  activeUTubID: number | null;
  utubOwnerID: number | null;
  members: Member[];
} = {
  activeUTubID: 1,
  utubOwnerID: 1,
  members: [],
};
vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => storeState),
  setState: vi.fn((partial: Partial<typeof storeState>) => {
    Object.assign(storeState, partial);
  }),
}));

const $ = window.jQuery;

const BASE_HTML = `
  <div id="MemberDeck">
    <button id="memberBtnTransferOwner" type="button">Transfer</button>
    <button id="utubBtnDelete" type="button">Delete</button>
    <button id="memberNameFilterBtn" type="button">Filter</button>
    <button id="memberBtnCreate" type="button">Add</button>
    <div id="transferOwnerPickerMount" class="transferOwnerPickerMount hidden"></div>
    <div id="displayMemberWrap"></div>
  </div>
`;

// Owner (id 1) + two eligible members.
const DEFAULT_MEMBERS: Member[] = [
  { id: 1, username: "owner_u", memberRole: "creator" },
  { id: 2, username: "alice", memberRole: "member" },
  { id: 3, username: "bob", memberRole: "cocreator" },
];

function mount(): JQuery {
  return $("#transferOwnerPickerMount");
}

function optionRows(): JQuery {
  return mount().find('.transferPickerOption[role="option"]');
}

function optionFor(memberId: number): JQuery {
  return mount().find(`#transferPickerOption-${memberId}`);
}

function filterInput(): JQuery {
  return mount().find(".transferPickerFilterInput");
}

function confirmBtn(): JQuery {
  return mount().find(".transferPickerConfirmBtn");
}

function footerMsg(): JQuery {
  return mount().find(".transferPickerMsg");
}

/** Dispatch a keydown that reaches the mount's capture-phase listener. */
function keydown(el: HTMLElement, key: string): void {
  el.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
}

function keyup(el: HTMLElement, key: string): void {
  el.dispatchEvent(new KeyboardEvent("keyup", { key, bubbles: true }));
}

beforeAll(() => {
  document.body.innerHTML = BASE_HTML;
  initTransferPicker();
});

beforeEach(() => {
  document.body.innerHTML = BASE_HTML;
  storeState.activeUTubID = 1;
  storeState.utubOwnerID = 1;
  storeState.members = DEFAULT_MEMBERS.map((member) => ({ ...member }));
  vi.clearAllMocks();
  vi.mocked(isMobile).mockReturnValue(false);
});

afterEach(() => {
  if (isTransferPickerOpen()) closeTransferPicker();
  document.body.innerHTML = "";
});

describe("openTransferPicker — rendering", () => {
  it("renders one option per non-owner member (owner excluded)", () => {
    openTransferPicker("#memberBtnTransferOwner");

    expect(optionRows().length).toBe(2);
    expect(optionFor(1).length).toBe(0); // owner excluded
    expect(optionFor(2).length).toBe(1);
    expect(optionFor(3).length).toBe(1);
    expect(isTransferPickerOpen()).toBe(true);
    expect($("#MemberDeck").hasClass("transfer-picker-open")).toBe(true);
  });

  it("puts role=listbox on the INNER listbox (not the mount), role=option/id/aria-selected on rows", () => {
    openTransferPicker("#memberBtnTransferOwner");

    expect(mount().attr("role")).toBeUndefined();
    expect(mount().find(".transferPickerListbox").attr("role")).toBe("listbox");
    expect(mount().find(".transferPickerListbox").attr("aria-label")).toBe(
      APP_CONFIG.strings.TRANSFER_OWNER_LISTBOX_ARIA,
    );
    const first = optionFor(2);
    expect(first.attr("role")).toBe("option");
    expect(first.attr("aria-selected")).toBe("false");
    // Single-select listbox omits aria-multiselectable.
    expect(
      mount().find(".transferPickerListbox").attr("aria-multiselectable"),
    ).toBeUndefined();
  });

  it("focuses the first row on open (roving entry tabindex 0, others -1); confirm starts disabled with the pick hint", () => {
    openTransferPicker("#memberBtnTransferOwner");

    expect(optionFor(2).attr("tabindex")).toBe("0");
    expect(optionFor(3).attr("tabindex")).toBe("-1");
    expect(document.activeElement).toBe(optionFor(2)[0]);
    expect(confirmBtn().prop("disabled")).toBe(true);
    expect(footerMsg().text()).toBe(
      APP_CONFIG.strings.TRANSFER_OWNER_PICK_HINT,
    );
  });

  it("renders the empty state (no filter, disabled confirm) when the owner is the only member", () => {
    storeState.members = [
      { id: 1, username: "owner_u", memberRole: "creator" },
    ];
    openTransferPicker("#memberBtnTransferOwner");

    const empty = mount().find(".transferPickerAllLocked");
    expect(empty.length).toBe(1);
    expect(empty.text()).toBe(APP_CONFIG.strings.TRANSFER_OWNER_NO_ELIGIBLE);
    expect(empty.attr("role")).toBe("status");
    expect(optionRows().length).toBe(0);
    expect(filterInput().length).toBe(0);
    expect(confirmBtn().prop("disabled")).toBe(true);
  });

  it("is a no-op when already open (re-entrancy guard)", () => {
    openTransferPicker("#memberBtnTransferOwner");
    // A second open must not re-run teardown collaborators.
    vi.mocked(closeAllMemberRowMenus).mockClear();
    openTransferPicker("#utubBtnDelete");
    expect(closeAllMemberRowMenus).not.toHaveBeenCalled();
  });
});

describe("filtering", () => {
  it("hides non-matching rows and shows the no-matches message, then clears on empty query", () => {
    openTransferPicker("#memberBtnTransferOwner");

    filterInput().val("ali").trigger("input");
    expect(optionFor(2).hasClass("hidden")).toBe(false); // alice matches
    expect(optionFor(3).hasClass("hidden")).toBe(true); // bob hidden
    expect(mount().find(".transferPickerNoMatches").hasClass("hidden")).toBe(
      true,
    );

    filterInput().val("zzz").trigger("input");
    expect(mount().find(".transferPickerNoMatches").hasClass("hidden")).toBe(
      false,
    );

    filterInput().val("").trigger("input");
    expect(optionFor(2).hasClass("hidden")).toBe(false);
    expect(optionFor(3).hasClass("hidden")).toBe(false);
  });
});

describe("single-select", () => {
  it("selecting a row marks exactly one selected, enables confirm, and updates the footer to the chosen username", () => {
    openTransferPicker("#memberBtnTransferOwner");

    optionFor(2).trigger("click");
    expect(optionFor(2).attr("aria-selected")).toBe("true");
    expect(optionFor(2).hasClass("active")).toBe(true);
    expect(confirmBtn().prop("disabled")).toBe(false);
    expect(footerMsg().text()).toBe(
      APP_CONFIG.strings.TRANSFER_OWNER_PICK_CHOSEN.replace(
        "{{ username }}",
        "alice",
      ),
    );
  });

  it("selecting a second row deselects the first (single-select)", () => {
    openTransferPicker("#memberBtnTransferOwner");

    optionFor(2).trigger("click");
    optionFor(3).trigger("click");
    expect(optionFor(2).attr("aria-selected")).toBe("false");
    expect(optionFor(2).hasClass("active")).toBe(false);
    expect(optionFor(3).attr("aria-selected")).toBe("true");
    expect(footerMsg().text()).toBe(
      APP_CONFIG.strings.TRANSFER_OWNER_PICK_CHOSEN.replace(
        "{{ username }}",
        "bob",
      ),
    );
  });
});

describe("keyboard", () => {
  it("ArrowDown roves focus and Enter selects the focused row", () => {
    openTransferPicker("#memberBtnTransferOwner");

    // First row (id 2) is focused on open; ArrowDown moves to id 3.
    keydown(optionFor(2)[0], "ArrowDown");
    expect(document.activeElement).toBe(optionFor(3)[0]);

    keyup(optionFor(3)[0], "Enter");
    expect(optionFor(3).attr("aria-selected")).toBe("true");
    expect(confirmBtn().prop("disabled")).toBe(false);
  });

  it("ArrowUp from the first row wraps to the last row", () => {
    openTransferPicker("#memberBtnTransferOwner");

    // First row (id 2) is focused on open; ArrowUp wraps to the last row (id 3).
    keydown(optionFor(2)[0], "ArrowUp");
    expect(document.activeElement).toBe(optionFor(3)[0]);
  });

  it("Escape closes the picker and returns focus to a selector-string opener", () => {
    openTransferPicker("#memberBtnTransferOwner");

    keydown(optionFor(2)[0], "Escape");
    expect(isTransferPickerOpen()).toBe(false);
    expect(mount().hasClass("hidden")).toBe(true);
    expect(document.activeElement).toBe(
      document.getElementById("memberBtnTransferOwner"),
    );
  });

  it("Escape returns focus to an HTMLElement opener", () => {
    const openerEl = document.getElementById(
      "utubBtnDelete",
    ) as HTMLButtonElement;
    openTransferPicker(openerEl);

    keydown(optionFor(2)[0], "Escape");
    expect(isTransferPickerOpen()).toBe(false);
    expect(document.activeElement).toBe(openerEl);
  });
});

describe("confirm hand-off (to Step 2's modal)", () => {
  it("hands the chosen member + opener to transferOwnershipShowModal and closes the picker", () => {
    openTransferPicker("#memberBtnTransferOwner");
    optionFor(2).trigger("click");
    confirmBtn().trigger("click");

    expect(vi.mocked(transferOwnershipShowModal)).toHaveBeenCalledWith({
      newOwnerId: 2,
      newOwnerUsername: "alice",
      utubID: 1,
      opener: "#memberBtnTransferOwner",
    });
    expect(isTransferPickerOpen()).toBe(false);
    expect(mount().hasClass("hidden")).toBe(true);
  });

  it("defensive guard: confirm when the staged member vanished resets to the empty-selection state instead of opening the modal", () => {
    openTransferPicker("#memberBtnTransferOwner");
    optionFor(2).trigger("click");

    // The staged member (id 2) is removed from the store mid-pick.
    storeState.members = storeState.members.filter((member) => member.id !== 2);
    confirmBtn().trigger("click");

    expect(vi.mocked(transferOwnershipShowModal)).not.toHaveBeenCalled();
    // Picker stays open, re-rendered, confirm disabled, hint restored.
    expect(isTransferPickerOpen()).toBe(true);
    expect(confirmBtn().prop("disabled")).toBe(true);
    expect(footerMsg().text()).toBe(
      APP_CONFIG.strings.TRANSFER_OWNER_PICK_HINT,
    );
  });

  it("Cancel closes the picker without opening the modal", () => {
    openTransferPicker("#memberBtnTransferOwner");
    optionFor(2).trigger("click");
    mount().find(".transferPickerCancelBtn").trigger("click");

    expect(vi.mocked(transferOwnershipShowModal)).not.toHaveBeenCalled();
    expect(isTransferPickerOpen()).toBe(false);
  });
});

describe("mutual exclusion (DD-6)", () => {
  it("opening the picker tears down the add-member combobox + member-name filter and marks the deck open", () => {
    openTransferPicker("#memberBtnTransferOwner");

    expect(hideAndResetMemberCombobox).toHaveBeenCalledTimes(1);
    expect(closeMemberNameFilter).toHaveBeenCalledTimes(1);
    expect(closeAllMemberRowMenus).toHaveBeenCalledTimes(1);
    expect($("#MemberDeck").hasClass("transfer-picker-open")).toBe(true);
  });

  it("emitting MEMBER_ADD_OPENED while the picker is open closes it", () => {
    openTransferPicker("#memberBtnTransferOwner");
    expect(isTransferPickerOpen()).toBe(true);

    emit(AppEvents.MEMBER_ADD_OPENED);
    expect(isTransferPickerOpen()).toBe(false);
  });

  it("emitting MEMBER_FILTER_OPENED while the picker is open closes it", () => {
    openTransferPicker("#memberBtnTransferOwner");
    emit(AppEvents.MEMBER_FILTER_OPENED);
    expect(isTransferPickerOpen()).toBe(false);
  });

  it("UTUB_SELECTED tears down an open picker", () => {
    openTransferPicker("#memberBtnTransferOwner");
    expect(isTransferPickerOpen()).toBe(true);

    emit(AppEvents.UTUB_SELECTED, {
      utubID: 1,
      utubName: "MyUTub",
      urls: [],
      tags: [],
      members: [],
      utubOwnerID: 1,
      isCurrentUserOwner: true,
      currentUserID: 1,
    });
    expect(isTransferPickerOpen()).toBe(false);
  });

  it("the delete-flow TRANSFER_PICKER_REQUESTED event opens the picker with its opener", () => {
    emit(AppEvents.TRANSFER_PICKER_REQUESTED, { opener: "#utubBtnDelete" });
    expect(isTransferPickerOpen()).toBe(true);
    optionFor(2).trigger("click");
    confirmBtn().trigger("click");
    // The delete trigger threads through to the confirm modal (DD-15).
    expect(vi.mocked(transferOwnershipShowModal)).toHaveBeenCalledWith(
      expect.objectContaining({ opener: "#utubBtnDelete" }),
    );
  });
});
