import {
  highlightInput,
  hideInputs,
  makeTextInput,
  makeUpdateButton,
  makeSubmitButton,
  makeCancelButton,
  handleFocus,
  handleBlur,
  initBtnsForms,
  disable,
  enable,
} from "../btns-forms.js";

const mockCreateUTubHideInput = vi.fn();
const mockUpdateUTubNameHideInput = vi.fn();
const mockUpdateUTubDescriptionHideInput = vi.fn();
const mockCreateMemberHideInput = vi.fn();
const mockIsHidden = vi.fn();

vi.mock("../visibility.js", () => ({
  isHidden: (...args: unknown[]) => mockIsHidden(...args),
}));
vi.mock("../utubs/create.js", () => ({
  createUTubHideInput: (...args: unknown[]) => mockCreateUTubHideInput(...args),
}));
vi.mock("../urls/update-name.js", () => ({
  updateUTubNameHideInput: (...args: unknown[]) =>
    mockUpdateUTubNameHideInput(...args),
}));
vi.mock("../urls/update-description.js", () => ({
  updateUTubDescriptionHideInput: (...args: unknown[]) =>
    mockUpdateUTubDescriptionHideInput(...args),
}));
vi.mock("../members/create.js", () => ({
  createMemberHideInput: (...args: unknown[]) =>
    mockCreateMemberHideInput(...args),
}));

const $ = window.jQuery;

const BTNS_FORMS_HTML = `
  <div id="createUTubWrap" class="createDiv" style="display:block;">
    <input class="text-input" type="text" name="testInput" />
    <label class="text-input-label" for="testInput">Label</label>
  </div>
  <div id="URLDeckHeader" style="display:block;">URL Deck Header</div>
  <div id="URLDeckSubheader" style="display:block;">Description</div>
  <div id="displayMemberWrap" style="display:block;">Members</div>
  <form id="testForm"><input type="text" /></form>
  <div class="createDiv" style="display:none;">
    <input id="hiddenInput" type="text" />
  </div>
`;

