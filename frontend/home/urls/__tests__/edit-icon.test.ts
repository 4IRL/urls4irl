import {
  setupUpdateUTubNameEventListeners,
  updateUTubNameHideInput,
} from "../update-name.js";
import {
  setupUpdateUTubDescriptionEventListeners,
  updateUTubDescriptionHideInput,
} from "../update-description.js";
import { getState } from "../../../store/app-store.js";
import { deselectAllURLs } from "../cards/selection.js";
import { temporarilyHideSearchForEdit } from "../search.js";

vi.mock("../../../lib/globals.js", async () => {
  const jquery = (await import("jquery")).default;
  return {
    $: jquery,
    jQuery: jquery,
    getInputValue: (input: string | JQuery) => {
      const element = typeof input === "string" ? jquery(input) : input;
      return element.val() as string;
    },
  };
});

vi.mock("../../../lib/config.js", () => ({
  APP_CONFIG: {
    routes: {},
    constants: {},
    strings: {},
  },
}));

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../utubs/utils.js", () => ({
  getCurrentUTubName: vi.fn(() => "Test UTub"),
  getAllAccessibleUTubNames: vi.fn(() => []),
  sameNameWarningHideModal: vi.fn(),
}));

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ isCurrentUserOwner: true })),
  setState: vi.fn(),
}));

vi.mock("../../btns-forms.js", () => ({
  showInput: vi.fn(),
  hideInput: vi.fn(),
  highlightInput: vi.fn(),
  hideInputs: vi.fn(),
}));

vi.mock("../search.js", () => ({
  temporarilyHideSearchForEdit: vi.fn(),
  showURLSearchIcon: vi.fn(),
  setURLSearchEventListener: vi.fn(),
  closeURLSearchAndEraseInput: vi.fn(),
  collapseURLSearchInput: vi.fn(),
  hideURLSearchIcon: vi.fn(),
  disableURLSearch: vi.fn(),
  reapplyURLSearchFilter: vi.fn(),
}));

vi.mock("../cards/selection.js", () => ({
  deselectAllURLs: vi.fn(),
}));

vi.mock("../../visibility.js", () => ({
  isHidden: vi.fn(() => false),
}));

vi.mock("../../utubs/create.js", () => ({
  createUTubHideInput: vi.fn(),
}));

vi.mock("../../members/create.js", () => ({
  createMemberHideInput: vi.fn(),
}));

const $ = window.jQuery;

const UTUB_ID = 1;

const EDIT_ICON_HTML = `
  <div class="titleElement">
    <div class="flex-row align-center" id="UTubNameOuterUpdateWrap">
      <div class="flex-row align-center" id="UTubNameUpdateWrap">
        <h2 id="URLDeckHeader">Test UTub</h2>
        <span class="edit-pencil-icon hidden" role="button" tabindex="0"
              aria-label="Edit UTub name">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14"
               fill="currentColor" class="bi bi-pencil" viewBox="0 0 16 16">
            <path d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293zm-9.761 5.175-.106.106-1.528 3.821 3.821-1.528.106-.106A.5.5 0 0 1 5 12.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.468-.325"/>
          </svg>
        </span>
      </div>
      <div class="createDiv flex-row full-width hidden">
        <div class="text-input-container">
          <div class="text-input-inner-container flex-row align-center">
            <input class="text-input" type="text" id="utubNameUpdate" />
            <label class="text-input-label" for="utubName">UTub Name</label>
            <button id="utubNameSubmitBtnUpdate"></button>
            <button id="utubNameCancelBtnUpdate"></button>
          </div>
          <span class="text-input-error-message" id="utubNameUpdate-error"></span>
        </div>
      </div>
    </div>
  </div>

  <div id="UTubDescriptionSubheaderOuterWrap" class="titleElement pad-in-15p dynamic-subheader flex-start align-center">
    <div class="flex-row align-center flex-start" id="UTubDescriptionSubheaderWrap">
      <h5 id="URLDeckSubheader">Test Description</h5>
      <span class="edit-pencil-icon hidden" role="button" tabindex="0"
            aria-label="Edit UTub description">
        <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14"
             fill="currentColor" class="bi bi-pencil" viewBox="0 0 16 16">
          <path d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293zm-9.761 5.175-.106.106-1.528 3.821 3.821-1.528.106-.106A.5.5 0 0 1 5 12.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.468-.325"/>
        </svg>
      </span>
    </div>

    <span id="URLDeckNoDescription" class="hidden">No description</span>

    <div id="SearchURLWrap" class="input-text-holder flex-column hidden">
      <div class="text-input-container">
        <div class="text-input-inner-container">
          <input placeholder="Search URLs" class="text-input search-input" type="text"
                 id="URLContentSearch" name="urlSearch" />
        </div>
      </div>
    </div>

    <button id="URLDeckSubheaderCreateDescription" class="opa-0 height-0"></button>
    <div class="createDiv flex-row full-width hidden" id="UTubDescriptionUpdateWrap">
      <div class="text-input-container" id="UTubDescriptionInnerUpdateWrap">
        <div class="text-input-inner-container flex-row align-center">
          <input class="text-input" type="text" id="utubDescriptionUpdate" />
          <label class="text-input-label" for="utubDescription">UTub Description</label>
          <button id="utubDescriptionSubmitBtnUpdate"></button>
          <button id="utubDescriptionCancelBtnUpdate"></button>
        </div>
        <span class="text-input-error-message" id="utubDescriptionUpdate-error"></span>
      </div>
    </div>
  </div>

  <button id="URLSearchFilterIcon" class="hidden"></button>
  <button id="URLSearchFilterIconClose" class="hidden"></button>
  <button id="urlBtnCreate" class="hidden"></button>
`;

