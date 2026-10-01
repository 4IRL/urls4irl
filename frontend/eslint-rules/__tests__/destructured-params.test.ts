/**
 * RuleTester suite for the local `u4i/destructured-params` ESLint rule, plus
 * consistency checks on its committed baseline.
 */

import tsParser from "@typescript-eslint/parser";
import { RuleTester } from "eslint";

import baseline from "../destructured-params-baseline.json";
import rule from "../destructured-params.js";

const ruleTester = new RuleTester({ languageOptions: { parser: tsParser } });

const FILENAME = "file.ts";
const ANONYMOUS = "<anonymous>";
const ALLOW_NAMES = ["on", "off", "emit"];

function positional({
  code,
  name,
  count = 2,
}: {
  code: string;
  name: string;
  count?: number;
}): RuleTester.InvalidTestCase {
  return {
    code,
    filename: FILENAME,
    errors: [
      {
        messageId: "positional",
        data: { name, count, key: `${FILENAME}:${name}` },
      },
    ],
  };
}

function booleanParam({
  code,
  name,
}: {
  code: string;
  name: string;
}): RuleTester.InvalidTestCase {
  return {
    code,
    filename: FILENAME,
    errors: [
      { messageId: "booleanParam", data: { name, key: `${FILENAME}:${name}` } },
    ],
  };
}

describe("u4i/destructured-params", () => {
  ruleTester.run("destructured-params", rule, {
    valid: [
      { code: "function f({ a, b }: Args) {}" },
      { code: "function f({ a } = {}) {}" },
      // Only non-destructured params count toward the positional limit.
      { code: "function f({ a }, b) {}" },
      { code: "function f(id: number) {}" },
      { code: "function f() {}" },
      { code: "function f(this: Window, id: number) {}" },
      { code: "items.map((item, index) => item);" },
      { code: '$el.on("click", function (event, data) {});' },
      { code: "new Promise((resolve, reject) => {});" },
      // Inline callbacks stay exempt through type-only wrappers.
      { code: "foo(((a, b) => {}) as Handler);" },
      { code: "foo(((a, b) => {}) satisfies Handler);" },
      { code: "foo(((a, b) => {})!);" },
      // A setter's single param is fixed by the language.
      { code: "class X { set open(value: boolean) {} }" },
      { code: "const obj = { set open(value: boolean) {} };" },
      { code: "function f(a: string, b: string): void;" },
      { code: "declare function f(a, b): void;" },
      {
        code: "function on(name, handler) {}",
        options: [{ allowNames: ALLOW_NAMES }],
      },
      {
        code: "const emit = (name, payload) => {};",
        options: [{ allowNames: ALLOW_NAMES }],
      },
      {
        code: "function f(a, b) {}",
        filename: FILENAME,
        options: [{ baseline: [`${FILENAME}:f`] }],
      },
      {
        code: "function f(open: boolean) {}",
        filename: FILENAME,
        options: [{ baseline: [`${FILENAME}:f`] }],
      },
      {
        code: "function kept({ a, b }) {}",
        filename: FILENAME,
        options: [{ baseline: ["other.ts:gone"] }],
      },
      // Keys resolve against the `root` option, not ESLint's cwd.
      {
        code: "function f(a, b) {}",
        filename: "/repo/frontend/lib/file.ts",
        options: [{ root: "/repo/frontend", baseline: ["lib/file.ts:f"] }],
      },
    ],
    invalid: [
      positional({
        code: "function f(a: string, b: number) {}",
        name: "f",
      }),
      positional({
        code: "const g = (a: string, b: string) => {};",
        name: "g",
      }),
      positional({
        code: "export function h(a, b, c) {}",
        name: "h",
        count: 3,
      }),
      positional({
        code: "const obj = { build(a, b) {} };",
        name: "build",
      }),
      positional({
        code: "class X { m(a, b) {} }",
        name: "m",
      }),
      positional({
        code: "class X { handler = (a, b) => {}; }",
        name: "handler",
      }),
      positional({
        code: "$.fn.offAndOn = function (a, b) {};",
        name: "offAndOn",
      }),
      positional({
        code: "export default function (a, b) {}",
        name: ANONYMOUS,
      }),
      // Computed keys have no stable name.
      positional({
        code: "const obj = { [key](a, b) {} };",
        name: ANONYMOUS,
      }),
      positional({
        code: "class X { [key](a, b) {} }",
        name: ANONYMOUS,
      }),
      positional({
        code: "function toggle(open: boolean, label: string) {}",
        name: "toggle",
      }),
      booleanParam({
        code: "function toggle(open: boolean) {}",
        name: "toggle",
      }),
      booleanParam({
        code: "function toggle(open?: boolean) {}",
        name: "toggle",
      }),
      booleanParam({
        code: "function toggle(open = false) {}",
        name: "toggle",
      }),
      booleanParam({
        code: "class X { constructor(private open: boolean) {} }",
        name: "constructor",
      }),
      {
        ...positional({
          code: "function send(name, payload) {}",
          name: "send",
        }),
        options: [{ allowNames: ALLOW_NAMES }],
      },
      {
        ...positional({ code: "function f(a, b) {}", name: "f" }),
        options: [{ baseline: ["other.ts:f"] }],
      },
      {
        code: "function gone({ a, b }) {}",
        filename: FILENAME,
        options: [{ baseline: [`${FILENAME}:gone`] }],
        errors: [
          { messageId: "staleBaseline", data: { key: `${FILENAME}:gone` } },
        ],
      },
      // An anonymous violator is never grandfathered, and its key is stale.
      {
        code: "export default function (a, b) {}",
        filename: FILENAME,
        options: [{ baseline: [`${FILENAME}:${ANONYMOUS}`] }],
        errors: [
          {
            messageId: "staleBaseline",
            data: { key: `${FILENAME}:${ANONYMOUS}` },
          },
          {
            messageId: "positional",
            data: {
              name: ANONYMOUS,
              count: 2,
              key: `${FILENAME}:${ANONYMOUS}`,
            },
          },
        ],
      },
      // The same key resolved against cwd instead of `root` is not covered.
      {
        code: "function f(a, b) {}",
        filename: "/repo/frontend/lib/file.ts",
        options: [{ root: "/repo", baseline: ["lib/file.ts:f"] }],
        errors: [
          {
            messageId: "positional",
            data: { name: "f", count: 2, key: "frontend/lib/file.ts:f" },
          },
        ],
      },
    ],
  });
});