describe("btns-forms", () => {
  beforeEach(() => {
    document.body.innerHTML = BTNS_FORMS_HTML;
    vi.clearAllMocks();
  });

  describe("highlightInput", () => {
    it("focuses and selects text in an input with a value", () => {
      const input = $<HTMLInputElement>(".text-input").first();
      input.val("hello");

      const focusSpy = vi.spyOn(input[0], "focus");
      const selectionSpy = vi.spyOn(input[0], "setSelectionRange");

      highlightInput(input);

      expect(focusSpy).toHaveBeenCalled();
      expect(selectionSpy).toHaveBeenCalledWith(0, 5);
    });

    it("focuses an empty input without calling setSelectionRange", () => {
      const input = $<HTMLInputElement>(".text-input").first();
      input.val("");

      const selectionSpy = vi.spyOn(input[0], "setSelectionRange");

      highlightInput(input);

      expect(selectionSpy).not.toHaveBeenCalled();
    });
  });

  describe("hideInputs", () => {
    it("calls hide functions for visible inputs", () => {
      // createUTubWrap is NOT hidden => call createUTubHideInput
      mockIsHidden.mockImplementation((el: JQuery<HTMLElement>) => {
        const id = $(el).attr("id");
        if (id === "createUTubWrap") return false;
        if (id === "URLDeckHeader") return true;
        if (id === "URLDeckSubheader") return true;
        if (id === "displayMemberWrap") return true;
        return false;
      });

      hideInputs();

      expect(mockCreateUTubHideInput).toHaveBeenCalled();
      expect(mockUpdateUTubNameHideInput).toHaveBeenCalled();
      expect(mockCreateMemberHideInput).toHaveBeenCalled();
    });

    it("does not call hide functions when inputs are already hidden", () => {
      mockIsHidden.mockImplementation((el: JQuery<HTMLElement>) => {
        const id = $(el).attr("id");
        if (id === "createUTubWrap") return true;
        if (id === "URLDeckHeader") return false;
        if (id === "URLDeckSubheader") return false;
        if (id === "displayMemberWrap") return false;
        return false;
      });

      hideInputs();

      expect(mockCreateUTubHideInput).not.toHaveBeenCalled();
      expect(mockUpdateUTubNameHideInput).not.toHaveBeenCalled();
      expect(mockCreateMemberHideInput).not.toHaveBeenCalled();
    });
  });

  describe("makeTextInput", () => {
    it("creates a text input element with correct classes and attributes", () => {
      const result = makeTextInput("testField", "Create");

      const input = result.find("input.text-input");
      expect(input.length).toBe(1);
      expect(input.attr("type")).toBe("text");
      expect(input.attr("name")).toBe("testField");
      expect(input.hasClass("testFieldCreate")).toBe(true);
    });

    it("uses custom input type when provided", () => {
      const result = makeTextInput("emailField", "Update", "email");

      const input = result.find("input.text-input");
      expect(input.attr("type")).toBe("email");
    });
  });

  describe("makeUpdateButton", () => {
    it("creates a button with an SVG pencil icon at specified size", () => {
      const btn = makeUpdateButton("20");

      expect(btn.is("button")).toBe(true);
      expect(btn.hasClass("mx-1")).toBe(true);
      expect(btn.find("svg.updateIcon").length).toBe(1);
      expect(btn.find("svg").attr("width")).toBe("20");
    });
  });

  describe("makeSubmitButton", () => {
    it("creates a button with green-clickable class", () => {
      const btn = makeSubmitButton("16");

      expect(btn.is("button")).toBe(true);
      expect(btn.hasClass("green-clickable")).toBe(true);
      expect(btn.find("svg").attr("width")).toBe("16");
    });
  });

  describe("makeCancelButton", () => {
    it("creates a button with cancel SVG", () => {
      const btn = makeCancelButton("18");

      expect(btn.is("button")).toBe(true);
      expect(btn.find("svg.cancelButton").length).toBe(1);
      expect(btn.find("svg").attr("width")).toBe("18");
    });
  });

  describe("handleFocus", () => {
    it("repositions label on focus", () => {
      const input = document.querySelector(".text-input") as HTMLInputElement;
      const label = input.nextElementSibling as HTMLElement;

      const fakeEvent = { target: input } as unknown as JQuery.TriggeredEvent;
      handleFocus(fakeEvent);

      expect(label.style.top).toBe("0px");
      expect(label.style.fontSize).toBe("14px");
    });
  });

  describe("handleBlur", () => {
    it("resets label position when input is empty", () => {
      const input = document.querySelector(".text-input") as HTMLInputElement;
      input.value = "";
      const label = input.nextElementSibling as HTMLElement;

      const fakeEvent = { target: input } as unknown as JQuery.TriggeredEvent;
      handleBlur(fakeEvent);

      expect(label.style.top).toBe("50%");
      expect(label.style.fontSize).toBe("16px");
    });

    it("does not reset label when input has a value", () => {
      const input = document.querySelector(".text-input") as HTMLInputElement;
      input.value = "some text";
      const label = input.nextElementSibling as HTMLElement;
      label.style.top = "0px";

      const fakeEvent = { target: input } as unknown as JQuery.TriggeredEvent;
      handleBlur(fakeEvent);

      expect(label.style.top).toBe("0px");
    });
  });

  describe("initBtnsForms", () => {
    it("prevents form submission from refreshing the page", () => {
      initBtnsForms();

      const form = document.querySelector("#testForm") as HTMLFormElement;
      const event = new Event("submit", { cancelable: true });
      form.dispatchEvent(event);

      expect($("#testForm").length).toBe(1);
    });
  });

  describe("disable / enable", () => {
    it("disable sets the disabled prop to true", () => {
      const btn = $(document.createElement("button"));
      document.body.appendChild(btn[0]);

      disable(btn);

      expect(btn.prop("disabled")).toBe(true);
    });

    it("enable sets the disabled prop to false", () => {
      const btn = $(document.createElement("button"));
      btn.prop("disabled", true);
      document.body.appendChild(btn[0]);

      enable(btn);

      expect(btn.prop("disabled")).toBe(false);
    });
  });
});
