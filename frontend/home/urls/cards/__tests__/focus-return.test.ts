import {
  armFocusReturnSuppression,
  FOCUS_RETURN_CLASS,
} from "../focus-return.js";

const $ = window.jQuery;

describe("armFocusReturnSuppression", () => {
  let urlRow: JQuery;

  beforeEach(() => {
    document.body.innerHTML = `
      <div class="urlRow" tabindex="-1">
        <span class="goToUrlIcon visible-on-focus"></span>
      </div>
    `;
    urlRow = $(".urlRow");
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("adds the suppression class", () => {
    armFocusReturnSuppression(urlRow);
    expect(urlRow.hasClass(FOCUS_RETURN_CLASS)).toBe(true);
  });

  it("removes the class and the icon's visible-on-focus class on blur", () => {
    armFocusReturnSuppression(urlRow);
    urlRow.trigger("blur");

    expect(urlRow.hasClass(FOCUS_RETURN_CLASS)).toBe(false);
    expect(urlRow.find(".goToUrlIcon").hasClass("visible-on-focus")).toBe(
      false,
    );
  });

  it("is one-shot: a later blur without re-arming does not touch the row", () => {
    armFocusReturnSuppression(urlRow);
    urlRow.trigger("blur");

    urlRow.addClass(FOCUS_RETURN_CLASS);
    urlRow.trigger("blur");

    expect(urlRow.hasClass(FOCUS_RETURN_CLASS)).toBe(true);
  });

  it("re-arms the one-shot blur listener when called twice after a blur", () => {
    armFocusReturnSuppression(urlRow);
    urlRow.trigger("blur");
    expect(urlRow.hasClass(FOCUS_RETURN_CLASS)).toBe(false);

    armFocusReturnSuppression(urlRow);
    expect(urlRow.hasClass(FOCUS_RETURN_CLASS)).toBe(true);
    urlRow.trigger("blur");

    expect(urlRow.hasClass(FOCUS_RETURN_CLASS)).toBe(false);
  });

  it("does not stack listeners when armed twice before a blur", () => {
    const removeSpy = vi.spyOn(urlRow, "removeClass");
    armFocusReturnSuppression(urlRow);
    armFocusReturnSuppression(urlRow);
    urlRow.trigger("blur");

    expect(removeSpy).toHaveBeenCalledTimes(1);
    expect(urlRow.hasClass(FOCUS_RETURN_CLASS)).toBe(false);
  });
});
