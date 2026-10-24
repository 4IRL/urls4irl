import { APP_CONFIG } from "../../../../lib/config.js";
import { isCoarsePointer } from "../../../mobile.js";
import { mountSchemePicker } from "../scheme-picker.js";
import type {
  MountSchemePickerArgs,
  SchemePickerHandle,
} from "../scheme-picker.js";
import type { Mock } from "vitest";

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
}));

const $ = window.jQuery;

const TOGGLE = ".urlSchemeToggle";
const FILTER = "input.urlSchemeFilter";
const OPTIONS = ".urlSchemeOption";

interface JQueryInternals {
  _data(
    element: Document,
    key: "events",
  ): Record<string, Array<{ namespace: string }>> | undefined;
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

function rowFor({ scheme }: { scheme: string }): HTMLElement {
  return document.querySelector<HTMLElement>(
    `${OPTIONS}[data-scheme="${scheme}"]`,
  )!;
}

function documentClickNamespaces(): string[] {
  const internals = $ as unknown as JQueryInternals;
  const handlers = internals._data(document, "events")?.click ?? [];
  return handlers
    .map((handler) => handler.namespace)
    .filter((namespace) => namespace.startsWith("urlSchemeSelector"));
}

describe("scheme-picker", () => {
  let host: JQuery<HTMLElement>;
  let onSelect: Mock<MountSchemePickerArgs["onSelect"]>;
  let picker: SchemePickerHandle;

  function mount(overrides: Partial<MountSchemePickerArgs> = {}): void {
    picker = mountSchemePicker({
      container: host,
      idPrefix: "test",
      initialScheme: "https",
      accessibleName: ({ scheme }) => `Scheme: ${scheme}`,
      onSelect,
      focusAfterSelect: "toggle",
      ...overrides,
    });
  }

  function isOpen(): boolean {
    return picker.toggle.attr("aria-expanded") === "true";
  }

  beforeEach(() => {
    document.body.innerHTML = '<div id="host"></div>';
    host = $("#host");
    onSelect = vi.fn();
    vi.mocked(isCoarsePointer).mockReturnValue(false);
  });

  afterEach(() => {
    picker.destroy();
    document.body.innerHTML = "";
  });

  it("opens from a toggle click and selects a row, calling onSelect", () => {
    mount();
    picker.toggle.trigger("click");
    expect(isOpen()).toBe(true);
    $(rowFor({ scheme: "http" })).trigger("click");
    expect(isOpen()).toBe(false);
    expect(picker.getScheme()).toBe("http");
    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith({ scheme: "http" });
  });

  it("filters the rows and Enter on the filter selects the first match", () => {
    mount();
    picker.open();
    const filter = $(FILTER);
    filter.val("mailto").trigger("input");
    fireKey({ target: filter[0], type: "keydown", key: "Enter" });
    fireKey({ target: filter[0], type: "keyup", key: "Enter" });
    expect(onSelect).toHaveBeenCalledWith({ scheme: "mailto" });
  });

  it("an outside click closes the list and a click inside keeps it open", () => {
    mount();
    picker.open();
    $(FILTER)[0].dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(isOpen()).toBe(true);
    document.body.dispatchEvent(new MouseEvent("click", { bubbles: true }));
    expect(isOpen()).toBe(false);
  });

  describe("Escape", () => {
    it("closes only the list and does not propagate while open", () => {
      mount();
      const bubbled = vi.fn();
      document.body.addEventListener("keydown", bubbled);
      picker.open();
      fireKey({ target: picker.toggle[0], type: "keydown", key: "Escape" });
      expect(isOpen()).toBe(false);
      expect(bubbled).not.toHaveBeenCalled();
      document.body.removeEventListener("keydown", bubbled);
    });

    it("with the list open, onEscapeWhenClosed is not called", () => {
      const onEscapeWhenClosed = vi.fn();
      mount({ onEscapeWhenClosed });
      picker.open();
      fireKey({ target: picker.toggle[0], type: "keydown", key: "Escape" });
      expect(onEscapeWhenClosed).not.toHaveBeenCalled();
    });

    it("closed with a callback: calls it once and stops propagation", () => {
      const onEscapeWhenClosed = vi.fn();
      mount({ onEscapeWhenClosed });
      const bubbled = vi.fn();
      document.body.addEventListener("keydown", bubbled);
      fireKey({ target: picker.toggle[0], type: "keydown", key: "Escape" });
      expect(onEscapeWhenClosed).toHaveBeenCalledTimes(1);
      expect(bubbled).not.toHaveBeenCalled();
      document.body.removeEventListener("keydown", bubbled);
    });

    it("closed without a callback: the event bubbles", () => {
      mount();
      const bubbled = vi.fn();
      document.body.addEventListener("keydown", bubbled);
      fireKey({ target: picker.toggle[0], type: "keydown", key: "Escape" });
      expect(bubbled).toHaveBeenCalledTimes(1);
      document.body.removeEventListener("keydown", bubbled);
    });
  });

  describe("read-only", () => {
    it("is focusable, aria-disabled, and never opens", () => {
      mount();
      picker.setReadOnly({ readOnly: true });
      expect(picker.toggle.attr("aria-disabled")).toBe("true");
      expect(picker.toggle.prop("disabled")).toBe(false);
      picker.toggle.trigger("click");
      expect(isOpen()).toBe(false);
    });

    it("closes an open list and re-enables when cleared", () => {
      mount();
      picker.open();
      picker.setReadOnly({ readOnly: true });
      expect(isOpen()).toBe(false);
      picker.setReadOnly({ readOnly: false });
      expect(picker.toggle.attr("aria-disabled")).toBeUndefined();
      picker.toggle.trigger("click");
      expect(isOpen()).toBe(true);
    });
  });

  describe("destroy", () => {
    it("removes the document click handler and the DOM", () => {
      mount();
      picker.open();
      expect(documentClickNamespaces()).toHaveLength(1);
      picker.destroy();
      expect(documentClickNamespaces()).toEqual([]);
      expect(document.querySelector(TOGGLE)).toBeNull();
    });

    it("unbinds the toggle click listener", () => {
      mount();
      picker.destroy();
      picker.toggle.trigger("click");
      expect(isOpen()).toBe(false);
    });
  });

  describe("focusAfterSelect", () => {
    it("'toggle' leaves focus on the toggle after a selection", () => {
      mount({ focusAfterSelect: "toggle" });
      picker.open();
      $(rowFor({ scheme: "http" })).trigger("click");
      expect(document.activeElement).toBe(picker.toggle[0]);
    });

    it("a function option is called once per selection", () => {
      const focusAfterSelect = vi.fn();
      mount({ focusAfterSelect });
      picker.open();
      $(rowFor({ scheme: "http" })).trigger("click");
      picker.open();
      $(rowFor({ scheme: "mailto" })).trigger("click");
      expect(focusAfterSelect).toHaveBeenCalledTimes(2);
    });
  });

  it("mounts no live region and a selection writes to none", () => {
    mount();
    expect(host.find("[aria-live]").filter(".urlSchemeAnnounce")).toHaveLength(
      0,
    );
    picker.open();
    $(rowFor({ scheme: "http" })).trigger("click");
    expect(host.find(".urlSchemeAnnounce")).toHaveLength(0);
    expect(host.find(".urlSchemeMsg").text()).toBe("");
  });

  describe("accessible name", () => {
    it("labelledBy: name includes the host label and tracks the scheme", () => {
      document.body.insertAdjacentHTML(
        "beforeend",
        '<span id="hostLabel">Default scheme</span>',
      );
      mount({ labelledBy: "hostLabel", accessibleName: undefined });
      const nameFor = (): string =>
        picker.toggle
          .attr("aria-labelledby")!
          .split(" ")
          .map((id) => document.getElementById(id)!.textContent)
          .join(" ");
      expect(picker.toggle.attr("aria-label")).toBeUndefined();
      expect(nameFor()).toBe("Default scheme https");
      picker.setScheme({ scheme: "mailto" });
      expect(nameFor()).toBe("Default scheme mailto");
      picker.open();
      $(rowFor({ scheme: "http" })).trigger("click");
      expect(nameFor()).toBe("Default scheme http");
      document.getElementById("hostLabel")!.remove();
    });

    it("accessibleName: aria-label follows mount, setScheme and selection", () => {
      mount();
      expect(picker.toggle.attr("aria-label")).toBe("Scheme: https");
      expect(picker.toggle.attr("aria-labelledby")).toBeUndefined();
      picker.setScheme({ scheme: "mailto" });
      expect(picker.toggle.attr("aria-label")).toBe("Scheme: mailto");
      picker.open();
      $(rowFor({ scheme: "http" })).trigger("click");
      expect(picker.toggle.attr("aria-label")).toBe("Scheme: http");
      expect(picker.toggle.text()).toContain("http");
    });

    it("throws when both forms are passed", () => {
      expect(() =>
        mountSchemePicker({
          idPrefix: "both",
          initialScheme: "https",
          labelledBy: "x",
          accessibleName: () => "x",
          onSelect,
          focusAfterSelect: "toggle",
        }),
      ).toThrow();
      // afterEach destroys `picker`; give it something valid.
      mount();
    });
  });

  it("setInvalid toggles invalid-field and toggleId sets the id", () => {
    mount({ toggleId: "urlsSettingsDefaultScheme" });
    expect(picker.toggle.attr("id")).toBe("urlsSettingsDefaultScheme");
    picker.setInvalid({ invalid: true });
    expect(picker.toggle.hasClass("invalid-field")).toBe(true);
    picker.setInvalid({ invalid: false });
    expect(picker.toggle.hasClass("invalid-field")).toBe(false);
  });

  it("selection runs close, then focusAfterSelect, then onSelect", () => {
    const order: string[] = [];
    mount({
      focusAfterSelect: () => {
        order.push(`focus:open=${isOpen()}`);
      },
      onSelect: () => {
        order.push("onSelect");
      },
    });
    picker.open();
    $(rowFor({ scheme: "http" })).trigger("click");
    expect(order).toEqual(["focus:open=false", "onSelect"]);
  });

  it("exposes toggle/listbox without attaching them when container is omitted", () => {
    picker = mountSchemePicker({
      idPrefix: "detached",
      initialScheme: "https",
      onSelect,
      focusAfterSelect: "toggle",
    });
    expect(picker.toggle).toHaveLength(1);
    expect(picker.listbox).toHaveLength(1);
    expect(document.querySelector(TOGGLE)).toBeNull();
    expect(picker.toggle.attr("aria-controls")).toBe(picker.listbox.attr("id"));
    expect(APP_CONFIG.constants.URL_SCHEMES).toContain("https");
  });
});
