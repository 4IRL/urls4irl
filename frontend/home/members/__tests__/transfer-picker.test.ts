import {
  closeTransferPicker,
  initTransferPicker,
  isTransferPickerOpen,
  openTransferPicker,
} from "../transfer-picker.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { AppEvents, emit } from "../../../lib/event-bus.js";
import { beginTransferFlow, showTransferConfirmView } from "../transfer.js";
import { closeAllMemberRowMenus } from "../row-menu.js";

// transfer.ts owns the modal lifecycle + confirm view; the picker only renders
// the pick view and hands off. Stub both hand-off points so this suite asserts
// the picker's own behaviour (render / select / filter / continue) in isolation.
vi.mock("../transfer.js", () => ({
  beginTransferFlow: vi.fn(),
  showTransferConfirmView: vi.fn(),
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

// The dedicated transfer modal skeleton (mirrors modals/transferOwnerModal.html).
const BASE_HTML = `
  <div id="MemberDeck">
    <button id="memberBtnTransferOwner" type="button">Transfer</button>
    <button id="utubBtnDelete" type="button">Delete</button>
    <div id="displayMemberWrap"></div>
  </div>
  <div class="modal fade" id="transferOwnerModal">
    <div class="modal-dialog modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header">
          <h4 id="transferOwnerModalTitle" class="modal-title"></h4>
        </div>
        <div class="modal-body">
          <div id="transferOwnerPickView"></div>
          <div id="transferOwnerConfirmView" class="hidden"></div>
        </div>
        <div class="modal-footer">
          <div id="transferOwnerFooterMsg" class="transferPickerMsg"></div>
          <button id="transferOwnerCancel" type="button" class="btn btn-secondary"></button>
          <button id="transferOwnerSubmit" type="button" class="btn btn-success" disabled></button>
        </div>
      </div>
    </div>
  </div>
`;

// Owner (id 1) + two eligible members.
const DEFAULT_MEMBERS: Member[] = [
  { id: 1, username: "owner_u", memberRole: "creator" },
  { id: 2, username: "alice", memberRole: "member" },
  { id: 3, username: "bob", memberRole: "cocreator" },
];

let modalSpy: ReturnType<typeof vi.fn>;

function installModalStub(): void {
  modalSpy = vi.fn(function (this: JQuery) {
    return this;
  });
  ($.fn as unknown as Record<string, unknown>).modal = modalSpy;
}

/** Manually fire the shown/hidden lifecycle events the jsdom stub can't. */
function fireShown(): void {
  $("#transferOwnerModal").trigger("shown.bs.modal");
}
function fireHidden(): void {
  $("#transferOwnerModal").trigger("hidden.bs.modal");
}

function pickView(): JQuery {
  return $("#transferOwnerPickView");
}
function optionRows(): JQuery {
  return pickView().find('.transferPickerOption[role="option"]');
}
function optionFor(memberId: number): JQuery {
  return pickView().find(`#transferPickerOption-${memberId}`);
}
function filterInput(): JQuery {
  return pickView().find(".transferPickerFilterInput");
}
function submitBtn(): JQuery {
  return $("#transferOwnerSubmit");
}
function cancelBtn(): JQuery {
  return $("#transferOwnerCancel");
}
function footerMsg(): JQuery {
  return $("#transferOwnerFooterMsg");
}

/** Dispatch a keydown that reaches the pick view's capture-phase listener. */
function keydown(el: HTMLElement, key: string): void {
  el.dispatchEvent(new KeyboardEvent("keydown", { key, bubbles: true }));
}

function keyup(el: HTMLElement, key: string): void {
  el.dispatchEvent(new KeyboardEvent("keyup", { key, bubbles: true }));
}

beforeAll(() => {
  document.body.innerHTML = BASE_HTML;
  installModalStub();
  initTransferPicker();
});

beforeEach(() => {
  document.body.innerHTML = BASE_HTML;
  installModalStub();
  storeState.activeUTubID = 1;
  storeState.utubOwnerID = 1;
  storeState.members = DEFAULT_MEMBERS.map((member) => ({ ...member }));
  vi.clearAllMocks();
});

afterEach(() => {
  // Complete teardown so the module-level open flag never leaks into the next
  // test (state reset happens in the hidden.bs.modal.transferPicker handler).
  if (isTransferPickerOpen()) {
    closeTransferPicker();
    fireHidden();
  }
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
  });

  it("puts role=listbox on the INNER listbox (not the pick view), role=option/id/aria-selected on rows", () => {
    openTransferPicker("#memberBtnTransferOwner");

    expect(pickView().attr("role")).toBeUndefined();
    expect(pickView().find(".transferPickerListbox").attr("role")).toBe(
      "listbox",
    );
    expect(pickView().find(".transferPickerListbox").attr("aria-label")).toBe(
      APP_CONFIG.strings.TRANSFER_OWNER_LISTBOX_ARIA,
    );
    const first = optionFor(2);
    expect(first.attr("role")).toBe("option");
    expect(first.attr("aria-selected")).toBe("false");
    // Single-select listbox omits aria-multiselectable.
    expect(
      pickView().find(".transferPickerListbox").attr("aria-multiselectable"),
    ).toBeUndefined();
  });

  it("sets the modal title to the picker title and hands off to beginTransferFlow", () => {
    openTransferPicker("#memberBtnTransferOwner");

    expect($("#transferOwnerModalTitle").text()).toBe(
      APP_CONFIG.strings.TRANSFER_OWNER_PICKER_TITLE,
    );
    expect(vi.mocked(beginTransferFlow)).toHaveBeenCalledWith(
      "#memberBtnTransferOwner",
    );
  });

  it("sets roving entry (tabindex 0 first, -1 rest) and focuses the first row on shown; confirm starts disabled with an empty footer (no redundant hint)", () => {
    openTransferPicker("#memberBtnTransferOwner");

    // Roving entry tabindex is set synchronously during render.
    expect(optionFor(2).attr("tabindex")).toBe("0");
    expect(optionFor(3).attr("tabindex")).toBe("-1");
    expect(submitBtn().prop("disabled")).toBe(true);
    // Footer stays empty until a member is staged — the modal title already
    // conveys the task, so a "select a member" hint would be redundant.
    expect(footerMsg().text()).toBe("");

    // Actual DOM focus is deferred to shown.bs.modal.
    fireShown();
    expect(document.activeElement).toBe(optionFor(2)[0]);
  });

  it("renders the empty state (no filter, disabled confirm) when the owner is the only member", () => {
    storeState.members = [
      { id: 1, username: "owner_u", memberRole: "creator" },
    ];
    openTransferPicker("#memberBtnTransferOwner");

    const empty = pickView().find(".transferPickerAllLocked");
    expect(empty.length).toBe(1);
    expect(empty.text()).toBe(APP_CONFIG.strings.TRANSFER_OWNER_NO_ELIGIBLE);
    expect(empty.attr("role")).toBe("status");
    expect(optionRows().length).toBe(0);
    expect(filterInput().length).toBe(0);
    expect(submitBtn().prop("disabled")).toBe(true);
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
    expect(pickView().find(".transferPickerNoMatches").hasClass("hidden")).toBe(
      true,
    );

    filterInput().val("zzz").trigger("input");
    expect(pickView().find(".transferPickerNoMatches").hasClass("hidden")).toBe(
      false,
    );

    filterInput().val("").trigger("input");
    expect(optionFor(2).hasClass("hidden")).toBe(false);
    expect(optionFor(3).hasClass("hidden")).toBe(false);
  });
});

describe("single-select", () => {
  it("selecting a row marks exactly one selected and enables confirm, footer stays empty", () => {
    openTransferPicker("#memberBtnTransferOwner");

    optionFor(2).trigger("click");
    expect(optionFor(2).attr("aria-selected")).toBe("true");
    expect(optionFor(2).hasClass("active")).toBe(true);
    expect(submitBtn().prop("disabled")).toBe(false);
    // The highlighted row conveys the choice; no footer status line.
    expect(footerMsg().text()).toBe("");
  });

  it("selecting a second row deselects the first (single-select)", () => {
    openTransferPicker("#memberBtnTransferOwner");

    optionFor(2).trigger("click");
    optionFor(3).trigger("click");
    expect(optionFor(2).attr("aria-selected")).toBe("false");
    expect(optionFor(2).hasClass("active")).toBe(false);
    expect(optionFor(3).attr("aria-selected")).toBe("true");
    expect(footerMsg().text()).toBe("");
  });
});

describe("keyboard", () => {
  it("ArrowDown roves focus and Enter selects the focused row", () => {
    openTransferPicker("#memberBtnTransferOwner");
    fireShown(); // focus the first row (id 2)

    keydown(optionFor(2)[0], "ArrowDown");
    expect(document.activeElement).toBe(optionFor(3)[0]);

    keyup(optionFor(3)[0], "Enter");
    expect(optionFor(3).attr("aria-selected")).toBe("true");
    expect(submitBtn().prop("disabled")).toBe(false);
  });

  it("ArrowUp from the first row wraps to the last row", () => {
    openTransferPicker("#memberBtnTransferOwner");
    fireShown(); // focus the first row (id 2)

    keydown(optionFor(2)[0], "ArrowUp");
    expect(document.activeElement).toBe(optionFor(3)[0]);
  });
});

describe("cancel / close", () => {
  it("Cancel click hides the modal (Bootstrap teardown resets picker state on hidden)", () => {
    openTransferPicker("#memberBtnTransferOwner");

    cancelBtn().trigger("click");
    expect(modalSpy).toHaveBeenCalledWith("hide");

    // The hidden handler completes teardown.
    fireHidden();
    expect(isTransferPickerOpen()).toBe(false);
    expect(pickView().children().length).toBe(0);
  });

  it("closeTransferPicker hides the modal; the hidden handler drops the open flag", () => {
    openTransferPicker("#memberBtnTransferOwner");
    closeTransferPicker();
    expect(modalSpy).toHaveBeenCalledWith("hide");

    fireHidden();
    expect(isTransferPickerOpen()).toBe(false);
  });
});

describe("continue hand-off (inline pick→confirm)", () => {
  it("Continue hands the chosen member to showTransferConfirmView WITHOUT closing the modal", () => {
    openTransferPicker("#memberBtnTransferOwner");
    optionFor(2).trigger("click");
    submitBtn().trigger("click");

    expect(vi.mocked(showTransferConfirmView)).toHaveBeenCalledWith({
      newOwnerId: 2,
      newOwnerUsername: "alice",
      utubID: 1,
    });
    // Same modal advances — it is NOT hidden.
    expect(modalSpy).not.toHaveBeenCalledWith("hide");
    expect(isTransferPickerOpen()).toBe(true);
  });

  it("defensive guard: Continue when the staged member vanished resets to the empty-selection state instead of advancing", () => {
    openTransferPicker("#memberBtnTransferOwner");
    optionFor(2).trigger("click");

    // The staged member (id 2) is removed from the store mid-pick.
    storeState.members = storeState.members.filter((member) => member.id !== 2);
    submitBtn().trigger("click");

    expect(vi.mocked(showTransferConfirmView)).not.toHaveBeenCalled();
    // Picker stays open, re-rendered, confirm disabled, footer cleared.
    expect(isTransferPickerOpen()).toBe(true);
    expect(submitBtn().prop("disabled")).toBe(true);
    expect(footerMsg().text()).toBe("");
  });
});

describe("event-bus wiring", () => {
  it("UTUB_SELECTED tears down an open modal", () => {
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
    expect(modalSpy).toHaveBeenCalledWith("hide");
    fireHidden();
    expect(isTransferPickerOpen()).toBe(false);
  });

  it("the delete-flow TRANSFER_PICKER_REQUESTED event opens the modal with its opener", () => {
    emit(AppEvents.TRANSFER_PICKER_REQUESTED, { opener: "#utubBtnDelete" });
    expect(isTransferPickerOpen()).toBe(true);
    // The delete trigger threads through to transfer.ts's flow (focus-on-cancel).
    expect(vi.mocked(beginTransferFlow)).toHaveBeenCalledWith("#utubBtnDelete");

    optionFor(2).trigger("click");
    submitBtn().trigger("click");
    expect(vi.mocked(showTransferConfirmView)).toHaveBeenCalledWith(
      expect.objectContaining({ newOwnerId: 2, utubID: 1 }),
    );
  });
});
