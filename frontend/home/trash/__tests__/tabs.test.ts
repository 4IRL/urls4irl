import { $ } from "../../../lib/globals.js";
import {
  _resetTrashTabsForTests,
  getActiveTrashScope,
  initTrashTabs,
  onTrashTabChanged,
} from "../tabs.js";

const TRASH_HTML = `
  <div id="TrashTablist" role="tablist" aria-label="Trash">
    <button type="button" id="TrashTabUrls" role="tab" aria-selected="true" aria-controls="TrashPanelUrls" tabindex="0">URLs (0)</button>
    <button type="button" id="TrashTabUtubs" role="tab" aria-selected="false" aria-controls="TrashPanelUtubs" tabindex="-1">UTubs (0)</button>
  </div>
  <div role="tabpanel" id="TrashPanelUrls" aria-labelledby="TrashTabUrls" tabindex="0"></div>
  <div role="tabpanel" id="TrashPanelUtubs" aria-labelledby="TrashTabUtubs" tabindex="0" hidden></div>
`;

function el(id: string): HTMLElement {
  return document.getElementById(id) as HTMLElement;
}

function press({ id, key }: { id: string; key: string }): void {
  $(`#${id}`).trigger($.Event("keydown", { key }));
}

describe("trash tabs", () => {
  beforeEach(() => {
    document.body.innerHTML = TRASH_HTML;
    initTrashTabs();
  });

  afterEach(() => {
    _resetTrashTabsForTests();
    document.body.innerHTML = "";
  });

  it("clicking the UTubs tab updates aria-selected, roving tabindex and panel hidden", () => {
    el("TrashTabUtubs").click();

    expect(el("TrashTabUtubs").getAttribute("aria-selected")).toBe("true");
    expect(el("TrashTabUtubs").getAttribute("tabindex")).toBe("0");
    expect(el("TrashTabUrls").getAttribute("aria-selected")).toBe("false");
    expect(el("TrashTabUrls").getAttribute("tabindex")).toBe("-1");
    expect(el("TrashPanelUtubs").hasAttribute("hidden")).toBe(false);
    expect(el("TrashPanelUrls").hasAttribute("hidden")).toBe(true);
    expect(getActiveTrashScope()).toBe("utubs");
  });

  it("mouse activation focuses the newly visible panel", () => {
    el("TrashTabUtubs").click();
    expect(document.activeElement).toBe(el("TrashPanelUtubs"));
  });

  it("ArrowRight activates the next tab and keeps focus on the tab", () => {
    el("TrashTabUrls").focus();
    press({ id: "TrashTabUrls", key: "ArrowRight" });

    expect(el("TrashTabUtubs").getAttribute("aria-selected")).toBe("true");
    expect(el("TrashPanelUtubs").hasAttribute("hidden")).toBe(false);
    expect(document.activeElement).toBe(el("TrashTabUtubs"));
  });

  it("ArrowLeft from the first tab wraps to the last", () => {
    el("TrashTabUrls").focus();
    press({ id: "TrashTabUrls", key: "ArrowLeft" });
    expect(el("TrashTabUtubs").getAttribute("aria-selected")).toBe("true");
  });

  it("ArrowRight from the last tab wraps to the first", () => {
    el("TrashTabUtubs").click();
    el("TrashTabUtubs").focus();
    press({ id: "TrashTabUtubs", key: "ArrowRight" });

    expect(el("TrashTabUrls").getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(el("TrashTabUrls"));
  });

  it("Home and End jump to the first and last tab", () => {
    el("TrashTabUrls").focus();
    press({ id: "TrashTabUrls", key: "End" });
    expect(el("TrashTabUtubs").getAttribute("aria-selected")).toBe("true");

    press({ id: "TrashTabUtubs", key: "Home" });
    expect(el("TrashTabUrls").getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(el("TrashTabUrls"));
  });

  it("an unrecognized key leaves all tab state unchanged", () => {
    el("TrashTabUrls").focus();
    press({ id: "TrashTabUrls", key: "Enter" });

    expect(el("TrashTabUrls").getAttribute("aria-selected")).toBe("true");
    expect(el("TrashPanelUtubs").hasAttribute("hidden")).toBe(true);
  });

  it("notifies registered handlers with the activated scope", () => {
    const handler = vi.fn();
    onTrashTabChanged(handler);

    el("TrashTabUtubs").click();
    expect(handler).toHaveBeenLastCalledWith("utubs");

    el("TrashTabUrls").click();
    expect(handler).toHaveBeenLastCalledWith("urls");
  });
});
