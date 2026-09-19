/**
 * Test helper for mocking `frontend/lib/globals.js` in vitest specs that assert
 * on Bootstrap Tooltip lifecycle calls.
 *
 * The ambient `test-setup.ts` Bootstrap mock returns `null` from
 * `Tooltip.getInstance()`, which makes every `getInstance(el)?.hide()` guard a
 * silent no-op — an assertion on it would pass vacuously. Specs that need those
 * guards to be observable replace `lib/globals.js` wholesale (`$` + `jQuery` +
 * `getInputValue` + `bootstrap`) and hand back one shared tooltip instance whose
 * methods are spies.
 *
 * `mockGlobalsWithTooltipInstance()` builds exactly that replacement. It returns
 * the two halves separately — `globalsMock` (only the real `lib/globals.js`
 * exports: `$`, `jQuery`, `getInputValue`, `bootstrap`) and `tooltipInstance`
 * (the spy object both `bootstrap.Tooltip.getInstance()` and
 * `getOrCreateInstance()` hand back) — so the instance never leaks into the
 * mocked module's export surface.
 *
 * Vitest hoists `vi.mock` calls above all ESM imports, so a plain
 * `import { mockGlobalsWithTooltipInstance } from "..."` is unavailable at the
 * time the factory runs. Use `vi.hoisted()` with a dynamic import so both the
 * helper and its result exist before the mocked module is first imported.
 *
 * Canonical usage at the top of a `<module>.test.ts`:
 *
 * ```ts
 * const { tooltipInstance, globalsMock } = await vi.hoisted(async () => {
 *   const { mockGlobalsWithTooltipInstance } = await import(
 *     "<path>/__tests__/helpers/mock-globals.js"
 *   );
 *   return await mockGlobalsWithTooltipInstance();
 * });
 *
 * vi.mock("<relative-path>/lib/globals.js", () => globalsMock);
 *
 * // Inside the test:
 * expect(tooltipInstance.hide).toHaveBeenCalled();
 * ```
 *
 * A spec that only needs the Bootstrap stub to stop no-opping — without
 * asserting on it — destructures `const { globalsMock } = ...` alone.
 *
 * The instance carries the full set of lifecycle spies every consuming spec
 * needs — `enable`/`disable` included, for the submit-button paths in
 * `urls/cards/update-string.ts` — so no spec has to re-declare its own.
 */

import type { Mock } from "vitest";

export type { Mock };

export interface TooltipInstanceMock {
  setContent: Mock;
  show: Mock;
  hide: Mock;
  enable: Mock;
  disable: Mock;
}

export interface GlobalsMocks {
  $: JQueryStatic;
  jQuery: JQueryStatic;
  getInputValue: (input: string | JQuery) => string;
  bootstrap: {
    Tooltip: {
      getInstance: Mock;
      getOrCreateInstance: Mock;
    };
  };
}

export interface GlobalsMockWithTooltipInstance {
  tooltipInstance: TooltipInstanceMock;
  globalsMock: GlobalsMocks;
}

export async function mockGlobalsWithTooltipInstance(): Promise<GlobalsMockWithTooltipInstance> {
  const jquery = (await import("jquery")).default;
  const tooltipInstance: TooltipInstanceMock = {
    setContent: vi.fn(),
    show: vi.fn(),
    hide: vi.fn(),
    enable: vi.fn(),
    disable: vi.fn(),
  };

  return {
    tooltipInstance,
    globalsMock: {
      $: jquery,
      jQuery: jquery,
      getInputValue: (input: string | JQuery) =>
        (typeof input === "string" ? jquery(input) : input).val() as string,
      bootstrap: {
        Tooltip: {
          getInstance: vi.fn(() => tooltipInstance),
          getOrCreateInstance: vi.fn(() => tooltipInstance),
        },
      },
    },
  };
}
