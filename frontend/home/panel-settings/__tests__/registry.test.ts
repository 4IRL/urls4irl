import { AppEvents, emit } from "../../../lib/event-bus.js";
import {
  _resetRegistryForTests,
  getSections,
  isKnownPanel,
  registerSection,
} from "../registry.js";
import { makeSection } from "./helpers.js";

vi.mock("../../../lib/event-bus.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../../lib/event-bus.js")
  >("../../../lib/event-bus.js");
  return { ...actual, emit: vi.fn() };
});

function changeEmits(): number {
  return vi
    .mocked(emit)
    .mock.calls.filter(
      ([eventName]) => eventName === AppEvents.PANEL_SETTINGS_SECTIONS_CHANGED,
    ).length;
}

describe("panel settings registry", () => {
  beforeEach(() => {
    _resetRegistryForTests();
    vi.mocked(emit).mockClear();
  });

  it("isKnownPanel accepts every panel id and rejects anything else", () => {
    for (const panel of ["utubs", "members", "tags", "urls"]) {
      expect(isKnownPanel(panel)).toBe(true);
    }
    expect(isKnownPanel("nope")).toBe(false);
    expect(isKnownPanel("toString")).toBe(false);
    expect(isKnownPanel(undefined)).toBe(false);
  });

  it("is empty by default", () => {
    expect(getSections("urls")).toEqual([]);
  });

  it("returns sections per panel in registration order", () => {
    const first = makeSection({ id: "first", panel: "urls" });
    const other = makeSection({ id: "other", panel: "tags" });
    const second = makeSection({ id: "second", panel: "urls" });
    registerSection(first);
    registerSection(other);
    registerSection(second);

    expect(getSections("urls")).toEqual([first, second]);
    expect(getSections("tags")).toEqual([other]);
  });

  it("fires the change event on register and on unregister", () => {
    const unregister = registerSection(makeSection());
    expect(changeEmits()).toBe(1);

    unregister();
    expect(changeEmits()).toBe(2);
    expect(getSections("urls")).toEqual([]);
  });

  it("unregister is idempotent and fires only once", () => {
    const unregister = registerSection(makeSection());
    unregister();
    unregister();
    expect(changeEmits()).toBe(2);
  });

  it("a stale unregister after re-registering the same section is a no-op", () => {
    const section = makeSection();
    const staleUnregister = registerSection(section);
    staleUnregister();
    const freshUnregister = registerSection(section);
    vi.mocked(emit).mockClear();

    staleUnregister();

    expect(changeEmits()).toBe(0);
    expect(getSections("urls")).toEqual([section]);
    freshUnregister();
    expect(getSections("urls")).toEqual([]);
  });

  describe("fail-closed validation", () => {
    const invalidSections: Array<
      [string, () => ReturnType<typeof makeSection>]
    > = [
      [
        "scope 'user' without userKind",
        () => makeSection({ scope: "user", panel: "members" }),
      ],
      [
        "scope 'user' with an unknown userKind",
        () =>
          makeSection({
            scope: "user",
            panel: "members",
            userKind: "bogus" as never,
          }),
      ],
      ["an unknown scope", () => makeSection({ scope: "team" as never })],
      ["an empty id", () => makeSection({ id: "" })],
      ["a non-string id", () => makeSection({ id: 5 as never })],
      ["an id containing '|'", () => makeSection({ id: "a|7" })],
      ["an unknown panel", () => makeSection({ panel: "bogus" as never })],
      [
        "scope 'utub' on the utubs panel",
        () => makeSection({ scope: "utub", panel: "utubs" }),
      ],
      [
        "per-utub userKind on the utubs panel",
        () =>
          makeSection({
            scope: "user",
            panel: "utubs",
            userKind: "per-utub",
          }),
      ],
    ];

    it.each(invalidSections)(
      "rejects %s with a no-op unregister and no change event",
      (_label, build) => {
        const unregister = registerSection(build());

        expect(changeEmits()).toBe(0);
        expect(unregister()).toBeUndefined();
        expect(changeEmits()).toBe(0);
        expect(getSections("utubs")).toEqual([]);
        expect(getSections("members")).toEqual([]);
        expect(getSections("urls")).toEqual([]);
      },
    );

    it("rejects a duplicate id", () => {
      const original = makeSection({ id: "dup" });
      registerSection(original);
      vi.mocked(emit).mockClear();

      const unregister = registerSection(
        makeSection({ id: "dup", panel: "tags" }),
      );
      unregister();

      expect(changeEmits()).toBe(0);
      expect(getSections("urls")).toEqual([original]);
      expect(getSections("tags")).toEqual([]);
    });

    it("accepts a global user section on the utubs panel", () => {
      registerSection(
        makeSection({ scope: "user", panel: "utubs", userKind: "global" }),
      );
      expect(getSections("utubs")).toHaveLength(1);
    });

    it("accepts a per-utub user section on the members panel", () => {
      registerSection(
        makeSection({ scope: "user", panel: "members", userKind: "per-utub" }),
      );
      expect(getSections("members")).toHaveLength(1);
    });
  });
});
