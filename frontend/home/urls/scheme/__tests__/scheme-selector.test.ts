import { APP_CONFIG } from "../../../../lib/config.js";
import { isCoarsePointer } from "../../../mobile.js";
import {
  getSchemeSelector,
  mountSchemeSelector,
  SCHEME_SELECTOR_DATA_KEY,
} from "../scheme-selector.js";
import type {
  MountSchemeSelectorArgs,
  SchemeSelectorHandle,
} from "../scheme-selector.js";
import type { Mock } from "vitest";

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
}));

const $ = window.jQuery;

const TOGGLE = ".urlSchemeToggle";
const FILTER = "input.urlSchemeFilter";
const OPTIONS = ".urlSchemeOption";

function mountMarkup(): void {
  document.body.innerHTML = `
    <div id="host">
      <div class="text-input-container" id="inputContainer">
        <div class="text-input-inner-container">
          <input class="text-input" type="url" id="urlStringCreate" />
        </div>
        <span class="text-input-error-message"></span>
      </div>
    </div>`;
}

function fireKey({
  target,
  type,
  key,
}: {
  target: Element;
  type: "keydown" | "keyup";
  key: string;
}): KeyboardEvent {
  const event = new KeyboardEvent(type, {
    key,
    bubbles: true,
    cancelable: true,
  });
  target.dispatchEvent(event);
  return event;
}

function pressKey({ target, key }: { target: Element; key: string }): void {
  fireKey({ target, type: "keydown", key });
  fireKey({ target, type: "keyup", key });
}

function rowFor({ scheme }: { scheme: string }): HTMLElement {
  return document.querySelector<HTMLElement>(
    `${OPTIONS}[data-scheme="${scheme}"]`,
  )!;
}

// jQuery 3.7 serves `focusout` from a capture-phase native `blur` listener
// when the environment has no native focusin/focusout (happy-dom), so the
// native event must be a non-bubbling blur to reach the handler.
function fireFocusLeave({
  target,
  relatedTarget,
}: {
  target: HTMLElement;
  relatedTarget: HTMLElement | null;
}): void {
  target.dispatchEvent(new FocusEvent("blur", { relatedTarget }));
}

function isListOpen(): boolean {
  return $(TOGGLE).attr("aria-expanded") === "true";
}

function isToggleExpanded({
  container,
}: {
  container: JQuery<HTMLElement>;
}): boolean {
  return container.find(TOGGLE).attr("aria-expanded") === "true";
}

function toggleControlsListbox({
  container,
}: {
  container: JQuery<HTMLElement>;
}): boolean {
  const listboxId = container.children(".urlSchemeListbox").attr("id");
  return container.find(TOGGLE).attr("aria-controls") === listboxId;
}

interface JQueryInternals {
  _data(
    element: Document,
    key: "events",
  ): Record<string, Array<{ namespace: string }>> | undefined;
}

// Namespaces of the selector's own click handlers currently bound on document.
// jQuery keeps its handler registry in the internal `_data` store.
function schemeSelectorDocumentClickNamespaces(): string[] {
  const internals = $ as unknown as JQueryInternals;
  const clickHandlers = internals._data(document, "events")?.click ?? [];
  return clickHandlers
    .map((handler) => handler.namespace)
    .filter((namespace) => namespace.startsWith("urlSchemeSelector"));
}

function clickOutside(): void {
  document.body.dispatchEvent(new MouseEvent("click", { bubbles: true }));
}