function setupAsOwner(): void {
  vi.mocked(getState).mockReturnValue({
    isCurrentUserOwner: true,
  } as ReturnType<typeof getState>);
}

function setupAsNonOwner(): void {
  vi.mocked(getState).mockReturnValue({
    isCurrentUserOwner: false,
  } as ReturnType<typeof getState>);
}

function namePencilIcon(): JQuery<HTMLElement> {
  return $("#UTubNameUpdateWrap .edit-pencil-icon");
}

function descriptionPencilIcon(): JQuery<HTMLElement> {
  return $("#UTubDescriptionSubheaderWrap .edit-pencil-icon");
}

describe("Edit pencil icon", () => {
  beforeEach(() => {
    document.body.innerHTML = EDIT_ICON_HTML;
    vi.clearAllMocks();
    setupAsOwner();
  });

  afterEach(() => {
    $(window).off();
    document.body.innerHTML = "";
  });

  describe("UTub name header", () => {
    describe("owner", () => {
      beforeEach(() => {
        setupUpdateUTubNameEventListeners(UTUB_ID);
      });

      it("removes hidden class from pencil icon", () => {
        expect(namePencilIcon().hasClass("hidden")).toBe(false);
      });

      it("pencil icon exists as sibling of header", () => {
        expect(namePencilIcon().length).toBe(1);
        expect(namePencilIcon().prev().attr("id")).toBe("URLDeckHeader");
      });

      it("clicking pencil icon calls deselectAllURLs", () => {
        namePencilIcon().trigger("click");

        expect(deselectAllURLs).toHaveBeenCalled();
      });

      it("clicking pencil icon hides the header", () => {
        namePencilIcon().trigger("click");

        expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);
      });

      it("clicking pencil icon calls temporarilyHideSearchForEdit", () => {
        namePencilIcon().trigger("click");

        expect(temporarilyHideSearchForEdit).toHaveBeenCalled();
      });

      it("hides pencil icon when edit form opens via header click", () => {
        $("#URLDeckHeader").trigger("click");

        expect(namePencilIcon().hasClass("hidden")).toBe(true);
      });

      it("hides pencil icon when edit form opens via pencil click", () => {
        namePencilIcon().trigger("click");

        expect(namePencilIcon().hasClass("hidden")).toBe(true);
      });

      it("restores pencil icon when edit form closes via cancel", () => {
        $("#URLDeckHeader").trigger("click");

        $("#utubNameCancelBtnUpdate").trigger("click");

        expect(namePencilIcon().hasClass("hidden")).toBe(false);
      });

      it("restores pencil icon when updateUTubNameHideInput is called directly", () => {
        $("#URLDeckHeader").trigger("click");

        updateUTubNameHideInput();

        expect(namePencilIcon().hasClass("hidden")).toBe(false);
      });

      it("clicking the wrapper gap between header and icon opens edit", () => {
        $("#UTubNameUpdateWrap").trigger("click");

        expect(deselectAllURLs).toHaveBeenCalled();
        expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);
      });

      it("pencil icon has role=button and aria-label", () => {
        expect(namePencilIcon().attr("role")).toBe("button");
        expect(namePencilIcon().attr("aria-label")).toBe("Edit UTub name");
      });

      it("pencil icon has tabindex=0", () => {
        expect(namePencilIcon().attr("tabindex")).toBe("0");
      });

      it("Enter key on pencil icon opens edit", () => {
        const enterEvent = $.Event("keydown", { key: "Enter" });
        namePencilIcon().trigger(enterEvent);

        expect(deselectAllURLs).toHaveBeenCalled();
        expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);
      });

      it("Space key on pencil icon opens edit", () => {
        const spaceEvent = $.Event("keydown", { key: " " });
        namePencilIcon().trigger(spaceEvent);

        expect(deselectAllURLs).toHaveBeenCalled();
        expect($("#URLDeckHeader").hasClass("hidden")).toBe(true);
      });

      it("Space key on pencil icon prevents default scroll", () => {
        const spaceEvent = $.Event("keydown", { key: " " });
        namePencilIcon().trigger(spaceEvent);

        expect(spaceEvent.isDefaultPrevented()).toBe(true);
      });

      it("non-activation keys on pencil icon do not open edit", () => {
        const tabEvent = $.Event("keydown", { key: "Tab" });
        namePencilIcon().trigger(tabEvent);

        expect(deselectAllURLs).not.toHaveBeenCalled();
        expect($("#URLDeckHeader").hasClass("hidden")).toBe(false);
      });

      it("focus returns to pencil icon after keyboard-opened edit is cancelled", () => {
        const focusSpy = vi.spyOn(namePencilIcon()[0], "focus");
        const enterEvent = $.Event("keydown", { key: "Enter" });
        namePencilIcon().trigger(enterEvent);
        $("#utubNameCancelBtnUpdate").trigger("click");

        expect(focusSpy).toHaveBeenCalled();
        focusSpy.mockRestore();
      });

      it("focus returns to pencil icon after keyboard-opened edit calls hideInput", () => {
        const focusSpy = vi.spyOn(namePencilIcon()[0], "focus");
        const enterEvent = $.Event("keydown", { key: "Enter" });
        namePencilIcon().trigger(enterEvent);
        updateUTubNameHideInput();

        expect(focusSpy).toHaveBeenCalled();
        focusSpy.mockRestore();
      });

      it("does not focus pencil icon after mouse-opened edit is cancelled", () => {
        const focusSpy = vi.spyOn(namePencilIcon()[0], "focus");
        namePencilIcon().trigger("click");
        $("#utubNameCancelBtnUpdate").trigger("click");

        expect(focusSpy).not.toHaveBeenCalled();
        focusSpy.mockRestore();
      });
    });

    describe("non-owner", () => {
      beforeEach(() => {
        setupAsNonOwner();
        setupUpdateUTubNameEventListeners(UTUB_ID);
      });

      it("keeps pencil icon hidden", () => {
        expect(namePencilIcon().hasClass("hidden")).toBe(true);
      });

      it("header does not have editable class", () => {
        expect($("#URLDeckHeader").hasClass("editable")).toBe(false);
      });

      it("clicking pencil icon does not call deselectAllURLs", () => {
        namePencilIcon().trigger("click");

        expect(deselectAllURLs).not.toHaveBeenCalled();
      });

      it("Enter key on pencil icon does not open edit", () => {
        const enterEvent = $.Event("keydown", { key: "Enter" });
        namePencilIcon().trigger(enterEvent);

        expect(deselectAllURLs).not.toHaveBeenCalled();
      });
    });
  });

  describe("UTub description header", () => {
    describe("owner", () => {
      beforeEach(() => {
        setupUpdateUTubDescriptionEventListeners(UTUB_ID);
      });

      it("removes hidden class from pencil icon", () => {
        expect(descriptionPencilIcon().hasClass("hidden")).toBe(false);
      });

      it("pencil icon exists as sibling of subheader", () => {
        expect(descriptionPencilIcon().length).toBe(1);
        expect(descriptionPencilIcon().prev().attr("id")).toBe(
          "URLDeckSubheader",
        );
      });

      it("clicking pencil icon calls deselectAllURLs", () => {
        descriptionPencilIcon().trigger("click");

        expect(deselectAllURLs).toHaveBeenCalled();
      });

      it("clicking pencil icon hides the subheader", () => {
        descriptionPencilIcon().trigger("click");

        expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);
      });

      it("clicking pencil icon calls temporarilyHideSearchForEdit", () => {
        descriptionPencilIcon().trigger("click");

        expect(temporarilyHideSearchForEdit).toHaveBeenCalled();
      });

      it("hides pencil icon when edit form opens via subheader click", () => {
        $("#URLDeckSubheader").trigger("click");

        expect(descriptionPencilIcon().hasClass("hidden")).toBe(true);
      });

      it("hides pencil icon when edit form opens via pencil click", () => {
        descriptionPencilIcon().trigger("click");

        expect(descriptionPencilIcon().hasClass("hidden")).toBe(true);
      });

      it("restores pencil icon when edit form closes via cancel", () => {
        $("#URLDeckSubheader").trigger("click");

        $("#utubDescriptionCancelBtnUpdate").trigger("click");

        expect(descriptionPencilIcon().hasClass("hidden")).toBe(false);
      });

      it("restores pencil icon when updateUTubDescriptionHideInput is called", () => {
        $("#URLDeckSubheader").trigger("click");

        updateUTubDescriptionHideInput(UTUB_ID);

        expect(descriptionPencilIcon().hasClass("hidden")).toBe(false);
      });

      it("clicking the wrapper gap between subheader and icon opens edit", () => {
        $("#UTubDescriptionSubheaderWrap").trigger("click");

        expect(deselectAllURLs).toHaveBeenCalled();
        expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);
      });

      it("pencil icon has role=button and aria-label", () => {
        expect(descriptionPencilIcon().attr("role")).toBe("button");
        expect(descriptionPencilIcon().attr("aria-label")).toBe(
          "Edit UTub description",
        );
      });

      it("pencil icon has tabindex=0", () => {
        expect(descriptionPencilIcon().attr("tabindex")).toBe("0");
      });

      it("Enter key on pencil icon opens edit", () => {
        const enterEvent = $.Event("keydown", { key: "Enter" });
        descriptionPencilIcon().trigger(enterEvent);

        expect(deselectAllURLs).toHaveBeenCalled();
        expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);
      });

      it("Space key on pencil icon opens edit", () => {
        const spaceEvent = $.Event("keydown", { key: " " });
        descriptionPencilIcon().trigger(spaceEvent);

        expect(deselectAllURLs).toHaveBeenCalled();
        expect($("#URLDeckSubheader").hasClass("hidden")).toBe(true);
      });

      it("Space key on pencil icon prevents default scroll", () => {
        const spaceEvent = $.Event("keydown", { key: " " });
        descriptionPencilIcon().trigger(spaceEvent);

        expect(spaceEvent.isDefaultPrevented()).toBe(true);
      });

      it("non-activation keys on pencil icon do not open edit", () => {
        const tabEvent = $.Event("keydown", { key: "Tab" });
        descriptionPencilIcon().trigger(tabEvent);

        expect(deselectAllURLs).not.toHaveBeenCalled();
        expect($("#URLDeckSubheader").hasClass("hidden")).toBe(false);
      });

      it("focus returns to pencil icon after keyboard-opened edit is cancelled", () => {
        const focusSpy = vi.spyOn(descriptionPencilIcon()[0], "focus");
        const enterEvent = $.Event("keydown", { key: "Enter" });
        descriptionPencilIcon().trigger(enterEvent);
        $("#utubDescriptionCancelBtnUpdate").trigger("click");

        expect(focusSpy).toHaveBeenCalled();
        focusSpy.mockRestore();
      });

      it("focus returns to pencil icon after keyboard-opened edit calls hideInput", () => {
        const focusSpy = vi.spyOn(descriptionPencilIcon()[0], "focus");
        const enterEvent = $.Event("keydown", { key: "Enter" });
        descriptionPencilIcon().trigger(enterEvent);
        updateUTubDescriptionHideInput(UTUB_ID);

        expect(focusSpy).toHaveBeenCalled();
        focusSpy.mockRestore();
      });

      it("does not focus pencil icon after mouse-opened edit is cancelled", () => {
        const focusSpy = vi.spyOn(descriptionPencilIcon()[0], "focus");
        descriptionPencilIcon().trigger("click");
        $("#utubDescriptionCancelBtnUpdate").trigger("click");

        expect(focusSpy).not.toHaveBeenCalled();
        focusSpy.mockRestore();
      });
    });

    describe("non-owner", () => {
      beforeEach(() => {
        setupAsNonOwner();
        setupUpdateUTubDescriptionEventListeners(UTUB_ID);
      });

      it("keeps pencil icon hidden", () => {
        expect(descriptionPencilIcon().hasClass("hidden")).toBe(true);
      });

      it("subheader does not have editable class", () => {
        expect($("#URLDeckSubheader").hasClass("editable")).toBe(false);
      });

      it("clicking pencil icon does not call deselectAllURLs", () => {
        descriptionPencilIcon().trigger("click");

        expect(deselectAllURLs).not.toHaveBeenCalled();
      });

      it("Enter key on pencil icon does not open edit", () => {
        const enterEvent = $.Event("keydown", { key: "Enter" });
        descriptionPencilIcon().trigger(enterEvent);

        expect(deselectAllURLs).not.toHaveBeenCalled();
      });
    });
  });

  describe("cross-feature interactions", () => {
    beforeEach(() => {
      setupUpdateUTubNameEventListeners(UTUB_ID);
      setupUpdateUTubDescriptionEventListeners(UTUB_ID);
    });

    it("name edit does not hide description pencil icon", () => {
      $("#URLDeckHeader").trigger("click");

      expect(descriptionPencilIcon().hasClass("hidden")).toBe(false);
      expect($("#URLDeckSubheader").hasClass("editable")).toBe(true);
    });

    it("description edit does not hide name pencil icon", () => {
      $("#URLDeckSubheader").trigger("click");

      expect(namePencilIcon().hasClass("hidden")).toBe(false);
      expect($("#URLDeckHeader").hasClass("editable")).toBe(true);
    });

    it("switching from name edit to description edit restores name pencil", () => {
      $("#URLDeckHeader").trigger("click");
      expect(namePencilIcon().hasClass("hidden")).toBe(true);

      $("#URLDeckSubheader").trigger("click");

      expect(namePencilIcon().hasClass("hidden")).toBe(false);
      expect(descriptionPencilIcon().hasClass("hidden")).toBe(true);
    });

    it("switching from description edit to name edit restores description pencil", () => {
      $("#URLDeckSubheader").trigger("click");
      expect(descriptionPencilIcon().hasClass("hidden")).toBe(true);

      namePencilIcon().trigger("click");

      expect(descriptionPencilIcon().hasClass("hidden")).toBe(false);
      expect(namePencilIcon().hasClass("hidden")).toBe(true);
    });

    it("search elements remain present when pencil icons are visible", () => {
      expect($("#SearchURLWrap").length).toBe(1);
      expect($("#URLSearchFilterIcon").length).toBe(1);
      expect(namePencilIcon().hasClass("hidden")).toBe(false);
      expect(descriptionPencilIcon().hasClass("hidden")).toBe(false);
    });

    it("updateUTubNameHideInput does not show pencil for non-owner", () => {
      setupAsNonOwner();
      setupUpdateUTubNameEventListeners(UTUB_ID);
      expect(namePencilIcon().hasClass("hidden")).toBe(true);

      updateUTubNameHideInput();

      expect(namePencilIcon().hasClass("hidden")).toBe(true);
    });

    it("updateUTubDescriptionHideInput does not show pencil for non-owner", () => {
      setupAsNonOwner();
      setupUpdateUTubDescriptionEventListeners(UTUB_ID);
      expect(descriptionPencilIcon().hasClass("hidden")).toBe(true);

      updateUTubDescriptionHideInput(UTUB_ID);

      expect(descriptionPencilIcon().hasClass("hidden")).toBe(true);
    });

    it("re-setup as non-owner hides both pencil icons", () => {
      expect(namePencilIcon().hasClass("hidden")).toBe(false);
      expect(descriptionPencilIcon().hasClass("hidden")).toBe(false);

      setupAsNonOwner();
      setupUpdateUTubNameEventListeners(UTUB_ID);
      setupUpdateUTubDescriptionEventListeners(UTUB_ID);

      expect(namePencilIcon().hasClass("hidden")).toBe(true);
      expect(descriptionPencilIcon().hasClass("hidden")).toBe(true);
    });

    it("re-setup as owner after non-owner shows both pencil icons", () => {
      setupAsNonOwner();
      setupUpdateUTubNameEventListeners(UTUB_ID);
      setupUpdateUTubDescriptionEventListeners(UTUB_ID);
      expect(namePencilIcon().hasClass("hidden")).toBe(true);
      expect(descriptionPencilIcon().hasClass("hidden")).toBe(true);

      setupAsOwner();
      setupUpdateUTubNameEventListeners(UTUB_ID);
      setupUpdateUTubDescriptionEventListeners(UTUB_ID);

      expect(namePencilIcon().hasClass("hidden")).toBe(false);
      expect(descriptionPencilIcon().hasClass("hidden")).toBe(false);
    });

    it("does not focus name pencil when hideInput called without edit open", () => {
      const focusSpy = vi.spyOn(namePencilIcon()[0], "focus");
      updateUTubNameHideInput();

      expect(focusSpy).not.toHaveBeenCalled();
      focusSpy.mockRestore();
    });

    it("does not focus description pencil when hideInput called without edit open", () => {
      const focusSpy = vi.spyOn(descriptionPencilIcon()[0], "focus");
      updateUTubDescriptionHideInput(UTUB_ID);

      expect(focusSpy).not.toHaveBeenCalled();
      focusSpy.mockRestore();
    });
  });
});
