import {
  emitFormSubmit,
  emitFormCancel,
  emitValidationError,
} from "../btns-forms.js";

vi.mock("../../lib/metrics-client.js", () => ({
  emit: vi.fn(),
  flush: vi.fn().mockResolvedValue(undefined),
  initMetricsClient: vi.fn(),
  resetMetricsClient: vi.fn(),
}));

vi.mock("../visibility.js", () => ({
  isHidden: vi.fn(() => false),
}));
vi.mock("../utubs/create.js", () => ({
  createUTubHideInput: vi.fn(),
}));
vi.mock("../urls/update-name.js", () => ({
  updateUTubNameHideInput: vi.fn(),
}));
vi.mock("../urls/update-description.js", () => ({
  updateUTubDescriptionHideInput: vi.fn(),
}));
vi.mock("../members/create.js", () => ({
  createMemberHideInput: vi.fn(),
}));

describe("btns-forms metrics helpers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("emitFormSubmit", () => {
    it("emits ui_form_submit with trigger and form dimensions for button_click", async () => {
      const { emit } = await import("../../lib/metrics-client.js");

      emitFormSubmit("utub_create", "button_click");

      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith("ui_form_submit", {
        trigger: "button_click",
        form: "utub_create",
      });
    });

    it("emits ui_form_submit with enter_key trigger", async () => {
      const { emit } = await import("../../lib/metrics-client.js");

      emitFormSubmit("url_title_edit", "enter_key");

      expect(emit).toHaveBeenCalledWith("ui_form_submit", {
        trigger: "enter_key",
        form: "url_title_edit",
      });
    });
  });

  describe("emitFormCancel", () => {
    it("emits ui_form_cancel with cancel_button trigger", async () => {
      const { emit } = await import("../../lib/metrics-client.js");

      emitFormCancel("tag_create", "cancel_button");

      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith("ui_form_cancel", {
        trigger: "cancel_button",
        form: "tag_create",
      });
    });

    it("emits ui_form_cancel with escape_key trigger", async () => {
      const { emit } = await import("../../lib/metrics-client.js");

      emitFormCancel("member_invite", "escape_key");

      expect(emit).toHaveBeenCalledWith("ui_form_cancel", {
        trigger: "escape_key",
        form: "member_invite",
      });
    });
  });

  describe("emitValidationError", () => {
    it("emits ui_validation_error with form dimension only", async () => {
      const { emit } = await import("../../lib/metrics-client.js");

      emitValidationError("url_create");

      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith("ui_validation_error", {
        form: "url_create",
      });
    });

    it("emits ui_validation_error for url_string_edit", async () => {
      const { emit } = await import("../../lib/metrics-client.js");

      emitValidationError("url_string_edit");

      expect(emit).toHaveBeenCalledWith("ui_validation_error", {
        form: "url_string_edit",
      });
    });
  });
});