describe("scheme-selector", () => {
  let inputContainer: JQuery<HTMLElement>;
  let urlInput: JQuery<HTMLElement>;
  let onChange: Mock<MountSchemeSelectorArgs["onChange"]>;
  let onEscapeWhenClosed: Mock<() => void>;
  let handle: SchemeSelectorHandle;
  let extraHandles: SchemeSelectorHandle[];

  // A second, independent container + input beside the primary one.
  function mountSecond({ idPrefix }: { idPrefix: string }): {
    secondHandle: SchemeSelectorHandle;
    secondContainer: JQuery<HTMLElement>;
  } {
    const secondContainer = $(
      `<div class="text-input-container" id="inputContainer2">
         <div class="text-input-inner-container">
           <input class="text-input" type="url" id="urlStringEdit" />
         </div>
       </div>`,
    );
    $("#host").append(secondContainer);
    const secondHandle = mountSchemeSelector({
      inputContainer: secondContainer,
      urlInput: secondContainer.find("input"),
      idPrefix,
      onChange: vi.fn<MountSchemeSelectorArgs["onChange"]>(),
    });
    extraHandles.push(secondHandle);
    return { secondHandle, secondContainer };
  }

  // Opens both lists at once. Two things would otherwise close the first list
  // legitimately: a bubbling click on the second toggle (an outside click for
  // the first), and opening the second list focusing its filter input
  // (focus leaving the first container). triggerHandler does not bubble and
  // the coarse-pointer path skips the filter focus.
  function openBothLists({
    secondContainer,
  }: {
    secondContainer: JQuery<HTMLElement>;
  }): void {
    vi.mocked(isCoarsePointer).mockReturnValue(true);
    inputContainer.find(TOGGLE).triggerHandler("click");
    secondContainer.find(TOGGLE).triggerHandler("click");
    vi.mocked(isCoarsePointer).mockReturnValue(false);
  }

  function mount(): SchemeSelectorHandle {
    return mountSchemeSelector({
      inputContainer,
      urlInput,
      idPrefix: "create",
      onChange,
      onEscapeWhenClosed,
    });
  }

  beforeEach(() => {
    vi.mocked(isCoarsePointer).mockReturnValue(false);
    mountMarkup();
    inputContainer = $("#inputContainer");
    urlInput = $("#urlStringCreate");
    onChange = vi.fn<MountSchemeSelectorArgs["onChange"]>();
    onEscapeWhenClosed = vi.fn<() => void>();
    extraHandles = [];
    handle = mount();
  });

  afterEach(() => {
    handle.destroy();
    extraHandles.forEach((extra) => extra.destroy());
    // Destroying every instance must leave no selector click handler behind.
    expect(schemeSelectorDocumentClickNamespaces()).toEqual([]);
    $(document).off("keyup");
    $(document).off("keydown");
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  describe("mount", () => {
    it("builds an accessible toggle showing the default scheme before the URL input", () => {
      const toggle = $(TOGGLE);
      expect(toggle).toHaveLength(1);
      expect(toggle.attr("type")).toBe("button");
      expect(toggle.attr("aria-haspopup")).toBe("listbox");
      expect(toggle.attr("aria-expanded")).toBe("false");
      expect(toggle.attr("aria-label")).toBe(
        APP_CONFIG.strings.URL_SCHEME_TOGGLE_LABEL,
      );
      expect(toggle.text()).toContain(APP_CONFIG.constants.URL_DEFAULT_SCHEME);

      const row = inputContainer.children(".urlSchemeInputRow");
      expect(row).toHaveLength(1);
      expect(row.children().first().is(TOGGLE)).toBe(true);
      expect(
        row.children(".text-input-inner-container").find("#urlStringCreate"),
      ).toHaveLength(1);
      // The toggle precedes the text input in DOM order (tab order).
      expect(row.children().index(toggle)).toBeLessThan(
        row.children().index(row.children(".text-input-inner-container")),
      );
    });

    it("puts the listbox beside the row and the class on the container itself", () => {
      expect(inputContainer.hasClass("urlSchemeSelector")).toBe(true);
      expect($(".urlSchemeSelector")).toHaveLength(1);
      const listbox = inputContainer.children(".urlSchemeListbox");
      expect(listbox).toHaveLength(1);
      expect(inputContainer.children(".urlSchemeInputRow")).toHaveLength(1);
      expect(
        inputContainer.children(".urlSchemeInputRow").find(".urlSchemeListbox"),
      ).toHaveLength(0);
      expect(toggleControlsListbox({ container: inputContainer })).toBe(true);
    });

    it("stores the handle and getSchemeSelector reads it (null when unmounted)", () => {
      expect(getSchemeSelector({ container: inputContainer })).toBe(handle);
      expect(inputContainer.data(SCHEME_SELECTOR_DATA_KEY)).toBe(handle);
      expect(getSchemeSelector({ container: $("<div></div>") })).toBeNull();
    });

    it("re-mounting on the same container is idempotent", () => {
      const second = mount();
      expect($(TOGGLE)).toHaveLength(1);
      expect(inputContainer.children(".urlSchemeInputRow")).toHaveLength(1);
      expect(getSchemeSelector({ container: inputContainer })).toBe(second);
      handle = second;
    });

    it("builds rows lazily on first open", () => {
      expect($(OPTIONS)).toHaveLength(0);
      $(TOGGLE).trigger("click");
      expect($(OPTIONS)).toHaveLength(APP_CONFIG.constants.URL_SCHEMES.length);
    });

    it("still attaches the toggle when the container has no inner input wrapper", () => {
      handle.destroy();
      const bare = $('<div class="text-input-container" id="bare"></div>');
      $("#host").append(bare);
      const bareHandle = mountSchemeSelector({
        inputContainer: bare,
        urlInput,
        idPrefix: "bare",
        onChange,
      });
      extraHandles.push(bareHandle);

      expect(bare.children(".urlSchemeInputRow").find(TOGGLE)).toHaveLength(1);
      expect(bare.children(".urlSchemeListbox")).toHaveLength(1);

      bareHandle.destroy();
      expect(bare.find(TOGGLE)).toHaveLength(0);
      expect(bare.children()).toHaveLength(0);
    });

    it("scrolls the entry row into view only once the list is visible", () => {
      const hiddenAtCall: boolean[] = [];
      const scrollSpy = vi
        .spyOn(Element.prototype, "scrollIntoView")
        .mockImplementation(() => {
          hiddenAtCall.push($(".urlSchemeListbox").hasClass("hidden"));
        });
      try {
        $(TOGGLE).trigger("click");
      } finally {
        scrollSpy.mockRestore();
      }
      expect(hiddenAtCall).toEqual([false]);
    });

    it("renders no hint for a scheme name inherited from Object.prototype", () => {
      const schemes = APP_CONFIG.constants.URL_SCHEMES as string[];
      handle.destroy();
      schemes.push("constructor");
      try {
        handle = mount();
        $(TOGGLE).trigger("click");
        expect(
          rowFor({ scheme: "constructor" }).querySelector(
            ".urlSchemeOptionHint",
          ),
        ).toBeNull();
      } finally {
        schemes.pop();
      }
    });
  });

  describe("multiple instances", () => {
    it("gives instances with different idPrefix distinct listbox ids and aria-controls", () => {
      const { secondContainer } = mountSecond({ idPrefix: "edit" });
      const listboxIds = $(".urlSchemeListbox")
        .toArray()
        .map((listbox) => listbox.id);

      expect(listboxIds).toHaveLength(2);
      expect(new Set(listboxIds).size).toBe(2);
      expect(toggleControlsListbox({ container: inputContainer })).toBe(true);
      expect(toggleControlsListbox({ container: secondContainer })).toBe(true);
    });

    it("gives instances sharing an idPrefix distinct listbox ids and aria-controls", () => {
      const { secondContainer } = mountSecond({ idPrefix: "create" });
      const listboxIds = $(".urlSchemeListbox")
        .toArray()
        .map((listbox) => listbox.id);

      expect(new Set(listboxIds).size).toBe(2);
      expect(toggleControlsListbox({ container: inputContainer })).toBe(true);
      expect(toggleControlsListbox({ container: secondContainer })).toBe(true);
    });

    it("sanitises the idPrefix in ids", () => {
      const { secondContainer } = mountSecond({ idPrefix: "we ird.pre#fix" });
      expect(secondContainer.children(".urlSchemeListbox").attr("id")).toMatch(
        /^[A-Za-z0-9_-]+$/,
      );
    });

    it.each(["create", "edit"])(
      "destroying one instance (idPrefix %s) keeps the other's outside-click handler",
      (secondPrefix) => {
        const { secondHandle, secondContainer } = mountSecond({
          idPrefix: secondPrefix,
        });
        openBothLists({ secondContainer });
        expect(isToggleExpanded({ container: inputContainer })).toBe(true);
        expect(isToggleExpanded({ container: secondContainer })).toBe(true);
        expect(schemeSelectorDocumentClickNamespaces()).toHaveLength(2);

        secondHandle.destroy();
        expect(schemeSelectorDocumentClickNamespaces()).toHaveLength(1);

        clickOutside();
        expect(isToggleExpanded({ container: inputContainer })).toBe(false);
      },
    );

    it("an outside click closing one instance keeps the other's handler", () => {
      const { secondContainer } = mountSecond({ idPrefix: "create" });
      openBothLists({ secondContainer });

      // Closing the second via its own toggle unbinds only its namespace.
      secondContainer.find(TOGGLE).triggerHandler("click");
      expect(isToggleExpanded({ container: secondContainer })).toBe(false);
      expect(schemeSelectorDocumentClickNamespaces()).toHaveLength(1);

      clickOutside();
      expect(isToggleExpanded({ container: inputContainer })).toBe(false);
    });
  });

  describe("stale handle", () => {
    it("destroy() on a handle replaced by a re-mount leaves the new instance intact", () => {
      const stale = handle;
      handle = mount();
      stale.destroy();

      expect(getSchemeSelector({ container: inputContainer })).toBe(handle);
      expect(inputContainer.hasClass("urlSchemeSelector")).toBe(true);
      expect($(TOGGLE)).toHaveLength(1);
      expect(inputContainer.children(".urlSchemeInputRow")).toHaveLength(1);
      $(TOGGLE).trigger("click");
      expect(isListOpen()).toBe(true);
    });

    it("destroy() on a handle whose data key was taken over leaves the owner's state alone", () => {
      const stale = handle;
      // Simulate a newer mount owning the container without going through
      // the idempotent re-mount teardown.
      inputContainer.removeData(SCHEME_SELECTOR_DATA_KEY);
      handle = mount();
      stale.destroy();

      expect(getSchemeSelector({ container: inputContainer })).toBe(handle);
      expect(inputContainer.hasClass("urlSchemeSelector")).toBe(true);
      expect(inputContainer.children(".urlSchemeInputRow")).not.toHaveLength(0);

      // The owner's arrow guard is still bound.
      const switchSpy = vi.fn();
      $(document).on("keyup.switchurls", switchSpy);
      fireKey({ target: urlInput[0], type: "keyup", key: "ArrowDown" });
      expect(switchSpy).not.toHaveBeenCalled();
      $(document).off("keyup.switchurls");

      // And its own toggle (its row was prepended) still opens its list.
      const ownerToggle = inputContainer
        .children(".urlSchemeInputRow")
        .first()
        .find(TOGGLE);
      ownerToggle.trigger("click");
      expect(ownerToggle.attr("aria-expanded")).toBe("true");
    });

    it("destroy() is idempotent", () => {
      handle.destroy();
      expect(() => handle.destroy()).not.toThrow();
      expect(getSchemeSelector({ container: inputContainer })).toBeNull();
    });
  });

  describe("open list", () => {
    beforeEach(() => {
      $(TOGGLE).trigger("click");
    });

    it("sets aria-expanded and renders rows in URL_SCHEMES order", () => {
      expect(isListOpen()).toBe(true);
      const schemes = $(OPTIONS)
        .toArray()
        .map((row) => row.getAttribute("data-scheme"));
      expect(schemes).toEqual([...APP_CONFIG.constants.URL_SCHEMES]);
      $(OPTIONS).each((_, row) => {
        expect(row.getAttribute("role")).toBe("option");
      });
    });

    it("marks only the current scheme aria-selected", () => {
      expect(rowFor({ scheme: "https" }).getAttribute("aria-selected")).toBe(
        "true",
      );
      expect(rowFor({ scheme: "http" }).getAttribute("aria-selected")).toBe(
        "false",
      );
    });

    it("shows a hint pill only for schemes in URL_SCHEME_HINTS", () => {
      const hints = APP_CONFIG.constants.URL_SCHEME_HINTS;
      $(OPTIONS).each((_, row) => {
        const scheme = row.getAttribute("data-scheme") as string;
        const hintEl = row.querySelector(".urlSchemeOptionHint");
        if (scheme in hints) {
          expect(hintEl?.textContent).toBe(hints[scheme]);
        } else {
          expect(hintEl).toBeNull();
        }
      });
    });

    it("labels the filter input", () => {
      const filter = $(FILTER);
      expect(filter.attr("type")).toBe("search");
      expect(filter.attr("aria-label")).toBe(
        APP_CONFIG.strings.URL_SCHEME_FILTER_LABEL,
      );
    });

    it("focuses the filter on a fine pointer", () => {
      expect(document.activeElement).toBe($(FILTER)[0]);
    });
  });

  describe("filtering", () => {
    beforeEach(() => {
      $(TOGGLE).trigger("click");
    });

    function typeFilter({ value }: { value: string }): void {
      $(FILTER).val(value).trigger("input");
    }

    it("hides non-matching rows case-insensitively and announces the count", () => {
      typeFilter({ value: "MA" });
      const visible = $(OPTIONS)
        .not(".hidden")
        .toArray()
        .map((row) => row.getAttribute("data-scheme"));
      const expected = APP_CONFIG.constants.URL_SCHEMES.filter((scheme) =>
        scheme.includes("ma"),
      );
      expect(visible).toEqual(expected);
      expect(expected.length).toBeGreaterThan(1);
      expect($(".urlSchemeMsg").text()).toBe(
        APP_CONFIG.strings.URL_SCHEME_MATCH_MANY.replace(
          "{count}",
          String(expected.length),
        ),
      );
    });

    it("uses the singular message for exactly one match", () => {
      typeFilter({ value: "spotify" });
      expect($(OPTIONS).not(".hidden")).toHaveLength(1);
      expect($(".urlSchemeMsg").text()).toBe(
        APP_CONFIG.strings.URL_SCHEME_MATCH_ONE,
      );
    });

    it("shows the no-matches hint and clears the count message", () => {
      typeFilter({ value: "zzz" });
      expect($(OPTIONS).not(".hidden")).toHaveLength(0);
      const hint = $(".urlSchemeHint");
      expect(hint.hasClass("hidden")).toBe(false);
      expect(hint.text()).toBe(APP_CONFIG.strings.URL_SCHEME_NO_MATCHES);
      expect($(".urlSchemeMsg").text()).toBe("");
    });

    it("clears the filter when the list is reopened", () => {
      typeFilter({ value: "ma" });
      $(TOGGLE).trigger("click");
      $(TOGGLE).trigger("click");
      expect($(FILTER).val()).toBe("");
      expect($(OPTIONS).not(".hidden")).toHaveLength(
        APP_CONFIG.constants.URL_SCHEMES.length,
      );
    });

    it("ArrowDown in the filter moves focus to the first visible row", () => {
      typeFilter({ value: "ma" });
      fireKey({ target: $(FILTER)[0], type: "keydown", key: "ArrowDown" });
      expect(document.activeElement).toBe($(OPTIONS).not(".hidden")[0]);
    });

    it("Enter in the filter selects the first visible row", () => {
      typeFilter({ value: "ma" });
      const firstVisible = $(OPTIONS).not(".hidden").first();
      pressKey({ target: $(FILTER)[0], key: "Enter" });
      expect(onChange).toHaveBeenCalledWith({
        scheme: firstVisible.attr("data-scheme"),
        source: "user",
      });
    });

    it("an Enter keyup on the filter without its own keydown does not select", () => {
      // Opening the list with Enter on the toggle moves focus to the filter
      // mid-press; the trailing keyup must not pick a scheme.
      fireKey({ target: $(FILTER)[0], type: "keyup", key: "Enter" });
      expect(onChange).not.toHaveBeenCalled();
    });

    it("a filter Enter keydown armed before the list closed does not select after reopening", () => {
      fireKey({ target: $(FILTER)[0], type: "keydown", key: "Enter" });
      handle.close();
      $(TOGGLE).trigger("click");
      expect(isListOpen()).toBe(true);

      fireKey({ target: $(FILTER)[0], type: "keyup", key: "Enter" });
      expect(onChange).not.toHaveBeenCalled();
    });

    it("a filter Enter keydown armed before the list closed does not select on a later keyup", () => {
      fireKey({ target: $(FILTER)[0], type: "keydown", key: "Enter" });
      handle.close();
      fireKey({ target: $(FILTER)[0], type: "keyup", key: "Enter" });
      expect(onChange).not.toHaveBeenCalled();
    });

    it("Enter with no matching rows does not select anything", () => {
      typeFilter({ value: "zzz" });
      pressKey({ target: $(FILTER)[0], key: "Enter" });
      expect(onChange).not.toHaveBeenCalled();
      expect(isListOpen()).toBe(true);
    });

    it.each(["(", ".", "[", "\\", "*"])(
      "filter text %s is matched literally: no throw, no rows",
      (value) => {
        expect(() => typeFilter({ value })).not.toThrow();
        expect($(OPTIONS).not(".hidden")).toHaveLength(0);
        expect($(".urlSchemeHint").hasClass("hidden")).toBe(false);
      },
    );

    it("ArrowUp in the filter moves focus to the last visible row", () => {
      fireKey({ target: $(FILTER)[0], type: "keydown", key: "ArrowUp" });
      const rows = $(OPTIONS).not(".hidden");
      expect(document.activeElement).toBe(rows[rows.length - 1]);
    });
  });

  describe("selection", () => {
    beforeEach(() => {
      $(TOGGLE).trigger("click");
    });

    it("clicking a row fires onChange, updates state and closes the list", () => {
      rowFor({ scheme: "mailto" }).click();

      expect(onChange).toHaveBeenCalledTimes(1);
      expect(onChange).toHaveBeenCalledWith({
        scheme: "mailto",
        source: "user",
      });
      expect(handle.getScheme()).toBe("mailto");
      expect(handle.isExplicit()).toBe(true);
      expect(rowFor({ scheme: "mailto" }).getAttribute("aria-selected")).toBe(
        "true",
      );
      expect(rowFor({ scheme: "https" }).getAttribute("aria-selected")).toBe(
        "false",
      );
      expect(isListOpen()).toBe(false);
      expect($(".urlSchemeListbox").hasClass("hidden")).toBe(true);
      expect($(TOGGLE).text()).toContain("mailto");
    });

    it("keyboard Enter on a row selects it", () => {
      const row = rowFor({ scheme: "ftp" });
      row.focus();
      pressKey({ target: row, key: "Enter" });
      expect(handle.getScheme()).toBe("ftp");
      expect(onChange).toHaveBeenCalledWith({ scheme: "ftp", source: "user" });
    });

    it("Enter activation does not submit: the URL input refocus is deferred", () => {
      vi.useFakeTimers();
      const submitSpy = vi.fn();
      // Mirrors url-string.ts: focusing the URL input binds a document keyup.
      urlInput.on("focus.test", () => {
        $(document).on("keyup.updateURLStringFocus", submitSpy);
      });

      const row = rowFor({ scheme: "ftp" });
      row.focus();
      pressKey({ target: row, key: "Enter" });
      expect(submitSpy).not.toHaveBeenCalled();
      expect(document.activeElement).not.toBe(urlInput[0]);

      vi.runAllTimers();
      expect(document.activeElement).toBe(urlInput[0]);
      expect(submitSpy).not.toHaveBeenCalled();
      $(document).off("keyup.updateURLStringFocus");
    });

    it("keyboard Space on a row selects it", () => {
      const row = rowFor({ scheme: "ftp" });
      row.focus();
      pressKey({ target: row, key: " " });
      expect(handle.getScheme()).toBe("ftp");
      expect(onChange).toHaveBeenCalledWith({ scheme: "ftp", source: "user" });
    });

    it("an onChange that destroys the selector arms no refocus", () => {
      vi.useFakeTimers();
      const focusSpy = vi.fn();
      urlInput.on("focus.test", focusSpy);
      onChange.mockImplementation(() => handle.destroy());

      const row = rowFor({ scheme: "ftp" });
      row.focus();
      pressKey({ target: row, key: "Enter" });

      expect(vi.getTimerCount()).toBe(0);
      expect(() => vi.runAllTimers()).not.toThrow();
      expect(focusSpy).not.toHaveBeenCalled();
      expect(document.activeElement).not.toBe(urlInput[0]);
    });

    it("an onChange that closes the selector arms no refocus", () => {
      vi.useFakeTimers();
      const focusSpy = vi.fn();
      urlInput.on("focus.test", focusSpy);
      onChange.mockImplementation(() => handle.close());

      const row = rowFor({ scheme: "ftp" });
      row.focus();
      pressKey({ target: row, key: "Enter" });

      expect(vi.getTimerCount()).toBe(0);
      vi.runAllTimers();
      expect(focusSpy).not.toHaveBeenCalled();
      expect(document.activeElement).not.toBe(urlInput[0]);
    });

    it("cancels the deferred refocus when destroyed first", () => {
      vi.useFakeTimers();
      const focusSpy = vi.fn();
      urlInput.on("focus.test", focusSpy);

      const row = rowFor({ scheme: "ftp" });
      row.focus();
      pressKey({ target: row, key: "Enter" });
      handle.destroy();
      vi.runAllTimers();

      expect(focusSpy).not.toHaveBeenCalled();
    });

    it("cancels the deferred refocus when closed first", () => {
      vi.useFakeTimers();
      const focusSpy = vi.fn();
      urlInput.on("focus.test", focusSpy);

      const row = rowFor({ scheme: "ftp" });
      row.focus();
      pressKey({ target: row, key: "Enter" });
      handle.close();
      vi.runAllTimers();

      expect(focusSpy).not.toHaveBeenCalled();
    });
  });

  describe("key guards", () => {
    beforeEach(() => {
      $(TOGGLE).trigger("click");
    });

    it("ArrowUp/ArrowDown keyup inside the selector never reaches document", () => {
      const switchSpy = vi.fn();
      $(document).on("keyup.switchurls", switchSpy);

      const row = rowFor({ scheme: "http" });
      row.focus();
      fireKey({ target: row, type: "keyup", key: "ArrowDown" });
      fireKey({ target: row, type: "keyup", key: "ArrowUp" });
      fireKey({ target: $(FILTER)[0], type: "keyup", key: "ArrowDown" });
      fireKey({ target: $(FILTER)[0], type: "keyup", key: "ArrowUp" });
      fireKey({ target: urlInput[0], type: "keyup", key: "ArrowDown" });

      expect(switchSpy).not.toHaveBeenCalled();
      $(document).off("keyup.switchurls");
    });

    it("other keyups still bubble to document", () => {
      const keyupSpy = vi.fn();
      $(document).on("keyup.other", keyupSpy);
      fireKey({ target: urlInput[0], type: "keyup", key: "a" });
      expect(keyupSpy).toHaveBeenCalledTimes(1);
      $(document).off("keyup.other");
    });

    it("Escape in the filter closes only the list and returns focus to the toggle", () => {
      const keydownSpy = vi.fn();
      $(document).on("keydown.test", keydownSpy);

      const event = fireKey({
        target: $(FILTER)[0],
        type: "keydown",
        key: "Escape",
      });

      expect(event.defaultPrevented).toBe(true);
      expect(isListOpen()).toBe(false);
      expect(keydownSpy).not.toHaveBeenCalled();
      expect(document.activeElement).toBe($(TOGGLE)[0]);
      expect(onEscapeWhenClosed).not.toHaveBeenCalled();
      $(document).off("keydown.test");
    });

    it("Escape on a row closes only the list", () => {
      const keydownSpy = vi.fn();
      $(document).on("keydown.test", keydownSpy);
      const row = rowFor({ scheme: "http" });
      row.focus();

      fireKey({ target: row, type: "keydown", key: "Escape" });

      expect(isListOpen()).toBe(false);
      expect(keydownSpy).not.toHaveBeenCalled();
      expect(document.activeElement).toBe($(TOGGLE)[0]);
      $(document).off("keydown.test");
    });

    it("Escape on the toggle while OPEN closes only the list (coarse case)", () => {
      const keydownSpy = vi.fn();
      $(document).on("keydown.test", keydownSpy);
      $(TOGGLE)[0].focus();

      fireKey({ target: $(TOGGLE)[0], type: "keydown", key: "Escape" });

      expect(isListOpen()).toBe(false);
      expect(keydownSpy).not.toHaveBeenCalled();
      expect(onEscapeWhenClosed).not.toHaveBeenCalled();
      $(document).off("keydown.test");
    });
  });

  describe("Escape on the closed toggle", () => {
    it("calls onEscapeWhenClosed and does not bubble", () => {
      const keydownSpy = vi.fn();
      $(document).on("keydown.test", keydownSpy);

      fireKey({ target: $(TOGGLE)[0], type: "keydown", key: "Escape" });

      expect(onEscapeWhenClosed).toHaveBeenCalledTimes(1);
      expect(keydownSpy).not.toHaveBeenCalled();
      $(document).off("keydown.test");
    });

    it("bubbles untouched when no callback was supplied", () => {
      handle.destroy();
      handle = mountSchemeSelector({
        inputContainer,
        urlInput,
        idPrefix: "create",
        onChange,
      });
      const keydownSpy = vi.fn();
      $(document).on("keydown.test", keydownSpy);

      fireKey({ target: $(TOGGLE)[0], type: "keydown", key: "Escape" });

      expect(keydownSpy).toHaveBeenCalledTimes(1);
      $(document).off("keydown.test");
    });

    it("ignores non-Escape keys", () => {
      fireKey({ target: $(TOGGLE)[0], type: "keydown", key: "a" });
      expect(onEscapeWhenClosed).not.toHaveBeenCalled();
    });
  });

  describe("outside click", () => {
    it("closes the open list", () => {
      $(TOGGLE).trigger("click");
      expect(isListOpen()).toBe(true);
      document.body.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(isListOpen()).toBe(false);
    });

    it("a click inside the selector (toggle, filter, URL input) keeps it open", () => {
      $(TOGGLE).trigger("click");
      $(FILTER)[0].dispatchEvent(new MouseEvent("click", { bubbles: true }));
      urlInput[0].dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(isListOpen()).toBe(true);
    });

    it("toggle click closes an open list", () => {
      $(TOGGLE).trigger("click");
      $(TOGGLE).trigger("click");
      expect(isListOpen()).toBe(false);
    });

    it("after close(), an outside click has no further effect", () => {
      $(TOGGLE).trigger("click");
      handle.close();
      document.body.dispatchEvent(new MouseEvent("click", { bubbles: true }));
      expect(isListOpen()).toBe(false);
      expect(onChange).not.toHaveBeenCalled();
    });

    it("after destroy(), an outside click throws nothing and does nothing", () => {
      $(TOGGLE).trigger("click");
      handle.destroy();
      expect(() =>
        document.body.dispatchEvent(new MouseEvent("click", { bubbles: true })),
      ).not.toThrow();
      expect(onChange).not.toHaveBeenCalled();
    });

    it("binds a document click handler only while open", () => {
      expect(schemeSelectorDocumentClickNamespaces()).toEqual([]);
      $(TOGGLE).trigger("click");
      expect(schemeSelectorDocumentClickNamespaces()).toHaveLength(1);
      handle.close();
      expect(schemeSelectorDocumentClickNamespaces()).toEqual([]);
    });

    it("leaves no document click handler after destroy() while open", () => {
      $(TOGGLE).trigger("click");
      expect(schemeSelectorDocumentClickNamespaces()).toHaveLength(1);
      handle.destroy();
      expect(schemeSelectorDocumentClickNamespaces()).toEqual([]);
    });

    it("leaves no document click handler after an outside click closes it", () => {
      $(TOGGLE).trigger("click");
      clickOutside();
      expect(schemeSelectorDocumentClickNamespaces()).toEqual([]);
    });

    it("closes when focus moves to an element outside the selector", () => {
      const outside = document.createElement("button");
      document.body.appendChild(outside);
      $(TOGGLE).trigger("click");
      fireFocusLeave({ target: $(FILTER)[0], relatedTarget: outside });
      expect(isListOpen()).toBe(false);
      outside.remove();
    });

    it("stays open when focus moves within the selector", () => {
      $(TOGGLE).trigger("click");
      fireFocusLeave({ target: $(FILTER)[0], relatedTarget: urlInput[0] });
      expect(isListOpen()).toBe(true);
    });

    it("stays open when focus leaves with no next target (window blur)", () => {
      $(TOGGLE).trigger("click");
      fireFocusLeave({ target: $(FILTER)[0], relatedTarget: null });
      expect(isListOpen()).toBe(true);
    });
  });

  describe("handle API", () => {
    it("setScheme without explicit updates the display only", () => {
      handle.setScheme({ scheme: "http", explicit: false });
      expect(handle.getScheme()).toBe("http");
      expect(handle.isExplicit()).toBe(false);
      expect($(TOGGLE).text()).toContain("http");
      expect(onChange).not.toHaveBeenCalled();
    });

    it("setScheme with explicit marks it explicit", () => {
      handle.setScheme({ scheme: "ftp", explicit: true });
      expect(handle.isExplicit()).toBe(true);
    });

    it("setScheme keeps built rows' aria-selected in sync", () => {
      $(TOGGLE).trigger("click");
      handle.setScheme({ scheme: "ssh", explicit: false });
      expect(rowFor({ scheme: "ssh" }).getAttribute("aria-selected")).toBe(
        "true",
      );
      expect(rowFor({ scheme: "https" }).getAttribute("aria-selected")).toBe(
        "false",
      );
    });

    it("reset returns to the default scheme, not explicit, and closes", () => {
      handle.setScheme({ scheme: "ftp", explicit: true });
      $(TOGGLE).trigger("click");
      handle.reset();
      expect(handle.getScheme()).toBe(APP_CONFIG.constants.URL_DEFAULT_SCHEME);
      expect(handle.isExplicit()).toBe(false);
      expect(isListOpen()).toBe(false);
      expect($(TOGGLE).text()).toContain(
        APP_CONFIG.constants.URL_DEFAULT_SCHEME,
      );
    });

    it("announce writes the set-scheme message into a polite hidden region", () => {
      handle.setScheme({ scheme: "mailto", explicit: true, announce: true });
      const region = $(".visually-hidden[aria-live='polite']");
      expect(region).toHaveLength(1);
      expect(region.text()).toBe(
        APP_CONFIG.strings.URL_SCHEME_SET_ANNOUNCE.replace(
          "{scheme}",
          "mailto",
        ),
      );
    });

    it("reset clears the announce region", () => {
      handle.setScheme({ scheme: "mailto", explicit: true, announce: true });
      expect($(".visually-hidden[aria-live='polite']").text()).not.toBe("");
      handle.reset();
      expect($(".visually-hidden[aria-live='polite']").text()).toBe("");
    });

    it("renders a scheme containing markup as text, never as elements", () => {
      handle.setScheme({
        scheme: "<img src=x onerror=1>",
        explicit: false,
        announce: true,
      });
      expect($(TOGGLE).find("img")).toHaveLength(0);
      expect($(TOGGLE).text()).toContain("<img src=x onerror=1>");
      expect($(".urlSchemeAnnounce").find("img")).toHaveLength(0);
    });

    it("does not announce unless asked", () => {
      handle.setScheme({ scheme: "mailto", explicit: true });
      expect($(".visually-hidden[aria-live='polite']").text()).toBe("");
    });

    it("inserts a scheme containing $& literally into the live region", () => {
      handle.setScheme({ scheme: "a$&b", explicit: false, announce: true });
      expect($(".visually-hidden[aria-live='polite']").text()).toBe(
        APP_CONFIG.strings.URL_SCHEME_SET_ANNOUNCE.replace(
          "{scheme}",
          () => "a$&b",
        ),
      );
    });

    it("setInvalid toggles .invalid-field on the toggle", () => {
      handle.setInvalid({ invalid: true });
      expect($(TOGGLE).hasClass("invalid-field")).toBe(true);
      handle.setInvalid({ invalid: false });
      expect($(TOGGLE).hasClass("invalid-field")).toBe(false);
    });

    it("destroy removes the DOM, class and data key and restores the input", () => {
      $(TOGGLE).trigger("click");
      handle.destroy();

      expect($(TOGGLE)).toHaveLength(0);
      expect($(".urlSchemeListbox")).toHaveLength(0);
      expect($(".urlSchemeInputRow")).toHaveLength(0);
      expect($(".urlSchemeAnnounce")).toHaveLength(0);
      expect(inputContainer.hasClass("urlSchemeSelector")).toBe(false);
      expect(getSchemeSelector({ container: inputContainer })).toBeNull();
      // The original inner container is a direct child again, input intact.
      expect(
        inputContainer.children(".text-input-inner-container").find("input"),
      ).toHaveLength(1);
      // Arrow guard is gone too.
      const switchSpy = vi.fn();
      $(document).on("keyup.switchurls", switchSpy);
      fireKey({ target: urlInput[0], type: "keyup", key: "ArrowDown" });
      expect(switchSpy).toHaveBeenCalledTimes(1);
      $(document).off("keyup.switchurls");
    });
  });

  describe("coarse pointer", () => {
    beforeEach(() => {
      vi.mocked(isCoarsePointer).mockReturnValue(true);
    });

    it("opening does not focus the filter", () => {
      $(TOGGLE)[0].focus();
      $(TOGGLE).trigger("click");
      expect(isListOpen()).toBe(true);
      expect(document.activeElement).toBe($(TOGGLE)[0]);
    });

    it("post-select focus goes to the toggle, not the URL input", () => {
      vi.useFakeTimers();
      $(TOGGLE).trigger("click");
      rowFor({ scheme: "ftp" }).click();
      vi.runAllTimers();
      expect(document.activeElement).toBe($(TOGGLE)[0]);
    });
  });

  describe("fine pointer", () => {
    it("post-select focus goes to the URL input", () => {
      vi.useFakeTimers();
      $(TOGGLE).trigger("click");
      rowFor({ scheme: "ftp" }).click();
      vi.runAllTimers();
      expect(document.activeElement).toBe(urlInput[0]);
    });
  });
});
