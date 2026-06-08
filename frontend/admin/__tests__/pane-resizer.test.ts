/**
 * Unit tests for the metrics-dashboard pane resizer.
 *
 * The resizer drives a single CSS custom property (`--metrics-left-pane`) on
 * `<html>`, persists the chosen percentage to localStorage, and supports both
 * pointer drag and keyboard nudge (Left/Right, Home/End) within a 25–75 clamp.
 *
 * happy-dom does not compute layout, so `getBoundingClientRect()` is stubbed
 * per spec to make pointer math deterministic.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  _resetPaneResizersForTests,
  initPaneResizers,
} from "../pane-resizer.js";

const CSS_VAR = "--metrics-left-pane";
const STORAGE_KEY = "metrics:left-pane-pct";
const DEFAULT_PCT = (1.4 / 2.4) * 100;
const CONTAINER_LEFT = 100;
const CONTAINER_WIDTH = 1000;

/**
 * happy-dom's localStorage proxy is fragile across versions, so each spec runs
 * against a fresh in-memory Map exposed through the standard Storage API.
 */
function installStorageStub(): void {
  const data = new Map<string, string>();
  vi.stubGlobal("localStorage", {
    getItem: (key: string): string | null => data.get(key) ?? null,
    setItem: (key: string, value: string): void => {
      data.set(key, String(value));
    },
    removeItem: (key: string): void => {
      data.delete(key);
    },
    clear: (): void => {
      data.clear();
    },
    key: (index: number): string | null =>
      Array.from(data.keys())[index] ?? null,
    get length(): number {
      return data.size;
    },
  });
}

function buildDashboard({ rows = 1 }: { rows?: number } = {}): void {
  const fragments: string[] = [];
  for (let index = 0; index < rows; index += 1) {
    fragments.push(`
      <div class="content-row" data-row-index="${index}">
        <div class="panel left"></div>
        <div class="content-row__resizer"
             role="separator"
             aria-orientation="vertical"
             aria-valuemin="25"
             aria-valuemax="75"
             tabindex="0"></div>
        <div class="panel right"></div>
      </div>
    `);
  }
  document.body.innerHTML = fragments.join("");

  document
    .querySelectorAll<HTMLElement>(".content-row")
    .forEach((container) => {
      container.getBoundingClientRect = (): DOMRect =>
        ({
          left: CONTAINER_LEFT,
          right: CONTAINER_LEFT + CONTAINER_WIDTH,
          top: 0,
          bottom: 300,
          width: CONTAINER_WIDTH,
          height: 300,
          x: CONTAINER_LEFT,
          y: 0,
          toJSON: () => ({}),
        }) as DOMRect;
    });
}

function dispatchPointer({
  target,
  type,
  clientX,
}: {
  target: HTMLElement;
  type: "pointerdown" | "pointermove" | "pointerup" | "pointercancel";
  clientX: number;
}): void {
  const event = new Event(type, { bubbles: true, cancelable: true });
  Object.defineProperty(event, "button", { value: 0 });
  Object.defineProperty(event, "pointerId", { value: 1 });
  Object.defineProperty(event, "clientX", { value: clientX });
  Object.defineProperty(event, "clientY", { value: 0 });
  target.dispatchEvent(event);
}

function getCssVarPct(): number | null {
  const value = document.documentElement.style.getPropertyValue(CSS_VAR);
  if (value === "") return null;
  return parseFloat(value);
}

function getResizer(): HTMLElement {
  const resizer = document.querySelector<HTMLElement>(".content-row__resizer");
  if (resizer === null) throw new Error("resizer not found");
  return resizer;
}

