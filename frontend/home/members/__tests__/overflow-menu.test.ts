import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  closeMemberOverflowMenu,
  initMemberOverflowMenu,
  isMemberOverflowMenuOpen,
} from "../overflow-menu.js";
import { AppEvents, emit } from "../../../lib/event-bus.js";
import { $ } from "../../../lib/globals.js";

const FIXTURE = `
  <div class="button-container">
    <button id="memberNameFilterBtn"></button>
    <button id="memberBtnSettings"></button>
    <button id="memberBtnOverflow" aria-haspopup="menu" aria-expanded="false"
      aria-controls="memberOverflowMenu"></button>
    <div id="memberOverflowMenu" class="memberOverflowMenu hidden" role="menu">
      <button id="memberOverflowFilter" class="memberOverflowItem" role="menuitem" tabindex="-1"></button>
      <button id="memberOverflowSettings" class="memberOverflowItem" role="menuitem" tabindex="-1"></button>
    </div>
  </div>
  <button id="outside"></button>
`;

function press({ selector, key }: { selector: string; key: string }) {
  $(selector).trigger($.Event("keydown", { key }));
}

describe("member overflow menu", () => {
  let dispose: () => void;
  let filterClick: ReturnType<typeof vi.fn<() => void>>;
  let settingsClick: ReturnType<typeof vi.fn<() => void>>;

  beforeEach(() => {
    document.body.innerHTML = FIXTURE;
    filterClick = vi.fn<() => void>();
    settingsClick = vi.fn<() => void>();
    $("#memberNameFilterBtn").on("click", filterClick);
    $("#memberBtnSettings").on("click", settingsClick);
    dispose = initMemberOverflowMenu();
  });

  afterEach(() => {
    dispose();
    document.body.innerHTML = "";
  });

  it("opens on click, focuses the first item and sets aria-expanded", () => {
    $("#memberBtnOverflow").trigger("click");

    expect(isMemberOverflowMenuOpen()).toBe(true);
    expect($("#memberBtnOverflow").attr("aria-expanded")).toBe("true");
    expect(document.activeElement?.id).toBe("memberOverflowFilter");
  });

  it("offers only the items whose control is available", () => {
    $("#memberNameFilterBtn").addClass("hidden");
    $("#memberBtnOverflow").trigger("click");

    expect($("#memberOverflowFilter").hasClass("hidden")).toBe(true);
    expect(document.activeElement?.id).toBe("memberOverflowSettings");
  });

  it("stays closed when no control is available", () => {
    $("#memberNameFilterBtn, #memberBtnSettings").addClass("hidden");
    $("#memberBtnOverflow").trigger("click");

    expect(isMemberOverflowMenuOpen()).toBe(false);
  });

  it("a second click closes it and returns focus to the button", () => {
    $("#memberBtnOverflow").trigger("click");
    $("#memberBtnOverflow").trigger("click");

    expect(isMemberOverflowMenuOpen()).toBe(false);
    expect(document.activeElement?.id).toBe("memberBtnOverflow");
  });

  it("ArrowDown and ArrowUp on the button open at the first and last item", () => {
    press({ selector: "#memberBtnOverflow", key: "ArrowUp" });
    expect(document.activeElement?.id).toBe("memberOverflowSettings");
    closeMemberOverflowMenu();
    press({ selector: "#memberBtnOverflow", key: "ArrowDown" });
    expect(document.activeElement?.id).toBe("memberOverflowFilter");
  });

  it("arrow keys wrap and Home/End jump", () => {
    $("#memberBtnOverflow").trigger("click");
    press({ selector: "#memberOverflowFilter", key: "ArrowDown" });
    expect(document.activeElement?.id).toBe("memberOverflowSettings");
    press({ selector: "#memberOverflowSettings", key: "ArrowDown" });
    expect(document.activeElement?.id).toBe("memberOverflowFilter");
    press({ selector: "#memberOverflowFilter", key: "ArrowUp" });
    expect(document.activeElement?.id).toBe("memberOverflowSettings");
    press({ selector: "#memberOverflowSettings", key: "Home" });
    expect(document.activeElement?.id).toBe("memberOverflowFilter");
    press({ selector: "#memberOverflowFilter", key: "End" });
    expect(document.activeElement?.id).toBe("memberOverflowSettings");
  });

  it("Escape closes and returns focus to the button", () => {
    $("#memberBtnOverflow").trigger("click");
    press({ selector: "#memberOverflowFilter", key: "Escape" });

    expect(isMemberOverflowMenuOpen()).toBe(false);
    expect(document.activeElement?.id).toBe("memberBtnOverflow");
  });

  it("Tab closes without stealing focus", () => {
    $("#memberBtnOverflow").trigger("click");
    press({ selector: "#memberOverflowFilter", key: "Tab" });

    expect(isMemberOverflowMenuOpen()).toBe(false);
    expect($("#memberBtnOverflow").attr("aria-expanded")).toBe("false");
  });

  it("an outside click closes; a click inside the menu does not", () => {
    $("#memberBtnOverflow").trigger("click");
    $("#memberOverflowMenu").trigger("click");
    expect(isMemberOverflowMenuOpen()).toBe(true);

    $("#outside").trigger("click");
    expect(isMemberOverflowMenuOpen()).toBe(false);
  });

  it("the filter item closes the menu and clicks the filter control", () => {
    $("#memberBtnOverflow").trigger("click");
    $("#memberOverflowFilter").trigger("click");

    expect(isMemberOverflowMenuOpen()).toBe(false);
    expect(filterClick).toHaveBeenCalledTimes(1);
    expect(settingsClick).not.toHaveBeenCalled();
  });

  it("the settings item closes the menu and clicks the gear", () => {
    $("#memberBtnOverflow").trigger("click");
    $("#memberOverflowSettings").trigger("click");

    expect(isMemberOverflowMenuOpen()).toBe(false);
    expect(settingsClick).toHaveBeenCalledTimes(1);
  });

  it("closes on resize and when the Members deck collapses", () => {
    $("#memberBtnOverflow").trigger("click");
    $(window).trigger("resize");
    expect(isMemberOverflowMenuOpen()).toBe(false);

    $("#memberBtnOverflow").trigger("click");
    emit(AppEvents.DECK_COLLAPSE_CHANGED, { deck: "tags", collapsed: true });
    expect(isMemberOverflowMenuOpen()).toBe(true);
    emit(AppEvents.DECK_COLLAPSE_CHANGED, { deck: "members", collapsed: true });
    expect(isMemberOverflowMenuOpen()).toBe(false);
  });

  it("closes when the left panel collapses or expands", () => {
    $("#memberBtnOverflow").trigger("click");
    expect(isMemberOverflowMenuOpen()).toBe(true);
    emit(AppEvents.LEFT_PANEL_COLLAPSE_CHANGED, { collapsed: true });
    expect(isMemberOverflowMenuOpen()).toBe(false);

    $("#memberBtnOverflow").trigger("click");
    emit(AppEvents.LEFT_PANEL_COLLAPSE_CHANGED, { collapsed: false });
    expect(isMemberOverflowMenuOpen()).toBe(false);
  });

  it("unbinding stops the menu responding", () => {
    dispose();
    $("#memberBtnOverflow").trigger("click");

    expect(isMemberOverflowMenuOpen()).toBe(false);
    dispose = initMemberOverflowMenu();
  });
});
