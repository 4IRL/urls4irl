import { getState, resetStore, setState } from "../../../store/app-store.js";
import { canWriteSection, isSectionVisible } from "../permissions.js";
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

  const ownerMatrix: Array<{
    owner: boolean;
    coCreator: boolean;
    locked: boolean;
    expected: boolean;
  }> = [
    { owner: true, coCreator: false, locked: false, expected: true },
    { owner: false, coCreator: true, locked: false, expected: false },
    { owner: false, coCreator: false, locked: false, expected: false },
    { owner: true, coCreator: false, locked: true, expected: false },
  ];

  it.each(ownerMatrix)(
    "writeAccess 'owner': owner=$owner coCreator=$coCreator locked=$locked -> $expected",
    ({ owner, coCreator, locked, expected }) => {
      setState({
        isCurrentUserOwner: owner,
        isCoCreator: coCreator,
        isCurrentUTubLocked: locked,
      });
      expect(
        canWriteSection({
          section: makeSection({ scope: "utub", writeAccess: "owner" }),
          state: getState(),
        }),
      ).toBe(expected);
    },
  );

  it("denies an unknown writeAccess that bypassed the registry", () => {
    setState({ isCurrentUserOwner: true });
    expect(
      canWriteSection({
        section: makeSection({ writeAccess: "everyone" as never }),
        state: getState(),
      }),
    ).toBe(false);
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

describe("isSectionVisible", () => {
  beforeEach(() => resetStore());

  const roles = [
    { role: "owner", owner: true, coCreator: false },
    { role: "co-owner", owner: false, coCreator: true },
    { role: "member", owner: false, coCreator: false },
  ];

  it.each(roles)("an absent visibleTo shows to the $role", (role) => {
    setState({ isCurrentUserOwner: role.owner, isCoCreator: role.coCreator });
    expect(
      isSectionVisible({ section: makeSection(), state: getState() }),
    ).toBe(true);
  });

  it.each(roles)(
    "visibleTo 'managers' shows to the $role only if a manager",
    (role) => {
      setState({ isCurrentUserOwner: role.owner, isCoCreator: role.coCreator });
      expect(
        isSectionVisible({
          section: makeSection({ visibleTo: "managers" }),
          state: getState(),
        }),
      ).toBe(role.owner || role.coCreator);
    },
  );

  it("denies an unknown visibleTo that bypassed the registry", () => {
    setState({ isCurrentUserOwner: true });
    expect(
      isSectionVisible({
        section: makeSection({ visibleTo: "nobody" as never }),
        state: getState(),
      }),
    ).toBe(false);
  });
});