describe("pane-resizer", () => {
  beforeEach(() => {
    installStorageStub();
    _resetPaneResizersForTests();
    document.body.innerHTML = "";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe("init", () => {
    it("applies the default percentage when nothing is stored", () => {
      buildDashboard();
      initPaneResizers();
      expect(getCssVarPct()).toBeCloseTo(DEFAULT_PCT, 4);
      expect(getResizer().getAttribute("aria-valuenow")).toBe(
        String(Math.round(DEFAULT_PCT)),
      );
    });

    it("restores a previously stored percentage", () => {
      window.localStorage.setItem(STORAGE_KEY, "42");
      buildDashboard();
      initPaneResizers();
      expect(getCssVarPct()).toBeCloseTo(42, 4);
      expect(getResizer().getAttribute("aria-valuenow")).toBe("42");
    });

    it("clamps an out-of-range stored value into 25–75", () => {
      window.localStorage.setItem(STORAGE_KEY, "999");
      buildDashboard();
      initPaneResizers();
      expect(getCssVarPct()).toBeCloseTo(75, 4);
    });

    it("ignores a non-numeric stored value", () => {
      window.localStorage.setItem(STORAGE_KEY, "not-a-number");
      buildDashboard();
      initPaneResizers();
      expect(getCssVarPct()).toBeCloseTo(DEFAULT_PCT, 4);
    });
  });

  describe("pointer drag", () => {
    it("updates the CSS var while dragging and persists on release", () => {
      buildDashboard();
      initPaneResizers();
      const resizer = getResizer();

      dispatchPointer({
        target: resizer,
        type: "pointerdown",
        clientX: CONTAINER_LEFT + 500,
      });
      expect(resizer.classList.contains("is-dragging")).toBe(true);

      dispatchPointer({
        target: resizer,
        type: "pointermove",
        clientX: CONTAINER_LEFT + 600,
      });
      expect(getCssVarPct()).toBeCloseTo(60, 4);

      dispatchPointer({
        target: resizer,
        type: "pointerup",
        clientX: CONTAINER_LEFT + 600,
      });
      expect(resizer.classList.contains("is-dragging")).toBe(false);
      expect(window.localStorage.getItem(STORAGE_KEY)).toBe("60");
    });

    it("clamps to the minimum (25%) when the pointer goes left of the container", () => {
      buildDashboard();
      initPaneResizers();
      const resizer = getResizer();

      dispatchPointer({
        target: resizer,
        type: "pointerdown",
        clientX: CONTAINER_LEFT + 500,
      });
      dispatchPointer({
        target: resizer,
        type: "pointermove",
        clientX: CONTAINER_LEFT - 9999,
      });
      expect(getCssVarPct()).toBeCloseTo(25, 4);
    });

    it("clamps to the maximum (75%) when the pointer goes right of the container", () => {
      buildDashboard();
      initPaneResizers();
      const resizer = getResizer();

      dispatchPointer({
        target: resizer,
        type: "pointerdown",
        clientX: CONTAINER_LEFT + 500,
      });
      dispatchPointer({
        target: resizer,
        type: "pointermove",
        clientX: CONTAINER_LEFT + CONTAINER_WIDTH + 9999,
      });
      expect(getCssVarPct()).toBeCloseTo(75, 4);
    });

    it("ignores non-primary-button pointerdown events", () => {
      buildDashboard();
      initPaneResizers();
      const resizer = getResizer();

      const event = new Event("pointerdown", {
        bubbles: true,
        cancelable: true,
      });
      Object.defineProperty(event, "button", { value: 2 });
      Object.defineProperty(event, "pointerId", { value: 1 });
      Object.defineProperty(event, "clientX", { value: 500 });
      resizer.dispatchEvent(event);

      expect(resizer.classList.contains("is-dragging")).toBe(false);
    });
  });

  describe("keyboard", () => {
    it("nudges left and right by the step amount", () => {
      buildDashboard();
      initPaneResizers();
      const resizer = getResizer();

      resizer.dispatchEvent(
        new KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }),
      );
      expect(getCssVarPct()).toBeCloseTo(DEFAULT_PCT + 2, 4);
      expect(window.localStorage.getItem(STORAGE_KEY)).toBe(
        String(DEFAULT_PCT + 2),
      );

      resizer.dispatchEvent(
        new KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }),
      );
      expect(getCssVarPct()).toBeCloseTo(DEFAULT_PCT, 4);
    });

    it("jumps to the min/max with Home and End", () => {
      buildDashboard();
      initPaneResizers();
      const resizer = getResizer();

      resizer.dispatchEvent(
        new KeyboardEvent("keydown", { key: "Home", bubbles: true }),
      );
      expect(getCssVarPct()).toBeCloseTo(25, 4);

      resizer.dispatchEvent(
        new KeyboardEvent("keydown", { key: "End", bubbles: true }),
      );
      expect(getCssVarPct()).toBeCloseTo(75, 4);
    });

    it("does not call preventDefault for unrelated keys", () => {
      buildDashboard();
      initPaneResizers();
      const resizer = getResizer();

      const event = new KeyboardEvent("keydown", {
        key: "Enter",
        bubbles: true,
        cancelable: true,
      });
      const preventDefaultSpy = vi.spyOn(event, "preventDefault");
      resizer.dispatchEvent(event);
      expect(preventDefaultSpy).not.toHaveBeenCalled();
    });
  });

  describe("multi-row sync", () => {
    it("applies one width across every dashboard tab's content-row", () => {
      buildDashboard({ rows: 3 });
      initPaneResizers();
      const resizers = document.querySelectorAll<HTMLElement>(
        ".content-row__resizer",
      );
      expect(resizers).toHaveLength(3);

      dispatchPointer({
        target: resizers[0],
        type: "pointerdown",
        clientX: CONTAINER_LEFT + 500,
      });
      dispatchPointer({
        target: resizers[0],
        type: "pointermove",
        clientX: CONTAINER_LEFT + 400,
      });
      dispatchPointer({
        target: resizers[0],
        type: "pointerup",
        clientX: CONTAINER_LEFT + 400,
      });

      resizers.forEach((resizer) => {
        expect(resizer.getAttribute("aria-valuenow")).toBe("40");
      });
    });

    it("does not double-bind when initPaneResizers is called twice", () => {
      buildDashboard();
      initPaneResizers();
      initPaneResizers();
      const resizer = getResizer();

      dispatchPointer({
        target: resizer,
        type: "pointerdown",
        clientX: CONTAINER_LEFT + 500,
      });
      dispatchPointer({
        target: resizer,
        type: "pointermove",
        clientX: CONTAINER_LEFT + 700,
      });
      dispatchPointer({
        target: resizer,
        type: "pointerup",
        clientX: CONTAINER_LEFT + 700,
      });
      expect(window.localStorage.getItem(STORAGE_KEY)).toBe("70");
    });
  });
});
