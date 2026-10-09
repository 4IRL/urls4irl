import { isCoarsePointer } from "../../mobile.js";
import {
  bindUTubEditPanelDirtyState,
  isUTubDescriptionDirty,
  isUTubNameDirty,
  syncUTubEditPanelDirtyState,
  unbindUTubEditPanelDirtyState,
} from "../utub-edit-panel-dirty.js";

vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => true),
}));

const $ = window.jQuery;

function mountHeader({ description }: { description: string }): void {
  document.body.innerHTML = `
    <h2 id="URLDeckHeader">My UTub</h2>
    <input id="utubNameUpdate" value="My UTub" />
    <button id="utubNameSubmitBtnUpdate"></button>
    <p id="URLDeckSubheader">${description}</p>
    <input id="utubDescriptionUpdate" value="${description}" />
    <button id="utubDescriptionSubmitBtnUpdate"></button>
  `;
}

describe("UTub edit panel dirty state (mobile)", () => {
  beforeEach(() => {
    vi.mocked(isCoarsePointer).mockReturnValue(true);
    mountHeader({ description: "About" });
  });

  afterEach(() => {
    unbindUTubEditPanelDirtyState();
    document.body.innerHTML = "";
  });

  it("name: trimmed input vs the stored name", () => {
    const input = $("#utubNameUpdate");

    expect(isUTubNameDirty()).toBe(false);
    input.val("  My UTub ");
    expect(isUTubNameDirty()).toBe(false);
    input.val("Renamed");
    expect(isUTubNameDirty()).toBe(true);
  });

  it("description: empty vs empty is unchanged, whitespace-only too", () => {
    mountHeader({ description: "" });
    const input = $("#utubDescriptionUpdate");

    expect(isUTubDescriptionDirty()).toBe(false);
    input.val("   ");
    expect(isUTubDescriptionDirty()).toBe(false);
    input.val("Now has one");
    expect(isUTubDescriptionDirty()).toBe(true);
  });

  it("both checks start disabled with aria-disabled (not native disabled) and the unchanged class", () => {
    bindUTubEditPanelDirtyState();

    ["#utubNameSubmitBtnUpdate", "#utubDescriptionSubmitBtnUpdate"].forEach(
      (selector) => {
        const button = $(selector);
        expect(button.attr("aria-disabled")).toBe("true");
        expect(button.hasClass("unchanged")).toBe(true);
        expect(button.prop("disabled")).toBe(false);
      },
    );
  });

  it("typing enables only the edited field's check and reverting disables it again", () => {
    bindUTubEditPanelDirtyState();
    const name = $("#utubNameSubmitBtnUpdate");
    const description = $("#utubDescriptionSubmitBtnUpdate");

    $("#utubNameUpdate").val("Renamed").trigger("input");
    expect(name.attr("aria-disabled")).toBeUndefined();
    expect(name.hasClass("unchanged")).toBe(false);
    expect(description.attr("aria-disabled")).toBe("true");

    $("#utubNameUpdate").val("My UTub").trigger("input");
    expect(name.attr("aria-disabled")).toBe("true");

    $("#utubDescriptionUpdate").val("Changed").trigger("input");
    expect(description.attr("aria-disabled")).toBeUndefined();
    expect(name.attr("aria-disabled")).toBe("true");
  });

  it("re-derives the state after a save moves the stored value", () => {
    bindUTubEditPanelDirtyState();
    const name = $("#utubNameSubmitBtnUpdate");
    $("#utubNameUpdate").val("Renamed").trigger("input");
    expect(name.attr("aria-disabled")).toBeUndefined();

    // What the success handler does: stored header text catches up to the input,
    // and the in-flight clear strips aria-disabled before the re-sync runs.
    $("#URLDeckHeader").text("Renamed");
    name.removeAttr("aria-disabled");
    syncUTubEditPanelDirtyState();

    expect(name.attr("aria-disabled")).toBe("true");
  });

  it("removes the state and stops reacting after unbind (panel close)", () => {
    bindUTubEditPanelDirtyState();

    unbindUTubEditPanelDirtyState();

    const name = $("#utubNameSubmitBtnUpdate");
    expect(name.attr("aria-disabled")).toBeUndefined();
    expect(name.hasClass("unchanged")).toBe(false);
    $("#utubNameUpdate").val("Renamed").trigger("input");
    syncUTubEditPanelDirtyState();
    expect(name.attr("aria-disabled")).toBeUndefined();
  });

  it("never binds or disables anything on a fine pointer (desktop)", () => {
    vi.mocked(isCoarsePointer).mockReturnValue(false);

    bindUTubEditPanelDirtyState();
    syncUTubEditPanelDirtyState();

    expect($("#utubNameSubmitBtnUpdate").attr("aria-disabled")).toBeUndefined();
    expect(
      $("#utubDescriptionSubmitBtnUpdate").attr("aria-disabled"),
    ).toBeUndefined();
  });
});