describe("destructured-params baseline", () => {
  const FRONTEND_PREFIX = "../../";
  const lintedModules = import.meta.glob([
    "../../**/*.ts",
    "!../../node_modules/**",
    "!../../**/__tests__/**",
    "!../../**/*.test.ts",
    "!../../**/*.d.ts",
    "!../../test-setup.ts",
  ]);
  const lintedPaths = new Set(
    Object.keys(lintedModules).map((modulePath) =>
      modulePath.slice(FRONTEND_PREFIX.length),
    ),
  );

  it("only references linted .ts files under frontend/", () => {
    const missingPaths = baseline
      .map((key) => key.slice(0, key.lastIndexOf(":")))
      .filter((keyPath) => !lintedPaths.has(keyPath));
    expect(missingPaths).toEqual([]);
  });

  it("is sorted", () => {
    const sortedKeys = [...baseline].sort((left, right) =>
      left.localeCompare(right, "en"),
    );
    expect(baseline).toEqual(sortedKeys);
  });

  it("has no duplicate keys", () => {
    expect(new Set(baseline).size).toBe(baseline.length);
  });

  it("has no anonymous keys", () => {
    const anonymousKeys = baseline.filter((key) =>
      key.endsWith(`:${ANONYMOUS}`),
    );
    expect(anonymousKeys).toEqual([]);
  });
});
