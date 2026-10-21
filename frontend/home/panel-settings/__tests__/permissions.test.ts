import { getState, resetStore, setState } from "../../../store/app-store.js";
import { canWriteSection } from "../permissions.js";
import { makeSection } from "./helpers.js";

describe("canWriteSection", () => {
  beforeEach(() => resetStore());

  const utubMatrix: Array<{
    owner: boolean;
    coCreator: boolean;
    locked: boolean;
    expected: boolean;
  }> = [
    { owner: true, coCreator: false, locked: false, expected: true },
    { owner: false, coCreator: true, locked: false, expected: true },
    { owner: false, coCreator: false, locked: false, expected: false },
    { owner: true, coCreator: false, locked: true, expected: false },
    { owner: false, coCreator: true, locked: true, expected: false },
    { owner: false, coCreator: false, locked: true, expected: false },
  ];

  it.each(utubMatrix)(
    "scope 'utub': owner=$owner coCreator=$coCreator locked=$locked -> $expected",
    ({ owner, coCreator, locked, expected }) => {
      setState({
        isCurrentUserOwner: owner,
        isCoCreator: coCreator,
        isCurrentUTubLocked: locked,
      });
      expect(
        canWriteSection({
          section: makeSection({ scope: "utub" }),
          state: getState(),
        }),
      ).toBe(expected);
    },
  );

  it("scope 'user' is always writable, even for a locked non-manager", () => {
    setState({
      isCurrentUserOwner: false,
      isCoCreator: false,
      isCurrentUTubLocked: true,
    });
    expect(
      canWriteSection({
        section: makeSection({
          scope: "user",
          userKind: "global",
          panel: "members",
        }),
        state: getState(),
      }),
    ).toBe(true);
  });

  it("denies an unknown scope", () => {
    setState({ isCurrentUserOwner: true });
    expect(
      canWriteSection({
        section: makeSection({ scope: "team" as never }),
        state: getState(),
      }),
    ).toBe(false);
  });
});
