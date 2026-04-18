import { getInputValue } from "../globals.js";

const $ = window.jQuery;

describe("getInputValue", () => {
  let container: HTMLDivElement;

  beforeEach(() => {
    container = document.createElement("div");
    document.body.appendChild(container);
  });

  afterEach(() => {
    container.remove();
  });

  it("returns value from a string selector", () => {
    const input = document.createElement("input");
    input.id = "test-input";
    input.value = "hello";
    container.appendChild(input);

    expect(getInputValue("#test-input")).toBe("hello");
  });

  it("returns value from a JQuery object", () => {
    const input = document.createElement("input");
    input.value = "world";
    container.appendChild(input);

    const jqInput = $(input);
    expect(getInputValue(jqInput)).toBe("world");
  });

  it("returns empty string when input value is empty", () => {
    const input = document.createElement("input");
    input.id = "empty-input";
    input.value = "";
    container.appendChild(input);

    expect(getInputValue("#empty-input")).toBe("");
  });

  it("returns undefined when selector matches no elements", () => {
    // jQuery .val() returns undefined for empty result sets; callers must pass a valid selector
    expect(getInputValue("#nonexistent")).toBeUndefined();
  });
});
